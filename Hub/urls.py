from django.urls import path, include
from . import views
from . import views_api
from . import views_resell
from . import views_admin_resell
from . import backup_views
from . import views_new_features

urlpatterns = [
    path('coming-soon/', views.coming_soon, name='coming_soon'),

    # Admin Panel URLs
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/new-dashboard/', views.admin_new_dashboard, name='admin_new_dashboard'),
    path('admin-panel/test/', views.admin_test, name='admin_test'),
    path('admin-panel/add-product/', views.admin_add_product, name='admin_add_product'),
    path('admin-panel/products/upload-reel/', views.admin_upload_reel_file, name='admin_upload_reel_file'),
    path('admin-panel/products/', views.admin_product_list, name='admin_product_list'),
    path('admin-panel/products/toggle-stock/<int:product_id>/', views.admin_toggle_stock, name='admin_toggle_stock'),
    path('admin-panel/products/edit/<int:product_id>/', views.admin_edit_product, name='admin_edit_product'),
    path('admin-panel/products/delete/<int:product_id>/', views.admin_delete_product, name='admin_delete_product'),
    path('admin-panel/products/gallery-image/delete/<int:image_id>/', views.admin_delete_gallery_image, name='admin_delete_gallery_image'),
    path('admin-panel/categories/', views.admin_categories, name='admin_categories'),
    path('admin-panel/subcategories/', views.admin_subcategories, name='admin_subcategories'),
    path('admin-panel/categories/add/', views.admin_add_category, name='admin_add_category'),
    path('admin-panel/categories/edit/<int:category_id>/', views.admin_edit_category, name='admin_edit_category'),
    path('admin-panel/categories/delete/<int:category_id>/', views.admin_delete_category, name='admin_delete_category'),
    path('admin-panel/categories/subcategory/save/', views.admin_save_subcategory_icon, name='admin_save_subcategory_icon'),
    path('admin-panel/edit-photo/', views.admin_edit_photo, name='admin_edit_photo'),
    path('admin-panel/edit-photo/preview/', views.admin_edit_photo_preview, name='admin_edit_photo_preview'),
    path('admin-panel/main-page-products/', views.admin_main_page_products, name='admin_main_page_products'),
    path('admin-panel/ready-ship-styles/', views.admin_ready_ship_styles, name='admin_ready_ship_styles'),
    path('admin-panel/brand-partners/', views.admin_brand_partners, name='admin_brand_partners'),
    path('admin-panel/brand-partners/add/', views.admin_add_brand_partner, name='admin_add_brand_partner'),
    path('admin-panel/brand-partners/edit/<int:partner_id>/', views.admin_edit_brand_partner, name='admin_edit_brand_partner'),
    path('admin-panel/brand-partners/delete/<int:partner_id>/', views.admin_delete_brand_partner, name='admin_delete_brand_partner'),
    path('admin-panel/site-settings/', views.admin_site_settings, name='admin_site_settings'),
    path('admin-panel/newsletter/', views.admin_newsletter_subscribers, name='admin_newsletter_subscribers'),
    path('admin-panel/reviews/', views.admin_reviews, name='admin_reviews'),
    path('admin-panel/orders/', views.admin_orders, name='admin_orders'),
    path('admin-panel/orders/<int:order_id>/', views.admin_order_details, name='admin_order_details'),
    path('admin-panel/orders/<int:order_id>/approve/', views.admin_approve_order, name='admin_approve_order'),
    path('admin-panel/orders/<int:order_id>/reject/', views.admin_reject_order, name='admin_reject_order'),
    path('admin-panel/orders/<int:order_id>/delete/', views.admin_delete_order, name='admin_delete_order'),
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
    path('admin-panel/main-page-banners/', views.admin_main_page_banners, name='admin_main_page_banners'),
    path('admin-panel/main-page-banners/add/', views.admin_add_main_page_banner, name='admin_add_main_page_banner'),
    path('admin-panel/main-page-banners/edit/<int:banner_id>/', views.admin_edit_main_page_banner, name='admin_edit_main_page_banner'),
    path('admin-panel/main-page-banners/delete/<int:banner_id>/', views.admin_delete_main_page_banner, name='admin_delete_main_page_banner'),
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
    path('admin-panel/returns-analytics/', views.admin_return_analytics, name='admin_return_analytics'),
    path('admin-panel/rto/', views.admin_rto_cases, name='admin_rto_cases'),
    path('admin-panel/rto/<int:rto_id>/', views.admin_rto_detail, name='admin_rto_detail'),
    path('admin-panel/marketing-studio/', views.admin_marketing_studio, name='admin_marketing_studio'),
    path('admin-panel/razorpay/health/', views.admin_razorpay_health, name='admin_razorpay_health'),

    # Backup Management (Local D Drive)
    path('admin-panel/backup/', backup_views.backup_dashboard, name='admin_backup_dashboard'),
    path('admin-panel/backup/configuration/', backup_views.backup_configuration, name='admin_backup_configuration'),
    path('admin-panel/backup/history/', backup_views.backup_history, name='admin_backup_history'),
    path('admin-panel/backup/analytics/', backup_views.backup_analytics, name='admin_backup_analytics'),
    path('admin-panel/backup/manual/', backup_views.create_manual_backup, name='admin_create_manual_backup'),
    path('admin-panel/backup/special/', backup_views.create_special_backup, name='admin_create_special_backup'),
    path('admin-panel/backup/<int:backup_id>/', backup_views.backup_detail, name='admin_backup_detail'),
    path('admin-panel/backup/api/status/', backup_views.api_backup_status, name='admin_api_backup_status'),
    path('admin-panel/backup/api/data-stats/', backup_views.api_data_stats, name='admin_api_data_stats'),
    path('admin-panel/backup/cleanup/<uuid:token>/', backup_views.cleanup_confirmation, name='admin_backup_cleanup_confirmation'),

    # ITR Financial Reports
    path('admin-panel/backup/itr-reports/', backup_views.itr_reports, name='admin_itr_reports'),
    
    # Resell Management URLs (Admin Panel)
    path('admin-panel/resell/orders/', views_admin_resell.admin_resell_orders, name='admin_resell_orders'),
    path('admin-panel/resell/analytics/', views_admin_resell.admin_reseller_analytics, name='admin_reseller_analytics'),
    path('admin-panel/resell/reports/', views_admin_resell.admin_resell_reports, name='admin_resell_reports'),
    path('admin-panel/resell/resellers/', views_admin_resell.admin_reseller_management, name='admin_reseller_management'),
    path('admin-panel/resell/payment-data/', views_admin_resell.admin_reseller_payment_data, name='admin_reseller_payment_data'),
    path('admin-panel/resell/resellers/<int:reseller_id>/toggle/', views_admin_resell.admin_toggle_reseller_status, name='admin_toggle_reseller_status'),
    path('admin-panel/resell/payouts/', views_admin_resell.admin_payout_management, name='admin_payout_management'),
    path('admin-panel/resell/payouts/process/', views_admin_resell.admin_process_payout, name='admin_process_payout'),
    path('admin-panel/resell/payouts/<int:payout_id>/approve/', views_admin_resell.admin_approve_payout, name='admin_approve_payout'),
    path('admin-panel/resell/payouts/<int:payout_id>/reject/', views_admin_resell.admin_reject_payout, name='admin_reject_payout'),
    path('admin-panel/resell/payouts/<int:payout_id>/invoice/', views_admin_resell.admin_download_payout_invoice, name='admin_download_payout_invoice'),
    
    # Reel Management URLs
    path('admin-panel/reels/', views.admin_reels, name='admin_reels'),
    path('admin-panel/reels/studio/', views.reel_studio, name='reel_studio'),
    path('admin-panel/reels/studio/export/', views.reel_studio_export, name='reel_studio_export'),
    path('admin-panel/reels/add/', views.admin_add_reel, name='admin_add_reel'),
    path('admin-panel/reels/<int:reel_id>/edit/', views.admin_edit_reel, name='admin_edit_reel'),
    path('admin-panel/reels/<int:reel_id>/delete/', views.admin_delete_reel, name='admin_delete_reel'),
    path('admin-panel/reels/<int:reel_id>/details/', views.admin_reel_details, name='admin_reel_details'),
    path('admin-panel/reels/<int:reel_id>/generate/', views.admin_generate_reel, name='admin_generate_reel'),
    
    # Auth
    path('accounts/login/', views.login_view, name='accounts_login'),

    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/address-book/', views.address_book_view, name='address_book'),
    path('profile/payment-methods/', views.payment_methods_view, name='payment_methods'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('api/profile/stats/', views_api.api_profile_stats, name='api_profile_stats'),
    path('api/products/search/', views_api.product_search_api, name='product_search_api'),
    path('api/upi/validate/', views_api.validate_upi_id, name='validate_upi_id'),
    path('api/ifsc/lookup/', views_api.lookup_ifsc, name='lookup_ifsc'),
    path('api/cart/summary/', views_api.cart_summary, name='cart_summary'),
    path('reels/<int:reel_id>/track-view/', views_api.reel_track_view, name='reel_track_view'),
    path('reels/<int:reel_id>/like/', views_api.reel_set_like, name='reel_set_like'),

    # Support Chat
    path('chat/thread/', views_api.chat_thread, name='chat_thread'),
    path('chat/message/', views_api.chat_message, name='chat_message'),
    path('newsletter/subscribe/', views_api.subscribe_newsletter, name='subscribe_newsletter'),
    
    # Cart URLs
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('cart/toggle/<int:product_id>/', views_api.ajax_toggle_cart, name='ajax_toggle_cart'),
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
    path('api/razorpay-webhook/', views.razorpay_webhook, name='razorpay_webhook'),
    path('admin-panel/orders/<int:order_id>/refund/', views.razorpay_refund, name='razorpay_refund'),
    path('resell-order/<int:order_id>/', views.resell_order, name='resell_order'),
    
    # Order Management URLs
    path('orders/', views.order_list, name='order_list'),
    path('track-order/', views.track_order_page, name='track_order'),
    path('order/download-invoice/<str:order_number>/', views.download_invoice, name='download_invoice'),
    path('order/<str:order_number>/', views.order_details, name='order_details'),
    path('order/<int:order_id>/return/', views.return_request, name='return_request'),
    path('verify-upi/', views.verify_upi, name='verify_upi'),
    
    # New Verification and Refund Endpoints
    path('api/refund/', views.process_refund_endpoint, name='process_refund'),
    path('api/verify-bank/', views.verify_bank_endpoint, name='verify_bank'),
    path('api/verify-upi-collect/', views.create_upi_collect_endpoint, name='verify_upi_collect'),
    path('api/verify-upi-collect-status/', views.verify_upi_collect_status_endpoint, name='verify_upi_collect_status'),
    path('api/verify-bank-transfer/', views.verify_bank_transfer_endpoint, name='verify_bank_transfer'),
    
    path('returns/<int:return_id>/', views.return_status, name='return_status'),
    path('order/track/<str:order_number>/', views.order_tracking, name='order_tracking'),
    path('order/cancel/<int:order_id>/', views.customer_cancel_order, name='customer_cancel_order'),
    
    # Review URLs
    path('product/<int:product_id>/submit-review/', views.submit_review, name='submit_review'),
    path('review/<int:review_id>/vote/', views.vote_review, name='vote_review'),
    path('mobile-review-prompt/dismiss/', views.mobile_review_prompt_dismiss, name='mobile_review_prompt_dismiss'),
    path('mobile-review-prompt/submit/<int:product_id>/', views.mobile_review_prompt_submit, name='mobile_review_prompt_submit'),
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
    
    # Coupon System URLs
    path('api/validate-coupon/', views_api.validate_coupon, name='validate_coupon'),
    path('api/available-coupons/', views_api.get_available_coupons, name='available_coupons'),
    
    # ============================================
    # RESELL FEATURE URLs
    # ============================================
    
    # Resell Link Management API
    path('api/resell/create-link/', views_resell.create_resell_link, name='create_resell_link'),
    path('api/resell/my-links/', views_resell.my_resell_links, name='my_resell_links'),
    path('api/resell/deactivate-link/', views_resell.deactivate_resell_link, name='deactivate_resell_link'),
    path('api/resell/reactivate-link/', views_resell.reactivate_resell_link, name='reactivate_resell_link'),
    
    # Reseller Dashboard Pages
    path('reseller/dashboard/', views_resell.reseller_dashboard, name='reseller_dashboard'),
    path('reseller/links/', views_resell.reseller_links_page, name='reseller_links'),
    path('reseller/earnings/', views_resell.earnings_history, name='earnings_history'),
    path('reseller/profile/', views_resell.reseller_profile_page, name='reseller_profile'),
    
    # Payout Management
    path('reseller/payout/', views_resell.payout_request_page, name='payout_request_page'),
    path('api/resell/request-payout/', views_resell.request_payout, name='request_payout'),
]

# Include new feature URLs
urlpatterns += [
    # Activity Logs
    path('admin-panel/activity-logs/', views_new_features.admin_activity_logs, name='admin_activity_logs'),
    
    # Discount Coupons
    path('admin-panel/coupons/', views_new_features.admin_coupons, name='admin_coupons'),
    path('admin-panel/coupons/add/', views_new_features.admin_add_coupon, name='admin_add_coupon'),
    path('admin-panel/coupons/edit/<int:coupon_id>/', views_new_features.admin_edit_coupon, name='admin_edit_coupon'),
    path('admin-panel/coupons/<int:coupon_id>/toggle-status/', views_new_features.toggle_coupon_status, name='toggle_coupon_status'),
    path('admin-panel/coupons/<int:coupon_id>/delete/', views_new_features.delete_coupon, name='delete_coupon'),
    
    # Low Stock Alerts
    path('admin-panel/low-stock-alerts/', views_new_features.admin_low_stock_alerts, name='admin_low_stock_alerts'),
    path('admin-panel/low-stock-alerts/check/', views_new_features.check_low_stock, name='check_low_stock'),
    path('admin-panel/low-stock-alerts/<int:alert_id>/update-status/', views_new_features.update_alert_status, name='update_alert_status'),
    path('admin-panel/low-stock-alerts/<int:alert_id>/delete/', views_new_features.delete_alert, name='delete_alert'),
    
    # Bulk Operations
    path('admin-panel/bulk-import-products/', views_new_features.admin_bulk_import_products, name='admin_bulk_import_products'),
    path('admin-panel/export-products/', views_new_features.admin_export_products, name='admin_export_products'),
    
    # Sales Reports
    path('admin-panel/sales-reports/', views_new_features.admin_sales_reports, name='admin_sales_reports'),
    path('admin-panel/sales-reports/generate/', views_new_features.generate_sales_report, name='generate_sales_report'),
    path('admin-panel/sales-reports/<int:report_id>/delete/', views_new_features.delete_sales_report, name='delete_sales_report'),
    
    # Role Management
    path('admin-panel/roles/', views_new_features.admin_roles, name='admin_roles'),
    path('admin-panel/roles/add/', views_new_features.admin_add_role, name='admin_add_role'),
    path('admin-panel/roles/edit/<int:role_id>/', views_new_features.admin_edit_role, name='admin_edit_role'),
    path('admin-panel/roles/assign/', views_new_features.assign_user_role, name='admin_assign_role'),
    path('admin-panel/roles/<int:role_id>/toggle-status/', views_new_features.toggle_role_status, name='toggle_role_status'),
    path('admin-panel/roles/<int:role_id>/delete/', views_new_features.delete_role, name='delete_role'),
]

# Include comprehensive feature URLs
from Hub import views_comprehensive_features

urlpatterns += [
    # Customer Insights & CRM
    path('admin-panel/customer-segmentation/', views_comprehensive_features.admin_customer_segmentation, name='admin_customer_segmentation'),
    path('admin-panel/customer-segmentation/add/', views_comprehensive_features.admin_add_customer_segment, name='admin_add_customer_segment'),
    path('admin-panel/support-tickets/', views_comprehensive_features.admin_customer_support_tickets, name='admin_customer_support_tickets'),
    
    # Financial Management
    path('admin-panel/profit-loss/', views_comprehensive_features.admin_profit_loss_statements, name='admin_profit_loss_statements'),
    path('admin-panel/profit-loss/generate/', views_comprehensive_features.admin_generate_pl_statement, name='admin_generate_pl_statement'),
    path('admin-panel/expenses/', views_comprehensive_features.admin_expense_management, name='admin_expense_management'),
    
    # Product Enhancements
    path('admin-panel/product-variants/', views_comprehensive_features.admin_product_variants, name='admin_product_variants'),
    path('admin-panel/product-bundles/', views_comprehensive_features.admin_product_bundles, name='admin_product_bundles'),
    path('admin-panel/product-seo/', views_comprehensive_features.admin_product_seo, name='admin_product_seo'),
    
    # Security & Access Control
    path('admin-panel/security-roles/', views_comprehensive_features.admin_security_roles, name='admin_security_roles'),
    path('admin-panel/security-audit/', views_comprehensive_features.admin_security_audit_log, name='admin_security_audit_log'),
    path('admin-panel/user-sessions/', views_comprehensive_features.admin_user_sessions, name='admin_user_sessions'),
    
    # Content Management
    path('admin-panel/blog-management/', views_comprehensive_features.admin_blog_management, name='admin_blog_management'),
    path('admin-panel/faq-management/', views_comprehensive_features.admin_faq_management, name='admin_faq_management'),
    path('admin-panel/email-templates/', views_comprehensive_features.admin_email_templates, name='admin_email_templates'),
    
    # Performance Optimization
    path('admin-panel/performance/', views_comprehensive_features.admin_performance_dashboard, name='admin_performance_dashboard'),
    path('admin-panel/image-optimization/', views_comprehensive_features.admin_image_optimization, name='admin_image_optimization'),
    
    # AI/ML Features
    path('admin-panel/recommendation-engines/', views_comprehensive_features.admin_recommendation_engines, name='admin_recommendation_engines'),
    path('admin-panel/dynamic-pricing/', views_comprehensive_features.admin_dynamic_pricing, name='admin_dynamic_pricing'),
    path('admin-panel/fraud-detection/', views_comprehensive_features.admin_fraud_detection, name='admin_fraud_detection'),
    path('admin-panel/chatbot-management/', views_comprehensive_features.admin_chatbot_management, name='admin_chatbot_management'),
    
    # AJAX Endpoints
    path('admin-panel/ajax/update-customer-segment/', views_comprehensive_features.ajax_update_customer_segment, name='ajax_update_customer_segment'),
    path('admin-panel/ajax/terminate-session/', views_comprehensive_features.ajax_terminate_user_session, name='ajax_terminate_user_session'),
    
    # Export Functions
    path('admin-panel/export/comprehensive-analytics/', views_comprehensive_features.export_comprehensive_analytics, name='export_comprehensive_analytics'),
]


# Additional comprehensive feature URLs
urlpatterns += [
    # Marketing Automation
    path('admin-panel/flash-sales/', views_comprehensive_features.admin_flash_sales, name='admin_flash_sales'),
    path('admin-panel/email-campaigns/', views_comprehensive_features.admin_email_campaigns, name='admin_email_campaigns'),
    path('admin-panel/whatsapp-campaigns/', views_comprehensive_features.admin_whatsapp_campaigns, name='admin_whatsapp_campaigns'),
    
    # Analytics & Reports
    path('admin-panel/sales-comparison/', views_comprehensive_features.admin_sales_comparison, name='admin_sales_comparison'),
    path('admin-panel/product-performance/', views_comprehensive_features.admin_product_performance, name='admin_product_performance'),
    path('admin-panel/customer-clv/', views_comprehensive_features.admin_customer_clv, name='admin_customer_clv'),
    path('admin-panel/abandoned-carts/', views_comprehensive_features.admin_abandoned_carts, name='admin_abandoned_carts'),
    
    # Financial Management
    path('admin-panel/gst-reports/', views_comprehensive_features.admin_gst_reports, name='admin_gst_reports'),
    path('admin-panel/payment-reconciliation/', views_comprehensive_features.admin_payment_reconciliation, name='admin_payment_reconciliation'),
    
    # Operations
    path('admin-panel/inventory-forecast/', views_comprehensive_features.admin_inventory_forecast, name='admin_inventory_forecast'),
    path('admin-panel/related-products/', views_comprehensive_features.admin_related_products, name='admin_related_products'),
    
    # Content Management
    path('admin-panel/page-builder/', views_comprehensive_features.admin_page_builder, name='admin_page_builder'),
]
