# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CategoryIcon,
    Slider,
    Feature,
    Banner,
    Product,
    ProductImage,
    DealCountdown,
    Cart,
    Wishlist,
    ProductReview,
    ReviewImage,
    ReviewVote,
    ProductQuestion,
    Order,
    OrderItem,
    OrderStatusHistory,
    AdminEmailSettings,
    ProductStockNotification,
    BrandPartner,
    LoyaltyPoints,
    PointsTransaction,
    ReturnRequest,
    WishlistPriceAlert,
    Notification,
    EmailLog,
)

admin.site.register(Slider)

@admin.register(CategoryIcon)
class CategoryIconAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_key', 'icon_preview', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'category_key')
    
    fieldsets = (
        ('📋 BASIC INFO', {
            'fields': ('name', 'category_key'),
            'description': 'Category name and key (must match Product category choices)'
        }),
        ('🎨 ICON & STYLING', {
            'fields': ('icon_class', 'icon_color', 'background_gradient'),
            'description': 'FontAwesome icon class, icon color, and background gradient'
        }),
        ('⚙️ SETTINGS', {
            'fields': ('order', 'is_active'),
            'description': 'Display order and active status'
        }),
    )
    
    def icon_preview(self, obj):
        return format_html(
            '<div style="display: inline-block; background: {}; padding: 10px; border-radius: 8px;"><i class="{}" style="font-size: 20px; color: {};"></i></div>',
            obj.background_gradient,
            obj.icon_class,
            obj.icon_color
        )
    icon_preview.short_description = 'Icon Preview'

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon_class', 'order', 'is_active')
    list_editable = ('order', 'is_active')

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'banner_type', 'button_text', 'order', 'is_active', 'image_thumbnail')
    list_editable = ('order', 'is_active')
    list_filter = ('banner_type', 'is_active', 'button_style')
    search_fields = ('title', 'subtitle', 'badge_text')
    readonly_fields = ('image_preview',)
    
    fieldsets = (
        ('📋 BASIC INFO', {
            'fields': ('title', 'subtitle', 'badge_text', 'banner_type'),
            'description': 'Banner title, subtitle, and badge text'
        }),
        ('🖼️ IMAGE', {
            'fields': ('image', 'image_preview', 'background_color'),
            'description': 'Upload banner image and set background color overlay (optional)'
        }),
        ('🔗 LINK & ACTION', {
            'fields': ('link_url', 'button_text', 'button_style'),
            'description': 'Set link URL and button configuration'
        }),
        ('⚙️ SETTINGS', {
            'fields': ('order', 'is_active'),
            'description': 'Display order and active status'
        }),
    )
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 80px; height: 50px; border-radius: 5px; object-fit: cover;" />',
                obj.image.url
            )
        return '-'
    image_thumbnail.short_description = 'Preview'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 400px; height: auto; border-radius: 8px; border: 1px solid #ddd; padding: 10px;" />',
                obj.image.url
            )
        return 'No image uploaded yet'
    image_preview.short_description = 'Full Preview'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'old_price', 'discount_percent', 'stock', 'rating', 'is_active', 'image_thumbnail')
    list_filter = ('is_active', 'is_top_deal')
    list_editable = ('is_active', 'price', 'stock')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'id', 'slug')
    readonly_fields = ('image_preview',)
    
    fieldsets = (
        ('BASIC INFORMATION', {
            'fields': ('name', 'slug', 'sku', 'is_active', 'is_top_deal'),
            'description': 'Product name, SKU, and status'
        }),
        ('PRODUCT IMAGE', {
            'fields': ('image', 'image_preview'),
            'description': 'Upload a product image (JPEG/PNG, recommended size: 400x400px)'
        }),
        ('DESCRIPTION & DETAILS', {
            'fields': ('description', 'descriptionImage', 'tags'),
            'description': 'Product description, large description image, and tags (comma-separated)'
        }),
        ('PRICING', {
            'fields': ('price', 'old_price', 'discount_percent'),
            'description': 'Set price, old price (for comparison), and discount percentage'
        }),
        ('INVENTORY', {
            'fields': ('stock', 'sold'),
            'description': 'Stock quantity and units sold'
        }),
        ('SPECIFICATIONS', {
            'fields': ('weight', 'dimensions', 'color', 'size', 'brand'),
            'description': 'Product specifications'
        }),
        ('SHIPPING & CARE', {
            'fields': ('shipping_info', 'care_info'),
            'description': 'Shipping and care information'
        }),
        ('RATINGS & REVIEWS', {
            'fields': ('rating', 'review_count'),
            'description': 'Product rating (0-5) and number of reviews'
        }),
    )
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; border-radius: 5px; object-fit: cover;" />',
                obj.image.url
            )
        return '-'
    image_thumbnail.short_description = 'Image'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; height: auto; border-radius: 8px; border: 1px solid #ddd; padding: 10px;" />',
                obj.image.url
            )
        return 'No image uploaded yet'
    image_preview.short_description = 'Image Preview'
    
    def save_model(self, request, obj, form, change):
        if obj.old_price and obj.price:
            discount = ((obj.old_price - obj.price) / obj.old_price) * 100
            if not obj.discount_percent or obj.discount_percent == 0:
                obj.discount_percent = int(discount)
        super().save_model(request, obj, form, change)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ('image', 'order', 'is_active')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'order', 'is_active', 'image_thumbnail')
    list_filter = ('is_active',)
    list_editable = ('order', 'is_active')
    
    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; border-radius: 5px; object-fit: cover;" />',
                obj.image.url
            )
        return '-'
    image_thumbnail.short_description = 'Image'


@admin.register(DealCountdown)
class DealCountdownAdmin(admin.ModelAdmin):
    list_display = ('title', 'end_time', 'is_active')
    list_editable = ('is_active',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'quantity', 'added_at')
    list_filter = ('user', 'added_at')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('added_at', 'updated_at')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'added_at')
    list_filter = ('user', 'added_at')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('added_at',)


@admin.register(ProductStockNotification)
class ProductStockNotificationAdmin(admin.ModelAdmin):
    list_display = ('product', 'email', 'user', 'is_sent', 'created_at', 'notified_at')
    list_filter = ('is_sent', 'created_at', 'notified_at', 'product')
    search_fields = ('email', 'product__name')
    readonly_fields = ('created_at', 'notified_at')


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1
    max_num = 5

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user', 'rating', 'is_approved', 'is_verified_purchase', 'helpful_count', 'created_at')
    list_filter = ('is_approved', 'is_verified_purchase', 'rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'comment')
    readonly_fields = ('created_at', 'updated_at', 'helpful_count', 'not_helpful_count')
    inlines = [ReviewImageInline]
    list_editable = ('is_approved', 'is_verified_purchase')

@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'user', 'is_helpful', 'created_at')
    list_filter = ('is_helpful', 'created_at')
    search_fields = ('review__product__name', 'user__username')

@admin.register(ProductQuestion)
class ProductQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user', 'question_preview', 'is_answered', 'is_approved', 'created_at')
    list_filter = ('is_answered', 'is_approved', 'created_at')
    search_fields = ('product__name', 'user__username', 'question', 'answer')
    readonly_fields = ('created_at', 'user', 'product')
    list_editable = ('is_approved',)
    actions = ['mark_as_answered_and_approved']
    
    fieldsets = (
        ('Question Info', {
            'fields': ('product', 'user', 'question', 'created_at')
        }),
        ('Answer (Required)', {
            'fields': ('answer', 'answered_by', 'answered_at', 'is_answered'),
            'description': 'Answer the question and mark as answered. It will be visible on the product page once approved.'
        }),
        ('Approval', {
            'fields': ('is_approved',),
            'description': 'Approve to show Q&A on product page'
        }),
    )
    
    def question_preview(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
    question_preview.short_description = 'Question'
    
    def mark_as_answered_and_approved(self, request, queryset):
        """Mark selected questions as answered and approved"""
        from django.utils import timezone
        updated = queryset.update(
            is_answered=True,
            is_approved=True,
            answered_by=request.user,
            answered_at=timezone.now()
        )
        self.message_user(request, f'{updated} question(s) marked as answered and approved.')
    mark_as_answered_and_approved.short_description = 'Mark as Answered & Approved'


# ===== ORDER & ORDERITEM ADMIN =====

class OrderItemInline(admin.TabularInline):
    """Inline Order Items display in Order admin"""
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product_price', 'quantity', 'subtotal', 'created_at')
    fields = ('product_name', 'product_price', 'quantity', 'subtotal')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Order Management in Admin Panel"""
    list_display = ('order_number', 'user_name', 'total_amount', 'approval_status_badge', 'payment_status_badge', 'order_status_badge', 'payment_method', 'risk_indicator', 'is_resell_badge', 'created_at', 'approval_actions')
    list_filter = ('approval_status', 'is_suspicious', 'order_status', 'payment_status', 'payment_method', 'is_resell', 'created_at')
    search_fields = ('order_number', 'user__username', 'user__email')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'risk_score', 'approved_by', 'approved_at')
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    actions = ['approve_orders', 'reject_orders']
    
    fieldsets = (
        ('📋 ORDER INFO', {
            'fields': ('order_number', 'user', 'created_at', 'updated_at')
        }),
        ('✅ APPROVAL STATUS', {
            'fields': ('approval_status', 'approval_notes', 'approved_by', 'approved_at'),
            'classes': ('collapse',),
        }),
        ('🚨 FRAUD DETECTION', {
            'fields': ('is_suspicious', 'suspicious_reason', 'risk_score'),
            'classes': ('collapse',),
        }),
        ('💰 PAYMENT DETAILS', {
            'fields': ('subtotal', 'tax', 'shipping_cost', 'total_amount', 'payment_method', 'payment_status', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')
        }),
        ('📦 ORDER STATUS', {
            'fields': ('order_status', 'tracking_number', 'delivery_date')
        }),
        ('📍 ADDRESSES', {
            'fields': ('shipping_address', 'billing_address')
        }),
        ('📝 NOTES', {
            'fields': ('customer_notes', 'admin_notes')
        }),
        ('🔄 RESELL', {
            'fields': ('is_resell',)
        }),
    )
    
    def user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    user_name.short_description = 'Customer'
    
    def approval_status_badge(self, obj):
        colors = {
            'PENDING_APPROVAL': '#ff9800',
            'APPROVED': '#4caf50',
            'REJECTED': '#f44336',
            'AUTO_APPROVED': '#2196f3',
        }
        icons = {
            'PENDING_APPROVAL': '⏳',
            'APPROVED': '✅',
            'REJECTED': '❌',
            'AUTO_APPROVED': '🤖',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{} {}</span>',
            colors.get(obj.approval_status, '#999'),
            icons.get(obj.approval_status, ''),
            obj.get_approval_status_display()
        )
    approval_status_badge.short_description = 'Approval'
    
    def risk_indicator(self, obj):
        if obj.is_suspicious:
            return format_html(
                '<span style="background-color: #f44336; color: white; padding: 5px 10px; border-radius: 3px;" title="{}">🚨 Risk: {}%</span>',
                obj.suspicious_reason,
                obj.risk_score
            )
        elif obj.risk_score > 50:
            return format_html(
                '<span style="background-color: #ff9800; color: white; padding: 5px 10px; border-radius: 3px;">⚠️ {}%</span>',
                obj.risk_score
            )
        return format_html('<span style="color: #4caf50;">✓ Safe</span>')
    risk_indicator.short_description = 'Risk'
    
    def approval_actions(self, obj):
        if obj.approval_status == 'PENDING_APPROVAL':
            return format_html(
                '<a class="button" href="/admin-panel/orders/{}/approve/" style="background-color: #4caf50; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; margin-right: 5px;">✅ Approve</a>'
                '<a class="button" href="/admin-panel/orders/{}/reject/" style="background-color: #f44336; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">❌ Reject</a>',
                obj.id, obj.id
            )
        return '-'
    approval_actions.short_description = 'Actions'
    
    def payment_status_badge(self, obj):
        colors = {
            'PENDING': '#ff9800',
            'PAID': '#4caf50',
            'FAILED': '#f44336',
            'REFUNDED': '#2196f3',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.payment_status, '#999'),
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment Status'
    
    def order_status_badge(self, obj):
        colors = {
            'PENDING': '#ff9800',
            'PROCESSING': '#2196f3',
            'PACKED': '#9c27b0',
            'SHIPPED': '#673ab7',
            'DELIVERED': '#4caf50',
            'CANCELLED': '#f44336',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.order_status, '#999'),
            obj.order_status
        )
    order_status_badge.short_description = 'Order Status'
    
    def is_resell_badge(self, obj):
        if obj.is_resell:
            return format_html('<span style="background-color: #2196f3; color: white; padding: 5px 10px; border-radius: 3px;">🔄 RESELL</span>')
        return '—'
    is_resell_badge.short_description = 'Type'
    
    # Admin Actions
    def approve_orders(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(approval_status='PENDING_APPROVAL').update(
            approval_status='APPROVED',
            approved_by=request.user,
            approved_at=timezone.now(),
            order_status='PROCESSING'
        )
        self.message_user(request, f'{updated} orders approved successfully.')
    approve_orders.short_description = "✅ Approve selected orders"
    
    def reject_orders(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(approval_status='PENDING_APPROVAL').update(
            approval_status='REJECTED',
            approved_by=request.user,
            approved_at=timezone.now(),
            order_status='CANCELLED'
        )
        self.message_user(request, f'{updated} orders rejected.')
    reject_orders.short_description = "❌ Reject selected orders"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """OrderItem Management in Admin Panel"""
    list_display = ('order_number', 'product_name', 'quantity', 'product_price', 'subtotal')
    list_filter = ('created_at', 'order__payment_status')
    search_fields = ('order__order_number', 'product_name')
    readonly_fields = ('product_name', 'product_price', 'product_image', 'subtotal', 'created_at')
    
    fieldsets = (
        ('📦 ORDER INFO', {
            'fields': ('order', 'product')
        }),
        ('📋 PRODUCT DETAILS', {
            'fields': ('product_name', 'product_price', 'product_image')
        }),
        ('🔢 QUANTITY & PRICING', {
            'fields': ('quantity', 'size', 'color', 'subtotal')
        }),
        ('📅 TIMESTAMP', {
            'fields': ('created_at',)
        }),
    )
    
    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order #'
    
    def product_image(self, obj):
        if obj.product_image:
            return format_html(
                '<img src="{}" style="max-width: 100px; height: auto; border-radius: 5px;" />',
                obj.product_image
            )
        return '—'
    product_image.short_description = 'Image'


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('new_status', 'created_at')
    search_fields = ('order__order_number', 'notes')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False


@admin.register(AdminEmailSettings)
class AdminEmailSettingsAdmin(admin.ModelAdmin):
    list_display = ('setting_name', 'admin_email', 'is_active', 'updated_at')
    list_editable = ('admin_email', 'is_active')
    
    def has_add_permission(self, request):
        # Only allow one admin email setting
        return not AdminEmailSettings.objects.exists()


@admin.register(BrandPartner)
class BrandPartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'logo_preview', 'link_url', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'link_url')
    readonly_fields = ('logo_preview_large', 'created_at', 'updated_at')
    
    fieldsets = (
        ('📋 BRAND INFO', {
            'fields': ('name', 'link_url'),
            'description': 'Brand name and optional website URL'
        }),
        ('🖼️ LOGO', {
            'fields': ('logo', 'logo_preview_large'),
            'description': 'Upload brand logo (recommended size: 200x80px)'
        }),
        ('⚙️ SETTINGS', {
            'fields': ('order', 'is_active', 'created_at', 'updated_at'),
            'description': 'Display order and status'
        }),
    )
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-width: 80px; height: 40px; object-fit: contain; border-radius: 4px;" />',
                obj.logo.url
            )
        return '—'
    logo_preview.short_description = 'Logo'
    
    def logo_preview_large(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 100px; object-fit: contain; border: 1px solid #ddd; padding: 10px; border-radius: 5px; background: #f9f9f9;" />',
                obj.logo.url
            )
        return 'No logo uploaded'
    logo_preview_large.short_description = 'Logo Preview'


# ============================================
# NEW FEATURES - Admin Registration
# ============================================

@admin.register(LoyaltyPoints)
class LoyaltyPointsAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_points', 'points_used', 'points_available', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'transaction_type', 'description', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'description')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('return_number', 'user', 'order', 'reason', 'status', 'refund_amount', 'requested_at')
    list_filter = ('status', 'reason', 'requested_at')
    search_fields = ('return_number', 'user__username', 'order__order_number')
    readonly_fields = ('return_number', 'requested_at', 'created_at', 'updated_at')

    fieldsets = (
        ('Return Information', {
            'fields': ('return_number', 'order', 'user', 'order_item')
        }),
        ('Reason & Details', {
            'fields': ('reason', 'reason_notes', 'description', 'images')
        }),
        ('Status & Workflow', {
            'fields': (
                'status',
                'approved_at',
                'pickup_scheduled_at',
                'received_at',
                'qc_checked_at',
                'resolved_at',
                'admin_notes'
            )
        }),
        ('Refund Information', {
            'fields': ('refund_amount', 'refund_method')
        }),
        ('Request Meta', {
            'fields': ('request_ip', 'request_user_agent')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'created_at', 'updated_at')
        }),
    )


@admin.register(WishlistPriceAlert)
class WishlistPriceAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'original_price', 'target_price', 'is_active', 'notified')
    list_filter = ('is_active', 'notified', 'created_at')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ('email_to', 'email_type', 'subject', 'sent_successfully', 'sent_at')
    list_filter = ('email_type', 'sent_successfully', 'sent_at')
    search_fields = ('email_to', 'subject', 'user__username')
    readonly_fields = ('sent_at',)
    date_hierarchy = 'sent_at'
