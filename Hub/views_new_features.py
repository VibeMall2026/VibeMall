"""
New Feature Views - Added without modifying existing code
Features: Bulk Operations, Activity Logs, Coupons, Low Stock Alerts, Role Management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from Hub.models_new_features import (
    ActivityLog, DiscountCoupon, LowStockAlert, BulkProductImport,
    AdminRole, AdminUserRole, SalesReport, EmailTemplate
)
from Hub.models import Product, Order, OrderItem


# Helper decorator for staff members
def staff_member_required(login_url='login'):
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_staff:
                return redirect(login_url)
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


# ============ ACTIVITY LOGS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_activity_logs(request):
    """View all admin activity logs"""
    logs = ActivityLog.objects.all()
    
    # Filters
    action_filter = request.GET.get('action')
    user_filter = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter:
        logs = logs.filter(admin_user__username__icontains=user_filter)
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'action_choices': ActivityLog.ACTION_CHOICES,
        'total_logs': logs.count(),
    }
    
    return render(request, 'admin_panel/activity_logs.html', context)


def log_activity(user, action, model_name, object_id=None, object_name='', changes=None, request=None):
    """Helper function to log admin activities"""
    ip_address = None
    user_agent = ''
    
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    ActivityLog.objects.create(
        admin_user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_name=object_name,
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ============ DISCOUNT COUPONS ============

@login_required(login_url='login')
@staff_member_required()
def admin_coupons(request):
    """List all discount coupons"""
    coupons = DiscountCoupon.objects.all()
    
    # Filters
    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    
    if status_filter:
        coupons = coupons.filter(status=status_filter)
    if search:
        coupons = coupons.filter(Q(code__icontains=search) | Q(description__icontains=search))
    
    paginator = Paginator(coupons, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': DiscountCoupon.STATUS_CHOICES,
        'total_coupons': coupons.count(),
    }
    
    return render(request, 'admin_panel/coupons.html', context)


@login_required(login_url='login')
@staff_member_required()
def admin_add_coupon(request):
    """Add new discount coupon"""
    if request.method == 'POST':
        try:
            code = request.POST.get('code', '').upper()
            discount_type = request.POST.get('discount_type')
            discount_value = Decimal(request.POST.get('discount_value', 0))
            min_purchase = Decimal(request.POST.get('min_purchase_amount', 0))
            valid_from = request.POST.get('valid_from')
            valid_until = request.POST.get('valid_until')
            max_uses = request.POST.get('max_uses')
            
            coupon = DiscountCoupon.objects.create(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                min_purchase_amount=min_purchase,
                valid_from=valid_from,
                valid_until=valid_until,
                max_uses=int(max_uses) if max_uses else None,
                created_by=request.user,
                description=request.POST.get('description', ''),
            )
            
            log_activity(request.user, 'CREATE', 'DiscountCoupon', coupon.id, coupon.code, request=request)
            messages.success(request, f'Coupon {code} created successfully!')
            return redirect('admin_coupons')
        
        except Exception as e:
            messages.error(request, f'Error creating coupon: {str(e)}')
    
    context = {
        'discount_types': DiscountCoupon.DISCOUNT_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/add_coupon.html', context)


@login_required(login_url='login')
@staff_member_required()
def admin_edit_coupon(request, coupon_id):
    """Edit discount coupon"""
    coupon = get_object_or_404(DiscountCoupon, id=coupon_id)
    
    if request.method == 'POST':
        try:
            old_data = {
                'code': coupon.code,
                'status': coupon.status,
                'discount_value': str(coupon.discount_value),
            }
            
            coupon.code = request.POST.get('code', coupon.code).upper()
            coupon.status = request.POST.get('status', coupon.status)
            coupon.discount_value = Decimal(request.POST.get('discount_value', coupon.discount_value))
            coupon.description = request.POST.get('description', coupon.description)
            coupon.save()
            
            new_data = {
                'code': coupon.code,
                'status': coupon.status,
                'discount_value': str(coupon.discount_value),
            }
            
            log_activity(request.user, 'UPDATE', 'DiscountCoupon', coupon.id, coupon.code, 
                        {'old': old_data, 'new': new_data}, request=request)
            
            messages.success(request, 'Coupon updated successfully!')
            return redirect('admin_coupons')
        
        except Exception as e:
            messages.error(request, f'Error updating coupon: {str(e)}')
    
    context = {
        'coupon': coupon,
        'discount_types': DiscountCoupon.DISCOUNT_TYPE_CHOICES,
        'status_choices': DiscountCoupon.STATUS_CHOICES,
    }
    
    return render(request, 'admin_panel/edit_coupon.html', context)


# ============ LOW STOCK ALERTS ============

@login_required(login_url='login')
@staff_member_required()
def admin_low_stock_alerts(request):
    """View low stock alerts"""
    alerts = LowStockAlert.objects.all()
    
    # Filters
    status_filter = request.GET.get('status')
    
    if status_filter:
        alerts = alerts.filter(status=status_filter)
    
    paginator = Paginator(alerts, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': LowStockAlert.STATUS_CHOICES,
        'pending_count': LowStockAlert.objects.filter(status='PENDING').count(),
    }
    
    return render(request, 'admin_panel/low_stock_alerts.html', context)


def check_and_create_low_stock_alerts(threshold=10):
    """Check products and create low stock alerts"""
    low_stock_products = Product.objects.filter(stock__lte=threshold, is_active=True)
    
    for product in low_stock_products:
        # Check if alert already exists
        existing_alert = LowStockAlert.objects.filter(
            product_id=product.id,
            status__in=['PENDING', 'SENT']
        ).exists()
        
        if not existing_alert:
            LowStockAlert.objects.create(
                product_id=product.id,
                product_name=product.name,
                current_stock=product.stock,
                threshold_stock=threshold,
            )


# ============ BULK OPERATIONS ============

@login_required(login_url='login')
@staff_member_required()
def admin_bulk_import_products(request):
    """Bulk import products from CSV"""
    if request.method == 'POST':
        try:
            csv_file = request.FILES.get('csv_file')
            
            if not csv_file:
                messages.error(request, 'Please select a CSV file')
                return redirect('admin_bulk_import_products')
            
            # Create import record
            import_record = BulkProductImport.objects.create(
                file_name=csv_file.name,
                csv_file=csv_file,
                imported_by=request.user,
            )
            
            # Process CSV
            decoded_file = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(StringIO(decoded_file))
            
            successful = 0
            failed = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    product = Product.objects.create(
                        name=row.get('name', ''),
                        price=Decimal(row.get('price', 0)),
                        stock=int(row.get('stock', 0)),
                        category=row.get('category', ''),
                        description=row.get('description', ''),
                        is_active=row.get('is_active', 'true').lower() == 'true',
                    )
                    successful += 1
                    log_activity(request.user, 'CREATE', 'Product', product.id, product.name, request=request)
                
                except Exception as e:
                    failed += 1
                    errors.append(f"Row {row_num}: {str(e)}")
            
            import_record.total_rows = successful + failed
            import_record.successful_imports = successful
            import_record.failed_imports = failed
            import_record.error_log = errors
            import_record.status = 'COMPLETED'
            import_record.completed_at = timezone.now()
            import_record.save()
            
            messages.success(request, f'Import completed: {successful} successful, {failed} failed')
            return redirect('admin_bulk_import_products')
        
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
    
    imports = BulkProductImport.objects.all()[:10]
    
    context = {
        'recent_imports': imports,
    }
    
    return render(request, 'admin_panel/bulk_import_products.html', context)


@login_required(login_url='login')
@staff_member_required()
def admin_export_products(request):
    """Export products to CSV"""
    products = Product.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Name', 'SKU', 'Price', 'Stock', 'Category', 'Active', 'Rating'])
    
    for product in products:
        writer.writerow([
            product.id,
            product.name,
            product.sku,
            product.price,
            product.stock,
            product.category,
            'Yes' if product.is_active else 'No',
            product.rating,
        ])
    
    log_activity(request.user, 'EXPORT', 'Product', None, f'Exported {products.count()} products', request=request)
    
    return response


# ============ SALES REPORTS ============

@login_required(login_url='login')
@staff_member_required()
def admin_sales_reports(request):
    """View sales reports"""
    reports = SalesReport.objects.all()
    
    # Filters
    report_type = request.GET.get('report_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if report_type:
        reports = reports.filter(report_type=report_type)
    if date_from:
        reports = reports.filter(report_date__gte=date_from)
    if date_to:
        reports = reports.filter(report_date__lte=date_to)
    
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'report_types': SalesReport.REPORT_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/sales_reports.html', context)


def generate_daily_sales_report(report_date=None):
    """Generate daily sales report"""
    if report_date is None:
        report_date = timezone.now().date()
    
    # Get orders for the day
    orders = Order.objects.filter(
        created_at__date=report_date,
        status__in=['COMPLETED', 'SHIPPED']
    )
    
    total_sales = orders.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
    total_orders = orders.count()
    
    # Get top products
    top_products = OrderItem.objects.filter(
        order__created_at__date=report_date
    ).values('product__name').annotate(
        total_qty=Count('id'),
        total_sales=Sum('price')
    ).order_by('-total_sales')[:5]
    
    report = SalesReport.objects.create(
        report_type='DAILY',
        report_date=report_date,
        total_sales=total_sales,
        total_orders=total_orders,
        top_products=list(top_products),
    )
    
    return report


# ============ ROLE MANAGEMENT ============

@login_required(login_url='login')
@staff_member_required()
def admin_roles(request):
    """Manage admin roles"""
    roles = AdminRole.objects.all()
    
    context = {
        'roles': roles,
    }
    
    return render(request, 'admin_panel/roles.html', context)


@login_required(login_url='login')
@staff_member_required()
def admin_add_role(request):
    """Add new admin role"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            permissions = request.POST.getlist('permissions')
            
            role = AdminRole.objects.create(
                name=name,
                description=request.POST.get('description', ''),
                permissions=permissions,
            )
            
            log_activity(request.user, 'CREATE', 'AdminRole', role.id, role.name, request=request)
            messages.success(request, f'Role {name} created successfully!')
            return redirect('admin_roles')
        
        except Exception as e:
            messages.error(request, f'Error creating role: {str(e)}')
    
    context = {
        'permission_choices': AdminRole.PERMISSION_CHOICES,
    }
    
    return render(request, 'admin_panel/add_role.html', context)
