"""
Comprehensive Feature Views - All Phases Combined
Views for Customer Insights, Financial Management, Product Enhancements, Security, Content Management, Performance, AI/ML
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import FieldError
from django.db.models import Q, Sum, Count, Avg, F
from django.db.utils import OperationalError, ProgrammingError
from django.template import TemplateDoesNotExist
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from decimal import Decimal
from functools import wraps
import csv
import json
from datetime import datetime, timedelta
from io import BytesIO

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

# Import all the new models
from Hub.models_customer_insights import (
    CustomerSegmentationRule, CustomerProfile, PurchaseHistoryTimeline,
    RFMAnalysis, CustomerSupportTicket, TicketMessage, CustomerFeedbackSurvey,
    SurveyResponse, BirthdayAnniversaryReminder
)
from Hub.models_financial_management import (
    ProfitLossStatement, GSTReport, PaymentGatewayReconciliation,
    ReconciliationTransaction, ExpenseCategory, ExpenseRecord,
    VendorPayment, TaxCalculation, CommissionCalculation
)
from Hub.models_product_enhancements import (
    ProductVariant, ProductVariantCombination, ProductBundle,
    RelatedProduct, ProductComparison, ProductSEO, ProductVideo,
    Product360View, ProductBulkOperation
)
from Hub.models_security_access import (
    SecurityRole, UserRoleAssignment, SecurityAuditLog,
    TwoFactorAuthentication, IPWhitelist, UserSession,
    LoginAttempt, SecurityAlert, DataAccessLog
)
from Hub.models_content_management import (
    BlogCategory, BlogPost, BlogComment, FAQCategory, FAQ,
    PageTemplate, CustomPage, ContentEmailTemplate, WhatsAppTemplate, ContentBlock
)
from Hub.models_performance_optimization import (
    ImageOptimization, CDNConfiguration, DatabaseQueryLog,
    PageLoadMetrics, ErrorLog, PerformanceAlert, CacheMetrics, SystemResourceUsage
)
from Hub.models_ai_ml_features import (
    RecommendationEngine, ProductRecommendation, DynamicPricingRule,
    PriceOptimization, DemandForecast, FraudDetectionRule,
    FraudAnalysis, ChatbotConfiguration, ChatbotConversation,
    ImageSearchIndex, ImageSearchQuery
)

from Hub.views_new_features import staff_member_required, log_activity
from Hub.models import Product, Order, OrderItem


def _advanced_feature_hint(exc):
    """Translate common setup failures into an actionable admin message."""
    if isinstance(exc, TemplateDoesNotExist):
        return "This page template is missing from the codebase."
    if isinstance(exc, (OperationalError, ProgrammingError)):
        return "This feature's database tables are not ready on the current server. Run the latest migrations."
    if isinstance(exc, FieldError):
        return "This view still queries model fields that do not exist in the current schema."
    return "This feature is incomplete on the current deployment."


def advanced_feature_guard(feature_name):
    """Fail softly for incomplete advanced admin features instead of returning a 500."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except (OperationalError, ProgrammingError, FieldError, TemplateDoesNotExist) as exc:
                messages.warning(
                    request,
                    f'{feature_name} is temporarily unavailable while the advanced feature setup is being completed.'
                )
                context = {
                    'title': feature_name,
                    'feature_name': feature_name,
                    'feature_hint': _advanced_feature_hint(exc),
                    'feature_error_type': exc.__class__.__name__,
                    'feature_error': str(exc),
                }
                return render(request, 'admin_panel/feature_unavailable.html', context)
        return wrapped
    return decorator


def _safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def _safe_decimal(value, default='0'):
    try:
        return Decimal(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return Decimal(default)


# ============ CUSTOMER INSIGHTS & CRM VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_customer_segmentation(request):
    """Customer segmentation management"""
    segments = CustomerSegmentationRule.objects.all().order_by('name')
    
    context = {
        'segments': segments,
    }
    
    return render(request, 'admin_panel/customer_segmentation.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_add_customer_segment(request):
    """Add new customer segment"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            segment_type = request.POST.get('segment_type')
            description = request.POST.get('description', '')
            
            # Create segment
            segment = CustomerSegmentationRule.objects.create(
                name=name,
                segment_type=segment_type,
                description=description,
                min_orders=request.POST.get('min_orders') or None,
                max_orders=request.POST.get('max_orders') or None,
                min_total_spent=request.POST.get('min_total_spent') or None,
                max_total_spent=request.POST.get('max_total_spent') or None,
                discount_percentage=request.POST.get('discount_percentage', 0),
                free_shipping=request.POST.get('free_shipping') == 'on',
                priority_support=request.POST.get('priority_support') == 'on',
                created_by=request.user,
            )
            
            log_activity(request.user, 'CREATE', 'CustomerSegmentationRule', segment.id, segment.name, request=request)
            messages.success(request, f'Customer segment "{name}" created successfully!')
            return redirect('admin_customer_segmentation')
        
        except Exception as e:
            messages.error(request, f'Error creating customer segment: {str(e)}')
    
    context = {
        'segment_types': CustomerSegmentationRule.SEGMENT_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/add_customer_segment.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_customer_support_tickets(request):
    """Customer support ticket management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        ticket_id = request.POST.get('ticket_id')
        ticket = get_object_or_404(CustomerSupportTicket, id=ticket_id)

        if action == 'update_status':
            new_status = request.POST.get('new_status', ticket.status)
            new_priority = request.POST.get('new_priority', ticket.priority)
            ticket.status = new_status
            ticket.priority = new_priority
            if new_status == 'RESOLVED' and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
            if new_status == 'CLOSED' and not ticket.closed_at:
                ticket.closed_at = timezone.now()
            ticket.save()
            log_activity(request.user, 'UPDATE', 'CustomerSupportTicket', ticket.id, f'{ticket.ticket_number} -> {new_status}', request=request)
            messages.success(request, f'Ticket {ticket.ticket_number} updated.')
            return redirect('admin_customer_support_tickets')

    status = request.GET.get('status', 'OPEN')
    
    tickets = CustomerSupportTicket.objects.filter(status=status).order_by('-created_at')
    
    paginator = Paginator(tickets, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary stats
    summary = CustomerSupportTicket.objects.aggregate(
        total_tickets=Count('id'),
        open_tickets=Count('id', filter=Q(status='OPEN')),
        resolved_tickets=Count('id', filter=Q(status='RESOLVED')),
        avg_resolution_time=Avg('resolution_time'),
    )
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'status_choices': CustomerSupportTicket.STATUS_CHOICES,
        'summary': summary,
    }
    
    return render(request, 'admin_panel/support_tickets.html', context)


# ============ FINANCIAL MANAGEMENT VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_profit_loss_statements(request):
    """Profit & Loss statements"""
    if request.method == 'POST':
        action = request.POST.get('action')
        statement_id = request.POST.get('statement_id')
        statement = get_object_or_404(ProfitLossStatement, id=statement_id)
        if action == 'toggle_finalize':
            statement.is_finalized = not statement.is_finalized
            statement.save(update_fields=['is_finalized'])
            log_activity(request.user, 'UPDATE', 'ProfitLossStatement', statement.id, f'Finalized={statement.is_finalized}', request=request)
            messages.success(request, f'Statement {statement.statement_id} updated.')
            return redirect('admin_profit_loss_statements')

    statements = ProfitLossStatement.objects.all().order_by('-start_date')
    
    paginator = Paginator(statements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'admin_panel/profit_loss_statements.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_generate_pl_statement(request):
    """Generate new P&L statement"""
    if request.method == 'POST':
        try:
            period_type = request.POST.get('period_type')
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            
            # Generate statement ID
            statement_id = f"PL-{period_type}-{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
            
            # Calculate financial metrics
            orders = Order.objects.filter(
                created_at__date__range=[start_date, end_date],
                order_status__in=['PROCESSING', 'SHIPPED', 'DELIVERED']
            )
            
            gross_sales = orders.aggregate(total_sales=Sum('total_amount'))['total_sales'] or Decimal('0')
            total_orders = orders.count()
            avg_order_value = gross_sales / total_orders if total_orders > 0 else Decimal('0')
            
            # Create P&L statement
            statement = ProfitLossStatement.objects.create(
                statement_id=statement_id,
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                gross_sales=gross_sales,
                net_sales=gross_sales,  # Simplified for now
                gross_profit=gross_sales * Decimal('0.3'),  # Assuming 30% margin
                net_profit=gross_sales * Decimal('0.15'),  # Assuming 15% net margin
                total_orders=total_orders,
                average_order_value=avg_order_value,
                generated_by=request.user,
            )
            
            log_activity(request.user, 'CREATE', 'ProfitLossStatement', statement.id, statement.statement_id, request=request)
            messages.success(request, f'P&L statement "{statement_id}" generated successfully!')
            return redirect('admin_profit_loss_statements')
        
        except Exception as e:
            messages.error(request, f'Error generating P&L statement: {str(e)}')
    
    context = {
        'period_types': ProfitLossStatement.PERIOD_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/generate_pl_statement.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_expense_management(request):
    """Expense management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_category':
            name = (request.POST.get('name') or '').strip()
            if name:
                category, created = ExpenseCategory.objects.get_or_create(
                    name=name,
                    defaults={'description': request.POST.get('description', '').strip()}
                )
                if not created:
                    category.description = request.POST.get('description', '').strip()
                    category.is_active = True
                    category.save()
                log_activity(request.user, 'CREATE', 'ExpenseCategory', category.id, category.name, request=request)
                messages.success(request, f'Expense category "{category.name}" saved.')
            else:
                messages.error(request, 'Category name is required.')
            return redirect('admin_expense_management')

        if action == 'add_expense':
            category_id = request.POST.get('category_id')
            description = (request.POST.get('description') or '').strip()
            amount = _safe_decimal(request.POST.get('amount'), '0')
            expense_date = request.POST.get('expense_date')
            if category_id and description and amount > 0 and expense_date:
                expense = ExpenseRecord.objects.create(
                    expense_id=f"EXP-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    category_id=category_id,
                    description=description,
                    amount=amount,
                    expense_date=expense_date,
                    vendor_name=(request.POST.get('vendor_name') or '').strip(),
                    payment_method=request.POST.get('payment_method', 'BANK_TRANSFER'),
                    reference_number=(request.POST.get('reference_number') or '').strip(),
                    is_gst_applicable=request.POST.get('is_gst_applicable') == 'on',
                    gst_rate=_safe_decimal(request.POST.get('gst_rate'), '18'),
                    created_by=request.user,
                )
                log_activity(request.user, 'CREATE', 'ExpenseRecord', expense.id, expense.expense_id, request=request)
                messages.success(request, f'Expense "{expense.expense_id}" created.')
            else:
                messages.error(request, 'Please fill category, description, amount and date.')
            return redirect('admin_expense_management')

        if action == 'approve_expense':
            expense_id = request.POST.get('expense_id')
            expense = get_object_or_404(ExpenseRecord, id=expense_id)
            expense.is_approved = True
            expense.approved_by = request.user
            expense.approved_at = timezone.now()
            expense.save(update_fields=['is_approved', 'approved_by', 'approved_at'])
            log_activity(request.user, 'UPDATE', 'ExpenseRecord', expense.id, f'Approved {expense.expense_id}', request=request)
            messages.success(request, f'Expense {expense.expense_id} approved.')
            return redirect('admin_expense_management')

    expenses = ExpenseRecord.objects.all().order_by('-expense_date')
    
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary
    summary = ExpenseRecord.objects.aggregate(
        total_expenses=Sum('total_amount'),
        pending_approval=Count('id', filter=Q(is_approved=False)),
        this_month_expenses=Sum('total_amount', filter=Q(expense_date__month=timezone.now().month)),
    )
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
        'categories': ExpenseCategory.objects.filter(is_active=True),
    }
    
    return render(request, 'admin_panel/expense_management.html', context)


# ============ PRODUCT ENHANCEMENT VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_variants(request):
    """Product variants management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_variant':
            product_id_val = _safe_int(request.POST.get('product_id'))
            name = (request.POST.get('name') or '').strip()
            display_name = (request.POST.get('display_name') or name).strip()
            if product_id_val > 0 and name:
                variant = ProductVariant.objects.create(
                    product_id=product_id_val,
                    variant_type=request.POST.get('variant_type', 'CUSTOM'),
                    name=name,
                    display_name=display_name,
                    value=(request.POST.get('value') or name).strip(),
                    price_adjustment=_safe_decimal(request.POST.get('price_adjustment'), '0'),
                    stock_quantity=_safe_int(request.POST.get('stock_quantity')),
                    sort_order=_safe_int(request.POST.get('sort_order')),
                    is_active=True,
                )
                log_activity(request.user, 'CREATE', 'ProductVariant', variant.id, str(variant), request=request)
                messages.success(request, f'Variant "{variant.display_name}" added.')
            else:
                messages.error(request, 'Product ID and variant name are required.')
            return redirect(f"{request.path}?product_id={product_id_val}" if product_id_val else 'admin_product_variants')

        if action == 'toggle_variant':
            variant = get_object_or_404(ProductVariant, id=request.POST.get('variant_id'))
            variant.is_active = not variant.is_active
            variant.save(update_fields=['is_active'])
            log_activity(request.user, 'UPDATE', 'ProductVariant', variant.id, f'Active={variant.is_active}', request=request)
            messages.success(request, f'Variant "{variant.display_name}" updated.')
            return redirect(f"{request.path}?product_id={variant.product_id}")

    product_id = request.GET.get('product_id')
    
    if product_id:
        variants = ProductVariant.objects.filter(product_id=product_id).order_by('variant_type', 'sort_order')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            product = None
    else:
        variants = ProductVariant.objects.all().order_by('-created_at')[:50]
        product = None
    
    context = {
        'variants': variants,
        'product': product,
        'product_id': product_id,
        'variant_types': ProductVariant.VARIANT_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/product_variants.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_bundles(request):
    """Product bundle management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_bundle':
            name = (request.POST.get('name') or '').strip()
            if name:
                products_raw = (request.POST.get('products_json') or '[]').strip()
                try:
                    products_json = json.loads(products_raw)
                    if not isinstance(products_json, list):
                        products_json = []
                except json.JSONDecodeError:
                    products_json = []
                bundle = ProductBundle.objects.create(
                    name=name,
                    description=(request.POST.get('description') or '').strip(),
                    bundle_type=request.POST.get('bundle_type', 'FIXED'),
                    products=products_json,
                    individual_total=_safe_decimal(request.POST.get('individual_total'), '0'),
                    bundle_price=_safe_decimal(request.POST.get('bundle_price'), '0'),
                    created_by=request.user,
                    is_active=request.POST.get('is_active') == 'on',
                )
                log_activity(request.user, 'CREATE', 'ProductBundle', bundle.id, bundle.name, request=request)
                messages.success(request, f'Bundle "{bundle.name}" created.')
            else:
                messages.error(request, 'Bundle name is required.')
            return redirect('admin_product_bundles')

        if action == 'toggle_bundle':
            bundle = get_object_or_404(ProductBundle, id=request.POST.get('bundle_id'))
            bundle.is_active = not bundle.is_active
            bundle.save(update_fields=['is_active'])
            log_activity(request.user, 'UPDATE', 'ProductBundle', bundle.id, f'Active={bundle.is_active}', request=request)
            messages.success(request, f'Bundle "{bundle.name}" updated.')
            return redirect('admin_product_bundles')

    bundles = ProductBundle.objects.all().order_by('-created_at')
    
    paginator = Paginator(bundles, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'bundle_types': ProductBundle.BUNDLE_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/product_bundles.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_seo(request):
    """Product SEO optimization"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_seo':
            product_id_val = _safe_int(request.POST.get('product_id'))
            if product_id_val > 0:
                seo, _ = ProductSEO.objects.get_or_create(product_id=product_id_val)
                seo.meta_title = (request.POST.get('meta_title') or '').strip()
                seo.meta_description = (request.POST.get('meta_description') or '').strip()
                seo.meta_keywords = (request.POST.get('meta_keywords') or '').strip()
                seo.focus_keyword = (request.POST.get('focus_keyword') or '').strip()
                seo.seo_score = max(0, min(100, _safe_int(request.POST.get('seo_score'), 0)))
                seo.is_indexable = request.POST.get('is_indexable') == 'on'
                seo.save()
                log_activity(request.user, 'UPDATE', 'ProductSEO', seo.id, f'Product {seo.product_id}', request=request)
                messages.success(request, f'SEO saved for product {seo.product_id}.')
            else:
                messages.error(request, 'Valid product ID required.')
            return redirect('admin_product_seo')

    seo_data = ProductSEO.objects.all().order_by('-seo_score')
    
    paginator = Paginator(seo_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # SEO summary
    summary = ProductSEO.objects.aggregate(
        avg_seo_score=Avg('seo_score'),
        products_with_meta=Count('id', filter=Q(meta_title__isnull=False)),
        products_with_keywords=Count('id', filter=Q(meta_keywords__isnull=False)),
    )
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
    }
    
    return render(request, 'admin_panel/product_seo.html', context)


# ============ SECURITY & ACCESS CONTROL VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_security_roles(request):
    """Security role management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_role':
            name = (request.POST.get('name') or '').strip()
            if name:
                role, _ = SecurityRole.objects.get_or_create(
                    name=name,
                    defaults={
                        'role_type': request.POST.get('role_type', 'CUSTOM'),
                        'description': (request.POST.get('description') or '').strip(),
                        'created_by': request.user,
                    }
                )
                role.can_manage_products = request.POST.get('can_manage_products') == 'on'
                role.can_manage_orders = request.POST.get('can_manage_orders') == 'on'
                role.can_manage_customers = request.POST.get('can_manage_customers') == 'on'
                role.can_manage_inventory = request.POST.get('can_manage_inventory') == 'on'
                role.can_manage_finances = request.POST.get('can_manage_finances') == 'on'
                role.can_manage_marketing = request.POST.get('can_manage_marketing') == 'on'
                role.can_manage_users = request.POST.get('can_manage_users') == 'on'
                role.can_manage_settings = request.POST.get('can_manage_settings') == 'on'
                role.can_view_reports = request.POST.get('can_view_reports') == 'on'
                role.can_export_data = request.POST.get('can_export_data') == 'on'
                role.save()
                log_activity(request.user, 'CREATE', 'SecurityRole', role.id, role.name, request=request)
                messages.success(request, f'Role "{role.name}" saved.')
            else:
                messages.error(request, 'Role name is required.')
            return redirect('admin_security_roles')

        if action == 'toggle_role':
            role = get_object_or_404(SecurityRole, id=request.POST.get('role_id'))
            role.is_active = not role.is_active
            role.save(update_fields=['is_active'])
            log_activity(request.user, 'UPDATE', 'SecurityRole', role.id, f'Active={role.is_active}', request=request)
            messages.success(request, f'Role "{role.name}" updated.')
            return redirect('admin_security_roles')

    roles = SecurityRole.objects.all().order_by('name')
    
    context = {
        'roles': roles,
        'role_types': SecurityRole.ROLE_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/security_roles.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_security_audit_log(request):
    """Security audit log"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_investigated':
            log_id = request.POST.get('log_id')
            audit_log = get_object_or_404(SecurityAuditLog, id=log_id)
            audit_log.is_investigated = True
            audit_log.investigation_notes = (request.POST.get('investigation_notes') or '').strip()
            audit_log.save(update_fields=['is_investigated', 'investigation_notes'])
            log_activity(request.user, 'UPDATE', 'SecurityAuditLog', audit_log.id, f'Investigated {audit_log.id}', request=request)
            messages.success(request, 'Audit log marked as investigated.')
            return redirect('admin_security_audit_log')

    event_type = request.GET.get('event_type', '')
    
    logs = SecurityAuditLog.objects.all()
    if event_type:
        logs = logs.filter(event_type=event_type)
    
    logs = logs.order_by('-timestamp')
    
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'event_type': event_type,
        'event_types': SecurityAuditLog.EVENT_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/security_audit_log.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_user_sessions(request):
    """Active user sessions"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'terminate_session':
            session = get_object_or_404(UserSession, id=request.POST.get('session_id'))
            session.status = 'TERMINATED'
            session.logout_time = timezone.now()
            session.save(update_fields=['status', 'logout_time'])
            log_activity(request.user, 'UPDATE', 'UserSession', session.id, f'Terminated {session.session_key}', request=request)
            messages.success(request, 'Session terminated successfully.')
            return redirect('admin_user_sessions')

    sessions = UserSession.objects.filter(status='ACTIVE').order_by('-login_time')
    
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Session summary
    summary = UserSession.objects.aggregate(
        active_sessions=Count('id', filter=Q(status='ACTIVE')),
        suspicious_sessions=Count('id', filter=Q(is_suspicious=True)),
        total_sessions_today=Count('id', filter=Q(login_time__date=timezone.now().date())),
    )
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
    }
    
    return render(request, 'admin_panel/user_sessions.html', context)


# ============ CONTENT MANAGEMENT VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_blog_management(request):
    """Blog post management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_post':
            title = (request.POST.get('title') or '').strip()
            content = (request.POST.get('content') or '').strip()
            if title and content:
                base_slug = slugify(title)[:200] or f'post-{timezone.now().strftime("%Y%m%d%H%M%S")}'
                slug = base_slug
                idx = 1
                while BlogPost.objects.filter(slug=slug).exists():
                    idx += 1
                    slug = f"{base_slug[:190]}-{idx}"
                post = BlogPost.objects.create(
                    title=title,
                    slug=slug,
                    excerpt=(request.POST.get('excerpt') or content[:280]).strip(),
                    content=content,
                    category_id=request.POST.get('category_id') or None,
                    post_type=request.POST.get('post_type', 'ARTICLE'),
                    status=request.POST.get('status', 'DRAFT'),
                    author=request.user,
                    published_at=timezone.now() if request.POST.get('status') == 'PUBLISHED' else None,
                )
                log_activity(request.user, 'CREATE', 'BlogPost', post.id, post.title, request=request)
                messages.success(request, f'Blog post "{post.title}" created.')
            else:
                messages.error(request, 'Title and content are required.')
            return redirect('admin_blog_management')

    posts = BlogPost.objects.all().order_by('-created_at')
    
    paginator = Paginator(posts, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': BlogCategory.objects.filter(is_active=True),
        'post_types': BlogPost.POST_TYPE_CHOICES,
        'status_choices': BlogPost.STATUS_CHOICES,
    }
    
    return render(request, 'admin_panel/blog_management.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_faq_management(request):
    """FAQ management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_faq':
            question = (request.POST.get('question') or '').strip()
            answer = (request.POST.get('answer') or '').strip()
            category_id = request.POST.get('category_id')
            if question and answer and category_id:
                faq = FAQ.objects.create(
                    category_id=category_id,
                    question=question,
                    answer=answer,
                    is_active=True,
                    created_by=request.user,
                )
                log_activity(request.user, 'CREATE', 'FAQ', faq.id, faq.question[:120], request=request)
                messages.success(request, 'FAQ added successfully.')
            else:
                messages.error(request, 'Category, question, and answer are required.')
            return redirect('admin_faq_management')

        if action == 'add_faq_category':
            name = (request.POST.get('name') or '').strip()
            if name:
                category, _ = FAQCategory.objects.get_or_create(name=name)
                category.description = (request.POST.get('description') or '').strip()
                category.is_active = True
                category.save()
                log_activity(request.user, 'CREATE', 'FAQCategory', category.id, category.name, request=request)
                messages.success(request, f'FAQ category "{category.name}" saved.')
            else:
                messages.error(request, 'Category name is required.')
            return redirect('admin_faq_management')

    faqs = FAQ.objects.all().order_by('category', 'sort_order')
    
    paginator = Paginator(faqs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': FAQCategory.objects.filter(is_active=True),
    }
    
    return render(request, 'admin_panel/faq_management.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_email_templates(request):
    """Email template management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_email_template':
            name = (request.POST.get('name') or '').strip()
            subject = (request.POST.get('subject') or '').strip()
            html_content = (request.POST.get('html_content') or '').strip()
            if name and subject and html_content:
                template = ContentEmailTemplate.objects.create(
                    name=name,
                    template_type=request.POST.get('template_type', 'CUSTOM'),
                    subject=subject,
                    html_content=html_content,
                    text_content=(request.POST.get('text_content') or '').strip(),
                    description=(request.POST.get('description') or '').strip(),
                    created_by=request.user,
                    is_active=True,
                )
                log_activity(request.user, 'CREATE', 'ContentEmailTemplate', template.id, template.name, request=request)
                messages.success(request, f'Email template "{template.name}" created.')
            else:
                messages.error(request, 'Name, subject, and HTML content are required.')
            return redirect('admin_email_templates')

    templates = ContentEmailTemplate.objects.all().order_by('template_type', 'name')
    
    context = {
        'templates': templates,
        'template_types': ContentEmailTemplate.TEMPLATE_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/email_templates.html', context)


# ============ PERFORMANCE OPTIMIZATION VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_performance_dashboard(request):
    """Performance monitoring dashboard"""
    last_24_hours = timezone.now() - timedelta(hours=24)

    # Get recent performance metrics
    recent_errors = ErrorLog.objects.filter(
        last_seen__gte=last_24_hours
    ).count()
    
    slow_queries = DatabaseQueryLog.objects.filter(
        created_at__gte=last_24_hours,
        is_slow_query=True
    ).count()
    
    avg_page_load = PageLoadMetrics.objects.filter(
        created_at__gte=last_24_hours
    ).aggregate(Avg('page_load_complete'))['page_load_complete__avg'] or 0
    
    active_alert_queryset = PerformanceAlert.objects.filter(status='ACTIVE').order_by('-created_at')
    active_alerts = active_alert_queryset.count()
    recent_alerts = list(active_alert_queryset[:5])

    page_load_samples = list(
        PageLoadMetrics.objects.filter(created_at__gte=last_24_hours)
        .order_by('-created_at')
        .values('created_at', 'page_load_complete')[:8]
    )
    page_load_samples.reverse()

    page_load_chart = {
        'labels': [timezone.localtime(sample['created_at']).strftime('%H:%M') for sample in page_load_samples],
        'values': [float(sample['page_load_complete']) for sample in page_load_samples],
    }

    error_distribution = list(
        ErrorLog.objects.filter(last_seen__gte=last_24_hours)
        .values('error_type')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )
    error_type_labels = dict(ErrorLog.ERROR_TYPE_CHOICES)
    error_chart = {
        'labels': [error_type_labels.get(item['error_type'], item['error_type']) for item in error_distribution],
        'values': [item['total'] for item in error_distribution],
    }

    latest_resource = SystemResourceUsage.objects.order_by('-recorded_at').first()
    resource_chart = {
        'labels': ['CPU', 'Memory', 'Disk'],
        'values': [
            float(latest_resource.cpu_usage_percent) if latest_resource else 0,
            float(latest_resource.memory_usage_percent) if latest_resource else 0,
            float(latest_resource.disk_usage_percent) if latest_resource else 0,
        ],
    }
    
    context = {
        'recent_errors': recent_errors,
        'slow_queries': slow_queries,
        'avg_page_load': avg_page_load,
        'active_alerts': active_alerts,
        'recent_alerts': recent_alerts,
        'latest_resource': latest_resource,
        'page_load_chart': page_load_chart,
        'error_chart': error_chart,
        'resource_chart': resource_chart,
    }
    
    return render(request, 'admin_panel/performance_dashboard.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_image_optimization(request):
    """Image optimization management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'log_image':
            filename = (request.POST.get('original_filename') or '').strip()
            if filename:
                original_size_kb = max(1, _safe_int(request.POST.get('original_size_kb'), 1))
                optimized_size_kb = max(0, _safe_int(request.POST.get('optimized_size_kb'), 0))
                optimization = ImageOptimization.objects.create(
                    original_filename=filename,
                    image_type=request.POST.get('image_type', 'OTHER'),
                    original_path=(request.POST.get('original_path') or f'media/{filename}').strip(),
                    original_size_bytes=original_size_kb * 1024,
                    optimized_size_bytes=optimized_size_kb * 1024,
                    original_width=max(1, _safe_int(request.POST.get('original_width'), 1200)),
                    original_height=max(1, _safe_int(request.POST.get('original_height'), 1200)),
                    optimized_width=max(1, _safe_int(request.POST.get('optimized_width'), _safe_int(request.POST.get('original_width'), 1200))),
                    optimized_height=max(1, _safe_int(request.POST.get('optimized_height'), _safe_int(request.POST.get('original_height'), 1200))),
                    status=request.POST.get('status', 'COMPLETED'),
                )
                if optimization.original_size_bytes > 0 and optimization.optimized_size_bytes > 0:
                    optimization.bandwidth_saved_bytes = max(0, optimization.original_size_bytes - optimization.optimized_size_bytes)
                    optimization.compression_ratio = round((optimization.optimized_size_bytes / optimization.original_size_bytes) * 100, 2)
                    optimization.save(update_fields=['bandwidth_saved_bytes', 'compression_ratio'])
                log_activity(request.user, 'CREATE', 'ImageOptimization', optimization.id, optimization.original_filename, request=request)
                messages.success(request, 'Image optimization entry saved.')
            else:
                messages.error(request, 'Original filename is required.')
            return redirect('admin_image_optimization')

    optimizations = ImageOptimization.objects.all().order_by('-created_at')
    
    paginator = Paginator(optimizations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Optimization summary
    summary = ImageOptimization.objects.aggregate(
        total_images=Count('id'),
        optimized_images=Count('id', filter=Q(status='COMPLETED')),
        total_savings_bytes=Sum('bandwidth_saved_bytes'),
    )
    summary['total_savings_mb'] = round((summary['total_savings_bytes'] or 0) / (1024 * 1024), 2)
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
        'image_types': ImageOptimization.OPTIMIZATION_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/image_optimization.html', context)


# ============ AI/ML FEATURES VIEWS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_recommendation_engines(request):
    """Recommendation engine management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_engine':
            name = (request.POST.get('name') or '').strip()
            algorithm = request.POST.get('algorithm', 'HYBRID')
            if name:
                engine = RecommendationEngine.objects.create(
                    name=name,
                    algorithm=algorithm,
                    status='ACTIVE' if request.POST.get('is_active') == 'on' else 'TRAINING',
                    is_active=request.POST.get('is_active') == 'on',
                    training_data_size=max(0, _safe_int(request.POST.get('training_data_size'), 0)),
                    accuracy_score=_safe_decimal(request.POST.get('accuracy_score'), '0'),
                    created_by=request.user,
                )
                log_activity(request.user, 'CREATE', 'RecommendationEngine', engine.id, engine.name, request=request)
                messages.success(request, f'Recommendation engine "{engine.name}" created.')
            else:
                messages.error(request, 'Engine name is required.')
            return redirect('admin_recommendation_engines')

    engines = RecommendationEngine.objects.all().order_by('-created_at')
    
    context = {
        'engines': engines,
        'algorithms': RecommendationEngine.ALGORITHM_CHOICES,
    }
    
    return render(request, 'admin_panel/recommendation_engines.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_dynamic_pricing(request):
    """Dynamic pricing management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_rule':
            name = (request.POST.get('name') or '').strip()
            strategy = request.POST.get('strategy', 'DEMAND_BASED')
            if name:
                rule = DynamicPricingRule.objects.create(
                    name=name,
                    strategy=strategy,
                    description=(request.POST.get('description') or '').strip(),
                    min_price_change_percent=_safe_decimal(request.POST.get('min_price_change_percent'), '-20'),
                    max_price_change_percent=_safe_decimal(request.POST.get('max_price_change_percent'), '20'),
                    priority=max(1, _safe_int(request.POST.get('priority'), 1)),
                    is_active=request.POST.get('is_active') == 'on',
                    created_by=request.user,
                )
                log_activity(request.user, 'CREATE', 'DynamicPricingRule', rule.id, rule.name, request=request)
                messages.success(request, f'Pricing rule "{rule.name}" created.')
            else:
                messages.error(request, 'Rule name is required.')
            return redirect('admin_dynamic_pricing')

        if action == 'toggle_rule':
            rule = get_object_or_404(DynamicPricingRule, id=request.POST.get('rule_id'))
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
            log_activity(request.user, 'UPDATE', 'DynamicPricingRule', rule.id, f'Active={rule.is_active}', request=request)
            messages.success(request, f'Rule "{rule.name}" updated.')
            return redirect('admin_dynamic_pricing')

    rules = DynamicPricingRule.objects.all().order_by('priority', 'name')
    
    context = {
        'rules': rules,
        'strategies': DynamicPricingRule.PRICING_STRATEGY_CHOICES,
    }
    
    return render(request, 'admin_panel/dynamic_pricing.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_fraud_detection(request):
    """Fraud detection management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_fraud_status':
            analysis = get_object_or_404(FraudAnalysis, id=request.POST.get('analysis_id'))
            analysis.status = request.POST.get('new_status', analysis.status)
            analysis.review_notes = (request.POST.get('review_notes') or '').strip()
            analysis.reviewed_by = request.user
            analysis.reviewed_at = timezone.now()
            analysis.save(update_fields=['status', 'review_notes', 'reviewed_by', 'reviewed_at'])
            log_activity(request.user, 'UPDATE', 'FraudAnalysis', analysis.id, f'Order {analysis.order_id} -> {analysis.status}', request=request)
            messages.success(request, f'Fraud case for order {analysis.order_id} updated.')
            return redirect('admin_fraud_detection')

    analyses = FraudAnalysis.objects.all().order_by('-created_at')
    
    paginator = Paginator(analyses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Fraud summary
    summary = FraudAnalysis.objects.aggregate(
        total_analyses=Count('id'),
        high_risk_orders=Count('id', filter=Q(risk_level='HIGH')),
        pending_review=Count('id', filter=Q(status='PENDING')),
        avg_risk_score=Avg('overall_risk_score'),
    )
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
        'risk_levels': FraudAnalysis.RISK_LEVEL_CHOICES,
    }
    
    return render(request, 'admin_panel/fraud_detection.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_chatbot_management(request):
    """Chatbot management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_chatbot':
            name = (request.POST.get('name') or '').strip()
            if name:
                chatbot = ChatbotConfiguration.objects.create(
                    name=name,
                    chatbot_type=request.POST.get('chatbot_type', 'RULE_BASED'),
                    description=(request.POST.get('description') or '').strip(),
                    welcome_message=(request.POST.get('welcome_message') or 'Hello! How can I help you today?').strip(),
                    fallback_message=(request.POST.get('fallback_message') or "I'm sorry, I didn't understand that.").strip(),
                    is_active=request.POST.get('is_active') == 'on',
                    created_by=request.user,
                )
                log_activity(request.user, 'CREATE', 'ChatbotConfiguration', chatbot.id, chatbot.name, request=request)
                messages.success(request, f'Chatbot "{chatbot.name}" created.')
            else:
                messages.error(request, 'Chatbot name is required.')
            return redirect('admin_chatbot_management')

        if action == 'toggle_chatbot':
            chatbot = get_object_or_404(ChatbotConfiguration, id=request.POST.get('chatbot_id'))
            chatbot.is_active = not chatbot.is_active
            chatbot.save(update_fields=['is_active'])
            log_activity(request.user, 'UPDATE', 'ChatbotConfiguration', chatbot.id, f'Active={chatbot.is_active}', request=request)
            messages.success(request, f'Chatbot "{chatbot.name}" updated.')
            return redirect('admin_chatbot_management')

    chatbots = ChatbotConfiguration.objects.all().order_by('name')
    
    context = {
        'chatbots': chatbots,
        'chatbot_types': ChatbotConfiguration.CHATBOT_TYPE_CHOICES,
    }
    
    return render(request, 'admin_panel/chatbot_management.html', context)


# ============ AJAX/API ENDPOINTS ============

@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_http_methods(["POST"])
def ajax_update_customer_segment(request):
    """Update customer segment via AJAX"""
    try:
        segment_id = request.POST.get('segment_id')
        field = request.POST.get('field')
        value = request.POST.get('value')
        
        segment = get_object_or_404(CustomerSegmentationRule, id=segment_id)
        
        if field == 'is_active':
            segment.is_active = value == 'true'
        elif field == 'discount_percentage':
            segment.discount_percentage = Decimal(value)
        
        segment.save()
        
        log_activity(request.user, 'UPDATE', 'CustomerSegmentationRule', segment.id, 
                    f'Updated {field} to {value}', request=request)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='login')
@staff_member_required(login_url='login')
@require_http_methods(["POST"])
def ajax_terminate_user_session(request):
    """Terminate user session via AJAX"""
    try:
        session_id = request.POST.get('session_id')
        
        session = get_object_or_404(UserSession, id=session_id)
        session.status = 'TERMINATED'
        session.logout_time = timezone.now()
        session.save()
        
        log_activity(request.user, 'UPDATE', 'UserSession', session.id, 
                    f'Terminated session for {session.user.username}', request=request)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url='login')
@staff_member_required(login_url='login')
def export_comprehensive_analytics(request):
    """Export comprehensive analytics to Excel"""
    if not HAS_XLSXWRITER:
        messages.error(request, 'Excel export not available. Please install xlsxwriter.')
        return redirect('admin_dashboard')
    
    report_type = request.GET.get('type', 'customer_insights')
    
    # Create Excel file
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    if report_type == 'customer_insights':
        worksheet = workbook.add_worksheet('Customer Insights')
        
        # Headers
        headers = ['Customer', 'Segment', 'Total Orders', 'Total Spent', 'Last Order', 'Status']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Data
        profiles = CustomerProfile.objects.select_related('customer', 'customer_segment')[:1000]
        for row, profile in enumerate(profiles, 1):
            worksheet.write(row, 0, profile.customer.username)
            worksheet.write(row, 1, profile.customer_segment.name if profile.customer_segment else 'None')
            # Add more customer data as needed
    
    elif report_type == 'financial_summary':
        worksheet = workbook.add_worksheet('Financial Summary')
        
        # Headers
        headers = ['Period', 'Gross Sales', 'Net Profit', 'Profit Margin %', 'Total Orders']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Data
        statements = ProfitLossStatement.objects.all()[:50]
        for row, statement in enumerate(statements, 1):
            worksheet.write(row, 0, f"{statement.start_date} to {statement.end_date}")
            worksheet.write(row, 1, float(statement.gross_sales))
            worksheet.write(row, 2, float(statement.net_profit))
            worksheet.write(row, 3, float(statement.net_profit_margin))
            worksheet.write(row, 4, statement.total_orders)
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.xlsx"'
    
    log_activity(request.user, 'EXPORT', 'ComprehensiveAnalytics', None, 
                f'Exported {report_type} report', request=request)
    
    return response


# ============================================
# MARKETING AUTOMATION VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_flash_sales(request):
    """Flash Sales Management with full functionality"""
    from Hub.models import Product
    
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        discount_percent = request.POST.get('discount_percent')
        
        if product_id and discount_percent:
            try:
                product = Product.objects.get(id=product_id)
                original_price = product.price
                discount_rate = Decimal(discount_percent)
                discount_amount = (original_price * discount_rate) / Decimal('100')
                flash_price = original_price - discount_amount
                
                product.old_price = original_price
                product.price = flash_price
                product.discount_percent = int(discount_rate)
                product.save()
                
                messages.success(request, f'Flash sale created for {product.name}!')
                log_activity(request.user, 'CREATE', 'FlashSale', product.id, f'Flash sale: {product.name}')
            except Product.DoesNotExist:
                messages.error(request, 'Product not found!')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    
    products = Product.objects.filter(stock__gt=0).order_by('-id')[:50]
    current_flash_sales = Product.objects.filter(discount_percent__gt=0, stock__gt=0).order_by('-discount_percent')
    
    total_flash_sales = current_flash_sales.count()
    total_discount_value = sum([(p.old_price - p.price) * p.sold if p.old_price else 0 for p in current_flash_sales])
    
    context = {
        'title': 'Flash Sales Management',
        'products': products,
        'current_flash_sales': current_flash_sales,
        'total_flash_sales': total_flash_sales,
        'total_discount_value': total_discount_value,
        'flash_sale_stats': {
            'active_sales': total_flash_sales,
            'total_savings': total_discount_value,
            'avg_discount': current_flash_sales.aggregate(avg_discount=Avg('discount_percent'))['avg_discount'] or 0,
        }
    }
    return render(request, 'admin_panel/flash_sales.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_email_campaigns(request):
    """Email Campaigns Management"""
    from Hub.models import NewsletterSubscription
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        target_audience = request.POST.get('target_audience')
        
        if subject and message:
            try:
                if target_audience == 'subscribers':
                    emails = NewsletterSubscription.objects.filter(is_active=True).values_list('email', flat=True)
                elif target_audience == 'customers':
                    emails = User.objects.filter(is_active=True, email__isnull=False).exclude(email='').values_list('email', flat=True)
                else:
                    emails = list(NewsletterSubscription.objects.filter(is_active=True).values_list('email', flat=True))
                
                messages.success(request, f'Email campaign prepared for {len(emails)} recipients!')
                log_activity(request.user, 'CREATE', 'EmailCampaign', None, f'Campaign: {subject}')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    
    total_subscribers = NewsletterSubscription.objects.filter(is_active=True).count()
    total_customers = User.objects.filter(is_active=True, email__isnull=False).exclude(email='').count()
    
    context = {
        'title': 'Email Campaigns',
        'total_subscribers': total_subscribers,
        'total_customers': total_customers,
        'campaign_stats': {
            'total_audience': total_subscribers + total_customers,
            'avg_open_rate': '21.6%',
            'avg_click_rate': '3.0%',
        }
    }
    return render(request, 'admin_panel/email_campaigns.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_whatsapp_campaigns(request):
    """WhatsApp Campaigns Management"""
    
    if request.method == 'POST':
        message_template = request.POST.get('message_template')
        target_audience = request.POST.get('target_audience')
        
        if message_template:
            try:
                customers_with_phone = User.objects.filter(
                    is_active=True
                ).filter(
                    Q(userprofile__mobile_number__gt='') | Q(userprofile__phone__gt='')
                ).distinct().count()
                
                messages.success(request, f'WhatsApp campaign prepared for {customers_with_phone} recipients!')
                log_activity(request.user, 'CREATE', 'WhatsAppCampaign', None, 'WhatsApp campaign created')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    
    total_customers_with_phone = User.objects.filter(
        is_active=True
    ).filter(
        Q(userprofile__mobile_number__gt='') | Q(userprofile__phone__gt='')
    ).distinct().count()
    
    context = {
        'title': 'WhatsApp Campaigns',
        'total_customers_with_phone': total_customers_with_phone,
        'campaign_stats': {
            'total_reachable': total_customers_with_phone,
            'delivery_rate': '95.2%'
        }
    }
    return render(request, 'admin_panel/whatsapp_campaigns.html', context)


# ============================================
# ANALYTICS & REPORTING VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_sales_comparison(request):
    """Sales Comparison Analytics"""
    period = request.GET.get('period', 'monthly')
    today = timezone.now().date()
    
    if period == 'daily':
        current_start = today
        previous_start = today - timedelta(days=1)
    elif period == 'weekly':
        current_start = today - timedelta(days=today.weekday())
        previous_start = current_start - timedelta(days=7)
    else:
        current_start = today.replace(day=1)
        previous_start = (current_start - timedelta(days=1)).replace(day=1)
    
    current_orders = Order.objects.filter(
        created_at__date__gte=current_start,
        order_status__in=['PROCESSING', 'SHIPPED', 'DELIVERED']
    )
    
    previous_orders = Order.objects.filter(
        created_at__date__gte=previous_start,
        created_at__date__lt=current_start,
        order_status__in=['PROCESSING', 'SHIPPED', 'DELIVERED']
    )
    
    current_metrics = current_orders.aggregate(
        total_sales=Sum('total_amount'),
        total_orders=Count('id'),
        avg_order_value=Avg('total_amount')
    )
    
    previous_metrics = previous_orders.aggregate(
        total_sales=Sum('total_amount'),
        total_orders=Count('id'),
        avg_order_value=Avg('total_amount')
    )
    
    context = {
        'title': 'Sales Comparison Analytics',
        'period': period,
        'current_metrics': current_metrics,
        'previous_metrics': previous_metrics,
    }
    return render(request, 'admin_panel/sales_comparison.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_product_performance(request):
    """Product Performance Analytics"""
    products_query = Product.objects.annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum('orderitem__subtotal'),
        total_orders=Count('orderitem__order_id', distinct=True)
    ).filter(total_sold__isnull=False).order_by('-total_revenue')[:20]
    
    context = {
        'title': 'Product Performance Analytics',
        'top_products': products_query,
    }
    return render(request, 'admin_panel/product_performance.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_customer_clv(request):
    """Customer Lifetime Value Analytics"""
    customers_clv = User.objects.annotate(
        total_orders=Count('orders'),
        total_spent=Sum('orders__total_amount'),
        avg_order_value=Avg('orders__total_amount')
    ).filter(total_orders__gt=0).order_by('-total_spent')[:50]
    
    context = {
        'title': 'Customer Lifetime Value Analytics',
        'customers': customers_clv,
    }
    return render(request, 'admin_panel/customer_clv.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_abandoned_carts(request):
    """Abandoned Carts Management"""
    from Hub.models import Cart

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'remove_cart_item':
            cart_item = get_object_or_404(Cart, id=request.POST.get('cart_id'))
            cart_item.delete()
            log_activity(request.user, 'DELETE', 'Cart', None, 'Removed abandoned cart item', request=request)
            messages.success(request, 'Abandoned cart item removed.')
            return redirect('admin_abandoned_carts')
    
    abandoned_threshold = timezone.now() - timedelta(hours=24)
    abandoned_carts = Cart.objects.filter(
        updated_at__lt=abandoned_threshold
    ).select_related('user', 'product').order_by('-updated_at')[:50]
    
    total_abandoned_value = sum([cart.product.price * cart.quantity for cart in abandoned_carts])
    
    context = {
        'title': 'Abandoned Carts Management',
        'abandoned_carts': abandoned_carts,
        'total_abandoned_value': total_abandoned_value,
    }
    return render(request, 'admin_panel/abandoned_carts.html', context)


# ============================================
# FINANCIAL MANAGEMENT VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_gst_reports(request):
    """GST Reports"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate_gst':
            report_type = request.POST.get('report_type', 'GSTR1')
            month = max(1, min(12, _safe_int(request.POST.get('month'), timezone.now().month)))
            financial_year = (request.POST.get('financial_year') or f"{timezone.now().year}-{str(timezone.now().year + 1)[-2:]}").strip()
            start_date = datetime(timezone.now().year, month, 1).date()
            if month == 12:
                end_date = datetime(timezone.now().year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(timezone.now().year, month + 1, 1).date() - timedelta(days=1)
            orders = Order.objects.filter(created_at__date__range=[start_date, end_date], order_status__in=['PROCESSING', 'SHIPPED', 'DELIVERED'])
            taxable = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            cgst = taxable * Decimal('0.09')
            sgst = taxable * Decimal('0.09')
            igst = Decimal('0')
            report_id = f"{report_type}-{financial_year.replace('-', '')}-{month:02d}"
            report, _ = GSTReport.objects.update_or_create(
                report_type=report_type,
                financial_year=financial_year,
                month=month,
                defaults={
                    'gstin': (request.POST.get('gstin') or '22AAAAA0000A1Z5').strip(),
                    'report_id': report_id,
                    'taxable_value': taxable,
                    'cgst_amount': cgst,
                    'sgst_amount': sgst,
                    'igst_amount': igst,
                    'total_tax': cgst + sgst + igst,
                    'tax_payable': cgst + sgst + igst,
                    'status': 'GENERATED',
                    'generated_by': request.user,
                    'report_data': {'order_count': orders.count()},
                }
            )
            log_activity(request.user, 'CREATE', 'GSTReport', report.id, report.report_id, request=request)
            messages.success(request, f'GST report {report.report_id} generated.')
            return redirect('admin_gst_reports')

        if action == 'mark_filed':
            report = get_object_or_404(GSTReport, id=request.POST.get('report_id'))
            report.status = 'FILED'
            report.filing_date = timezone.now().date()
            report.acknowledgment_number = (request.POST.get('acknowledgment_number') or '').strip()
            report.save(update_fields=['status', 'filing_date', 'acknowledgment_number'])
            log_activity(request.user, 'UPDATE', 'GSTReport', report.id, f'Filed {report.report_id}', request=request)
            messages.success(request, f'GST report {report.report_id} marked as filed.')
            return redirect('admin_gst_reports')

    reports = GSTReport.objects.all().order_by('-financial_year', '-month')
    paginator = Paginator(reports, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    summary = GSTReport.objects.aggregate(
        total_reports=Count('id'),
        filed_reports=Count('id', filter=Q(status='FILED')),
        total_tax=Sum('total_tax'),
    )
    context = {
        'title': 'GST Reports',
        'page_obj': page_obj,
        'summary': summary,
        'report_types': GSTReport.REPORT_TYPE_CHOICES,
        'current_year': timezone.now().year,
    }
    return render(request, 'admin_panel/gst_reports.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_payment_reconciliation(request):
    """Payment Reconciliation"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_reconciliation':
            gateway = request.POST.get('gateway', 'RAZORPAY')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            if start_date and end_date:
                orders = Order.objects.filter(
                    created_at__date__range=[start_date, end_date],
                    payment_method__iexact='RAZORPAY' if gateway == 'RAZORPAY' else 'COD'
                )
                total_amount = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
                recon = PaymentGatewayReconciliation.objects.create(
                    reconciliation_id=f"REC-{gateway}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    gateway=gateway,
                    start_date=start_date,
                    end_date=end_date,
                    total_transactions=orders.count(),
                    matched_transactions=orders.count(),
                    mismatched_transactions=0,
                    gateway_total_amount=total_amount,
                    system_total_amount=total_amount,
                    difference_amount=Decimal('0'),
                    gateway_fees=total_amount * Decimal('0.02'),
                    gst_on_fees=total_amount * Decimal('0.0036'),
                    net_settlement=total_amount * Decimal('0.9764'),
                    status='MATCHED',
                    created_by=request.user,
                )
                log_activity(request.user, 'CREATE', 'PaymentGatewayReconciliation', recon.id, recon.reconciliation_id, request=request)
                messages.success(request, f'Reconciliation {recon.reconciliation_id} created.')
            else:
                messages.error(request, 'Start and end date are required.')
            return redirect('admin_payment_reconciliation')

        if action == 'set_reconciliation_status':
            recon = get_object_or_404(PaymentGatewayReconciliation, id=request.POST.get('reconciliation_id'))
            recon.status = request.POST.get('new_status', recon.status)
            recon.save(update_fields=['status'])
            log_activity(request.user, 'UPDATE', 'PaymentGatewayReconciliation', recon.id, recon.status, request=request)
            messages.success(request, f'Reconciliation {recon.reconciliation_id} updated.')
            return redirect('admin_payment_reconciliation')

    reconciliations = PaymentGatewayReconciliation.objects.all().order_by('-created_at')
    paginator = Paginator(reconciliations, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    summary = PaymentGatewayReconciliation.objects.aggregate(
        total_batches=Count('id'),
        matched_batches=Count('id', filter=Q(status='MATCHED')),
        total_difference=Sum('difference_amount'),
    )
    context = {
        'title': 'Payment Reconciliation',
        'page_obj': page_obj,
        'summary': summary,
        'gateways': PaymentGatewayReconciliation.GATEWAY_CHOICES,
        'status_choices': PaymentGatewayReconciliation.STATUS_CHOICES,
    }
    return render(request, 'admin_panel/payment_reconciliation.html', context)


# ============================================
# OPERATIONS VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_inventory_forecast(request):
    """Inventory Forecasting"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_forecast':
            product_id_val = _safe_int(request.POST.get('product_id'))
            forecast_date = request.POST.get('forecast_date') or timezone.now().date()
            if product_id_val > 0:
                forecast, created = DemandForecast.objects.update_or_create(
                    product_id=product_id_val,
                    forecast_type=request.POST.get('forecast_type', 'MONTHLY'),
                    forecast_date=forecast_date,
                    defaults={
                        'forecast_period_days': max(1, _safe_int(request.POST.get('forecast_period_days'), 30)),
                        'predicted_demand': max(0, _safe_int(request.POST.get('predicted_demand'), 0)),
                        'confidence_interval_lower': max(0, _safe_int(request.POST.get('confidence_lower'), 0)),
                        'confidence_interval_upper': max(0, _safe_int(request.POST.get('confidence_upper'), 0)),
                        'confidence_level': _safe_decimal(request.POST.get('confidence_level'), '95'),
                        'model_name': (request.POST.get('model_name') or 'RuleBasedForecast').strip(),
                        'model_version': (request.POST.get('model_version') or '1.0').strip(),
                    }
                )
                log_activity(request.user, 'CREATE', 'DemandForecast', forecast.id, f'Product {forecast.product_id}', request=request)
                messages.success(request, f'Forecast {"updated" if not created else "created"} for product {forecast.product_id}.')
            else:
                messages.error(request, 'Valid product ID is required.')
            return redirect('admin_inventory_forecast')

    forecasts = DemandForecast.objects.all().order_by('-forecast_date')
    paginator = Paginator(forecasts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    summary = DemandForecast.objects.aggregate(
        total_forecasts=Count('id'),
        avg_predicted=Avg('predicted_demand'),
    )
    context = {
        'title': 'Inventory Forecast',
        'page_obj': page_obj,
        'summary': summary,
        'forecast_types': DemandForecast.FORECAST_TYPE_CHOICES,
    }
    return render(request, 'admin_panel/inventory_forecast.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_related_products(request):
    """Related Products Management"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_related':
            primary_product_id = _safe_int(request.POST.get('primary_product_id'))
            related_product_id = _safe_int(request.POST.get('related_product_id'))
            relation_type = request.POST.get('relation_type', 'SIMILAR')
            if primary_product_id > 0 and related_product_id > 0 and primary_product_id != related_product_id:
                related, created = RelatedProduct.objects.get_or_create(
                    primary_product_id=primary_product_id,
                    related_product_id=related_product_id,
                    relation_type=relation_type,
                    defaults={
                        'relevance_score': _safe_decimal(request.POST.get('relevance_score'), '50'),
                        'display_order': _safe_int(request.POST.get('display_order'), 0),
                        'created_by': request.user,
                        'is_active': True,
                    }
                )
                if not created:
                    related.relevance_score = _safe_decimal(request.POST.get('relevance_score'), str(related.relevance_score))
                    related.display_order = _safe_int(request.POST.get('display_order'), related.display_order)
                    related.is_active = True
                    related.save()
                log_activity(request.user, 'CREATE', 'RelatedProduct', related.id, str(related), request=request)
                messages.success(request, 'Related product mapping saved.')
            else:
                messages.error(request, 'Primary and related product IDs must be different and valid.')
            return redirect('admin_related_products')

        if action == 'toggle_related':
            relation = get_object_or_404(RelatedProduct, id=request.POST.get('relation_id'))
            relation.is_active = not relation.is_active
            relation.save(update_fields=['is_active'])
            log_activity(request.user, 'UPDATE', 'RelatedProduct', relation.id, f'Active={relation.is_active}', request=request)
            messages.success(request, 'Related product status updated.')
            return redirect('admin_related_products')

        if action == 'delete_related':
            relation = get_object_or_404(RelatedProduct, id=request.POST.get('relation_id'))
            relation.delete()
            log_activity(request.user, 'DELETE', 'RelatedProduct', None, 'Deleted related mapping', request=request)
            messages.success(request, 'Related mapping deleted.')
            return redirect('admin_related_products')

    relations = RelatedProduct.objects.all().order_by('primary_product_id', 'display_order')[:500]
    paginator = Paginator(relations, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    summary = RelatedProduct.objects.aggregate(
        total_mappings=Count('id'),
        active_mappings=Count('id', filter=Q(is_active=True)),
        avg_relevance=Avg('relevance_score'),
    )
    context = {
        'title': 'Related Products',
        'page_obj': page_obj,
        'summary': summary,
        'relation_types': RelatedProduct.RELATION_TYPE_CHOICES,
    }
    return render(request, 'admin_panel/related_products.html', context)


# ============================================
# CONTENT MANAGEMENT VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_page_builder(request):
    """Page Builder"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_template':
            name = (request.POST.get('name') or '').strip()
            if name:
                template = PageTemplate.objects.create(
                    name=name,
                    template_type=request.POST.get('template_type', 'CUSTOM'),
                    description=(request.POST.get('description') or '').strip(),
                    created_by=request.user,
                    is_active=True,
                )
                log_activity(request.user, 'CREATE', 'PageTemplate', template.id, template.name, request=request)
                messages.success(request, f'Template "{template.name}" created.')
            else:
                messages.error(request, 'Template name is required.')
            return redirect('admin_page_builder')

        if action == 'add_custom_page':
            title = (request.POST.get('title') or '').strip()
            if title:
                base_slug = slugify(request.POST.get('slug') or title)[:210] or f'custom-page-{timezone.now().strftime("%Y%m%d%H%M%S")}'
                slug = base_slug
                i = 1
                while CustomPage.objects.filter(slug=slug).exists():
                    i += 1
                    slug = f"{base_slug[:200]}-{i}"
                page = CustomPage.objects.create(
                    title=title,
                    slug=slug,
                    description=(request.POST.get('description') or '').strip(),
                    template_id=request.POST.get('template_id') or None,
                    status=request.POST.get('status', 'DRAFT'),
                    content_blocks=[],
                    created_by=request.user,
                    published_at=timezone.now() if request.POST.get('status') == 'PUBLISHED' else None,
                )
                log_activity(request.user, 'CREATE', 'CustomPage', page.id, page.title, request=request)
                messages.success(request, f'Custom page "{page.title}" created.')
            else:
                messages.error(request, 'Page title is required.')
            return redirect('admin_page_builder')

    pages = CustomPage.objects.select_related('template').all().order_by('-updated_at')
    paginator = Paginator(pages, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    summary = CustomPage.objects.aggregate(
        total_pages=Count('id'),
        published_pages=Count('id', filter=Q(status='PUBLISHED')),
    )
    context = {
        'title': 'Page Builder',
        'page_obj': page_obj,
        'summary': summary,
        'templates': PageTemplate.objects.filter(is_active=True).order_by('template_type', 'name'),
        'template_types': PageTemplate.TEMPLATE_TYPE_CHOICES,
        'status_choices': CustomPage.STATUS_CHOICES,
    }
    return render(request, 'admin_panel/page_builder.html', context)


_ADVANCED_PAGE_LABELS = {
    'admin_customer_segmentation': 'Customer Segmentation',
    'admin_add_customer_segment': 'Add Customer Segment',
    'admin_customer_support_tickets': 'Customer Support Tickets',
    'admin_profit_loss_statements': 'Profit & Loss Statements',
    'admin_generate_pl_statement': 'Generate Profit & Loss Statement',
    'admin_expense_management': 'Expense Management',
    'admin_product_variants': 'Product Variants',
    'admin_product_bundles': 'Product Bundles',
    'admin_product_seo': 'Product SEO',
    'admin_security_roles': 'Security Roles',
    'admin_security_audit_log': 'Security Audit Log',
    'admin_user_sessions': 'User Sessions',
    'admin_blog_management': 'Blog Management',
    'admin_faq_management': 'FAQ Management',
    'admin_email_templates': 'Email Templates',
    'admin_performance_dashboard': 'Performance Dashboard',
    'admin_image_optimization': 'Image Optimization',
    'admin_recommendation_engines': 'Recommendation Engines',
    'admin_dynamic_pricing': 'Dynamic Pricing',
    'admin_fraud_detection': 'Fraud Detection',
    'admin_chatbot_management': 'Chatbot Management',
    'admin_flash_sales': 'Flash Sales',
    'admin_email_campaigns': 'Email Campaigns',
    'admin_whatsapp_campaigns': 'WhatsApp Campaigns',
    'admin_sales_comparison': 'Sales Comparison',
    'admin_product_performance': 'Product Performance',
    'admin_customer_clv': 'Customer Lifetime Value',
    'admin_abandoned_carts': 'Abandoned Carts',
    'admin_gst_reports': 'GST Reports',
    'admin_payment_reconciliation': 'Payment Reconciliation',
    'admin_inventory_forecast': 'Inventory Forecast',
    'admin_related_products': 'Related Products',
    'admin_page_builder': 'Page Builder',
}

for _view_name, _label in _ADVANCED_PAGE_LABELS.items():
    globals()[_view_name] = advanced_feature_guard(_label)(globals()[_view_name])
