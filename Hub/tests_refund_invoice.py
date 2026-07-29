from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .email_utils import build_refund_invoice_context, send_refund_invoice_email
from .models import Order, OrderItem, Product, ReturnItem, ReturnRequest, UserProfile


def _tiny_image(name="ri.gif"):
    return SimpleUploadedFile(
        name,
        (
            b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
            b"\x01\x00\x00\x02\x02D\x01\x00;"
        ),
        content_type="image/gif",
    )


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@vibemall.in',
)
class RefundCreditNoteTests(TestCase):
    """A customer gets a credit note by email once the refund actually goes out."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="ri_buyer", password="pass12345", email="buyer@example.com",
            first_name="Aarav", last_name="Shah",
        )
        UserProfile.objects.get_or_create(user=self.user, defaults={'mobile_number': '9876543210'})
        self.product = Product.objects.create(
            name="Refundable Item", image=_tiny_image(), price=Decimal("1000.00"),
            stock=5, is_active=True,
        )
        self.order = Order.objects.create(
            user=self.user, subtotal=Decimal('1000.00'), total_amount=Decimal('1000.00'),
            payment_method='RAZORPAY', payment_status='REFUNDED',
            razorpay_payment_id='pay_ABC123', order_status='DELIVERED',
            customer_email='buyer@example.com',
        )
        self.order_item = OrderItem.objects.create(
            order=self.order, product=self.product, product_name=self.product.name,
            product_price=Decimal('1000.00'), quantity=1, subtotal=Decimal('1000.00'),
        )
        self.rr = ReturnRequest.objects.create(
            order=self.order, user=self.user, refund_method='RAZORPAY',
            refund_amount=Decimal('1000.00'), refund_fee=Decimal('20.00'),
            refund_amount_net=Decimal('980.00'), status='REFUNDED',
            resolved_at=timezone.now(),
        )
        ReturnItem.objects.create(
            return_request=self.rr, order_item=self.order_item,
            product=self.product, quantity=1,
        )

    # ── the context ──────────────────────────────────────────────────────────

    def test_context_carries_the_refund_figures(self):
        ctx = build_refund_invoice_context(self.rr)
        self.assertEqual(ctx['refund_gross'], Decimal('1000.00'))
        self.assertEqual(ctx['refund_fee'], Decimal('20.00'))
        self.assertEqual(ctx['refund_net'], Decimal('980.00'))
        self.assertEqual(ctx['credit_note_number'], f'CN-{self.rr.return_number}')

    def test_context_lists_the_returned_items(self):
        ctx = build_refund_invoice_context(self.rr)
        self.assertEqual(len(ctx['returned_items']), 1)
        item = ctx['returned_items'][0]
        self.assertEqual(item['name'], 'Refundable Item')
        self.assertEqual(item['line_total'], Decimal('1000.00'))

    def test_net_is_derived_when_it_was_never_stored(self):
        self.rr.refund_amount_net = None
        ctx = build_refund_invoice_context(self.rr)
        self.assertEqual(ctx['refund_net'], Decimal('980.00'))

    def test_method_label_and_eta_follow_the_refund_route(self):
        ctx = build_refund_invoice_context(self.rr)
        self.assertEqual(ctx['refund_method_label'], 'Back to original payment method')
        self.assertIn('5-7', ctx['refund_eta'])

        self.rr.refund_method = 'WALLET'
        ctx = build_refund_invoice_context(self.rr)
        self.assertEqual(ctx['refund_method_label'], 'VibeMall Wallet')
        self.assertIn('instant', ctx['refund_eta'])

    # ── the email ────────────────────────────────────────────────────────────

    def test_email_is_sent_to_the_customer(self):
        self.assertTrue(send_refund_invoice_email(self.rr))
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['buyer@example.com'])
        self.assertIn(self.rr.return_number, sent.subject)

    def test_email_body_states_the_amount_and_route(self):
        send_refund_invoice_email(self.rr)
        body = mail.outbox[0].body
        self.assertIn('980.00', body)
        self.assertIn('Back to original payment method', body)
        self.assertIn(self.order.order_number, body)

    def test_email_has_an_html_alternative(self):
        send_refund_invoice_email(self.rr)
        alternatives = mail.outbox[0].alternatives
        self.assertEqual(len(alternatives), 1)
        html, mimetype = alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('Your refund has been processed', html)
        self.assertIn('980.00', html)

    def test_a_pdf_credit_note_is_attached(self):
        send_refund_invoice_email(self.rr)
        attachments = mail.outbox[0].attachments
        self.assertEqual(len(attachments), 1)
        filename, content, mimetype = attachments[0]
        self.assertEqual(filename, f'CreditNote_{self.rr.return_number}.pdf')
        self.assertEqual(mimetype, 'application/pdf')
        self.assertTrue(content.startswith(b'%PDF'), 'attachment is not a real PDF')

    def test_still_emails_when_the_rich_pdf_engine_is_missing(self):
        """
        WeasyPrint needs native libraries that are not always present. The
        ReportLab fallback must keep a credit note on the message.
        """
        import builtins
        real_import = builtins.__import__

        def no_weasyprint(name, *args, **kwargs):
            if name == 'weasyprint':
                raise ImportError('no weasyprint here')
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=no_weasyprint):
            self.assertTrue(send_refund_invoice_email(self.rr))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].attachments[0][1].startswith(b'%PDF'))

    def test_no_email_address_is_reported_not_crashed(self):
        self.user.email = ''
        self.user.save()
        self.order.customer_email = ''
        self.order.save()
        self.assertFalse(send_refund_invoice_email(self.rr))
        self.assertEqual(len(mail.outbox), 0)

    def test_send_failure_is_swallowed(self):
        """The money already moved; a mail outage must not raise into the view."""
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=Exception('smtp down')):
            self.assertFalse(send_refund_invoice_email(self.rr))

    # ── wired into the admin flow ────────────────────────────────────────────

    def test_admin_refund_action_sends_the_credit_note(self):
        staff = User.objects.create_user(username='ri_staff', password='pass12345',
                                         is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        # REFUNDED is only reachable from REFUND_PENDING (RETURN_STATUS_FLOW).
        self.rr.status = 'REFUND_PENDING'
        self.rr.save()

        with patch('Hub.views._process_refund', return_value=(True, '')):
            response = self.client.post(
                f'/admin-panel/returns/{self.rr.id}/',
                {'action': 'REFUNDED', 'refund_method': 'RAZORPAY', 'notes': ''},
            )
        self.assertIn(response.status_code, (200, 302))
        # The view also sends its usual return-status update, so look for the
        # credit note among the messages rather than assuming it is the only one.
        credit_notes = [m for m in mail.outbox if m.subject.startswith('Refund Processed')]
        self.assertEqual(len(credit_notes), 1)
        self.assertEqual(credit_notes[0].to, ['buyer@example.com'])
        self.assertTrue(credit_notes[0].attachments[0][1].startswith(b'%PDF'))

    def test_failed_refund_sends_no_credit_note(self):
        staff = User.objects.create_user(username='ri_staff2', password='pass12345',
                                         is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        # REFUNDED is only reachable from REFUND_PENDING (RETURN_STATUS_FLOW).
        self.rr.status = 'REFUND_PENDING'
        self.rr.save()

        with patch('Hub.views._process_refund', return_value=(False, 'gateway down')):
            self.client.post(
                f'/admin-panel/returns/{self.rr.id}/',
                {'action': 'REFUNDED', 'refund_method': 'RAZORPAY', 'notes': ''},
            )
        subjects = [m.subject for m in mail.outbox]
        self.assertNotIn(f'Refund Processed - {self.rr.return_number} - VibeMall', subjects)
