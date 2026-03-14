"""
Context processors for VibeMall
Adds cart, wishlist, and site configuration to every template
Implements caching to optimize database queries
"""
from collections import defaultdict

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from datetime import timedelta

from .models import Cart, Wishlist, SiteSettings, LoyaltyPoints, CategoryIcon, Product, SubCategory, Coupon, Order
from django.db.models import F, Sum


def cart_wishlist_context(request):
    """Add cart and wishlist counts and totals to template context"""
    context = {
        'cart_count': 0,
        'wishlist_count': 0,
        'cart_total': 0,
        'cart_items': [],
        'loyalty_points': 0,
    }

    # Admin pages do not need storefront cart/wishlist context.
    if request.path.startswith('/admin-panel/'):
        return context

    if request.user.is_authenticated:
        # Cart items and count
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        context['cart_count'] = cart_items.count()
        context['cart_items'] = cart_items
        
        # Calculate cart total
        cart_total = sum(item.get_total_price() for item in cart_items)
        context['cart_total'] = f"{cart_total:.2f}"
        
        # Wishlist count
        context['wishlist_count'] = Wishlist.objects.filter(user=request.user).count()
        
        # Loyalty points
        try:
            loyalty = LoyaltyPoints.objects.get(user=request.user)
            context['loyalty_points'] = loyalty.points_available
        except LoyaltyPoints.DoesNotExist:
            # Avoid writes inside request-time context processor.
            context['loyalty_points'] = 0
    
    return context


def site_settings_context(request):
    """Add site settings to every template"""
    try:
        site_settings = SiteSettings.get_settings()
    except:
        # If table doesn't exist yet (during migrations)
        site_settings = None
    
    return {
        'site_settings': site_settings,
        'site_url': getattr(settings, 'SITE_URL', '').rstrip('/'),
    }


def header_menu_context(request):
    """
    Add header menu data to context with caching for performance
    Cache invalidated when categories are updated
    """
    # Admin pages do not need storefront mega-menu data.
    if request.path.startswith('/admin-panel/'):
        return {
            'header_categories': [],
            'header_links': [],
            'header_offer_coupon': None,
            'header_offer_heading': 'Coupon Offer',
            'header_offer_message': 'Apply this code at checkout:',
        }

    # Try to get from cache
    cache_key = 'header_menu_context'
    cached_context = cache.get(cache_key)
    if cached_context is not None:
        return cached_context
    
    badge_map = {
        'TOP_DEALS': {'text': 'HOT', 'class': ''},
        'TOP_SELLING': {'text': 'HOT', 'class': ''},
        'TOP_FEATURED': {'text': 'HOT', 'class': ''},
        'RECOMMENDED': {'text': 'NEW', 'class': 'green'},
        'GENZ_TRENDS': {'text': 'NEW', 'class': 'green'},
        'NEXT_GEN': {'text': 'NEW', 'class': 'green'},
    }

    header_categories = []
    subcategory_map = defaultdict(list)

    # Use only() to fetch only needed fields for performance
    active_subcategories = (
        SubCategory.objects
        .only('category_key', 'name', 'order')
        .filter(is_active=True)
        .order_by('category_key', 'order', 'name')
    )
    for sub in active_subcategories:
        key = (sub.category_key or '').strip()
        if not key:
            continue
        subcategory_map[key].append({
            'name': sub.name,
        })

    # Fallback: if SubCategory master is empty for a category, derive from product values.
    product_subcategory_map = defaultdict(list)
    product_subcategory_rows = (
        Product.objects
        .only('category', 'sub_category')
        .filter(is_active=True)
        .exclude(sub_category='')
        .values('category', 'sub_category')
        .distinct()
        .order_by('category', 'sub_category')
    )
    for row in product_subcategory_rows:
        key = (row.get('category') or '').strip()
        sub_name = (row.get('sub_category') or '').strip()
        if not key or not sub_name:
            continue
        product_subcategory_map[key].append({
            'name': sub_name,
        })
    icon_categories = CategoryIcon.objects.filter(is_active=True).order_by('order', 'id')
    for icon in icon_categories:
        category_key = (icon.category_key or '').strip()
        badge = badge_map.get(category_key)
        sub_categories = subcategory_map.get(category_key) or product_subcategory_map.get(category_key, [])
        header_categories.append({
            'label': icon.name,
            'key': category_key,
            'badge_text': badge['text'] if badge else '',
            'badge_class': badge['class'] if badge else '',
            'has_children': bool(sub_categories),
            'sub_categories': sub_categories,
        })
    if not header_categories:
        excluded_categories = {'TOP_DEALS', 'TOP_SELLING', 'TOP_FEATURED', 'RECOMMENDED'}
        for key, label in Product.CATEGORY_CHOICES:
            if key in excluded_categories:
                continue
            category_key = (key or '').strip()
            sub_categories = subcategory_map.get(category_key) or product_subcategory_map.get(category_key, [])
            header_categories.append({
                'label': label,
                'key': category_key,
                'badge_text': '',
                'badge_class': '',
                'has_children': bool(sub_categories),
                'sub_categories': sub_categories,
            })

    header_links = [
        {'label': 'About Us', 'url_name': 'about'},
        {'label': 'Order Tracking', 'url_name': 'track_order'},
        {'label': 'Contact Us', 'url_name': 'contact'},
        {'label': 'FAQs', 'url_name': 'faq'},
    ]

    header_offer_coupon = None
    header_offer_heading = 'Coupon Offer'
    header_offer_message = 'Apply this code at checkout:'
    try:
        now = timezone.now()
        header_offer_coupon = (
            Coupon.objects
            .filter(is_active=True, valid_from__lte=now, valid_to__gte=now)
            .order_by('coupon_type', '-created_at')
            .first()
        )
        if header_offer_coupon:
            coupon_label_map = {
                'FIRST_ORDER': 'First Order Offer',
                'SPEND_5K': 'Spend 5K Reward',
                'MANUAL': 'Limited Time Offer',
            }
            header_offer_heading = coupon_label_map.get(
                header_offer_coupon.coupon_type,
                'Coupon Offer'
            )
            if header_offer_coupon.description:
                header_offer_message = header_offer_coupon.description.strip()
    except Exception:
        header_offer_coupon = None

    # Build context and cache for 1 hour
    context = {
        'header_categories': header_categories,
        'header_links': header_links,
        'header_offer_coupon': header_offer_coupon,
        'header_offer_heading': header_offer_heading,
        'header_offer_message': header_offer_message,
    }
    
    # Cache the context for performance (1 hour TTL)
    cache.set(cache_key, context, 3600)
    
    return context


def admin_panel_context(request):
    """Add dynamic admin navbar data for custom admin panel."""
    context = {
        'admin_display_name': '',
        'admin_role_label': 'User',
        'admin_avatar_url': '',
        'admin_billing_alert_count': 0,
        'admin_presence_class': 'avatar-offline',
    }

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return context

    context['admin_display_name'] = user.get_full_name() or user.username

    if user.is_superuser:
        context['admin_role_label'] = 'Super Admin'
    elif user.is_staff:
        context['admin_role_label'] = 'Admin'

    try:
        profile = user.userprofile
        if profile.profile_image and profile.profile_image.name != 'profile_images/default.png':
            context['admin_avatar_url'] = profile.profile_image.url
    except Exception:
        pass

    try:
        from Hub.models_security_access import UserSession
        active_cutoff = timezone.now() - timedelta(minutes=15)
        is_online = UserSession.objects.filter(
            user=user,
            status='ACTIVE',
            last_activity__gte=active_cutoff,
        ).exists()
    except Exception:
        last_login = getattr(user, 'last_login', None)
        is_online = bool(last_login and last_login >= (timezone.now() - timedelta(minutes=30)))

    context['admin_presence_class'] = 'avatar-online' if is_online else 'avatar-offline'

    if request.path.startswith('/admin-panel/'):
        try:
            cache_key = 'admin_billing_alert_count'
            cached_count = cache.get(cache_key)
            if cached_count is None:
                cached_count = Order.objects.filter(
                    payment_status__in=['PENDING', 'FAILED']
                ).count()
                cache.set(cache_key, cached_count, 45)
            context['admin_billing_alert_count'] = cached_count
        except Exception:
            context['admin_billing_alert_count'] = 0

    return context
