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
                status__in=['COMPLETED', 'SHIPPED', 'DELIVERED']
            )
            
            gross_sales = orders.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
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
    # Get recent performance metrics
    recent_errors = ErrorLog.objects.filter(
        last_seen__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    slow_queries = DatabaseQueryLog.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24),
        is_slow_query=True
    ).count()
    
    avg_page_load = PageLoadMetrics.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).aggregate(Avg('page_load_complete'))['page_load_complete__avg'] or 0
    
    active_alerts = PerformanceAlert.objects.filter(status='ACTIVE').count()
    
    context = {
        'recent_errors': recent_errors,
        'slow_queries': slow_queries,
        'avg_page_load': avg_page_load,
        'active_alerts': active_alerts,
    }
    
    return render(request, 'admin_panel/performance_dashboard.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_image_optimization(request):
    """Image optimization management"""
    optimizations = ImageOptimization.objects.all().order_by('-created_at')
    
    paginator = Paginator(optimizations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Optimization summary
    summary = ImageOptimization.objects.aggregate(
        total_images=Count('id'),
        optimized_images=Count('id', filter=Q(status='COMPLETED')),
        total_savings_mb=Sum('bandwidth_saved_bytes') / (1024 * 1024) if Sum('bandwidth_saved_bytes') else 0,
    )
    
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
                discount_amount = (original_price * float(discount_percent)) / 100
                flash_price = original_price - discount_amount
                
                product.old_price = original_price
                product.price = flash_price
                product.discount_percent = float(discount_percent)
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
        order_status__in=['confirmed', 'shipped', 'delivered']
    )
    
    previous_orders = Order.objects.filter(
        created_at__date__gte=previous_start,
        created_at__date__lt=current_start,
        order_status__in=['confirmed', 'shipped', 'delivered']
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
    context = {
        'title': 'GST Reports',
        'message': 'GST Reports feature - Coming soon with full GSTR-1 and GSTR-3B compliance'
    }
    return render(request, 'admin_panel/gst_reports.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_payment_reconciliation(request):
    """Payment Reconciliation"""
    context = {
        'title': 'Payment Reconciliation',
        'message': 'Payment reconciliation with Razorpay integration - Coming soon'
    }
    return render(request, 'admin_panel/payment_reconciliation.html', context)


# ============================================
# OPERATIONS VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_inventory_forecast(request):
    """Inventory Forecasting"""
    context = {
        'title': 'Inventory Forecast',
        'message': 'AI-powered inventory forecasting - Coming soon'
    }
    return render(request, 'admin_panel/inventory_forecast.html', context)


@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_related_products(request):
    """Related Products Management"""
    context = {
        'title': 'Related Products',
        'message': 'Related products and cross-selling management - Coming soon'
    }
    return render(request, 'admin_panel/related_products.html', context)


# ============================================
# CONTENT MANAGEMENT VIEWS
# ============================================

@login_required(login_url='login')
@staff_member_required(login_url='login')
def admin_page_builder(request):
    """Page Builder"""
    context = {
        'title': 'Page Builder',
        'message': 'Drag-and-drop page builder - Coming soon'
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
