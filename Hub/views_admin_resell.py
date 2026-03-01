"""
Admin Panel Views for Resell Management

This module contains custom admin panel views for managing resell operations:
- Resell orders view with filters
- Reseller analytics view
- Resell reports view
- Reseller management view
- Payout management view
"""

from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.core.paginator import Paginator
import csv

from .models import (
    Order,
    OrderItem,
    ResellLink,
    ResellerProfile,
    ResellerEarning,
    PayoutTransaction,
    User
)


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
    
    # Base queryset
    orders = Order.objects.filter(is_resell=True).select_related(
        'user', 'reseller', 'resell_link'
    ).prefetch_related('items').order_by('-created_at')
    
    # Apply filters
    if reseller_id:
        orders = orders.filter(reseller_id=reseller_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire end date
            date_to_obj = date_to_obj + timedelta(days=1)
            orders = orders.filter(created_at__lt=date_to_obj)
        except ValueError:
            pass
    
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
    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_margin = orders.aggregate(total=Sum('total_margin'))['total'] or Decimal('0.00')
    total_base = orders.aggregate(total=Sum('base_amount'))['total'] or Decimal('0.00')
    
    # Pagination
    paginator = Paginator(orders, 25)
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
        orders = Order.objects.filter(reseller=reseller, is_resell=True)
        
        # Calculate metrics
        total_orders = orders.count()
        total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        total_margin = orders.aggregate(total=Sum('total_margin'))['total'] or Decimal('0.00')
        
        # Get resell links
        links = ResellLink.objects.filter(reseller=reseller)
        total_links = links.count()
        active_links = links.filter(is_active=True).count()
        total_views = links.aggregate(total=Sum('views_count'))['total'] or 0
        
        # Calculate conversion rate
        conversion_rate = (total_orders / total_views * 100) if total_views > 0 else 0
        
        # Get earnings breakdown
        earnings = ResellerEarning.objects.filter(reseller=reseller)
        pending_earnings = earnings.filter(status='PENDING').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
        confirmed_earnings = earnings.filter(status='CONFIRMED').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
        paid_earnings = earnings.filter(status='PAID').aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
        
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
        resellers = ResellerProfile.objects.filter(
            is_reseller_enabled=True
        ).select_related('user').order_by('-total_earnings')
        
        # Calculate overall metrics
        total_resellers = resellers.count()
        total_orders = Order.objects.filter(is_resell=True).count()
        total_revenue = Order.objects.filter(is_resell=True).aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        total_margin = Order.objects.filter(is_resell=True).aggregate(
            total=Sum('total_margin')
        )['total'] or Decimal('0.00')
        
        # Get top performers
        top_resellers = resellers[:10]
        
        # Pagination
        paginator = Paginator(resellers, 25)
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
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        messages.error(request, 'Invalid date format.')
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
    
    # Base queryset
    resellers = ResellerProfile.objects.select_related('user').order_by('-created_at')
    
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
    paginator = Paginator(resellers, 25)
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
    }
    
    return render(request, 'admin_panel/resell/resellers.html', context)


@staff_member_required
def admin_toggle_reseller_status(request, reseller_id):
    """
    Toggle reseller enabled/disabled status
    POST /admin-panel/resell/resellers/<id>/toggle/
    """
    if request.method == 'POST':
        profile = get_object_or_404(ResellerProfile, id=reseller_id)
        profile.is_reseller_enabled = not profile.is_reseller_enabled
        profile.save()
        
        status = 'enabled' if profile.is_reseller_enabled else 'disabled'
        messages.success(request, f'Reseller {profile.user.username} has been {status}.')
    
    return redirect('admin_reseller_management')


# ============================================
# ADMIN PAYOUT MANAGEMENT VIEW
# ============================================

@staff_member_required
def admin_payout_management(request):
    """
    Admin payout management view
    GET /admin-panel/resell/payouts/
    
    View and manage payout transactions
    """
    status_filter = request.GET.get('status', '')
    reseller_id = request.GET.get('reseller', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    payouts = PayoutTransaction.objects.select_related('reseller').order_by('-initiated_at')
    
    # Apply filters
    if status_filter:
        payouts = payouts.filter(status=status_filter)
    
    if reseller_id:
        payouts = payouts.filter(reseller_id=reseller_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            payouts = payouts.filter(initiated_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            payouts = payouts.filter(initiated_at__lt=date_to_obj)
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(payouts, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary
    total_payouts = PayoutTransaction.objects.count()
    initiated_payouts = PayoutTransaction.objects.filter(status='INITIATED').count()
    completed_payouts = PayoutTransaction.objects.filter(status='COMPLETED').count()
    failed_payouts = PayoutTransaction.objects.filter(status='FAILED').count()
    total_amount = PayoutTransaction.objects.filter(status='COMPLETED').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Get all resellers for filter
    resellers = User.objects.filter(
        reseller_profile__is_reseller_enabled=True
    ).order_by('username')
    
    context = {
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
    }
    
    return render(request, 'admin_panel/resell/payouts.html', context)


@staff_member_required
def admin_approve_payout(request, payout_id):
    """
    Approve a payout transaction
    POST /admin-panel/resell/payouts/<id>/approve/
    """
    if request.method == 'POST':
        payout = get_object_or_404(PayoutTransaction, id=payout_id)
        
        if payout.status == 'INITIATED':
            payout.status = 'COMPLETED'
            payout.completed_at = timezone.now()
            payout.save()
            
            # Update associated earnings to PAID
            ResellerEarning.objects.filter(
                reseller=payout.reseller,
                status='CONFIRMED',
                payout_transaction__isnull=True
            ).update(
                status='PAID',
                paid_at=timezone.now(),
                payout_transaction=payout
            )
            
            messages.success(request, f'Payout of ₹{payout.amount} approved successfully.')
        else:
            messages.error(request, 'Payout cannot be approved in its current status.')
    
    return redirect('admin_payout_management')


@staff_member_required
def admin_reject_payout(request, payout_id):
    """
    Reject a payout transaction and refund balance
    POST /admin-panel/resell/payouts/<id>/reject/
    """
    if request.method == 'POST':
        payout = get_object_or_404(PayoutTransaction, id=payout_id)
        
        if payout.status == 'INITIATED':
            payout.status = 'FAILED'
            payout.admin_notes = request.POST.get('reason', 'Rejected by admin')
            payout.save()
            
            # Refund to reseller balance
            profile = payout.reseller.reseller_profile
            profile.available_balance += payout.amount
            profile.save()
            
            messages.success(request, f'Payout rejected and ₹{payout.amount} refunded to reseller balance.')
        else:
            messages.error(request, 'Payout cannot be rejected in its current status.')
    
    return redirect('admin_payout_management')
