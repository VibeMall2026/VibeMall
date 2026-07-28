"""
Seller (own-product) earnings.

Pays a seller for products they created (Product.created_by), minus platform
commission. Runs alongside resell_services.py, which pays affiliate margin on
ResellLink orders; the two never touch each other's balances.

Money rules enforced here:

- One earning row per (order, seller). An order with three sellers' products
  produces three rows.
- Commission is charged on (base_price x quantity) only. Shipping, tax and
  coupon discounts are the platform's concern, so a discount never reduces
  what the seller is paid.
- The commission rate is snapshotted onto the earning. Changing a seller's
  rate later never rewrites past earnings.
- Every balance change runs inside a transaction with the profile row locked,
  so two concurrent order updates cannot interleave and lose a credit.
- Creation and confirmation are idempotent. Django signals can fire more than
  once for the same save, and a double credit is real money lost.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    DEFAULT_SELLER_COMMISSION_PERCENT,
    OrderItem,
    ResellerProfile,
    SellerEarning,
)

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')


def _money(value) -> Decimal:
    """Round to paise, half-up. Bankers' rounding would quietly lose money."""
    return Decimal(value or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ── TDS (Income Tax Act s.194-O) ─────────────────────────────────────────────
#
# Off by default. Withholding tax from a seller without the operator having
# deliberately configured it would be wrong, so this only engages once
# SELLER_TDS_ENABLED is set. Rates and threshold are settings, not constants,
# because they are policy that changes with the Finance Act - they are not
# facts about this codebase.
#
#   SELLER_TDS_ENABLED           default False
#   SELLER_TDS_PERCENT           default 1%   (PAN on file)
#   SELLER_TDS_PERCENT_NO_PAN    default 5%   (higher rate, s.206AA)
#   SELLER_TDS_ANNUAL_THRESHOLD  default 500000 (gross per financial year)


def _setting(name, default):
    return getattr(settings, name, default)


def financial_year_start(on: date | None = None) -> date:
    """Indian financial year runs 1 April - 31 March."""
    today = on or timezone.now().date()
    year = today.year if today.month >= 4 else today.year - 1
    return date(year, 4, 1)


def _seller_gross_this_financial_year(seller) -> Decimal:
    total = (
        SellerEarning.objects
        .filter(seller=seller, created_at__gte=financial_year_start())
        .exclude(status='CANCELLED')
        .aggregate(t=Sum('gross_amount'))['t']
    )
    return _money(total or 0)


def calculate_tds(seller, gross_amount: Decimal) -> Decimal:
    """
    TDS to withhold on this earning.

    The threshold is cumulative across the financial year, so it is evaluated
    against the seller's year-to-date gross plus this sale - not this sale
    alone, which would let a seller stay under it forever by splitting orders.
    """
    if not _setting('SELLER_TDS_ENABLED', False):
        return Decimal('0.00')

    gross_amount = _money(gross_amount)
    if gross_amount <= 0:
        return Decimal('0.00')

    pan = ''
    try:
        pan = (seller.reseller_profile.pan_number or '').strip()
    except ResellerProfile.DoesNotExist:
        pan = ''

    threshold = Decimal(str(_setting('SELLER_TDS_ANNUAL_THRESHOLD', 500000)))
    ytd = _seller_gross_this_financial_year(seller)

    # No PAN means the higher rate applies from the first rupee; the
    # small-seller exemption is only available to a seller who furnished one.
    if pan:
        if ytd + gross_amount <= threshold:
            return Decimal('0.00')
        rate = Decimal(str(_setting('SELLER_TDS_PERCENT', '1.00')))
    else:
        rate = Decimal(str(_setting('SELLER_TDS_PERCENT_NO_PAN', '5.00')))

    return _money(gross_amount * rate / Decimal('100'))


def get_seller_commission_percent(seller) -> Decimal:
    """Per-seller rate, falling back to the platform default."""
    try:
        profile = seller.reseller_profile
    except ResellerProfile.DoesNotExist:
        return DEFAULT_SELLER_COMMISSION_PERCENT
    rate = profile.seller_commission_percent
    if rate is None:
        return DEFAULT_SELLER_COMMISSION_PERCENT
    return Decimal(rate)


def _seller_items(order):
    """
    Group an order's items by the seller who owns the product.

    base_price is the seller's price before any reseller margin. Older rows may
    have base_price = 0 (the field was added for the resell flow), so fall back
    to product_price to avoid silently paying a seller nothing.
    """
    grouped: dict[int, dict] = {}
    items = (
        OrderItem.objects
        .filter(order=order)
        .select_related('product', 'product__created_by')
    )
    for item in items:
        product = item.product
        seller = getattr(product, 'created_by', None) if product else None
        if seller is None:
            continue  # platform-owned product: no seller to pay

        unit_price = item.base_price if item.base_price and item.base_price > 0 else item.product_price
        bucket = grouped.setdefault(seller.id, {'seller': seller, 'gross': Decimal('0'), 'units': 0})
        bucket['gross'] += Decimal(unit_price) * item.quantity
        bucket['units'] += item.quantity
    return grouped


@transaction.atomic
def create_seller_earnings(order) -> list[SellerEarning]:
    """
    Create PENDING earnings for every seller with products in this order.

    Safe to call repeatedly: sellers that already have an earning for the order
    are skipped, so a replayed signal cannot double-credit.
    """
    existing = set(
        SellerEarning.objects.filter(order=order).values_list('seller_id', flat=True)
    )
    created: list[SellerEarning] = []

    for seller_id, bucket in _seller_items(order).items():
        if seller_id in existing:
            continue

        seller = bucket['seller']
        gross = _money(bucket['gross'])
        if gross <= 0:
            continue

        percent = get_seller_commission_percent(seller)
        commission = _money(gross * percent / Decimal('100'))
        tds = calculate_tds(seller, gross)
        net = _money(gross - commission - tds)

        earning = SellerEarning.objects.create(
            seller=seller,
            order=order,
            gross_amount=gross,
            commission_percent=percent,
            commission_amount=commission,
            tds_amount=tds,
            net_amount=net,
            item_count=bucket['units'],
            status='PENDING',
        )
        created.append(earning)
        logger.info(
            "Created seller earning %s: seller=%s order=%s gross=%s commission=%s tds=%s net=%s",
            earning.id, seller.username, order.order_number, gross, commission, tds, net,
        )

    return created


@transaction.atomic
def confirm_seller_earning(earning_id: int) -> SellerEarning:
    """
    Move one earning PENDING -> CONFIRMED and credit the seller's balance.

    Re-reads the row with a lock so a concurrent call cannot confirm twice.
    """
    earning = SellerEarning.objects.select_for_update().select_related('seller').get(id=earning_id)

    if earning.status != 'PENDING':
        # Already handled (or cancelled). Not an error - signals replay.
        return earning

    profile, _ = ResellerProfile.objects.select_for_update().get_or_create(user=earning.seller)

    earning.status = 'CONFIRMED'
    earning.confirmed_at = timezone.now()
    earning.save(update_fields=['status', 'confirmed_at'])

    profile.seller_available_balance = _money(profile.seller_available_balance + earning.net_amount)
    profile.seller_total_earnings = _money(profile.seller_total_earnings + earning.net_amount)
    profile.seller_total_orders += 1
    profile.save(update_fields=[
        'seller_available_balance', 'seller_total_earnings', 'seller_total_orders',
    ])

    logger.info(
        "Confirmed seller earning %s: seller=%s net=%s new_balance=%s",
        earning.id, earning.seller.username, earning.net_amount, profile.seller_available_balance,
    )
    return earning


def confirm_seller_earnings_for_order(order) -> list[SellerEarning]:
    """Confirm every pending earning on an order (called on delivery)."""
    ids = list(
        SellerEarning.objects.filter(order=order, status='PENDING').values_list('id', flat=True)
    )
    return [confirm_seller_earning(pk) for pk in ids]


@transaction.atomic
def cancel_seller_earning(earning_id: int, reason: str = '') -> SellerEarning:
    """
    Cancel an earning, reversing the balance if it was already confirmed.

    A PAID earning is never cancelled here: that money has left the platform,
    so clawing it back is a manual finance decision, not an automatic one.
    """
    earning = SellerEarning.objects.select_for_update().select_related('seller').get(id=earning_id)

    if earning.status in ('CANCELLED', 'PAID'):
        return earning

    was_confirmed = earning.status == 'CONFIRMED'

    earning.status = 'CANCELLED'
    earning.cancelled_at = timezone.now()
    earning.cancel_reason = (reason or '')[:200]
    earning.save(update_fields=['status', 'cancelled_at', 'cancel_reason'])

    if was_confirmed:
        profile, _ = ResellerProfile.objects.select_for_update().get_or_create(user=earning.seller)

        # If this earning is already locked inside an open payout, its money
        # left the available balance when the payout was requested. Debiting
        # again here would take it off the seller twice. Flag the payout so an
        # admin resolves it before any money is actually sent.
        open_payout = earning.payout if (earning.payout and earning.payout.is_open) else None

        if open_payout is None:
            profile.seller_available_balance = _money(
                max(Decimal('0'), profile.seller_available_balance - earning.net_amount)
            )
        else:
            note = (
                f"[ALERT] Earning #{earning.id} (order {earning.order.order_number}, "
                f"Rs.{earning.net_amount}) was cancelled after this payout was requested. "
                f"Reject this payout and let the seller re-request."
            )
            open_payout.admin_notes = (
                (open_payout.admin_notes + "\n") if open_payout.admin_notes else ""
            ) + note
            open_payout.save(update_fields=['admin_notes'])
            logger.error(
                "Seller earning %s cancelled while locked in open payout %s (seller=%s, amount=%s)",
                earning.id, open_payout.id, earning.seller.username, earning.net_amount,
            )

        profile.seller_total_earnings = _money(
            max(Decimal('0'), profile.seller_total_earnings - earning.net_amount)
        )
        if profile.seller_total_orders > 0:
            profile.seller_total_orders -= 1
        profile.save(update_fields=[
            'seller_available_balance', 'seller_total_earnings', 'seller_total_orders',
        ])
        logger.warning(
            "Reversed confirmed seller earning %s: seller=%s net=%s reason=%s",
            earning.id, earning.seller.username, earning.net_amount, reason,
        )

    return earning


def cancel_seller_earnings_for_order(order, reason: str = '') -> list[SellerEarning]:
    """Cancel all of an order's earnings (called on cancellation/refund)."""
    ids = list(
        SellerEarning.objects
        .filter(order=order)
        .exclude(status__in=['CANCELLED', 'PAID'])
        .values_list('id', flat=True)
    )
    return [cancel_seller_earning(pk, reason=reason) for pk in ids]


def get_seller_balance(seller) -> Decimal:
    """
    Read the balance straight from the database rather than through
    seller.reseller_profile.

    Django caches a reverse one-to-one on the instance, so a caller that
    touched the profile earlier in the same request would otherwise read a
    balance from before this request's confirmations - and a stale balance
    shown next to a withdraw button is money waiting to be double-spent.
    """
    balance = (
        ResellerProfile.objects
        .filter(user=seller)
        .values_list('seller_available_balance', flat=True)
        .first()
    )
    return balance if balance is not None else Decimal('0.00')


def get_seller_earnings_summary(seller) -> dict:
    """Totals for the seller dashboard, one query per status bucket."""
    qs = SellerEarning.objects.filter(seller=seller)

    def total(status):
        return _money(
            qs.filter(status=status).aggregate(t=Sum('net_amount'))['t'] or Decimal('0')
        )

    return {
        'available_balance': get_seller_balance(seller),
        'pending_amount': total('PENDING'),
        'confirmed_amount': total('CONFIRMED'),
        'paid_amount': total('PAID'),
        'cancelled_amount': total('CANCELLED'),
        'total_orders': qs.exclude(status='CANCELLED').values('order_id').distinct().count(),
        'commission_paid': _money(
            qs.exclude(status='CANCELLED').aggregate(t=Sum('commission_amount'))['t'] or Decimal('0')
        ),
        'tds_withheld': _money(
            qs.exclude(status='CANCELLED').aggregate(t=Sum('tds_amount'))['t'] or Decimal('0')
        ),
        'gross_this_fy': _seller_gross_this_financial_year(seller),
    }
