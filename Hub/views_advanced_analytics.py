"""
Advanced Analytics Views - Added without modifying existing code
Features: Sales Comparison, CLV, Abandoned Cart, Traffic Analytics, Conversion Funnel
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum, Count, Avg, F
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from decimal import Decimal
import csv
import json
from datetime import datetime, timedelta
from io import BytesIO
import xlsxwriter

from Hub.models_advanced_analytics import (
    SalesComparison, ProductPerformanceMatrix, CustomerLifetimeValue,
    AbandonedCart, TrafficSource, ConversionFunnel, ScheduledReport
)
from Hub.models import Product, Order, OrderItem
from Hub.views_new_features import staff_member_required, log_activity


# ============ SALES COMPARISON ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_sales_comparison(request):
    """Sales comparison analytics (MOM, YOY, WOW, DOD)"""
    comparison_type = request.GET.get('type', 'MOM')
    
    # Generate comparison if not exists
    generate_sales_comparison(comparison_type)
    
    comparisons = SalesComparison.objects.filter(comparison_type=comparison_type)[:12]
    
    context = {
        'comparisons': comparisons,
        'comparison_type': comparison_type,
        'comparison_types': SalesComparison.COMPARISON_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/sales_comparison.html', context)


def generate_sales_comparison(comparison_type='MOM'):
    """Generate sales comparison data"""
    today = timezone.now().date()
    
    if comparison_type == 'MOM':
        # Current month vs previous month
        current_start = today.replace(day=1)
        current_end = today
        previous_start = (current_start - timedelta(days=1)).replace(day=1)
        previous_end = current_start - timedelta(days=1)
    elif comparison_type == 'YOY':
        # Current year vs previous year
        current_start = today.replace(month=1, day=1)
        current_end = today
        previous_start = current_start.replace(year=current_start.year - 1)
        previous_end = current_end.replace(year=current_end.year - 1)
    elif comparison_type == 'WOW':
        # Current week vs previous week
        days_since_monday = today.weekday()
        current_start = today - timedelta(days=days_since_monday)
        current_end = today
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start - timedelta(days=1)
    else:  # DOD
        # Today vs yesterday
        current_start = today
        current_end = today
        previous_start = today - timedelta(days=1)
        previous_end = today - timedelta(days=1)
    
    # Calculate current period sales
    current_orders = Order.objects.filter(
        created_at__date__range=[current_start, current_end],
        status__in=['COMPLETED', 'SHIPPED', 'DELIVERED']
    )
    current_sales = current_orders.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
    current_count = current_orders.count()
    
    # Calculate previous period sales
    previous_orders = Order.objects.filter(
        created_at__date__range=[previous_start, previous_end],
        status__in=['COMPLETED', 'SHIPPED', 'DELIVERED']
    )
    previous_sales = previous_orders.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
    previous_count = previous_orders.count()
    
    # Calculate growth
    if previous_sales > 0:
        growth_percentage = ((current_sales - previous_sales) / previous_sales) * 100
    else:
        growth_percentage = 100 if current_sales > 0 else 0
    
    if previous_count > 0:
        order_growth = ((current_count - previous_count) / previous_count) * 100
    else:
        order_growth = 100 if current_count > 0 else 0
    
    # Create or update comparison record
    comparison, created = SalesComparison.objects.get_or_create(
        comparison_type=comparison_type,
        current_period_start=current_start,
        current_period_end=current_end,
        defaults={
            'previous_period_start': previous_start,
            'previous_period_end': previous_end,
            'current_sales': current_sales,
            'previous_sales': previous_sales,
            'growth_percentage': growth_percentage,
            'current_orders': current_count,
            'previous_orders': previous_count,
            'order_growth_percentage': order_growth,
        }
    )
    
    return comparison


# ============ PRODUCT PERFORMANCE MATRIX ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_performance(request):
    """Product performance matrix with profit analysis"""
    period = request.GET.get('period', '30')  # days
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=int(period))
    
    # Generate performance data
    generate_product_performance(start_date, end_date)
    
    performance_data = ProductPerformanceMatrix.objects.filter(
        period_start=start_date,
        period_end=end_date
    ).order_by('-total_profit')
    
    paginator = Paginator(performance_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'admin_panel/product_performance.html', context)


def generate_product_performance(start_date, end_date):
    """Generate product performance matrix"""
    # Get all products with sales in the period
    products_with_sales = OrderItem.objects.filter(
        order__created_at__date__range=[start_date, end_date],
        order__status__in=['COMPLETED', 'SHIPPED', 'DELIVERED']
    ).values('product_id').distinct()
    
    for item in products_with_sales:
        product_id = item['product_id']
        
        try:
            from Hub.models import Product
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            continue
        
        # Calculate sales metrics
        order_items = OrderItem.objects.filter(
            product_id=product_id,
            order__created_at__date__range=[start_date, end_date],
            order__status__in=['COMPLETED', 'SHIPPED', 'DELIVERED']
        )
        
        total_sales = order_items.aggregate(Sum('price'))['price__sum'] or Decimal('0')
        total_orders = order_items.values('order_id').distinct().count()
        total_quantity = order_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
        
        # Calculate profit (assuming cost price is 70% of selling price if not available)
        cost_price = getattr(product, 'cost_price', product.price * Decimal('0.7'))
        selling_price = product.price
        profit_per_unit = selling_price - cost_price
        total_profit = profit_per_unit * total_quantity
        
        if selling_price > 0:
            profit_margin = (profit_per_unit / selling_price) * 100
        else:
            profit_margin = 0
        
        # Calculate return rate
        from Hub.models import ReturnRequest
        returns = ReturnRequest.objects.filter(
            order_item__product_id=product_id,
            created_at__date__range=[start_date, end_date]
        ).count()
        
        return_rate = (returns / total_quantity * 100) if total_quantity > 0 else 0
        
        # Get average rating
        from Hub.models import ProductReview
        avg_rating = ProductReview.objects.filter(
            product_id=product_id,
            is_approved=True
        ).aggregate(Avg('rating'))['rating__avg'] or 0
        
        # Create or update performance record
        ProductPerformanceMatrix.objects.update_or_create(
            product_id=product_id,
            period_start=start_date,
            period_end=end_date,
            defaults={
                'product_name': product.name,
                'total_sales': total_sales,
                'total_orders': total_orders,
                'total_quantity_sold': total_quantity,
                'cost_price': cost_price,
                'selling_price': selling_price,
                'profit_margin_percentage': profit_margin,
                'total_profit': total_profit,
                'return_rate': return_rate,
                'average_rating': avg_rating,
            }
        )


# ============ CUSTOMER LIFETIME VALUE ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_customer_clv(request):
    """Customer Lifetime Value analysis"""
    segment = request.GET.get('segment', 'ALL')
    
    # Generate CLV data for all customers
    generate_customer_clv()
    
    clv_data = CustomerLifetimeValue.objects.all()
    
    if segment != 'ALL':
        clv_data = clv_data.filter(clv_segment=segment)
    
    clv_data = clv_data.order_by('-predicted_clv')
    
    paginator = Paginator(clv_data, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary stats
    summary = CustomerLifetimeValue.objects.aggregate(
        total_customers=Count('id'),
        avg_clv=Avg('predicted_clv'),
        total_clv=Sum('predicted_clv'),
        high_value_customers=Count('id', filter=Q(clv_segment='HIGH')),
    )
    
    context = {
        'page_obj': page_obj,
        'segment': segment,
        'segments': CustomerLifetimeValue.CLV_SEGMENT_CHOICES,
        'summary': summary,
    }
    
    return render(request, 'admin_panel/customer_clv.html', context)


def generate_customer_clv():
    """Generate Customer Lifetime Value for all customers"""
    customers_with_orders = Order.objects.values('user_id').distinct()
    
    for customer_data in customers_with_orders:
        user_id = customer_data['user_id']
        
        try:
            customer = User.objects.get(id=user_id)
        except User.DoesNotExist:
            continue
        
        # Get customer orders
        orders = Order.objects.filter(
            user_id=user_id,
            status__in=['COMPLETED', 'SHIPPED', 'DELIVERED']
        ).order_by('created_at')
        
        if not orders.exists():
            continue
        
        # Calculate metrics
        first_order = orders.first()
        last_order = orders.last()
        total_orders = orders.count()
        total_spent = orders.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
        
        # Calculate averages
        avg_order_value = total_spent / total_orders if total_orders > 0 else Decimal('0')
        
        # Calculate customer lifespan
        if first_order and last_order:
            lifespan_days = (last_order.created_at.date() - first_order.created_at.date()).days
            if lifespan_days == 0:
                lifespan_days = 1
        else:
            lifespan_days = 1
        
        # Calculate purchase frequency (orders per day)
        purchase_frequency = total_orders / lifespan_days if lifespan_days > 0 else 0
        
        # Predict CLV (simple formula: AOV * Purchase Frequency * Lifespan * 365)
        predicted_clv = avg_order_value * Decimal(str(purchase_frequency)) * Decimal('365')
        
        # Determine segment
        if predicted_clv >= 50000:
            segment = 'HIGH'
        elif predicted_clv >= 20000:
            segment = 'MEDIUM'
        elif predicted_clv >= 5000:
            segment = 'LOW'
        elif total_orders == 1:
            segment = 'NEW'
        else:
            segment = 'AT_RISK'
        
        # Calculate days since last order
        days_since_last = (timezone.now().date() - last_order.created_at.date()).days
        
        # Calculate churn probability (simple rule-based)
        if days_since_last > 90:
            churn_probability = min(90, days_since_last - 90)
        else:
            churn_probability = 0
        
        # Create or update CLV record
        CustomerLifetimeValue.objects.update_or_create(
            customer=customer,
            defaults={
                'first_order_date': first_order.created_at.date(),
                'last_order_date': last_order.created_at.date(),
                'total_orders': total_orders,
                'total_spent': total_spent,
                'average_order_value': avg_order_value,
                'purchase_frequency': purchase_frequency,
                'customer_lifespan_days': lifespan_days,
                'predicted_clv': predicted_clv,
                'clv_segment': segment,
                'days_since_last_order': days_since_last,
                'is_active': days_since_last <= 60,
                'churn_probability': churn_probability,
            }
        )


# ============ ABANDONED CART TRACKING ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_abandoned_carts(request):
    """Abandoned cart tracking and recovery"""
    status = request.GET.get('status', 'ABANDONED')
    
    carts = AbandonedCart.objects.filter(status=status).order_by('-abandoned_at')
    
    paginator = Paginator(carts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary
    summary = AbandonedCart.objects.aggregate(
        total_abandoned=Count('id', filter=Q(status='ABANDONED')),
        total_value=Sum('total_value', filter=Q(status='ABANDONED')),
        recovered_count=Count('id', filter=Q(status='RECOVERED')),
        recovered_value=Sum('total_value', filter=Q(status='RECOVERED')),
    )
    
    if summary['total_abandoned'] and summary['recovered_count']:
        recovery_rate = (summary['recovered_count'] / summary['total_abandoned']) * 100
    else:
        recovery_rate = 0
    
    summary['recovery_rate'] = recovery_rate
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'status_choices': AbandonedCart.STATUS_CHOICES,
        'summary': summary,
    }
    
    return render(request, 'admin_panel/abandoned_carts.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_http_methods(["POST"])
def send_recovery_email(request, cart_id):
    """Send abandoned cart recovery email"""
    try:
        cart = get_object_or_404(AbandonedCart, id=cart_id)
        
        # Update email tracking
        cart.recovery_emails_sent += 1
        cart.last_email_sent = timezone.now()
        cart.save()
        
        # TODO: Implement actual email sending
        # send_abandoned_cart_email(cart)
        
        log_activity(request.user, 'UPDATE', 'AbandonedCart', cart.id, 
                    f'Recovery email sent to {cart.customer.email}', request=request)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============ TRAFFIC SOURCE ANALYTICS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_traffic_analytics(request):
    """Traffic source analytics"""
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = timezone.now().date().strftime('%Y-%m-%d')
    
    traffic_data = TrafficSource.objects.filter(
        date__range=[date_from, date_to]
    ).order_by('-date', 'source_type')
    
    # Aggregate by source type
    source_summary = TrafficSource.objects.filter(
        date__range=[date_from, date_to]
    ).values('source_type').annotate(
        total_visitors=Sum('visitors'),
        total_sessions=Sum('sessions'),
        total_conversions=Sum('conversions'),
        total_revenue=Sum('revenue'),
        avg_conversion_rate=Avg('conversion_rate'),
    ).order_by('-total_revenue')
    
    paginator = Paginator(traffic_data, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'source_summary': source_summary,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_panel/traffic_analytics.html', context)


# ============ CONVERSION FUNNEL ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_conversion_funnel(request):
    """Conversion funnel visualization"""
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=7)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = timezone.now().date().strftime('%Y-%m-%d')
    
    # Get funnel data
    funnel_data = ConversionFunnel.objects.filter(
        date__range=[date_from, date_to]
    ).values('funnel_step').annotate(
        total_count=Sum('count'),
        avg_conversion_rate=Avg('conversion_rate_from_previous'),
    ).order_by('funnel_step')
    
    # Calculate funnel metrics
    funnel_steps = []
    previous_count = None
    
    for step in funnel_data:
        step_data = {
            'step': step['funnel_step'],
            'step_display': dict(ConversionFunnel.FUNNEL_STEP_CHOICES)[step['funnel_step']],
            'count': step['total_count'],
            'conversion_rate': step['avg_conversion_rate'],
        }
        
        if previous_count:
            step_data['drop_off'] = previous_count - step['total_count']
            step_data['drop_off_rate'] = ((previous_count - step['total_count']) / previous_count * 100) if previous_count > 0 else 0
        
        funnel_steps.append(step_data)
        previous_count = step['total_count']
    
    context = {
        'funnel_steps': funnel_steps,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_panel/conversion_funnel.html', context)


# ============ SCHEDULED REPORTS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_scheduled_reports(request):
    """Manage scheduled email reports"""
    reports = ScheduledReport.objects.all().order_by('name')
    
    context = {
        'reports': reports,
    }
    
    return render(request, 'admin_panel/scheduled_reports.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_add_scheduled_report(request):
    """Add new scheduled report"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            report_type = request.POST.get('report_type')
            frequency = request.POST.get('frequency')
            send_time = request.POST.get('send_time')
            email_recipients = request.POST.get('email_recipients', '').split(',')
            
            # Clean email list
            email_recipients = [email.strip() for email in email_recipients if email.strip()]
            
            report = ScheduledReport.objects.create(
                name=name,
                report_type=report_type,
                frequency=frequency,
                send_time=send_time,
                email_recipients=email_recipients,
                include_charts=request.POST.get('include_charts') == 'on',
                export_format=request.POST.get('export_format', 'PDF'),
                created_by=request.user,
            )
            
            log_activity(request.user, 'CREATE', 'ScheduledReport', report.id, report.name, request=request)
            messages.success(request, f'Scheduled report "{name}" created successfully!')
            return redirect('admin_scheduled_reports')
        
        except Exception as e:
            messages.error(request, f'Error creating scheduled report: {str(e)}')
    
    context = {
        'report_types': ScheduledReport.REPORT_TYPE_CHOICES,
        'frequencies': ScheduledReport.FREQUENCY_CHOICES,
    }
    
    return render(request, 'admin_panel/add_scheduled_report.html', context)


# ============ EXPORT FUNCTIONS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def export_analytics_excel(request):
    """Export analytics data to Excel"""
    report_type = request.GET.get('type', 'sales_comparison')
    
    # Create Excel file
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    if report_type == 'sales_comparison':
        worksheet = workbook.add_worksheet('Sales Comparison')
        
        # Headers
        headers = ['Period', 'Current Sales', 'Previous Sales', 'Growth %', 'Current Orders', 'Previous Orders', 'Order Growth %']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Data
        comparisons = SalesComparison.objects.all()[:12]
        for row, comparison in enumerate(comparisons, 1):
            worksheet.write(row, 0, f"{comparison.current_period_start} to {comparison.current_period_end}")
            worksheet.write(row, 1, float(comparison.current_sales))
            worksheet.write(row, 2, float(comparison.previous_sales))
            worksheet.write(row, 3, float(comparison.growth_percentage))
            worksheet.write(row, 4, comparison.current_orders)
            worksheet.write(row, 5, comparison.previous_orders)
            worksheet.write(row, 6, float(comparison.order_growth_percentage))
    
    elif report_type == 'product_performance':
        worksheet = workbook.add_worksheet('Product Performance')
        
        # Headers
        headers = ['Product', 'Total Sales', 'Total Orders', 'Quantity Sold', 'Profit Margin %', 'Total Profit', 'Return Rate %']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Data
        performance_data = ProductPerformanceMatrix.objects.all()[:100]
        for row, product in enumerate(performance_data, 1):
            worksheet.write(row, 0, product.product_name)
            worksheet.write(row, 1, float(product.total_sales))
            worksheet.write(row, 2, product.total_orders)
            worksheet.write(row, 3, product.total_quantity_sold)
            worksheet.write(row, 4, float(product.profit_margin_percentage))
            worksheet.write(row, 5, float(product.total_profit))
            worksheet.write(row, 6, float(product.return_rate))
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{report_type}_analytics.xlsx"'
    
    log_activity(request.user, 'EXPORT', 'Analytics', None, f'Exported {report_type} analytics', request=request)
    
    return response