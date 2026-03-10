"""
New Feature URLs - Added without modifying existing code
"""

from django.urls import path
from . import views_new_features

urlpatterns = [
    # Activity Logs
    path('admin-panel/activity-logs/', views_new_features.admin_activity_logs, name='admin_activity_logs'),
    
    # Discount Coupons
    path('admin-panel/coupons/', views_new_features.admin_coupons, name='admin_coupons'),
    path('admin-panel/coupons/add/', views_new_features.admin_add_coupon, name='admin_add_coupon'),
    path('admin-panel/coupons/edit/<int:coupon_id>/', views_new_features.admin_edit_coupon, name='admin_edit_coupon'),
    
    # Low Stock Alerts
    path('admin-panel/low-stock-alerts/', views_new_features.admin_low_stock_alerts, name='admin_low_stock_alerts'),
    
    # Bulk Operations
    path('admin-panel/bulk-import-products/', views_new_features.admin_bulk_import_products, name='admin_bulk_import_products'),
    path('admin-panel/export-products/', views_new_features.admin_export_products, name='admin_export_products'),
    
    # Sales Reports
    path('admin-panel/sales-reports/', views_new_features.admin_sales_reports, name='admin_sales_reports'),
    
    # Role Management
    path('admin-panel/roles/', views_new_features.admin_roles, name='admin_roles'),
    path('admin-panel/roles/add/', views_new_features.admin_add_role, name='admin_add_role'),
]
