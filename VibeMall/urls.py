from django.contrib import admin
from django.urls import path, include

from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from Hub import views

urlpatterns = [
    path('trading/', include('trading.urls')),
    path('admin/new-dashboard/', RedirectView.as_view(url='/admin-panel/new-dashboard/', permanent=False)),
    path('favicon.ico', RedirectView.as_view(url=f'{settings.STATIC_URL}assets/img/favicon.ico?v=20260426-03', permanent=False)),
    path('admin/', admin.site.urls),
    path('', include('Hub.urls')),
    path('', views.index, name='index'),
    path('spa-home/', views.spa_home, name='spa_home'),
    path('about/', views.about, name='about'),
    path('blog/', views.blog, name='blog'),
    path('blog-details/', views.blog_details, name='blog-details'),
    path('blog/<slug:slug>/', views.blog_details, name='blog_detail_slug'),
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('product/', views.product, name='product'),
    path('product-details/', views.product_details, name='product-details'),
    path('product-details/<int:product_id>/', views.product_details, name='product-details'),
    path('shop/', views.shop, name='shop'),
    path('shop-details/', views.shop_details, name='shop-details'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('404/', views.page_404, name='404'),
    # order_tracking takes an order_number, so this argument-less path raised a
    # TypeError - a 500 - on every request. There was once a second, one-argument
    # order_tracking defined earlier in views.py, but Python kept only the later
    # definition, so this route has never worked. Send it to the real lookup page.
    path('order-tracking/', RedirectView.as_view(pattern_name='track_order', permanent=False),
         name='order-tracking'),
    path('register/', views.register_view, name='register'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms-and-conditions'),
    path('privacy-policy/', views.privacy_policy, name='privacy-policy'),
    path('add-product/', views.add_product, name='add_product'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error Handlers
handler404 = 'Hub.views.custom_404'
handler500 = 'Hub.views.custom_500'
handler403 = 'Hub.views.custom_404'
handler400 = 'Hub.views.custom_404'
