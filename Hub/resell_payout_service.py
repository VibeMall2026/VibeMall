"""
Resell Payout Management Service

Handles:
- 7-day earning eligibility logic
- Payout reminder emails to admins
- Invoice generation and sending
- Payment method processing (Razorpay, Bank Transfer, UPI)
"""

import logging
from decimal import Decimal
from datetime import timedelta
from urllib.parse import urlparse
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.db import transaction

from .models import Order, ResellerEarning, PayoutTransaction, ReturnRequest, User

logger = logging.getLogger(__name__)


def _split_invoice_lines(value):
    if not value:
        return []

    normalized = str(value).replace('\r', '\n')
    if '\n' in normalized:
        parts = [line.strip() for line in normalized.split('\n')]
    else:
        parts = [line.strip() for line in normalized.split(',')]

    return [part for part in parts if part]


class PayoutEligibilityManager:
    """Manages 7-day earning hold and payout eligibility logic"""

    HOLD_PERIOD_DAYS = 7

    @staticmethod
    def check_and_confirm_earnings():
        """
        Auto-confirm earnings that have passed 7-day hold (no returns filed).
        Run daily via management command or Celery task.
        """
        cutoff_time = timezone.now() - timedelta(days=PayoutEligibilityManager.HOLD_PERIOD_DAYS)

        # Find earned pending orders delivered before cutoff
        pending_earnings = ResellerEarning.objects.filter(
            status='PENDING',
            order__order_status='DELIVERED',
            order__delivery_date__lte=cutoff_time
        ).select_related('order', 'reseller')

        confirmed_count = 0
        for earning in pending_earnings:
            # Check if return request exists for this order
            has_return = ReturnRequest.objects.filter(
                order=earning.order,
                status__in=['OPEN', 'IN_PROGRESS']
            ).exists()

            if not has_return:
                # Safe to confirm - no pending returns
                earning.status = 'CONFIRMED'
                earning.confirmed_at = timezone.now()
                earning.save(update_fields=['status', 'confirmed_at'])
                confirmed_count += 1
                logger.info(f"Auto-confirmed earning {earning.id} for order {earning.order.order_number}")

        return confirmed_count

    @staticmethod
    def get_eligible_payouts_for_admin():
        """
        Get all earnings ready for payout (confirmed & no active payout).
        Returns QuerySet with delivery timing info.
        """
        from django.db.models import F, ExpressionWrapper, DurationField, Case, When, CharField

        now = timezone.now()
        seven_days_ago = now - timedelta(days=PayoutEligibilityManager.HOLD_PERIOD_DAYS)

        eligible = ResellerEarning.objects.filter(
            status='CONFIRMED',
            payout_transaction__isnull=True,
            order__delivery_date__lte=seven_days_ago
        ).select_related(
            'order',
            'reseller',
            'order__user'
        ).annotate(
            days_since_delivery=ExpressionWrapper(
                now - F('order__delivery_date'),
                output_field=DurationField()
            )
        ).order_by('order__delivery_date')

        return eligible

    @staticmethod
    def get_payout_eligibility_status(earning):
        """
        Returns eligibility status for a single earning.
        Possible returns: 'not_delivered', 'hold_period', 'return_pending', 'eligible', 'paid'
        """
        if earning.status == 'PAID':
            return 'paid', earning.paid_at

        if earning.order.order_status != 'DELIVERED':
            return 'not_delivered', None

        if not earning.order.delivery_date:
            return 'not_delivered', None

        # Check for active return requests
        active_return = ReturnRequest.objects.filter(
            order=earning.order,
            status__in=['OPEN', 'IN_PROGRESS']
        ).exists()

        if active_return:
            return 'return_pending', None

        # Check 7-day hold period
        days_since_delivery = (timezone.now() - earning.order.delivery_date).days
        if days_since_delivery < PayoutEligibilityManager.HOLD_PERIOD_DAYS:
            return 'hold_period', (earning.order.delivery_date + timedelta(days=PayoutEligibilityManager.HOLD_PERIOD_DAYS))

        if earning.status == 'CONFIRMED':
            return 'eligible', None

        if earning.status == 'PENDING':
            return 'hold_period', (earning.order.delivery_date + timedelta(days=PayoutEligibilityManager.HOLD_PERIOD_DAYS))

        return 'unknown', None


class PayoutEmailService:
    """Sends payout-related emails to admins and resellers"""

    @staticmethod
    def send_admin_payout_reminder(earning):
        """
        Send admin a reminder email 7 days after delivery.
        Should be called by scheduled task.
        """
        try:
            admin_emails = User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)

            context = {
                'reseller_name': earning.reseller.get_full_name() or earning.reseller.username,
                'customer_name': earning.order.user.get_full_name() or earning.order.user.username,
                'order_number': earning.order.order_number,
                'margin_amount': earning.margin_amount,
                'total_order_amount': earning.order.total_amount,
                'delivery_date': earning.order.delivery_date,
                'payout_url': f"{settings.SITE_URL}/admin/resell/payouts/",
            }

            html_message = render_to_string('emails/payout_reminder_admin.html', context)
            plain_message = render_to_string('emails/payout_reminder_admin.txt', context)

            email = EmailMessage(
                subject=f'Payout Ready: ₹{earning.margin_amount} from {earning.reseller.username}',
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=admin_emails,
            )
            email.attach_alternative(html_message, "text/html")
            email.send()

            logger.info(f"Payout reminder sent to admins for earning {earning.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send payout reminder for earning {earning.id}: {e}")
            return False

    @staticmethod
    def send_payout_confirmation_to_reseller(payout_transaction, invoice_pdf_path=None):
        """
        Send reseller confirmation email with invoice after payout is completed.
        """
        try:
            reseller = payout_transaction.reseller
            context = {
                'reseller_name': reseller.get_full_name() or reseller.username,
                'payout_amount': payout_transaction.amount,
                'payout_method': dict(PayoutTransaction.PAYOUT_METHOD_CHOICES).get(
                    payout_transaction.payout_method, payout_transaction.payout_method
                ),
                'transaction_id': payout_transaction.transaction_id or 'N/A',
                'completed_date': payout_transaction.completed_at,
                'account_details': payout_transaction.bank_account or payout_transaction.upi_id or 'N/A',
            }

            html_message = render_to_string('emails/payout_confirmation_reseller.html', context)
            plain_message = render_to_string('emails/payout_confirmation_reseller.txt', context)

            email = EmailMessage(
                subject=f'Payout Confirmed: ₹{payout_transaction.amount}',
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[reseller.email],
            )
            email.attach_alternative(html_message, "text/html")

            # Attach invoice if available
            if invoice_pdf_path:
                with open(invoice_pdf_path, 'rb') as pdf_file:
                    email.attach(
                        f'payout_invoice_{payout_transaction.id}.pdf',
                        pdf_file.read(),
                        'application/pdf'
                    )

            email.send()
            logger.info(f"Payout confirmation email sent to {reseller.username}")
            return True

        except Exception as e:
            logger.error(f"Failed to send payout confirmation to reseller: {e}")
            return False


class PayoutInvoiceGenerator:
    """Generates PDF invoices for payouts"""

    @staticmethod
    def build_payout_invoice_context(payout_transaction, earning_list):
        reseller = payout_transaction.reseller
        generated_date = timezone.now()
        payout_date = payout_transaction.completed_at or payout_transaction.initiated_at or generated_date
        company_name = getattr(settings, 'COMPANY_NAME', 'VibeMall')
        company_address = getattr(settings, 'COMPANY_ADDRESS', '')
        company_phone = getattr(settings, 'COMPANY_PHONE', '')
        company_email = getattr(settings, 'COMPANY_EMAIL', settings.DEFAULT_FROM_EMAIL)
        site_url = getattr(settings, 'SITE_URL', '')
        site_host = urlparse(site_url).netloc if site_url else ''
        total_margin = sum((earning.margin_amount for earning in earning_list), Decimal('0.00'))

        earnings_rows = []
        delivery_dates = []
        confirmed_dates = []

        for earning in earning_list:
            delivery_date = getattr(earning.order, 'delivery_date', None)
            if delivery_date:
                delivery_dates.append(delivery_date)
            if earning.confirmed_at:
                confirmed_dates.append(earning.confirmed_at)

            customer = earning.order.user.get_full_name() or earning.order.user.username
            earnings_rows.append({
                'order_number': earning.order.order_number,
                'customer_name': customer,
                'delivery_date': delivery_date,
                'margin_amount': earning.margin_amount,
                'status_display': earning.get_status_display(),
            })

        account_destination = payout_transaction.bank_account or payout_transaction.upi_id or 'N/A'
        if payout_transaction.bank_account:
            last_four = payout_transaction.bank_account[-4:]
            account_destination = f"Bank Account ending {last_four}" if last_four else 'Bank Account'
        elif payout_transaction.upi_id:
            account_destination = payout_transaction.upi_id

        payout_notes = [
            'This document confirms the reseller payout processed for completed eligible orders.',
            'Settlement timelines may vary by bank or payment provider, typically within 1 to 2 business days.',
            'Retain this invoice for reconciliation, bookkeeping, and tax records.',
        ]

        return {
            'company_name': company_name,
            'company_address_lines': _split_invoice_lines(company_address),
            'company_phone': company_phone,
            'company_email': company_email,
            'site_host': site_host,
            'generated_date': generated_date,
            'payout_date': payout_date,
            'payout_id': payout_transaction.id,
            'payout_transaction': payout_transaction,
            'reseller': reseller,
            'reseller_name': reseller.get_full_name() or reseller.username,
            'reseller_code': f"RSL-{reseller.id:05d}",
            'reseller_email': reseller.email,
            'reseller_username': reseller.username,
            'earnings': earnings_rows,
            'total_margin': total_margin,
            'earnings_count': len(earnings_rows),
            'coverage_start': min(delivery_dates) if delivery_dates else None,
            'coverage_end': max(delivery_dates) if delivery_dates else None,
            'confirmed_on': max(confirmed_dates) if confirmed_dates else None,
            'payout_method_display': payout_transaction.get_payout_method_display(),
            'payout_status_display': payout_transaction.get_status_display(),
            'transaction_reference': payout_transaction.transaction_id or 'Awaiting Reference',
            'account_destination': account_destination,
            'admin_notes': payout_transaction.admin_notes,
            'payout_notes': payout_notes,
        }

    @staticmethod
    def generate_payout_invoice_pdf(payout_transaction, earning_list):
        """
        Generate a professional PDF invoice for the payout.
        earning_list: List of ResellerEarning objects included in this payout.
        Returns: Path to generated PDF file.
        """
        try:
            from weasyprint import HTML
            import os

            context = PayoutInvoiceGenerator.build_payout_invoice_context(
                payout_transaction,
                earning_list,
            )

            # Render HTML template
            html_content = render_to_string('admin/resell/payout_invoice.html', context)

            # Create output directory
            invoice_dir = os.path.join(settings.MEDIA_ROOT, 'payout_invoices')
            os.makedirs(invoice_dir, exist_ok=True)

            # Generate PDF
            output_path = os.path.join(invoice_dir, f'payout_{payout_transaction.id}.pdf')
            HTML(string=html_content, base_url=settings.BASE_DIR).write_pdf(output_path)

            logger.info(f"Generated payout invoice at {output_path}")
            return output_path

        except (ImportError, OSError) as exc:
            logger.warning("WeasyPrint PDF dependencies unavailable. Skipping payout PDF generation: %s", exc)
            return None
        except Exception as e:
            logger.error(f"Failed to generate payout invoice: {e}")
            return None


class RazorpayPaymentProcessor:
    """Handles Razorpay payment processing for payouts"""

    @staticmethod
    def initiate_razorpay_payout(payout_transaction):
        """
        Initiate a Razorpay payout via their API.
        Requires: settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET
        """
        try:
            import razorpay

            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            # Get reseller bank/UPI details from profile
            reseller = payout_transaction.reseller
            profile = reseller.reseller_profile

            payout_payload = {
                'account_number': settings.RAZORPAY_ACCOUNT_NUMBER,
                'amount': int(payout_transaction.amount * 100),  # Amount in paise
                'currency': 'INR',
                'mode': 'NEFT' if payout_transaction.payout_method == 'BANK_TRANSFER' else 'UPI',
                'purpose': 'payout',
                'receipt': f"payout_{payout_transaction.id}",
            }

            # Add beneficiary details
            if payout_transaction.payout_method == 'BANK_TRANSFER':
                payout_payload.update({
                    'fund_account': {
                        'account_type': 'bank_account',
                        'bank_account': {
                            'name': profile.bank_account_name,
                            'notes': {},
                            'account_number': payout_transaction.bank_account,
                            'ifsc': profile.bank_ifsc_code,
                        },
                        'contact': {
                            'name': reseller.get_full_name() or reseller.username,
                            'email': reseller.email,
                            'type': 'vendor',
                        }
                    }
                })
            elif payout_transaction.payout_method == 'UPI':
                payout_payload.update({
                    'fund_account': {
                        'account_type': 'vpa',
                        'vpa': {
                            'address': payout_transaction.upi_id,
                        },
                        'contact': {
                            'name': reseller.get_full_name() or reseller.username,
                            'email': reseller.email,
                            'type': 'vendor',
                        }
                    }
                })

            # Create payout via Razorpay
            response = client.payout.create(data=payout_payload)

            if response.get('id'):
                payout_transaction.transaction_id = response['id']
                payout_transaction.status = 'PROCESSING'
                payout_transaction.save(update_fields=['transaction_id', 'status'])
                logger.info(f"Razorpay payout initiated: {response['id']}")
                return response
            else:
                logger.error(f"Razorpay payout failed: {response}")
                return None

        except ImportError:
            logger.warning("Razorpay SDK not installed. Please install: pip install razorpay")
            return None
        except Exception as e:
            logger.error(f"Razorpay payout error: {e}")
            return None

    @staticmethod
    def verify_razorpay_payout_status(payout_transaction):
        """
        Check the status of a Razorpay payout if transaction_id exists.
        """
        try:
            if not payout_transaction.transaction_id:
                return None

            import razorpay

            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            response = client.payout.fetch(payout_transaction.transaction_id)

            if response.get('status') == 'processed':
                payout_transaction.status = 'COMPLETED'
                payout_transaction.completed_at = timezone.now()
                payout_transaction.save(update_fields=['status', 'completed_at'])
                logger.info(f"Razorpay payout {payout_transaction.transaction_id} completed")
                return 'COMPLETED'
            elif response.get('status') == 'failed':
                payout_transaction.status = 'FAILED'
                payout_transaction.admin_notes = f"Razorpay failure: {response.get('failure_reason')}"
                payout_transaction.save(update_fields=['status', 'admin_notes'])
                logger.warning(f"Razorpay payout {payout_transaction.transaction_id} failed")
                return 'FAILED'
            else:
                return response.get('status')  # pending, processing, etc.

        except Exception as e:
            logger.error(f"Error verifying Razorpay payout: {e}")
            return None


class BankTransferPaymentProcessor:
    """Handles bank transfer processing (manual or via payment gateway)"""

    @staticmethod
    def process_bank_transfer(payout_transaction):
        """
        Mark bank transfer as initiated and ready for manual/automated processing.
        In production, integrate with your bank's API.
        """
        payout_transaction.status = 'PROCESSING'
        payout_transaction.save(update_fields=['status'])

        logger.info(
            f"Bank transfer initiated for {payout_transaction.reseller.username}: "
            f"₹{payout_transaction.amount} to {payout_transaction.bank_account}"
        )
        return True


class UPIPaymentProcessor:
    """Handles UPI payment processing"""

    @staticmethod
    def process_upi_payment(payout_transaction):
        """
        Initiate UPI payout (can use Razorpay's UPI mode or direct API).
        """
        payout_transaction.status = 'PROCESSING'
        payout_transaction.save(update_fields=['status'])

        logger.info(
            f"UPI transfer initiated for {payout_transaction.reseller.username}: "
            f"₹{payout_transaction.amount} to {payout_transaction.upi_id}"
        )
        return True
