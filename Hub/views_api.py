"""
API view wrappers.

This module keeps URL routing separated from page/admin handlers without
changing existing request logic. Each function delegates to the current
implementation in `Hub.views`.
"""

from . import views as legacy_views


def api_profile_stats(request):
    return legacy_views.api_profile_stats(request)


def product_search_api(request):
    return legacy_views.product_search_api(request)


def validate_upi_id(request):
    return legacy_views.validate_upi_id(request)


def lookup_ifsc(request):
    return legacy_views.lookup_ifsc(request)


def cart_summary(request):
    return legacy_views.cart_summary(request)


def reel_track_view(request, reel_id):
    return legacy_views.reel_track_view(request, reel_id)


def reel_set_like(request, reel_id):
    return legacy_views.reel_set_like(request, reel_id)


def chat_thread(request):
    return legacy_views.chat_thread(request)


def chat_message(request):
    return legacy_views.chat_message(request)


def subscribe_newsletter(request):
    return legacy_views.subscribe_newsletter(request)


def ajax_toggle_cart(request, product_id):
    return legacy_views.ajax_toggle_cart(request, product_id)


def validate_coupon(request):
    return legacy_views.validate_coupon(request)


def get_available_coupons(request):
    return legacy_views.get_available_coupons(request)
