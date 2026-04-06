"""
Management command to send all demo order email templates to a given address.

Usage:
    python manage.py send_demo_emails --to rajpaladiya2023@gmail.com
"""

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from Hub.email_utils import _get_from_email


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_mock_order(to_email, order_number='VM-DEMO-001'):
    """Build a lightweight mock order object that satisfies all template needs."""

    User = get_user_model()

    # Try to find a real user; fall back to a namespace mock
    user = User.objects.filter(email=to_email).first()
    if not user:
        user = SimpleNamespace(
            email=to_email,
            username='demo_user',
            get_full_name=lambda: 'Demo Customer',
            userprofile=None,
            id=1,
        )

    item = SimpleNamespace(
        product_name='Hand-Woven Silk Kurta',
        product_price=Decimal('12500.00'),
        subtotal=Decimal('12500.00'),
        quantity=1,
        size='M',
        color='Ivory',
        product_image=None,
        product=None,
        image_url='',
        name='Hand-Woven Silk Kurta',
        variant_text='Ivory / M',
        line_total=Decimal('12500.00'),
    )

    return_obj = SimpleNamespace(
        id='RET-DEMO-001',
        reason='Size Exchange (M to L)',
        get_status_display=lambda: 'Accepted',
        pickup_date=datetime.now().date() + timedelta(days=2),
        pickup_window='10:00 AM – 1:00 PM',
        pickup_partner='Delhivery',
    )

    order = SimpleNamespace(
        id=1,
        order_number=order_number,
        order_date=datetime.now(),
        order_status='SHIPPED',
        payment_status='PAID',
        payment_method='RAZORPAY',
        shipping_cost=Decimal('0.00'),
        subtotal=Decimal('12500.00'),
        tax=Decimal('1500.00'),
        coupon_discount=Decimal('0.00'),
        total_amount=Decimal('14000.00'),
        shipping_address='42, Heritage Enclave\nGolf Course Road, Sector 54\nGurugram, Haryana 122002',
        billing_address='42, Heritage Enclave\nGolf Course Road, Sector 54\nGurugram, Haryana 122002',
        delivery_date=datetime.now().date() + timedelta(days=3),
        approved_at=datetime.now(),
        tracking_number='BD-4492-AXQ1',
        courier_name='Blue Dart',
        payment_due_date=datetime.now().date() + timedelta(days=1),
        user=user,
        return_request=return_obj,
        get_payment_method_display=lambda: 'Razorpay',
        get_payment_status_display=lambda: 'Paid',
        get_order_status_display=lambda: 'Shipped',
        items=SimpleNamespace(
            select_related=lambda *a, **kw: SimpleNamespace(all=lambda: [item]),
            all=lambda: [item],
        ),
    )
    return order, [
        {
            'product_name': item.product_name,
            'name': item.product_name,
            'quantity': item.quantity,
            'product_price': item.product_price,
            'subtotal': item.subtotal,
            'line_total': item.line_total,
            'variant_text': item.variant_text,
            'image_url': '',
        }
    ]


def _send(subject, template, context, to_email):
    html = render_to_string(template, context)
    text = f"{subject}\n\nThis is a demo email from VibeMall."
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=_get_from_email(),
        to=[to_email],
    )
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Send all demo order email templates to a given address.'

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True, help='Recipient email address')

    def handle(self, *args, **options):
        to_email = options['to'].strip()
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
        now = datetime.now()
        year = now.year
        order, order_items = _make_mock_order(to_email)

        # Shared base context
        base = {
            'order': order,
            'order_items': order_items,
            'order_date': now.strftime('%B %d, %Y'),
            'payment_status_display': 'Paid',
            'shipping_cost_display': 'Complimentary',
            'estimated_delivery': (now + timedelta(days=3)).strftime('%B %d, %Y'),
            'estimated_dispatch_date': (now + timedelta(days=1)).strftime('%B %d, %Y'),
            'confirmation_date': now.strftime('%B %d, %Y'),
            'track_order_url': f'{site_url}/track-order/',
            'order_details_url': f'{site_url}/orders/{order.order_number}/',
            'contact_url': f'{site_url}/contact/',
            'returns_policy_url': f'{site_url}/faq/',
            'invoice_download_url': f'{site_url}/orders/{order.order_number}/',
            'current_year': year,
        }

        # Status update shared context
        def status_ctx(status_type, badge, hero_title, hero_body, cta_label, cta_url,
                       show_tracking=False, show_return=False, show_pickup=False, show_payment=False):
            return {
                **base,
                'status_type': status_type,
                'status_title': hero_title,
                'status_badge': badge,
                'hero_title': hero_title,
                'hero_body': hero_body,
                'primary_cta_label': cta_label,
                'primary_cta_url': cta_url,
                'order_url': f'{site_url}/orders/',
                'tracking_url': f'{site_url}/track-order/',
                'returns_url': f'{site_url}/faq/',
                'contact_url': f'{site_url}/contact/',
                'show_contact_link': True,
                'event_date': now.strftime('%b %d, %Y').upper(),
                'show_tracking': show_tracking,
                'courier_name': order.courier_name,
                'tracking_number': order.tracking_number,
                'timeline_value': (now + timedelta(days=3)).strftime('%B %d, %Y'),
                'show_return': show_return,
                'return_request_id': order.return_request.id,
                'return_reason': order.return_request.reason,
                'return_status_display': order.return_request.get_status_display(),
                'show_pickup': show_pickup,
                'pickup_date': order.return_request.pickup_date.strftime('%B %d, %Y'),
                'pickup_window': order.return_request.pickup_window,
                'pickup_partner': order.return_request.pickup_partner,
                'show_payment': show_payment,
                'payment_amount': order.total_amount,
                'payment_due_date': (now + timedelta(days=1)).strftime('%B %d, %Y'),
                'payment_url': f'{site_url}/orders/{order.order_number}/',
            }

        demos = [
            # (label, subject, template, context)
            (
                '1. Order Received',
                f'[DEMO] Order Received – #{order.order_number}',
                'emails/order_received.html',
                {**base, 'hero_title': 'Order Received',
                 'hero_message': 'Thank you, your order has been placed successfully.'},
            ),
            (
                '2. Order Confirmed',
                f'[DEMO] Order Confirmed – #{order.order_number}',
                'emails/order_confirmation.html',
                {**base, 'hero_title': 'Your Order Is Confirmed',
                 'hero_message': 'We have verified your order and our atelier has begun preparing your selections.'},
            ),
            (
                '3. Order Shipped',
                f'[DEMO] Order Shipped – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'SHIPPED', 'SHIPPING UPDATE',
                    'Your Curations Are on the Way',
                    'Each piece has been carefully inspected and is now being transported to your doorstep.',
                    'Track Your Journey', f'{site_url}/track-order/',
                    show_tracking=True,
                ),
            ),
            (
                '4. Out for Delivery',
                f'[DEMO] Out for Delivery – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'OUT_FOR_DELIVERY', 'OUT FOR DELIVERY',
                    'Arriving Today',
                    'Your order is with our delivery partner and will arrive at your doorstep today.',
                    'Track Your Journey', f'{site_url}/track-order/',
                    show_tracking=True,
                ),
            ),
            (
                '5. Return Request Submitted',
                f'[DEMO] Return Request Submitted – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'RETURN_SUBMITTED', 'RETURN REQUEST',
                    'Return Request Received',
                    'We have received your return request and our team is reviewing it.',
                    'View Return Status', f'{site_url}/orders/{order.order_number}/',
                    show_return=True,
                ),
            ),
            (
                '6. Return Request Accepted',
                f'[DEMO] Return Accepted – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'RETURN_ACCEPTED', 'RETURN ACCEPTED',
                    'Your Return is Approved',
                    'Your return has been approved. We will schedule a pickup at your convenience.',
                    'View Return Details', f'{site_url}/orders/{order.order_number}/',
                    show_return=True,
                ),
            ),
            (
                '7. Pickup Scheduled',
                f'[DEMO] Pickup Scheduled – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'PICKUP_SCHEDULED', 'PICKUP DATE CONFIRMED',
                    'Pickup is Scheduled',
                    'A pickup has been scheduled for your return. Please keep the items ready.',
                    'View Pickup Details', f'{site_url}/orders/{order.order_number}/',
                    show_return=True, show_pickup=True,
                ),
            ),
            (
                '8. Pickup Successful',
                f'[DEMO] Pickup Successful – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'PICKUP_DONE', 'PICKUP COMPLETE',
                    'Items Picked Up Successfully',
                    'Your items have been picked up. Refund will be processed after quality check.',
                    'Track Refund Status', f'{site_url}/orders/{order.order_number}/',
                    show_return=True, show_pickup=True,
                ),
            ),
            (
                '9. Proceed to Payment',
                f'[DEMO] Payment Required – #{order.order_number}',
                'emails/order_status_update.html',
                status_ctx(
                    'PROCEED_TO_PAYMENT', 'ACTION REQUIRED',
                    'Complete Your Payment',
                    'There is a pending balance on your order. Please complete the payment to proceed.',
                    'Pay Now', f'{site_url}/orders/{order.order_number}/',
                    show_payment=True,
                ),
            ),
        ]

        import time
        success = 0
        for label, subject, template, ctx in demos:
            try:
                _send(subject, template, ctx, to_email)
                self.stdout.write(self.style.SUCCESS(f'  ✓ {label}'))
                success += 1
                time.sleep(4)  # 4s gap to avoid Gmail rate limiting
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  ✗ {label}: {exc}'))
                self.stdout.write('  Waiting 15s before retrying next...')
                time.sleep(15)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. {success}/{len(demos)} emails sent to {to_email}'
        ))
