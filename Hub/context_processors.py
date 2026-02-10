"""
Context processors for FashioHub
Adds cart and wishlist counts to every template
"""
from .models import Cart, Wishlist, SiteSettings, LoyaltyPoints, CategoryIcon, Product
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
    badge_map = {
        'TOP_DEALS': {'text': 'HOT', 'class': ''},
        'TOP_SELLING': {'text': 'HOT', 'class': ''},
        'TOP_FEATURED': {'text': 'HOT', 'class': ''},
        'RECOMMENDED': {'text': 'NEW', 'class': 'green'},
        'GENZ_TRENDS': {'text': 'NEW', 'class': 'green'},
        'NEXT_GEN': {'text': 'NEW', 'class': 'green'},
    }

    header_categories = []
    icon_categories = CategoryIcon.objects.filter(is_active=True).order_by('order', 'id')
    for icon in icon_categories:
        category_key = (icon.category_key or '').strip()
        badge = badge_map.get(category_key)
        header_categories.append({
            'label': icon.name,
            'key': category_key,
            'badge_text': badge['text'] if badge else '',
            'badge_class': badge['class'] if badge else '',
            'has_children': False,
        })
    if not header_categories:
        excluded_categories = {'TOP_DEALS', 'TOP_SELLING', 'TOP_FEATURED', 'RECOMMENDED'}
        for key, label in Product.CATEGORY_CHOICES:
            if key in excluded_categories:
                continue
            header_categories.append({
                'label': label,
                'key': key,
                'badge_text': '',
                'badge_class': '',
                'has_children': False,
            })

    header_links = [
        {'label': 'About Us', 'url_name': 'about'},
        {'label': 'Order Tracking', 'url_name': 'track_order'},
        {'label': 'Contact Us', 'url_name': 'contact'},
        {'label': 'FAQs', 'url_name': 'faq'},
    ]

    return {
        'header_categories': header_categories,
        'header_links': header_links,
    }
