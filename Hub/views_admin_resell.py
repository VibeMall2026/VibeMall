"""
Admin Panel Views for Resell Management

This module contains custom admin panel views for managing resell operations:
- Resell orders view with filters
- Reseller analytics view
- Resell reports view
- Reseller management view
- Payout management view (with 7-day eligibility)
"""

from decimal import Decimal
from datetime import datetime, timedelta
import logging
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.conf import settings
import csv

from .models import (
    Order,
    OrderItem,
    ResellLink,
    ResellerProfile,
    ResellerEarning,
    PayoutTransaction,
    User,
    ReturnRequest
)
from .resell_payout_service import (
    PayoutEligibilityManager,
    PayoutEmailService,
    PayoutInvoiceGenerator,
    RazorpayPaymentProcessor,
    BankTransferPaymentProcessor,
    UPIPaymentProcessor,
)


logger = logging.getLogger(__name__)


def _parse_admin_date(date_str, field_label):
    """Parse admin date filter in YYYY-MM-DD format."""
    if not date_str:
        return None

    try:
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValidationError(f"{field_label} must be in YYYY-MM-DD format.") from exc

    ten_years_ago = (timezone.now() - timedelta(days=3650)).date()
    today = timezone.now().date()

    if parsed_date < ten_years_ago:
        raise ValidationError(f"{field_label} cannot be older than 10 years.")
    if parsed_date > today:
        raise ValidationError(f"{field_label} cannot be in the future.")

    return parsed_date


def _get_safe_page_size(request, default=25, maximum=100):
    """Return validated page size for pagination."""
    try:
        page_size = int(request.GET.get('page_size', default))
    except (TypeError, ValueError):
        return default

    if page_size < 1:
        return default
    return min(page_size, maximum)


# ============================================
# ADMIN RESELL ORDERS VIEW
# ============================================

@staff_member_required
def admin_resell_orders(request):
    """
    Admin resell orders view with filters
    GET /admin-panel/resell/orders/
    
    Filters:
    - reseller: Filter by reseller user ID
    - date_from: Start date
    - date_to: End date
    - status: Order status
    - payment_status: Payment status
    """
    # Get filter parameters
    reseller_id = request.GET.get('reseller', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    order_status = request.GET.get('status', '')
    payment_status = request.GET.get('payment_status', '')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-created_at')
    page_size = _get_safe_page_size(request)

    order_sort_fields = {
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'total_amount': 'total_amount',
        '-total_amount': '-total_amount',
        'total_margin': 'total_margin',
        '-total_margin': '-total_margin',
        'order_number': 'order_number',
        '-order_number': '-order_number',
    }
    order_by = order_sort_fields.get(sort_by, '-created_at')
    
    # Base queryset
    orders = Order.objects.filter(is_resell=True).select_related(
        'user', 'reseller', 'resell_link'
    ).prefetch_related('items').order_by(order_by)
    
    # Apply filters
    if reseller_id:
        orders = orders.filter(reseller_id=reseller_id)
    
    parsed_date_from = None
    parsed_date_to = None
    try:
        parsed_date_from = _parse_admin_date(date_from, 'Date from')
        parsed_date_to = _parse_admin_date(date_to, 'Date to')
        if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
            raise ValidationError('Date from cannot be after date to.')
    except ValidationError as exc:
        messages.error(request, str(exc))

    if parsed_date_from:
        orders = orders.filter(created_at__gte=parsed_date_from)
    if parsed_date_to:
        orders = orders.filter(created_at__lt=(parsed_date_to + timedelta(days=1)))
    
    if order_status:
        orders = orders.filter(order_status=order_status)
    
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(reseller__username__icontains=search_query)
        )
    
    # Calculate summary statistics
    summary = orders.aggregate(
        total_orders=Count('id'),
        total_revenue=Sum('total_amount'),
        total_margin=Sum('total_margin'),
        total_base=Sum('base_amount')
    )
    total_orders = summary['total_orders'] or 0
    total_revenue = summary['total_revenue'] or Decimal('0.00')
    total_margin = summary['total_margin'] or Decimal('0.00')
    total_base = summary['total_base'] or Decimal('0.00')
    
    # Pagination
    paginator = Paginator(orders, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all resellers for filter dropdown
    resellers = User.objects.filter(
        reseller_profile__is_reseller_enabled=True
    ).order_by('username')
    
    context = {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'resellers': resellers,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_margin': total_margin,
        'total_base': total_base,
        # Filter values for form
        'filter_reseller': reseller_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'filter_status': order_status,
        'filter_payment_status': payment_status,
        'filter_search': search_query,
        'filter_sort': sort_by,
        'page_size': page_size,
    }
    
    return render(request, 'admin_panel/resell/orders.html', context)


# ============================================
# ADMIN RESELLER ANALYTICS VIEW
# ============================================

@staff_member_required
def admin_reseller_analytics(request):
    """
    Admin reseller analytics view with performance metrics
    GET /admin-panel/resell/analytics/
    
    Optional parameter:
    - reseller_id: View specific reseller analytics
    """
    reseller_id = request.GET.get('reseller_id', '')
    
    if reseller_id:
        # Single reseller analytics
        reseller = get_object_or_404(User, id=reseller_id)
        profile = get_object_or_404(ResellerProfile, user=reseller)
        
        # Get reseller's orders
        orders = Order.objects.filter(
            reseller=reseller,
            is_resell=True
        ).select_related('user', 'reseller', 'resell_link')

        # Calculate metrics in one query
        order_summary = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            total_margin=Sum('total_margin')
        )
        total_orders = order_summary['total_orders'] or 0
        total_revenue = order_summary['total_revenue'] or Decimal('0.00')
        total_margin = order_summary['total_margin'] or Decimal('0.00')
        
        # Get resell links
        links = ResellLink.objects.filter(reseller=reseller)
        total_links = links.count()
        active_links = links.filter(is_active=True).count()
        total_views = links.aggregate(total=Sum('views_count'))['total'] or 0
        
        # Calculate conversion rate
        conversion_rate = (total_orders / total_views * 100) if total_views > 0 else 0
        
        # Get earnings breakdown in one query
        earnings = ResellerEarning.objects.filter(reseller=reseller)
        earnings_summary = earnings.aggregate(
            pending_earnings=Sum('margin_amount', filter=Q(status='PENDING')),
            confirmed_earnings=Sum('margin_amount', filter=Q(status='CONFIRMED')),
            paid_earnings=Sum('margin_amount', filter=Q(status='PAID')),
        )
        pending_earnings = earnings_summary['pending_earnings'] or Decimal('0.00')
        confirmed_earnings = earnings_summary['confirmed_earnings'] or Decimal('0.00')
        paid_earnings = earnings_summary['paid_earnings'] or Decimal('0.00')
        
        # Get recent orders
        recent_orders = orders.order_by('-created_at')[:10]
        
        # Get top performing links
        top_links = links.order_by('-total_earnings')[:10]
        
        context = {
            'reseller': reseller,
            'profile': profile,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_margin': total_margin,
            'total_links': total_links,
            'active_links': active_links,
            'total_views': total_views,
            'conversion_rate': round(conversion_rate, 2),
            'pending_earnings': pending_earnings,
            'confirmed_earnings': confirmed_earnings,
            'paid_earnings': paid_earnings,
            'recent_orders': recent_orders,
            'top_links': top_links,
        }
        
        return render(request, 'admin_panel/resell/reseller_detail.html', context)
    
    else:
        # All resellers analytics
        sort_by = request.GET.get('sort', '-total_earnings')
        page_size = _get_safe_page_size(request)
        reseller_sort_fields = {
            'total_earnings': 'total_earnings',
            '-total_earnings': '-total_earnings',
            'available_balance': 'available_balance',
            '-available_balance': '-available_balance',
            'total_orders': 'total_orders',
            '-total_orders': '-total_orders',
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'user__username': 'user__username',
            '-user__username': '-user__username',
        }
        order_by = reseller_sort_fields.get(sort_by, '-total_earnings')

        resellers = ResellerProfile.objects.filter(
            is_reseller_enabled=True
        ).select_related('user').order_by(order_by)
        
        # Calculate overall metrics
        total_resellers = resellers.count()
        all_resell_orders = Order.objects.filter(is_resell=True)
        order_metrics = all_resell_orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            total_margin=Sum('total_margin')
        )
        total_orders = order_metrics['total_orders'] or 0
        total_revenue = order_metrics['total_revenue'] or Decimal('0.00')
        total_margin = order_metrics['total_margin'] or Decimal('0.00')
        
        # Get top performers
        top_resellers = resellers[:10]
        
        # Pagination
        paginator = Paginator(resellers, page_size)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'resellers': page_obj.object_list,
            'total_resellers': total_resellers,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_margin': total_margin,
            'top_resellers': top_resellers,
            'filter_sort': sort_by,
            'page_size': page_size,
        }
        
        return render(request, 'admin_panel/resell/analytics.html', context)


# ============================================
# ADMIN RESELL REPORTS VIEW
# ============================================

@staff_member_required
def admin_resell_reports(request):
    """
    Admin resell reports view with date range and export
    GET /admin-panel/resell/reports/
    
    Parameters:
    - date_from: Start date
    - date_to: End date
    - export: 'csv' to export as CSV
    """
    # Get date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    export_format = request.GET.get('export', '')
    
    # Default to last 30 days if no dates provided
    if not date_from:
        date_from = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = timezone.now().strftime('%Y-%m-%d')
    
    # Parse dates
    try:
        parsed_date_from = _parse_admin_date(date_from, 'Date from')
        parsed_date_to = _parse_admin_date(date_to, 'Date to')
        if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
            raise ValidationError('Date from cannot be after date to.')
        date_from_obj = parsed_date_from
        date_to_obj = parsed_date_to + timedelta(days=1)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect('admin_resell_reports')
    
    # Get data for date range
    orders = Order.objects.filter(
        is_resell=True,
        created_at__gte=date_from_obj,
        created_at__lt=date_to_obj
    )
    
    earnings = ResellerEarning.objects.filter(
        created_at__gte=date_from_obj,
        created_at__lt=date_to_obj
    )
    
    payouts = PayoutTransaction.objects.filter(
        initiated_at__gte=date_from_obj,
        initiated_at__lt=date_to_obj
    )
    
    # Calculate metrics
    total_resellers = ResellerProfile.objects.filter(is_reseller_enabled=True).count()
    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_margin = orders.aggregate(total=Sum('total_margin'))['total'] or Decimal('0.00')
    total_base = orders.aggregate(total=Sum('base_amount'))['total'] or Decimal('0.00')
    
    # Earnings breakdown
    pending_earnings = earnings.filter(status='PENDING').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
    confirmed_earnings = earnings.filter(status='CONFIRMED').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
    paid_earnings = earnings.filter(status='PAID').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
    cancelled_earnings = earnings.filter(status='CANCELLED').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
    
    # Payout metrics
    total_payouts = payouts.count()
    completed_payouts = payouts.filter(status='COMPLETED').count()
    failed_payouts = payouts.filter(status='FAILED').count()
    total_payout_amount = payouts.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Top performing resellers
    top_resellers = ResellerProfile.objects.filter(
        is_reseller_enabled=True
    ).annotate(
        period_orders=Count('user__resold_orders', filter=Q(
            user__resold_orders__created_at__gte=date_from_obj,
            user__resold_orders__created_at__lt=date_to_obj,
            user__resold_orders__is_resell=True
        )),
        period_earnings=Sum('user__resold_orders__total_margin', filter=Q(
            user__resold_orders__created_at__gte=date_from_obj,
            user__resold_orders__created_at__lt=date_to_obj,
            user__resold_orders__is_resell=True
        ))
    ).order_by('-period_earnings')[:10]
    
    # Export as CSV
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="resell_report_{date_from}_to_{date_to}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Resell Report'])
        writer.writerow(['Date Range', f'{date_from} to {date_to}'])
        writer.writerow([])
        
        writer.writerow(['Summary Metrics'])
        writer.writerow(['Total Resellers', total_resellers])
        writer.writerow(['Total Orders', total_orders])
        writer.writerow(['Total Revenue', f'₹{total_revenue}'])
        writer.writerow(['Total Margin', f'₹{total_margin}'])
        writer.writerow(['Total Base Amount', f'₹{total_base}'])
        writer.writerow([])
        
        writer.writerow(['Earnings Breakdown'])
        writer.writerow(['Pending Earnings', f'₹{pending_earnings}'])
        writer.writerow(['Confirmed Earnings', f'₹{confirmed_earnings}'])
        writer.writerow(['Paid Earnings', f'₹{paid_earnings}'])
        writer.writerow(['Cancelled Earnings', f'₹{cancelled_earnings}'])
        writer.writerow([])
        
        writer.writerow(['Payout Metrics'])
        writer.writerow(['Total Payouts', total_payouts])
        writer.writerow(['Completed Payouts', completed_payouts])
        writer.writerow(['Failed Payouts', failed_payouts])
        writer.writerow(['Total Payout Amount', f'₹{total_payout_amount}'])
        writer.writerow([])
        
        writer.writerow(['Top Performing Resellers'])
        writer.writerow(['Username', 'Orders', 'Earnings'])
        for reseller in top_resellers:
            writer.writerow([
                reseller.user.username,
                reseller.period_orders or 0,
                f'₹{reseller.period_earnings or 0}'
            ])
        
        return response
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_resellers': total_resellers,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_margin': total_margin,
        'total_base': total_base,
        'pending_earnings': pending_earnings,
        'confirmed_earnings': confirmed_earnings,
        'paid_earnings': paid_earnings,
        'cancelled_earnings': cancelled_earnings,
        'total_payouts': total_payouts,
        'completed_payouts': completed_payouts,
        'failed_payouts': failed_payouts,
        'total_payout_amount': total_payout_amount,
        'top_resellers': top_resellers,
    }
    
    return render(request, 'admin_panel/resell/reports.html', context)


# ============================================
# ADMIN RESELLER MANAGEMENT VIEW
# ============================================

@staff_member_required
def admin_reseller_management(request):
    """
    Admin reseller management view
    GET /admin-panel/resell/resellers/
    
    Manage reseller accounts - enable/disable, view details
    """
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', '-created_at')
    page_size = _get_safe_page_size(request)

    sort_fields = {
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'total_earnings': 'total_earnings',
        '-total_earnings': '-total_earnings',
        'available_balance': 'available_balance',
        '-available_balance': '-available_balance',
        'total_orders': 'total_orders',
        '-total_orders': '-total_orders',
        'user__username': 'user__username',
        '-user__username': '-user__username',
    }
    order_by = sort_fields.get(sort_by, '-created_at')
    
    # Base queryset
    resellers = ResellerProfile.objects.select_related('user').order_by(order_by)
    
    # Apply filters
    if search_query:
        resellers = resellers.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(business_name__icontains=search_query)
        )
    
    if status_filter == 'enabled':
        resellers = resellers.filter(is_reseller_enabled=True)
    elif status_filter == 'disabled':
        resellers = resellers.filter(is_reseller_enabled=False)
    
    # Pagination
    paginator = Paginator(resellers, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary
    total_resellers = ResellerProfile.objects.count()
    enabled_resellers = ResellerProfile.objects.filter(is_reseller_enabled=True).count()
    disabled_resellers = total_resellers - enabled_resellers
    
    context = {
        'page_obj': page_obj,
        'resellers': page_obj.object_list,
        'total_resellers': total_resellers,
        'enabled_resellers': enabled_resellers,
        'disabled_resellers': disabled_resellers,
        'filter_search': search_query,
        'filter_status': status_filter,
        'filter_sort': sort_by,
        'page_size': page_size,
    }
    
    return render(request, 'admin_panel/resell/resellers.html', context)


@staff_member_required
def admin_reseller_payment_data(request):
    """
    Admin payment data view for reseller bank and UPI details
    GET /admin-panel/resell/payment-data/
    """
    search_query = request.GET.get('search', '')
    payment_filter = request.GET.get('payment', '')  # all, bank, upi, both, missing
    sort_by = request.GET.get('sort', '-updated_at')
    page_size = _get_safe_page_size(request)

    sort_fields = {
        'updated_at': 'updated_at',
        '-updated_at': '-updated_at',
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'user__username': 'user__username',
        '-user__username': '-user__username',
        'business_name': 'business_name',
        '-business_name': '-business_name',
    }
    order_by = sort_fields.get(sort_by, '-updated_at')

    profiles = ResellerProfile.objects.select_related('user').order_by(order_by)

    if search_query:
        profiles = profiles.filter(
            Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(business_name__icontains=search_query)
            | Q(upi_id__icontains=search_query)
            | Q(bank_account_name__icontains=search_query)
            | Q(bank_ifsc_code__icontains=search_query)
        )

    has_bank_q = (
        Q(bank_account_name__gt='')
        & Q(bank_account_number__gt='')
        & Q(bank_ifsc_code__gt='')
    )
    has_upi_q = Q(upi_id__gt='')

    if payment_filter == 'bank':
        profiles = profiles.filter(has_bank_q)
    elif payment_filter == 'upi':
        profiles = profiles.filter(has_upi_q)
    elif payment_filter == 'both':
        profiles = profiles.filter(has_bank_q & has_upi_q)
    elif payment_filter == 'missing':
        profiles = profiles.exclude(has_bank_q | has_upi_q)

    paginator = Paginator(profiles, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    total_profiles = ResellerProfile.objects.count()
    bank_ready = ResellerProfile.objects.filter(has_bank_q).count()
    upi_ready = ResellerProfile.objects.filter(has_upi_q).count()
    both_ready = ResellerProfile.objects.filter(has_bank_q & has_upi_q).count()

    context = {
        'page_obj': page_obj,
        'profiles': page_obj.object_list,
        'total_profiles': total_profiles,
        'bank_ready': bank_ready,
        'upi_ready': upi_ready,
        'both_ready': both_ready,
        'filter_search': search_query,
        'filter_payment': payment_filter,
        'filter_sort': sort_by,
        'page_size': page_size,
    }

    return render(request, 'admin_panel/resell/payment_data.html', context)


@staff_member_required
def admin_toggle_reseller_status(request, reseller_id):
    """
    Toggle reseller enabled/disabled status
    POST /admin-panel/resell/resellers/<id>/toggle/
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request method for status update.')
        return redirect('admin_reseller_management')

    try:
        profile = get_object_or_404(ResellerProfile, id=reseller_id)
        profile.is_reseller_enabled = not profile.is_reseller_enabled
        profile.save(update_fields=['is_reseller_enabled'])

        status = 'enabled' if profile.is_reseller_enabled else 'disabled'
        messages.success(request, f'Reseller {profile.user.username} has been {status}.')
    except Exception:
        logger.exception('Failed to toggle reseller status. reseller_id=%s', reseller_id)
        messages.error(request, 'Unable to update reseller status right now.')
    
    return redirect('admin_reseller_management')


# ============================================
# ADMIN PAYOUT MANAGEMENT VIEW
# ============================================

@staff_member_required
def admin_payout_management(request):
    """
    Admin payout management view with 7-day eligibility
    GET /admin-panel/resell/payouts/
    
    Displays:
    - Eligible payouts (7+ days after delivery, no returns)
    - Pending payouts (under 7 days, in return window)
    - Completed/failed payouts
    """
    view_type = request.GET.get('view', 'eligible')  # eligible, pending, completed
    reseller_id = request.GET.get('reseller', '')
    sort_by = request.GET.get('sort', '-margin_amount')
    page_size = _get_safe_page_size(request)

    # Get all resellers for filter
    resellers = User.objects.filter(
        reseller_profile__is_reseller_enabled=True
    ).order_by('username')

    if view_type == 'eligible':
        # Show earnings ready for payout (passed 7-day hold)
        earnings = PayoutEligibilityManager.get_eligible_payouts_for_admin()
        earnings = earnings.select_related('order__user', 'reseller__reseller_profile')
        
        # Add eligibility status for each
        earnings_list = []
        for earning in earnings:
            status, extra_date = PayoutEligibilityManager.get_payout_eligibility_status(earning)
            earnings_list.append({
                'earning': earning,
                'status': status,
                'extra_date': extra_date,
                'days_since_delivery': (timezone.now() - earning.order.delivery_date).days if earning.order.delivery_date else 0,
            })
        
        # Sort
        sort_map = {
            'margin_amount': lambda x: x['earning'].margin_amount,
            '-margin_amount': lambda x: -x['earning'].margin_amount,
            'delivery_date': lambda x: x['earning'].order.delivery_date or timezone.now(),
            '-delivery_date': lambda x: -(x['earning'].order.delivery_date.timestamp() if x['earning'].order.delivery_date else 0),
            'reseller': lambda x: x['earning'].reseller.username,
            '-reseller': lambda x: x['earning'].reseller.username,
        }
        
        reverse = sort_by.startswith('-')
        sort_key = sort_map.get(sort_by, sort_map['-margin_amount'])
        earnings_list.sort(key=sort_key, reverse=reverse)
        
        # Paginate
        paginator = Paginator(earnings_list, page_size)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Summary for eligible
        total_earnings = ResellerEarning.objects.filter(
            status='CONFIRMED',
            payout_transaction__isnull=True
        ).aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
        
        context = {
            'view_type': 'eligible',
            'page_obj': page_obj,
            'earnings': page_obj.object_list,
            'total_eligible_amount': total_earnings,
            'resellers': resellers,
            'filter_reseller': reseller_id,
            'filter_sort': sort_by,
            'payout_methods': dict(PayoutTransaction.PAYOUT_METHOD_CHOICES),
        }

    else:
        # Show completed payouts (old behavior)
        status_filter = request.GET.get('status', 'COMPLETED')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        payout_sort_fields = {
            'initiated_at': 'initiated_at',
            '-initiated_at': '-initiated_at',
            'amount': 'amount',
            '-amount': '-amount',
            'status': 'status',
        }
        order_by = payout_sort_fields.get(sort_by, '-initiated_at')
        
        payouts = PayoutTransaction.objects.select_related('reseller').order_by(order_by)
        
        if status_filter:
            payouts = payouts.filter(status=status_filter)
        
        if reseller_id:
            payouts = payouts.filter(reseller_id=reseller_id)
        
        parsed_date_from = None
        parsed_date_to = None
        try:
            parsed_date_from = _parse_admin_date(date_from, 'Date from')
            parsed_date_to = _parse_admin_date(date_to, 'Date to')
            if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
                raise ValidationError('Date from cannot be after date to.')
        except ValidationError as exc:
            messages.error(request, str(exc))

        if parsed_date_from:
            payouts = payouts.filter(initiated_at__gte=parsed_date_from)
        if parsed_date_to:
            payouts = payouts.filter(initiated_at__lt=(parsed_date_to + timedelta(days=1)))
        
        paginator = Paginator(payouts, page_size)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        total_payouts = PayoutTransaction.objects.count()
        initiated_payouts = PayoutTransaction.objects.filter(status='INITIATED').count()
        completed_payouts = PayoutTransaction.objects.filter(status='COMPLETED').count()
        failed_payouts = PayoutTransaction.objects.filter(status='FAILED').count()
        total_amount = PayoutTransaction.objects.filter(status='COMPLETED').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        context = {
            'view_type': 'completed',
            'page_obj': page_obj,
            'payouts': page_obj.object_list,
            'total_payouts': total_payouts,
            'initiated_payouts': initiated_payouts,
            'completed_payouts': completed_payouts,
            'failed_payouts': failed_payouts,
            'total_amount': total_amount,
            'resellers': resellers,
            'filter_status': status_filter,
            'filter_reseller': reseller_id,
            'filter_date_from': date_from,
            'filter_date_to': date_to,
            'filter_sort': sort_by,
        }
    
    return render(request, 'admin_panel/resell/payouts.html', context)


@staff_member_required
def admin_process_payout(request):
    """
    Process payout for eligible earnings with payment method selection
    POST /admin-panel/resell/payouts/process/
    
    Form data:
    - earning_ids: comma-separated list of ResellerEarning IDs
    - payout_method: BANK_TRANSFER, UPI, RAZORPAY, or WALLET
    - bank_account (if BANK_TRANSFER): account number to transfer to
    - upi_id (if UPI): UPI ID to transfer to
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        earning_ids = request.POST.get('earning_ids', '').split(',')
        earning_ids = [int(eid.strip()) for eid in earning_ids if eid.strip().isdigit()]
        
        if not earning_ids:
            return JsonResponse({'success': False, 'error': 'No earnings selected'}, status=400)
        
        payout_method = request.POST.get('payout_method', '').upper()
        valid_methods = dict(PayoutTransaction.PAYOUT_METHOD_CHOICES).keys()
        if payout_method not in valid_methods:
            return JsonResponse({'success': False, 'error': f'Invalid payment method. Valid: {", ".join(valid_methods)}'}, status=400)
        
        with transaction.atomic():
            earnings = ResellerEarning.objects.filter(
                id__in=earning_ids,
                status='CONFIRMED',
                payout_transaction__isnull=True
            ).select_related('reseller', 'order__user')
            
            if not earnings.exists():
                return JsonResponse({'success': False, 'error': 'No valid earnings found'}, status=400)
            
            # All earnings must belong to same reseller (for now)
            resellers = set(e.reseller_id for e in earnings)
            if len(resellers) > 1:
                return JsonResponse(
                    {'success': False, 'error': 'Cannot process payouts for multiple resellers in one request'},
                    status=400
                )
            
            reseller = earnings.first().reseller
            total_amount = sum(e.margin_amount for e in earnings)
            
            # Create payout transaction
            payout = PayoutTransaction.objects.create(
                reseller=reseller,
                amount=total_amount,
                payout_method=payout_method,
                bank_account=request.POST.get('bank_account', ''),
                upi_id=request.POST.get('upi_id', ''),
                status='INITIATED'
            )
            
            # Link earnings to payout
            earnings_list = list(earnings)
            ResellerEarning.objects.filter(id__in=earning_ids).update(payout_transaction=payout)
            
            # Generate invoice
            invoice_path = PayoutInvoiceGenerator.generate_payout_invoice_pdf(
                payout,
                earnings_list
            )
            
            # Process payment based on method
            if payout_method == 'RAZORPAY':
                result = RazorpayPaymentProcessor.initiate_razorpay_payout(payout)
                if result:
                    payout.status = 'PROCESSING'
                    payout.save()
                    logger.info(f"Razorpay payout initiated: {payout.id}")
                else:
                    payout.status = 'FAILED'
                    payout.admin_notes = 'Razorpay API error'
                    payout.save()
                    return JsonResponse(
                        {'success': False, 'error': 'Failed to initiate Razorpay payout'},
                        status=500
                    )
            elif payout_method == 'BANK_TRANSFER':
                BankTransferPaymentProcessor.process_bank_transfer(payout)
                payout.status = 'PROCESSING'
                payout.save()
            elif payout_method == 'UPI':
                UPIPaymentProcessor.process_upi_payment(payout)
                payout.status = 'PROCESSING'
                payout.save()
            
            # Send confirmation email to reseller with invoice
            PayoutEmailService.send_payout_confirmation_to_reseller(payout, invoice_path)
            
            messages.success(
                request,
                f'Payout of ₹{total_amount} initiated for {reseller.username} ({payout_method})'
            )
            
            return JsonResponse({
                'success': True,
                'payout_id': payout.id,
                'amount': str(total_amount),
                'redirect': '?view=completed'
            })
    
    except ValidationError as e:
        logger.warning(f"Validation error in payout processing: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.exception('Failed to process payout')
        return JsonResponse(
            {'success': False, 'error': 'An error occurred while processing payout'},
            status=500
        )


@staff_member_required
def admin_approve_payout(request, payout_id):
    """
    Mark payout as completed (for already-processed payments)
    POST /admin-panel/resell/payouts/<id>/approve/
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request method for payout approval.')
        return redirect('admin_payout_management')

    try:
        with transaction.atomic():
            payout = PayoutTransaction.objects.select_for_update().select_related('reseller').get(id=payout_id)

            if payout.status not in ('INITIATED', 'PROCESSING'):
                messages.error(request, 'Payout cannot be approved in its current status.')
                return redirect('admin_payout_management')

            payout.status = 'COMPLETED'
            payout.completed_at = timezone.now()
            payout.save(update_fields=['status', 'completed_at'])

            # Mark earnings as PAID
            ResellerEarning.objects.filter(
                payout_transaction=payout,
                status='CONFIRMED'
            ).update(
                status='PAID',
                paid_at=timezone.now()
            )

            messages.success(request, f'Payout of ₹{payout.amount} marked as completed.')
    except PayoutTransaction.DoesNotExist:
        messages.error(request, 'Payout transaction not found.')
    except Exception:
        logger.exception('Failed to approve payout. payout_id=%s', payout_id)
        messages.error(request, 'Unable to approve payout right now. Please try again.')
    
    return redirect('admin_payout_management' + '?view=completed')


@staff_member_required
def admin_reject_payout(request, payout_id):
    """
    Reject a payout transaction and release earnings for re-payout
    POST /admin-panel/resell/payouts/<id>/reject/
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request method for payout rejection.')
        return redirect('admin_payout_management')

    try:
        with transaction.atomic():
            payout = PayoutTransaction.objects.select_for_update().select_related('reseller').get(id=payout_id)

            if payout.status not in ('INITIATED', 'PROCESSING', 'FAILED'):
                messages.error(request, 'Payout cannot be rejected in its current status.')
                return redirect('admin_payout_management')

            rejection_reason = (request.POST.get('reason') or 'Rejected by admin').strip()
            payout.status = 'FAILED'
            payout.admin_notes = rejection_reason
            payout.save(update_fields=['status', 'admin_notes'])

            # Release earnings back to eligible for re-payout
            ResellerEarning.objects.filter(
                payout_transaction=payout,
                status__in=['CONFIRMED', 'PENDING']
            ).update(payout_transaction=None)

            messages.success(request, f'Payout rejected. Earnings released for re-payout.')
    except PayoutTransaction.DoesNotExist:
        messages.error(request, 'Payout transaction not found.')
    except Exception:
        logger.exception('Failed to reject payout. payout_id=%s', payout_id)
        messages.error(request, 'Unable to reject payout right now. Please try again.')
    
    return redirect('admin_payout_management' + '?view=completed')


@staff_member_required
def admin_download_payout_invoice(request, payout_id):
    """
    Download payout invoice PDF
    GET /admin-panel/resell/payouts/<id>/invoice/
    """
    try:
        payout = get_object_or_404(PayoutTransaction, id=payout_id)
        
        # Generate invoice if doesn't exist
        earnings = ResellerEarning.objects.filter(payout_transaction=payout)
        if not earnings.exists():
            messages.error(request, 'No earnings found for this payout.')
            return redirect('admin_payout_management')
        
        invoice_path = PayoutInvoiceGenerator.generate_payout_invoice_pdf(
            payout,
            list(earnings)
        )
        
        if invoice_path and os.path.exists(invoice_path):
            response = FileResponse(
                open(invoice_path, 'rb'),
                as_attachment=True,
                filename=f'payout_invoice_{payout_id}.pdf'
            )
            response['Content-Type'] = 'application/pdf'
            return response
        else:
            messages.error(request, 'Unable to generate invoice. Please try again.')
            return redirect('admin_payout_management')
    
    except Exception:
        logger.exception(f'Failed to download payout invoice {payout_id}')
        messages.error(request, 'Unable to download invoice.')
        return redirect('admin_payout_management')
