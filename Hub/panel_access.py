from functools import wraps

from django.shortcuts import resolve_url
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.db.models import Q

from .models import CategoryIcon, Order, OrderItem, Product, ResellLink, SubCategory
from .models_security_access import UserRoleAssignment


SELLER_ROLE_TYPES = {'SELLER'}


def _get_active_role_assignment(user):
    if not user or not user.is_authenticated:
        return None

    cache_key = f'panel_active_role_assignment_{user.id}'
    cached_assignment_id = cache.get(cache_key)
    if cached_assignment_id is not None:
        try:
            return UserRoleAssignment.objects.select_related('role').get(
                id=cached_assignment_id,
                user=user,
                is_active=True,
                role__is_active=True,
            )
        except UserRoleAssignment.DoesNotExist:
            cache.delete(cache_key)

    assignment = (
        UserRoleAssignment.objects
        .select_related('role')
        .filter(user=user, is_active=True, role__is_active=True)
        .order_by('-is_primary', 'assigned_at')
        .first()
    )
    if assignment:
        cache.set(cache_key, assignment.id, 120)
    return assignment


def is_seller_user(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return False

    assignment = _get_active_role_assignment(user)
    if assignment and assignment.role.role_type in SELLER_ROLE_TYPES:
        return True

    try:
        profile = user.reseller_profile
        return bool(profile.is_reseller_enabled)
    except Exception:
        return False


def is_panel_admin_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def get_panel_mode(user):
    if is_seller_user(user):
        return 'seller'
    if is_panel_admin_user(user):
        return 'admin'
    return 'user'


def get_panel_label(user):
    if is_seller_user(user):
        return 'Seller'
    if user and user.is_authenticated and user.is_superuser:
        return 'Super Admin'
    if user and user.is_authenticated and user.is_staff:
        return 'Admin'
    return 'User'


def get_panel_permissions(user):
    if is_seller_user(user):
        return {
            'can_manage_products': True,
            'can_manage_orders': True,
            'can_manage_categories': True,
            'can_manage_invoices': True,
            'can_manage_resellers': True,
            'can_view_reports': True,
            'can_export_data': False,
            'can_manage_customers': False,
            'can_manage_finances': False,
            'can_manage_settings': False,
            'can_manage_users': False,
            'can_manage_marketing': False,
        }

    return {
        'can_manage_products': True,
        'can_manage_orders': True,
        'can_manage_categories': True,
        'can_manage_invoices': True,
        'can_manage_resellers': True,
        'can_view_reports': True,
        'can_export_data': True,
        'can_manage_customers': True,
        'can_manage_finances': True,
        'can_manage_settings': True,
        'can_manage_users': True,
        'can_manage_marketing': True,
    }


def admin_panel_required(view_func=None, login_url='login'):
    seller_allowed_url_names = {
        'admin_dashboard',
        'admin_product_list',
        'admin_add_product',
        'admin_edit_product',
        'admin_delete_product',
        'admin_toggle_stock',
        'admin_delete_gallery_image',
        'admin_upload_reel_file',
        'admin_categories',
        'admin_add_category',
        'admin_edit_category',
        'admin_delete_category',
        'admin_save_subcategory_icon',
        'admin_subcategories',
        'admin_orders',
        'admin_order_details',
        'admin_approve_order',
        'admin_reject_order',
        'admin_delete_order',
        'razorpay_refund',
        'admin_invoices',
        'admin_invoice_inventory',
        'admin_update_inventory',
        'admin_resell_orders',
        'admin_reseller_analytics',
        'admin_reseller_management',
        'admin_reseller_payment_data',
        'admin_payout_management',
        'admin_process_payout',
        'admin_approve_payout',
        'admin_reject_payout',
        'admin_download_payout_invoice',
        'admin_resell_reports',
    }

    def decorator(func):
        @wraps(func)
        def wrapped_view(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return redirect_to_login(request.get_full_path(), resolve_url(login_url))
            if is_panel_admin_user(user):
                return func(request, *args, **kwargs)
            if is_seller_user(user):
                resolver_match = getattr(request, 'resolver_match', None)
                url_name = getattr(resolver_match, 'url_name', '') or ''
                if url_name in seller_allowed_url_names:
                    return func(request, *args, **kwargs)
            return redirect_to_login(request.get_full_path(), resolve_url(login_url))

        return wrapped_view

    if view_func is not None:
        return decorator(view_func)
    return decorator


def get_product_scope(user):
    return Product.objects.filter(created_by=user) if is_seller_user(user) else Product.objects.all()


def get_category_scope(user):
    return CategoryIcon.objects.filter(created_by=user) if is_seller_user(user) else CategoryIcon.objects.all()


def get_subcategory_scope(user):
    return SubCategory.objects.filter(created_by=user) if is_seller_user(user) else SubCategory.objects.all()


def get_resell_link_scope(user):
    return ResellLink.objects.filter(reseller=user) if is_seller_user(user) else ResellLink.objects.all()


def get_order_scope(user):
    if is_seller_user(user):
        return (
            Order.objects.filter(
                Q(reseller=user) |
                Q(resell_link__reseller=user) |
                Q(items__product__created_by=user)
            ).distinct()
        )
    return Order.objects.all()


def get_order_item_scope(user):
    if is_seller_user(user):
        return (
            OrderItem.objects.filter(
                Q(order__reseller=user) |
                Q(order__resell_link__reseller=user) |
                Q(product__created_by=user)
            ).distinct()
        )
    return OrderItem.objects.all()
