"""
Context processors for VibeMall
Adds cart, wishlist, and site configuration to every template
Implements caching to optimize database queries
"""
from collections import defaultdict

from django.utils import timezone
from django.core.cache import cache

from .models import Cart, Wishlist, SiteSettings, LoyaltyPoints, CategoryIcon, Product, SubCategory, Coupon
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
            # Create loyalty points account if doesn't exist
            loyalty = LoyaltyPoints.objects.create(user=request.user)
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
    }


def header_menu_context(request):
    """
    Add header menu data to context with caching for performance
    Cache invalidated when categories are updated
    """
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
