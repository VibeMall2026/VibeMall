"""
Seller payouts: turning confirmed earnings into money leaving the platform.

Settlement model
----------------
A payout settles *specific earnings*, never a loose amount. The seller names a
target amount; we take their CONFIRMED, unsettled earnings oldest-first while
the running total still fits inside that target, and the payout is worth
exactly that running total.

The alternative - paying an arbitrary amount and marking earnings PAID
approximately - lets the sum of "paid" earnings drift away from the money
actually sent. Once those two numbers disagree there is no way to answer "what
did we pay this seller for?" without a manual audit, so they are kept in exact
correspondence here instead.

A consequence worth knowing: asking for less than your oldest single earning
settles nothing, and the caller is told the smallest amount that would work.

Balance handling
----------------
The balance is debited when the payout is *requested*, not when it is approved.
A request is a claim on the money; leaving it in the available balance until an
admin gets round to approving would let the seller request it a second time.
Rejection and failure both refund it.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import ResellerProfile, SellerEarning, SellerPayout

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _setting(name, default):
    return getattr(settings, name, default)


def min_payout_amount() -> Decimal:
    return Decimal(str(_setting('SELLER_MIN_PAYOUT', '500.00')))


def get_settleable_earnings(seller):
    """Confirmed earnings not already attached to a payout, oldest first."""
    return (
        SellerEarning.objects
        .filter(seller=seller, status='CONFIRMED', payout__isnull=True)
        .order_by('created_at', 'id')
    )


def get_settleable_total(seller) -> Decimal:
    total = get_settleable_earnings(seller).aggregate(t=Sum('net_amount'))['t']
    return _money(total or 0)


def _select_earnings_for_amount(seller, target: Decimal):
    """
    Greedily pick earnings that fit inside `target`, oldest first.

    Returns (earnings, total). Oldest-first matters beyond fairness: it stops
    old earnings being stranded forever behind newer ones and keeps the ledger
    reading in the order things happened.
    """
    selected = []
    total = Decimal('0.00')
    for earning in get_settleable_earnings(seller):
        if total + earning.net_amount > target:
            continue
        selected.append(earning)
        total = _money(total + earning.net_amount)
    return selected, total


@transaction.atomic
def request_payout(seller, requested_amount, payout_method: str, payment_details: dict | None = None) -> SellerPayout:
    """
    Create a PENDING payout and debit the seller's available balance.

    Raises ValidationError with a message meant to be shown to the seller.
    """
    payment_details = payment_details or {}
    requested_amount = _money(requested_amount)

    profile = (
        ResellerProfile.objects
        .select_for_update()
        .filter(user=seller)
        .first()
    )
    if profile is None:
        raise ValidationError("No payee profile found. Contact support.")
    if not profile.is_reseller_enabled:
        raise ValidationError("Your seller account is disabled.")

    if requested_amount <= 0:
        raise ValidationError("Payout amount must be greater than zero.")

    minimum = min_payout_amount()
    if requested_amount < minimum:
        raise ValidationError(f"Minimum payout is Rs.{minimum}.")

    if requested_amount > profile.seller_available_balance:
        raise ValidationError(
            f"Insufficient balance. Available: Rs.{profile.seller_available_balance}"
        )

    earnings, settled_total = _select_earnings_for_amount(seller, requested_amount)
    if not earnings:
        smallest = get_settleable_earnings(seller).first()
        if smallest is None:
            raise ValidationError("You have no confirmed earnings available to withdraw.")
        raise ValidationError(
            f"No earning fits inside Rs.{requested_amount}. "
            f"The smallest you can withdraw right now is Rs.{smallest.net_amount}."
        )
    if settled_total < minimum:
        raise ValidationError(
            f"The earnings that fit inside Rs.{requested_amount} total only "
            f"Rs.{settled_total}, which is below the Rs.{minimum} minimum."
        )

    method = (payout_method or '').strip().upper()
    if method not in dict(SellerPayout.PAYOUT_METHOD_CHOICES):
        raise ValidationError("Choose a valid payout method.")

    # Snapshot the destination. Editing the profile later must not silently
    # redirect a payout that has already been requested.
    payout = SellerPayout(
        seller=seller,
        amount=settled_total,
        payout_method=method,
        status='PENDING',
    )
    if method == 'BANK_TRANSFER':
        payout.bank_account_name = payment_details.get('bank_account_name') or profile.bank_account_name
        payout.bank_account_number = payment_details.get('bank_account_number') or profile.bank_account_number
        payout.bank_ifsc_code = payment_details.get('bank_ifsc_code') or profile.bank_ifsc_code
    else:
        payout.upi_id = payment_details.get('upi_id') or profile.upi_id
    payout.save()  # model.clean() enforces the destination fields are present

    SellerEarning.objects.filter(id__in=[e.id for e in earnings]).update(payout=payout)

    profile.seller_available_balance = _money(profile.seller_available_balance - settled_total)
    profile.save(update_fields=['seller_available_balance'])

    logger.info(
        "Seller payout requested: id=%s seller=%s amount=%s earnings=%s balance_left=%s",
        payout.id, seller.username, settled_total, len(earnings), profile.seller_available_balance,
    )
    return payout


def _refund_to_balance(payout: SellerPayout, reason: str) -> Decimal:
    """
    Return a payout's money to the seller and release its earnings.

    Earnings cancelled while the payout was open (their order was refunded)
    are excluded from the refund and stay attached to the dead payout. Paying
    that money back into the balance would resurrect an earning the customer
    got refunded for. Returns the amount actually refunded.
    """
    linked = SellerEarning.objects.filter(payout=payout)
    cancelled_total = _money(
        linked.filter(status='CANCELLED').aggregate(t=Sum('net_amount'))['t'] or 0
    )
    refund = _money(max(Decimal('0'), payout.amount - cancelled_total))

    profile, _ = ResellerProfile.objects.select_for_update().get_or_create(user=payout.seller)
    profile.seller_available_balance = _money(profile.seller_available_balance + refund)
    profile.save(update_fields=['seller_available_balance'])

    # Only live earnings become withdrawable again.
    linked.exclude(status='CANCELLED').update(payout=None)

    logger.warning(
        "Seller payout %s refunded to balance (%s): seller=%s refunded=%s withheld_cancelled=%s",
        payout.id, reason, payout.seller.username, refund, cancelled_total,
    )
    return refund


@transaction.atomic
def approve_payout(payout_id: int, admin_user, notes: str = '') -> SellerPayout:
    payout = SellerPayout.objects.select_for_update().get(id=payout_id)
    if payout.status != 'PENDING':
        raise ValidationError(f"Only pending payouts can be approved (this one is {payout.status}).")

    # Last gate before money can move. If an order was refunded after the
    # seller requested this payout, approving would pay them for a sale that
    # no longer exists.
    stale = SellerEarning.objects.filter(payout=payout, status='CANCELLED').count()
    if stale:
        raise ValidationError(
            f"{stale} earning(s) in this payout were cancelled after it was requested "
            f"(the order was refunded or cancelled). Reject this payout and ask the "
            f"seller to request a new one."
        )

    payout.status = 'APPROVED'
    payout.processed_by = admin_user
    payout.processed_at = timezone.now()
    if notes:
        payout.admin_notes = notes
    payout.save(update_fields=['status', 'processed_by', 'processed_at', 'admin_notes'])

    logger.info("Seller payout %s approved by %s", payout.id, getattr(admin_user, 'username', '?'))
    return payout


@transaction.atomic
def reject_payout(payout_id: int, admin_user, reason: str) -> SellerPayout:
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError("A rejection reason is required.")

    payout = SellerPayout.objects.select_for_update().get(id=payout_id)
    if payout.status in ('COMPLETED', 'REJECTED'):
        raise ValidationError(f"This payout is already {payout.status}.")
    if payout.status == 'PROCESSING':
        raise ValidationError(
            "This payout is already being processed. Mark it failed instead if the transfer did not go through."
        )

    _refund_to_balance(payout, 'rejected')

    payout.status = 'REJECTED'
    payout.rejection_reason = reason[:300]
    payout.processed_by = admin_user
    payout.processed_at = timezone.now()
    payout.save(update_fields=['status', 'rejection_reason', 'processed_by', 'processed_at'])
    return payout


@transaction.atomic
def mark_processing(payout_id: int) -> SellerPayout:
    payout = SellerPayout.objects.select_for_update().get(id=payout_id)
    if payout.status != 'APPROVED':
        raise ValidationError("Only an approved payout can move to processing.")
    payout.status = 'PROCESSING'
    payout.save(update_fields=['status'])
    return payout


@transaction.atomic
def complete_payout(payout_id: int, transaction_id: str = '', admin_user=None) -> SellerPayout:
    """Money has actually reached the seller: settle the linked earnings."""
    payout = SellerPayout.objects.select_for_update().get(id=payout_id)
    if payout.status not in ('APPROVED', 'PROCESSING'):
        raise ValidationError(f"Cannot complete a payout that is {payout.status}.")

    now = timezone.now()
    payout.status = 'COMPLETED'
    payout.transaction_id = (transaction_id or '').strip()[:100]
    payout.completed_at = now
    if admin_user is not None:
        payout.processed_by = admin_user
    payout.save(update_fields=['status', 'transaction_id', 'completed_at', 'processed_by'])

    SellerEarning.objects.filter(payout=payout).exclude(status='CANCELLED').update(
        status='PAID', paid_at=now,
    )

    logger.info(
        "Seller payout %s completed: seller=%s amount=%s txn=%s",
        payout.id, payout.seller.username, payout.amount, payout.transaction_id,
    )
    return payout


@transaction.atomic
def fail_payout(payout_id: int, reason: str, admin_user=None) -> SellerPayout:
    """The transfer bounced. Give the money back so it can be retried."""
    payout = SellerPayout.objects.select_for_update().get(id=payout_id)
    if payout.status == 'COMPLETED':
        raise ValidationError("A completed payout cannot be marked failed.")
    if payout.status == 'FAILED':
        return payout

    _refund_to_balance(payout, 'failed')

    payout.status = 'FAILED'
    payout.admin_notes = ((payout.admin_notes + '\n') if payout.admin_notes else '') + f"Failed: {reason}"
    if admin_user is not None:
        payout.processed_by = admin_user
    payout.processed_at = timezone.now()
    payout.save(update_fields=['status', 'admin_notes', 'processed_by', 'processed_at'])
    return payout


# ── Payment gateway ──────────────────────────────────────────────────────────

def gateway_enabled() -> bool:
    """
    Automated transfers are opt-in.

    Default off: an operator has to deliberately turn on the ability for this
    code to move real money to real bank accounts. Until then payouts are
    marked processing and settled by hand, which is what the reseller side
    already does.
    """
    return bool(_setting('SELLER_PAYOUT_GATEWAY_ENABLED', False))


@transaction.atomic
def send_via_gateway(payout_id: int, admin_user=None) -> SellerPayout:
    """
    Hand an approved payout to Razorpay Payouts.

    Admin-triggered only - never called from a signal or a schedule, because
    an automatic path from "order delivered" to "money left the bank" has no
    point where a human can stop a mistake.
    """
    payout = SellerPayout.objects.select_for_update().get(id=payout_id)

    if not gateway_enabled():
        raise ValidationError(
            "Automated payouts are disabled. Set SELLER_PAYOUT_GATEWAY_ENABLED=1 to enable, "
            "or settle this payout manually."
        )
    if payout.status != 'APPROVED':
        raise ValidationError("Only an approved payout can be sent to the gateway.")

    key_id = _setting('RAZORPAY_KEY_ID', '')
    key_secret = _setting('RAZORPAY_KEY_SECRET', '')
    account_number = _setting('RAZORPAY_ACCOUNT_NUMBER', '')
    if not (key_id and key_secret and account_number):
        raise ValidationError("Razorpay payout credentials are not configured.")

    try:
        import razorpay
    except ImportError:
        raise ValidationError("The razorpay package is not installed on this server.")

    client = razorpay.Client(auth=(key_id, key_secret))
    seller = payout.seller

    if payout.payout_method == 'BANK_TRANSFER':
        fund_account = {
            'account_type': 'bank_account',
            'bank_account': {
                'name': payout.bank_account_name or (seller.get_full_name() or seller.username),
                'account_number': payout.bank_account_number,
                'ifsc': payout.bank_ifsc_code,
            },
        }
        mode = 'NEFT'
    else:
        fund_account = {
            'account_type': 'vpa',
            'vpa': {'address': payout.upi_id},
        }
        mode = 'UPI'

    payload = {
        'account_number': account_number,
        'amount': int(payout.amount * 100),  # paise
        'currency': 'INR',
        'mode': mode,
        'purpose': 'payout',
        'queue_if_low_balance': True,
        'reference_id': f"seller_payout_{payout.id}",
        'narration': f"VibeMall seller payout {payout.id}",
        'fund_account': dict(
            fund_account,
            contact={
                'name': seller.get_full_name() or seller.username,
                'email': seller.email or '',
                'type': 'vendor',
            },
        ),
    }

    try:
        response = client.payout.create(payload)
    except Exception as exc:
        logger.error("Razorpay seller payout %s failed: %s", payout.id, exc, exc_info=True)
        raise ValidationError(f"Gateway rejected the payout: {exc}")

    payout.status = 'PROCESSING'
    payout.transaction_id = str(response.get('id') or '')[:100]
    if admin_user is not None:
        payout.processed_by = admin_user
    payout.save(update_fields=['status', 'transaction_id', 'processed_by'])

    logger.info("Seller payout %s sent to gateway: txn=%s", payout.id, payout.transaction_id)
    return payout


# ── Notifications ────────────────────────────────────────────────────────────
#
# Plain text on purpose. These are short transactional notices about money, and
# a missing template should never be the reason a payout state change fails -
# every send is best-effort and swallowed.


def _send(subject: str, body: str, recipients: list[str]) -> bool:
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message=body,
            from_email=_setting('DEFAULT_FROM_EMAIL', None),
            recipient_list=recipients,
            fail_silently=True,
        )
        return True
    except Exception as exc:
        logger.warning("Seller payout email failed (%s): %s", subject, exc)
        return False


def _admin_emails() -> list[str]:
    from django.contrib.auth.models import User
    return list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(email='')
        .values_list('email', flat=True)
    )


def notify_payout_requested(payout: SellerPayout) -> None:
    site = _setting('SITE_URL', '')
    _send(
        f"Seller payout request: Rs.{payout.amount} from {payout.seller.username}",
        (
            f"{payout.seller.get_full_name() or payout.seller.username} requested a payout.\n\n"
            f"Amount: Rs.{payout.amount}\n"
            f"Method: {payout.get_payout_method_display()}\n"
            f"Requested: {payout.requested_at:%d %b %Y %H:%M}\n\n"
            f"Review it at {site}/admin-panel/seller-payouts/\n"
        ),
        _admin_emails(),
    )


def notify_payout_decision(payout: SellerPayout) -> None:
    """Tell the seller what happened to their request."""
    if payout.status == 'APPROVED':
        subject = f"Your payout of Rs.{payout.amount} was approved"
        body = (
            f"Your payout request of Rs.{payout.amount} has been approved and is being processed.\n"
            f"You will get another email once the transfer completes.\n"
        )
    elif payout.status == 'REJECTED':
        subject = f"Your payout request of Rs.{payout.amount} was declined"
        body = (
            f"Your payout request of Rs.{payout.amount} was declined.\n\n"
            f"Reason: {payout.rejection_reason}\n\n"
            f"The amount has been returned to your available balance and can be requested again.\n"
        )
    elif payout.status == 'COMPLETED':
        subject = f"Rs.{payout.amount} has been sent to you"
        body = (
            f"Your payout of Rs.{payout.amount} has been sent.\n"
            f"Reference: {payout.transaction_id or 'n/a'}\n"
            f"Method: {payout.get_payout_method_display()}\n"
        )
    elif payout.status == 'FAILED':
        subject = f"Your payout of Rs.{payout.amount} could not be sent"
        body = (
            f"The transfer of Rs.{payout.amount} did not go through.\n"
            f"The amount is back in your available balance - please check your payment "
            f"details and request it again.\n"
        )
    else:
        return

    _send(subject, body, [payout.seller.email])


# ── Reporting ────────────────────────────────────────────────────────────────

def seller_settlement_report(date_from=None, date_to=None, seller=None) -> list[dict]:
    """
    Per-seller settlement summary for a period: what was sold, what the
    platform kept, what was withheld, and what is still owed.
    """
    from django.contrib.auth.models import User

    earnings = SellerEarning.objects.exclude(status='CANCELLED')
    if date_from:
        earnings = earnings.filter(created_at__gte=date_from)
    if date_to:
        earnings = earnings.filter(created_at__lte=date_to)
    if seller is not None:
        earnings = earnings.filter(seller=seller)

    rows = (
        earnings
        .values('seller_id', 'seller__username')
        .annotate(
            gross=Sum('gross_amount'),
            commission=Sum('commission_amount'),
            tds=Sum('tds_amount'),
            net=Sum('net_amount'),
        )
        .order_by('-gross')
    )

    paid_by_seller = dict(
        earnings.filter(status='PAID')
        .values_list('seller_id')
        .annotate(t=Sum('net_amount'))
        .values_list('seller_id', 't')
    )

    report = []
    for row in rows:
        seller_id = row['seller_id']
        net = _money(row['net'])
        paid = _money(paid_by_seller.get(seller_id, 0))
        report.append({
            'seller_id': seller_id,
            'seller': row['seller__username'],
            'gross': _money(row['gross']),
            'commission': _money(row['commission']),
            'tds': _money(row['tds']),
            'net': net,
            'paid': paid,
            'outstanding': _money(net - paid),
        })
    return report
