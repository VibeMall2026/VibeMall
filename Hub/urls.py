from django.urls import path
from . import views

urlpatterns = [
    # Admin Panel URLs
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/new-dashboard/', views.admin_new_dashboard, name='admin_new_dashboard'),
    path('admin-panel/test/', views.admin_test, name='admin_test'),
    path('admin-panel/add-product/', views.admin_add_product, name='admin_add_product'),
    path('admin-panel/products/', views.admin_product_list, name='admin_product_list'),
    path('admin-panel/products/toggle-stock/<int:product_id>/', views.admin_toggle_stock, name='admin_toggle_stock'),
    path('admin-panel/products/edit/<int:product_id>/', views.admin_edit_product, name='admin_edit_product'),
    path('admin-panel/products/delete/<int:product_id>/', views.admin_delete_product, name='admin_delete_product'),
    path('admin-panel/categories/', views.admin_categories, name='admin_categories'),
    path('admin-panel/subcategories/', views.admin_subcategories, name='admin_subcategories'),
    path('admin-panel/categories/add/', views.admin_add_category, name='admin_add_category'),
    path('admin-panel/categories/edit/<int:category_id>/', views.admin_edit_category, name='admin_edit_category'),
    path('admin-panel/categories/delete/<int:category_id>/', views.admin_delete_category, name='admin_delete_category'),
    path('admin-panel/categories/subcategory/save/', views.admin_save_subcategory_icon, name='admin_save_subcategory_icon'),
    path('admin-panel/edit-photo/', views.admin_edit_photo, name='admin_edit_photo'),
    path('admin-panel/edit-photo/preview/', views.admin_edit_photo_preview, name='admin_edit_photo_preview'),
    path('admin-panel/main-page-products/', views.admin_main_page_products, name='admin_main_page_products'),
    path('admin-panel/brand-partners/', views.admin_brand_partners, name='admin_brand_partners'),
    path('admin-panel/brand-partners/add/', views.admin_add_brand_partner, name='admin_add_brand_partner'),
    path('admin-panel/brand-partners/edit/<int:partner_id>/', views.admin_edit_brand_partner, name='admin_edit_brand_partner'),
    path('admin-panel/brand-partners/delete/<int:partner_id>/', views.admin_delete_brand_partner, name='admin_delete_brand_partner'),
    path('admin-panel/site-settings/', views.admin_site_settings, name='admin_site_settings'),
    path('admin-panel/reviews/', views.admin_reviews, name='admin_reviews'),
    path('admin-panel/orders/', views.admin_orders, name='admin_orders'),
    path('admin-panel/orders/<int:order_id>/', views.admin_order_details, name='admin_order_details'),
    path('admin-panel/orders/<int:order_id>/approve/', views.admin_approve_order, name='admin_approve_order'),
    path('admin-panel/orders/<int:order_id>/reject/', views.admin_reject_order, name='admin_reject_order'),
    path('admin-panel/chat/', views.admin_chat_list, name='admin_chat_list'),
    path('admin-panel/chat/<int:thread_id>/', views.admin_chat_detail, name='admin_chat_detail'),
    path('admin-panel/invoices/', views.admin_invoices, name='admin_invoices'),
    path('admin-panel/invoice-inventory/', views.admin_invoice_inventory, name='admin_invoice_inventory'),
    path('admin-panel/inventory/update-stock/', views.admin_update_inventory, name='admin_update_inventory'),
    path('admin-panel/customers/', views.admin_customers, name='admin_customers'),
    path('admin-panel/customers/<int:customer_id>/', views.admin_customer_details, name='admin_customer_details'),
    path('admin-panel/banners/', views.admin_banners, name='admin_banners'),
    path('admin-panel/banners/add/', views.admin_add_banner, name='admin_add_banner'),
    path('admin-panel/banners/edit/<int:banner_id>/', views.admin_edit_banner, name='admin_edit_banner'),
    path('admin-panel/banners/delete/<int:banner_id>/', views.admin_delete_banner, name='admin_delete_banner'),
    path('admin-panel/sliders/', views.admin_sliders, name='admin_sliders'),
    path('admin-panel/sliders/add/', views.admin_add_slider, name='admin_add_slider'),
    path('admin-panel/sliders/edit/<int:slider_id>/', views.admin_edit_slider, name='admin_edit_slider'),
    path('admin-panel/sliders/delete/<int:slider_id>/', views.admin_delete_slider, name='admin_delete_slider'),
    path('admin-panel/questions/', views.admin_questions, name='admin_questions'),
    path('admin-panel/questions/<int:question_id>/approve/', views.admin_approve_question, name='admin_approve_question'),
    path('admin-panel/questions/<int:question_id>/delete/', views.admin_delete_question, name='admin_delete_question'),
    path('admin-panel/api/orders/search/', views.admin_api_search_orders, name='admin_api_search_orders'),
    path('admin-panel/product/<int:product_id>/adjust-rating/', views.admin_adjust_rating, name='admin_adjust_rating'),
    path('admin-panel/reviews/<int:review_id>/details/', views.admin_review_details, name='admin_review_details'),
    path('admin-panel/reviews/<int:review_id>/approve/', views.admin_approve_review, name='admin_approve_review'),
    path('admin-panel/reviews/<int:review_id>/delete/', views.admin_delete_review, name='admin_delete_review'),
    path('admin-panel/product/<int:product_id>/add-review/', views.admin_add_review, name='admin_add_review'),
    path('admin-panel/returns/', views.admin_returns, name='admin_returns'),
    path('admin-panel/returns/<int:return_id>/', views.admin_return_detail, name='admin_return_detail'),
    path('admin-panel/razorpay/health/', views.admin_razorpay_health, name='admin_razorpay_health'),
    
    # Auth
    path('accounts/login/', views.login_view, name='accounts_login'),

    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('api/profile/stats/', views.api_profile_stats, name='api_profile_stats'),
    path('api/products/search/', views.product_search_api, name='product_search_api'),
    path('api/upi/validate/', views.validate_upi_id, name='validate_upi_id'),
    path('api/ifsc/lookup/', views.lookup_ifsc, name='lookup_ifsc'),
    path('api/cart/summary/', views.cart_summary, name='cart_summary'),

    # Support Chat
    path('chat/thread/', views.chat_thread, name='chat_thread'),
    path('chat/message/', views.chat_message, name='chat_message'),
    
    # Cart URLs
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('cart/toggle/<int:product_id>/', views.ajax_toggle_cart, name='ajax_toggle_cart'),
    path('remove-from-cart/<int:cart_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart-quantity/<int:cart_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    
    # Wishlist URLs
    path('add-to-wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/add/<int:product_id>/', views.ajax_add_to_wishlist, name='ajax_add_to_wishlist'),
    path('ajax-add-to-wishlist/<int:product_id>/', views.ajax_add_to_wishlist, name='ajax_add_to_wishlist_alt'),
    path('check-wishlist/<int:product_id>/', views.check_wishlist, name='check_wishlist'),
    path('remove-from-wishlist/<int:wishlist_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('move-wishlist-to-cart/<int:wishlist_id>/', views.move_wishlist_to_cart, name='move_wishlist_to_cart'),
    
    # Buy Now & Checkout URLs
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/confirm/', views.checkout_confirm, name='checkout_confirm'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('razorpay-payment/<int:order_id>/', views.razorpay_payment, name='razorpay_payment'),
    path('razorpay-payment-success/', views.razorpay_payment_success, name='razorpay_payment_success'),
    path('razorpay-payment-cancel/<int:order_id>/', views.razorpay_payment_cancel, name='razorpay_payment_cancel'),
    path('razorpay-webhook/', views.razorpay_webhook, name='razorpay_webhook'),
    path('admin-panel/orders/<int:order_id>/refund/', views.razorpay_refund, name='razorpay_refund'),
    path('resell-order/<int:order_id>/', views.resell_order, name='resell_order'),
    
    # Order Management URLs
    path('orders/', views.order_list, name='order_list'),
    path('track-order/', views.track_order_page, name='track_order'),
    path('order/download-invoice/<str:order_number>/', views.download_invoice, name='download_invoice'),
    path('order/<str:order_number>/', views.order_details, name='order_details'),
    path('order/<int:order_id>/return/', views.return_request, name='return_request'),
    path('returns/<int:return_id>/', views.return_status, name='return_status'),
    path('order/track/<str:order_number>/', views.order_tracking, name='order_tracking'),
    path('order/cancel/<int:order_id>/', views.customer_cancel_order, name='customer_cancel_order'),
    
    # Review URLs
    path('product/<int:product_id>/submit-review/', views.submit_review, name='submit_review'),
    path('review/<int:review_id>/vote/', views.vote_review, name='vote_review'),
    path('product/<int:product_id>/submit-question/', views.submit_question, name='submit_question'),
    path('product/<int:product_id>/notify/', views.request_stock_notification, name='request_stock_notification'),
    
    # Password Reset URLs
    path('password_reset/', views.password_reset_view, name='password_reset'),
    path('password_reset_done/', views.password_reset_done_view, name='password_reset_done'),
    path('password_reset_confirm/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password_reset_complete/', views.password_reset_complete_view, name='password_reset_complete'),

    # Email Verification URLs
    path('verify-email/', views.verify_email_sent, name='verify_email_sent'),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
]