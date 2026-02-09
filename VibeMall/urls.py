from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from Hub import views

urlpatterns = [
    path('admin/new-dashboard/', RedirectView.as_view(url='/admin-panel/new-dashboard/', permanent=False)),
    path('admin/', admin.site.urls),
    path('', include('Hub.urls')),
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('blog/', views.blog, name='blog'),
    path('blog-details/', views.blog_details, name='blog-details'),
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
    path('order-tracking/', views.order_tracking, name='order-tracking'),
    path('register/', views.register_view, name='register'),
    path('add-product/', views.add_product, name='add_product'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)