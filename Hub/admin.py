# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db import models as django_models
from .email_utils import send_order_status_update_email
from .models import (
    CategoryIcon,
    Slider,
    Feature,
    Banner,
    MainPageBanner,
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
    Reel,
    ReelImage,
    NewsletterSubscription,
    # Resell feature models
    ResellLink,
    ResellerProfile,
    ResellerEarning,
    PayoutTransaction,
    # Webhook logging models
    WebhookLog,
    VerificationTestLog,
)

# Import improved Reel admin classes
from .admin_reel_reorder import ReelAdminImproved, ReelImageAdminImproved

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

@admin.register(MainPageBanner)
class MainPageBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'banner_area_display', 'order', 'is_active', 'image_thumbnail')
    list_filter = ('banner_area', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('title', 'badge_text', 'description')
    readonly_fields = ('image_preview', 'created_at', 'updated_at')
    
    fieldsets = (
        ('📍 BANNER AREA', {
            'fields': ('banner_area',),
            'description': 'Select which banner area this banner belongs to'
        }),
        ('📋 CONTENT', {
            'fields': ('badge_text', 'title', 'description'),
            'description': 'Badge text, title, and description text'
        }),
        ('🖼️ IMAGE', {
            'fields': ('image', 'image_preview'),
            'description': 'Upload banner image (recommended size: 600x400px)'
        }),
        ('🔗 LINK & SETTINGS', {
            'fields': ('link_url', 'order', 'is_active'),
            'description': 'Set link URL, display order, and active status'
        }),
        ('⏰ METADATA', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Creation and update timestamps'
        }),
    )
    
    def banner_area_display(self, obj):
        area_names = {
            'first': '🎯 Promotion area 3 card',
            'second': '🎯 Marketing area 2 card',
        }
        return area_names.get(obj.banner_area, obj.get_banner_area_display())
    banner_area_display.short_description = 'Banner Area'
    
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


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ('image', 'order', 'is_active')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'old_price', 'discount_percent', 'stock', 'rating', 'is_active', 'image_thumbnail')
    list_filter = ('is_active', 'is_top_deal')
    list_editable = ('is_active', 'price', 'stock')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'id', 'slug')
    readonly_fields = ('image_preview',)
    inlines = [ProductImageInline]
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
    fields = ('image', 'color', 'order', 'is_active')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'color', 'order', 'is_active', 'image_thumbnail')
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


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'is_active',
        'source_page_display',
        'ip_address',
        'user_agent_display',
        'subscribed_at',
        'updated_at',
    )
    list_filter = ('is_active', 'source_page', 'subscribed_at')
    search_fields = ('email', 'source_page', 'ip_address', 'user_agent')
    readonly_fields = ('ip_address', 'user_agent', 'subscribed_at', 'updated_at', 'unsubscribed_at')

    def source_page_display(self, obj):
        return obj.source_page or 'Unknown'
    source_page_display.short_description = 'Source'
    source_page_display.admin_order_field = 'source_page'

    def user_agent_display(self, obj):
        if not obj.user_agent:
            return '-'
        if len(obj.user_agent) <= 80:
            return obj.user_agent
        return f"{obj.user_agent[:77]}..."
    user_agent_display.short_description = 'User Agent'

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
            'fields': ('is_resell', 'reseller', 'resell_link', 'base_amount', 'total_margin', 'resell_from_name', 'resell_from_phone')
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
                '<a class="button" href="/admin-panel/orders/{}/reject/" style="background-color: #f44336; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; margin-right: 5px;">❌ Reject</a>'
                '<a class="button" href="/admin-panel/orders/{}/delete/" onclick="return confirm(\'Are you sure you want to delete this order? This action cannot be undone.\');" style="background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">🗑️ Delete</a>',
                obj.id, obj.id, obj.id
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
        from .email_utils import send_order_approval_email
        
        orders_to_approve = queryset.filter(approval_status='PENDING_APPROVAL')
        updated = 0
        email_sent_count = 0
        
        for order in orders_to_approve:
            order.approval_status = 'APPROVED'
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.order_status = 'PROCESSING'
            order.save()
            updated += 1
            
            # Send approval email
            if send_order_approval_email(order, approved_by=request.user):
                email_sent_count += 1
        
        message = f'{updated} orders approved successfully.'
        if email_sent_count < updated:
            message += f' {email_sent_count}/{updated} approval emails sent. Check logs for failures.'
        
        self.message_user(request, message)
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

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            try:
                old_status = Order.objects.only('order_status').get(pk=obj.pk).order_status
            except Order.DoesNotExist:
                old_status = None

        super().save_model(request, obj, form, change)

        if change and old_status and old_status != obj.order_status:
            OrderStatusHistory.objects.create(
                order=obj,
                old_status=old_status,
                new_status=obj.order_status,
                changed_by=request.user,
                notes='Status updated from Django admin',
            )

            sent = send_order_status_update_email(obj, old_status, obj.order_status)
            if sent:
                self.message_user(request, f'Status email sent to {obj.user.email}.')
            else:
                self.message_user(request, 'Order status updated, but email failed. Check SMTP env and logs.', level='warning')


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



# ============================================
# REEL MANAGEMENT
# ============================================

class ReelImageInline(admin.TabularInline):
    """Inline Reel Images in Reel admin"""
    model = ReelImage
    extra = 3
    fields = ('image', 'order', 'text_overlay', 'text_position', 'text_color', 'text_size')
    ordering = ['order']


# Reel Admin - Use improved admin module with better UX
# First unregister if already registered (to avoid "already registered" errors)
try:
    admin.site.unregister(Reel)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(ReelImage)
except admin.sites.NotRegistered:
    pass

# Register with improved admin classes
admin.site.register(Reel, ReelAdminImproved)
admin.site.register(ReelImage, ReelImageAdminImproved)


# ============================================
# RESELL FEATURE ADMIN
# ============================================

@admin.register(ResellLink)
class ResellLinkAdmin(admin.ModelAdmin):
    """Resell Link Management"""
    list_display = ('resell_code', 'reseller_name', 'product_name', 'margin_amount', 'margin_percentage', 
                    'is_active', 'views_count', 'orders_count', 'total_earnings', 'created_at')
    list_filter = ('is_active', 'created_at', 'reseller')
    search_fields = ('resell_code', 'reseller__username', 'reseller__email', 'product__name')
    readonly_fields = ('resell_code', 'margin_percentage', 'views_count', 'orders_count', 'total_earnings', 'created_at')
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Link Information', {
            'fields': ('resell_code', 'reseller', 'product', 'is_active')
        }),
        ('Margin Details', {
            'fields': ('margin_amount', 'margin_percentage')
        }),
        ('Statistics', {
            'fields': ('views_count', 'orders_count', 'total_earnings')
        }),
        ('Dates', {
            'fields': ('created_at', 'expires_at')
        }),
    )
    
    def reseller_name(self, obj):
        return obj.reseller.username
    reseller_name.short_description = 'Reseller'
    reseller_name.admin_order_field = 'reseller__username'
    
    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = 'Product'
    product_name.admin_order_field = 'product__name'


@admin.register(ResellerProfile)
class ResellerProfileAdmin(admin.ModelAdmin):
    """Reseller Profile Management"""
    list_display = ('user_name', 'is_reseller_enabled', 'business_name', 'total_earnings', 
                    'available_balance', 'total_orders', 'created_at')
    list_filter = ('is_reseller_enabled', 'created_at')
    search_fields = ('user__username', 'user__email', 'business_name', 'pan_number')
    readonly_fields = ('total_earnings', 'available_balance', 'total_orders', 'created_at', 'updated_at')
    list_per_page = 50
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'is_reseller_enabled', 'business_name')
        }),
        ('Earnings & Balance', {
            'fields': ('total_earnings', 'available_balance', 'total_orders')
        }),
        ('Payment Details', {
            'fields': ('bank_account_name', 'bank_account_number', 'bank_ifsc_code', 'upi_id', 'pan_number')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_name(self, obj):
        return obj.user.username
    user_name.short_description = 'User'
    user_name.admin_order_field = 'user__username'


@admin.register(ResellerEarning)
class ResellerEarningAdmin(admin.ModelAdmin):
    """Reseller Earning Management"""
    list_display = ('reseller_name', 'order_number', 'margin_amount', 'status', 
                    'confirmed_at', 'paid_at', 'created_at')
    list_filter = ('status', 'created_at', 'confirmed_at', 'paid_at')
    search_fields = ('reseller__username', 'order__order_number')
    readonly_fields = ('reseller', 'order', 'resell_link', 'margin_amount', 'created_at')
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Earning Information', {
            'fields': ('reseller', 'order', 'resell_link', 'margin_amount')
        }),
        ('Status', {
            'fields': ('status', 'confirmed_at', 'paid_at', 'payout_transaction')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    actions = ['confirm_earnings', 'cancel_earnings']
    
    def reseller_name(self, obj):
        return obj.reseller.username
    reseller_name.short_description = 'Reseller'
    reseller_name.admin_order_field = 'reseller__username'
    
    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order'
    order_number.admin_order_field = 'order__order_number'
    
    def confirm_earnings(self, request, queryset):
        """Confirm selected earnings"""
        from .resell_services import confirm_reseller_earnings
        from django.core.exceptions import ValidationError
        
        confirmed_count = 0
        error_count = 0
        
        for earning in queryset.filter(status='PENDING'):
            try:
                confirm_reseller_earnings(earning.order)
                confirmed_count += 1
            except ValidationError as e:
                error_count += 1
                self.message_user(request, f'Error confirming earning for order #{earning.order.order_number}: {str(e)}', level='error')
            except Exception as e:
                error_count += 1
                self.message_user(request, f'Unexpected error for order #{earning.order.order_number}: {str(e)}', level='error')
        
        if confirmed_count > 0:
            self.message_user(request, f'{confirmed_count} earnings confirmed successfully.')
        if error_count > 0:
            self.message_user(request, f'{error_count} earnings could not be confirmed.', level='warning')
    confirm_earnings.short_description = 'Confirm selected earnings'
    
    def cancel_earnings(self, request, queryset):
        """Cancel selected earnings"""
        cancelled_count = queryset.filter(status='PENDING').update(status='CANCELLED')
        self.message_user(request, f'{cancelled_count} earnings cancelled.')
    cancel_earnings.short_description = 'Cancel selected earnings'


@admin.register(PayoutTransaction)
class PayoutTransactionAdmin(admin.ModelAdmin):
    """Payout Transaction Management"""
    list_display = ('reseller_name', 'amount', 'payout_method', 'status', 
                    'transaction_id', 'initiated_at', 'completed_at')
    list_filter = ('status', 'payout_method', 'initiated_at', 'completed_at')
    search_fields = ('reseller__username', 'transaction_id', 'bank_account', 'upi_id')
    readonly_fields = ('reseller', 'amount', 'initiated_at')
    list_per_page = 50
    date_hierarchy = 'initiated_at'
    
    fieldsets = (
        ('Payout Information', {
            'fields': ('reseller', 'amount', 'payout_method', 'status')
        }),
        ('Payment Details', {
            'fields': ('transaction_id', 'bank_account', 'upi_id')
        }),
        ('Admin Notes', {
            'fields': ('admin_notes',)
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'completed_at')
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def reseller_name(self, obj):
        return obj.reseller.username
    reseller_name.short_description = 'Reseller'
    reseller_name.admin_order_field = 'reseller__username'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected payouts as completed"""
        from django.utils import timezone
        
        completed_count = 0
        for payout in queryset.filter(status='INITIATED'):
            payout.status = 'COMPLETED'
            payout.completed_at = timezone.now()
            payout.save()
            
            # Mark only earnings reserved for this payout as PAID.
            ResellerEarning.objects.filter(
                status='CONFIRMED',
                payout_transaction=payout
            ).update(
                status='PAID',
                paid_at=timezone.now()
            )
            
            completed_count += 1
        
        self.message_user(request, f'{completed_count} payouts marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected payouts as failed and refund balance"""
        failed_count = 0
        for payout in queryset.filter(status='INITIATED'):
            payout.status = 'FAILED'
            payout.save()

            # Release reserved earnings for failed payout.
            ResellerEarning.objects.filter(
                payout_transaction=payout,
                status='CONFIRMED'
            ).update(payout_transaction=None)
            
            # Refund to reseller balance
            profile = payout.reseller.reseller_profile
            profile.available_balance += payout.amount
            profile.save()
            
            failed_count += 1
        
        self.message_user(request, f'{failed_count} payouts marked as failed and balance refunded.')
    mark_as_failed.short_description = 'Mark as failed (refund balance)'




# ============================================
# AUTO-GENERATED ADMIN REGISTRATIONS - Task 8.1
# ============================================

from .models import Address, ChatAttachment, ChatMessage, ChatThread, Coupon, CouponUsage, MainPageProduct, MainPageSubCategoryBanner, OrderCancellationRequest, PasswordResetLog, ReadyShipStyle, ReturnAttachment, ReturnHistory, ReturnItem, ReturnLabel, ReviewImage, SiteSettings, SubCategory, UserProfile, UserSpendTracker
from .models_activation_tracking import FeatureActivationStatus, MigrationExecutionLog, ModelActivationStatus
from .models_ai_ml_features import ChatbotConfiguration, ChatbotConversation, DemandForecast, DynamicPricingRule, FraudAnalysis, FraudDetectionRule, ImageSearchIndex, ImageSearchQuery, PriceOptimization, ProductRecommendation, RecommendationEngine
from .models_content_management import BlogCategory, BlogComment, BlogPost, ContentBlock, ContentEmailTemplate, CustomPage, FAQ, FAQCategory, PageTemplate, WhatsAppTemplate
from .models_customer_insights import BirthdayAnniversaryReminder, CustomerFeedbackSurvey, CustomerProfile, CustomerSegmentationRule, CustomerSupportTicket, PurchaseHistoryTimeline, RFMAnalysis, SurveyResponse, TicketMessage
from .models_financial_management import CommissionCalculation, ExpenseCategory, ExpenseRecord, GSTReport, PaymentGatewayReconciliation, ProfitLossStatement, ReconciliationTransaction, TaxCalculation, VendorPayment
from .models_new_features import ActivityLog, AdminRole, AdminUserRole, BulkProductImport, DiscountCoupon, EmailTemplate, LowStockAlert, SalesReport
from .models_performance_optimization import CDNConfiguration, CacheMetrics, DatabaseQueryLog, ErrorLog, ImageOptimization, PageLoadMetrics, PerformanceAlert, SystemResourceUsage
from .models_product_enhancements import Product360View, ProductBulkOperation, ProductBundle, ProductComparison, ProductSEO, ProductVariant, ProductVariantCombination, ProductVideo, RelatedProduct
from .models_security_access import DataAccessLog, IPWhitelist, LoginAttempt, SecurityAlert, SecurityAuditLog, SecurityRole, TwoFactorAuthentication, UserRoleAssignment, UserSession

# Auto-generated admin registrations
# Generated by AdminCodeGenerator

class PasswordResetLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'status', 'ip_address', 'timestamp', 'reason']

admin.site.register(PasswordResetLog, PasswordResetLogAdmin)

class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'category_key', 'icon_class', 'background_gradient', 'icon_color']

admin.site.register(SubCategory, SubCategoryAdmin)

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'phone', 'country_code', 'mobile_number', 'is_blocked', 'customer_segment', 'total_spent']

admin.site.register(UserProfile, UserProfileAdmin)

class ReviewImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'uploaded_at']

admin.site.register(ReviewImage, ReviewImageAdmin)

class AddressAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'created_at', 'mobile_number', 'address_line1', 'address_line2', 'city']

admin.site.register(Address, AddressAdmin)

class OrderCancellationRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'upi_id', 'bank_account_name', 'bank_name', 'upi_name', 'status', 'refund_amount']

admin.site.register(OrderCancellationRequest, OrderCancellationRequestAdmin)

class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'quantity', 'condition']

admin.site.register(ReturnItem, ReturnItemAdmin)

class ReturnHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'old_status', 'new_status', 'created_at']

admin.site.register(ReturnHistory, ReturnHistoryAdmin)

class ReturnAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_name', 'created_at', 'size_bytes']

admin.site.register(ReturnAttachment, ReturnAttachmentAdmin)

class ReturnLabelAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'label_url']

admin.site.register(ReturnLabel, ReturnLabelAdmin)

class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ['id', 'guest_name', 'guest_email', 'status', 'created_at', 'updated_at']

admin.site.register(ChatThread, ChatThreadAdmin)

class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'sender_type']

admin.site.register(ChatMessage, ChatMessageAdmin)

class ChatAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_name', 'created_at', 'size_bytes']

admin.site.register(ChatAttachment, ChatAttachmentAdmin)

class MainPageProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'updated_at', 'category', 'order']

admin.site.register(MainPageProduct, MainPageProductAdmin)

class MainPageSubCategoryBannerAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'is_active', 'created_at', 'updated_at']

admin.site.register(MainPageSubCategoryBanner, MainPageSubCategoryBannerAdmin)

class ReadyShipStyleAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'is_active', 'created_at', 'updated_at']

admin.site.register(ReadyShipStyle, ReadyShipStyleAdmin)

class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'site_name', 'contact_email', 'updated_at', 'tagline', 'contact_phone', 'facebook_url']

admin.site.register(SiteSettings, SiteSettingsAdmin)

class CouponAdmin(admin.ModelAdmin):
    list_display = ['id', 'valid_from', 'valid_to', 'is_active', 'created_at', 'updated_at', 'min_purchase_amount']

admin.site.register(Coupon, CouponAdmin)

class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['id', 'discount_amount', 'used_at']

admin.site.register(CouponUsage, CouponUsageAdmin)

class UserSpendTrackerAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'updated_at', 'total_spent', 'current_cycle_spent', 'last_5k_coupon_at']

admin.site.register(UserSpendTracker, UserSpendTrackerAdmin)

class ModelActivationStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'model_name', 'table_created', 'activation_date', 'model_file', 'has_migration', 'migration_applied']

admin.site.register(ModelActivationStatus, ModelActivationStatusAdmin)

class FeatureActivationStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'feature_name', 'url_name', 'view_name', 'http_status']

admin.site.register(FeatureActivationStatus, FeatureActivationStatusAdmin)

class MigrationExecutionLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'model_name', 'migration_file', 'execution_order', 'success', 'executed_at']

admin.site.register(MigrationExecutionLog, MigrationExecutionLogAdmin)

class RecommendationEngineAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'status', 'is_active', 'created_at', 'created_by']

admin.site.register(RecommendationEngine, RecommendationEngineAdmin)

class ProductRecommendationAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'confidence_score', 'source_product_id', 'recommendation_type', 'relevance_score', 'is_viewed']

admin.site.register(ProductRecommendation, ProductRecommendationAdmin)

class DynamicPricingRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by', 'min_price_change_percent', 'max_price_change_percent']

admin.site.register(DynamicPricingRule, DynamicPricingRuleAdmin)

class PriceOptimizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'created_at', 'original_price', 'optimized_price', 'price_change_percent']

admin.site.register(PriceOptimization, PriceOptimizationAdmin)

class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'confidence_interval_lower', 'confidence_interval_upper', 'confidence_level', 'model_name', 'created_at']

admin.site.register(DemandForecast, DemandForecastAdmin)

class FraudDetectionRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by']

admin.site.register(FraudDetectionRule, FraudDetectionRuleAdmin)

class FraudAnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'status', 'created_at', 'order_amount']

admin.site.register(FraudAnalysis, FraudAnalysisAdmin)

class ChatbotConfigurationAdmin(admin.ModelAdmin):
    list_display = ['id', 'confidence_threshold', 'name', 'ai_model_name', 'is_active', 'created_at', 'created_by']

admin.site.register(ChatbotConfiguration, ChatbotConfigurationAdmin)

class ChatbotConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation_id', 'session_id', 'status', 'ip_address', 'message_count', 'was_resolved']

admin.site.register(ChatbotConversation, ChatbotConversationAdmin)

class ImageSearchIndexAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'image_width', 'created_at', 'updated_at']

admin.site.register(ImageSearchIndex, ImageSearchIndexAdmin)

class ImageSearchQueryAdmin(admin.ModelAdmin):
    list_display = ['id', 'query_id', 'session_id', 'created_at', 'query_image_path', 'query_image_url', 'ip_address']

admin.site.register(ImageSearchQuery, ImageSearchQueryAdmin)

class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'meta_title', 'is_active', 'created_at']

admin.site.register(BlogCategory, BlogCategoryAdmin)

class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['id', 'guest_author_name', 'title', 'meta_title', 'og_title', 'status', 'created_at']

admin.site.register(BlogPost, BlogPostAdmin)

class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'guest_name', 'guest_email', 'status', 'created_at']

admin.site.register(BlogComment, BlogCommentAdmin)

class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'icon', 'sort_order']

admin.site.register(FAQCategory, FAQCategoryAdmin)

class FAQAdmin(admin.ModelAdmin):
    list_display = ['id', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(FAQ, FAQAdmin)

class PageTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(PageTemplate, PageTemplateAdmin)

class CustomPageAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'meta_title', 'status', 'created_at', 'created_by', 'updated_at']

admin.site.register(CustomPage, CustomPageAdmin)

class ContentEmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(ContentEmailTemplate, ContentEmailTemplateAdmin)

class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'whatsapp_template_id', 'name', 'status', 'is_active', 'created_at', 'created_by']

admin.site.register(WhatsAppTemplate, WhatsAppTemplateAdmin)

class ContentBlockAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(ContentBlock, ContentBlockAdmin)

class CustomerSegmentationRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(CustomerSegmentationRule, CustomerSegmentationRuleAdmin)

class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'email_notifications', 'marketing_emails', 'created_at', 'updated_at', 'date_of_birth', 'price_range_min']

admin.site.register(CustomerProfile, CustomerProfileAdmin)

class PurchaseHistoryTimelineAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'created_at', 'order_date', 'order_number', 'order_value', 'items_count']

admin.site.register(PurchaseHistoryTimeline, PurchaseHistoryTimelineAdmin)

class RFMAnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'analysis_start_date', 'analysis_end_date', 'recency_days', 'recency_score', 'frequency_count', 'frequency_score']

admin.site.register(RFMAnalysis, RFMAnalysisAdmin)

class CustomerSupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'related_order_id', 'related_product_id', 'status', 'created_at', 'updated_at']

admin.site.register(CustomerSupportTicket, CustomerSupportTicketAdmin)

class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'is_internal', 'read_by_customer', 'read_by_staff']

admin.site.register(TicketMessage, TicketMessageAdmin)

class CustomerFeedbackSurveyAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'created_at', 'created_by', 'start_date', 'end_date']

admin.site.register(CustomerFeedbackSurvey, CustomerFeedbackSurveyAdmin)

class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'ip_address', 'completion_time_seconds', 'is_complete', 'submitted_at']

admin.site.register(SurveyResponse, SurveyResponseAdmin)

class BirthdayAnniversaryReminderAdmin(admin.ModelAdmin):
    list_display = ['id', 'send_email', 'email_opened', 'status', 'created_at', 'reminder_date']

admin.site.register(BirthdayAnniversaryReminder, BirthdayAnniversaryReminderAdmin)

class ProfitLossStatementAdmin(admin.ModelAdmin):
    list_display = ['id', 'statement_id', 'start_date', 'end_date', 'period_type', 'gross_sales', 'returns_refunds']

admin.site.register(ProfitLossStatement, ProfitLossStatementAdmin)

class GSTReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_id', 'status', 'filing_date', 'cgst_amount', 'sgst_amount', 'igst_amount']

admin.site.register(GSTReport, GSTReportAdmin)

class PaymentGatewayReconciliationAdmin(admin.ModelAdmin):
    list_display = ['id', 'reconciliation_id', 'status', 'created_at', 'created_by', 'start_date', 'end_date']

admin.site.register(PaymentGatewayReconciliation, PaymentGatewayReconciliationAdmin)

class ReconciliationTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'gateway_transaction_id', 'system_order_id', 'gateway_date', 'system_date', 'gateway_amount', 'system_amount']

admin.site.register(ReconciliationTransaction, ReconciliationTransactionAdmin)

class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'is_tax_deductible', 'gst_applicable', 'monthly_budget']

admin.site.register(ExpenseCategory, ExpenseCategoryAdmin)

class ExpenseRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'expense_id', 'vendor_name', 'created_at', 'created_by', 'expense_date', 'amount']

admin.site.register(ExpenseRecord, ExpenseRecordAdmin)

class VendorPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'payment_id', 'vendor_name', 'vendor_bank_name', 'status', 'created_at', 'created_by']

admin.site.register(VendorPayment, VendorPaymentAdmin)

class TaxCalculationAdmin(admin.ModelAdmin):
    list_display = ['id', 'calculation_id', 'tax_paid', 'taxable_amount', 'final_tax_amount']

admin.site.register(TaxCalculation, TaxCalculationAdmin)

class CommissionCalculationAdmin(admin.ModelAdmin):
    list_display = ['id', 'calculation_id', 'is_paid', 'start_date', 'end_date', 'payment_date']

admin.site.register(CommissionCalculation, CommissionCalculationAdmin)

class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'object_id', 'model_name', 'object_name', 'action', 'ip_address', 'timestamp']

admin.site.register(ActivityLog, ActivityLogAdmin)

class DiscountCouponAdmin(admin.ModelAdmin):
    list_display = ['id', 'valid_from', 'valid_until', 'status', 'created_at', 'created_by', 'updated_at']

admin.site.register(DiscountCoupon, DiscountCouponAdmin)

class LowStockAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'product_name', 'status', 'created_at']

admin.site.register(LowStockAlert, LowStockAlertAdmin)

class BulkProductImportAdmin(admin.ModelAdmin):
    list_display = ['id', 'file_name', 'status', 'created_at', 'total_rows', 'successful_imports', 'failed_imports']

admin.site.register(BulkProductImport, BulkProductImportAdmin)

class AdminRoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'updated_at']

admin.site.register(AdminRole, AdminRoleAdmin)

class AdminUserRoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'assigned_at']

admin.site.register(AdminUserRole, AdminUserRoleAdmin)

class SalesReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_date', 'report_type', 'total_sales', 'total_orders', 'total_customers', 'average_order_value']

admin.site.register(SalesReport, SalesReportAdmin)

class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'updated_at']

admin.site.register(EmailTemplate, EmailTemplateAdmin)

class ImageOptimizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_width', 'optimized_width', 'bandwidth_saved_bytes', 'original_filename', 'optimized_filename', 'status']

admin.site.register(ImageOptimization, ImageOptimizationAdmin)

class CDNConfigurationAdmin(admin.ModelAdmin):
    list_display = ['id', 'provider', 'zone_id', 'total_bandwidth_gb', 'name', 'is_active', 'created_at']

admin.site.register(CDNConfiguration, CDNConfigurationAdmin)

class DatabaseQueryLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'view_name', 'created_at', 'query_type', 'execution_time_ms', 'rows_examined', 'rows_returned']

admin.site.register(DatabaseQueryLog, DatabaseQueryLogAdmin)

class PageLoadMetricsAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_id', 'page_title', 'created_at', 'url_path', 'dns_lookup_time', 'tcp_connect_time']

admin.site.register(PageLoadMetrics, PageLoadMetricsAdmin)

class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'view_name', 'server_name', 'status', 'error_type', 'severity', 'url_path']

admin.site.register(ErrorLog, ErrorLogAdmin)

class PerformanceAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'created_at', 'alert_type', 'severity', 'threshold_value']

admin.site.register(PerformanceAlert, PerformanceAlertAdmin)

class CacheMetricsAdmin(admin.ModelAdmin):
    list_display = ['id', 'measurement_date', 'cache_type', 'cache_key_pattern', 'hit_count', 'miss_count', 'total_requests']

admin.site.register(CacheMetrics, CacheMetricsAdmin)

class SystemResourceUsageAdmin(admin.ModelAdmin):
    list_display = ['id', 'cpu_usage_percent', 'cpu_load_average', 'memory_total_mb', 'memory_used_mb', 'memory_usage_percent', 'disk_total_gb']

admin.site.register(SystemResourceUsage, SystemResourceUsageAdmin)

class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'name', 'display_name', 'is_active', 'created_at', 'price_adjustment']

admin.site.register(ProductVariant, ProductVariantAdmin)

class ProductVariantCombinationAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'is_active', 'created_at', 'updated_at', 'price', 'cost_price']

admin.site.register(ProductVariantCombination, ProductVariantCombinationAdmin)

class ProductBundleAdmin(admin.ModelAdmin):
    list_display = ['id', 'individual_total', 'name', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(ProductBundle, ProductBundleAdmin)

class RelatedProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'primary_product_id', 'related_product_id', 'is_active', 'created_at', 'created_by']

admin.site.register(RelatedProduct, RelatedProductAdmin)

class ProductComparisonAdmin(admin.ModelAdmin):
    list_display = ['id', 'comparison_id', 'session_id', 'created_at', 'created_by_user']

admin.site.register(ProductComparison, ProductComparisonAdmin)

class ProductSEOAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'meta_title', 'og_title', 'twitter_title', 'created_at', 'updated_at']

admin.site.register(ProductSEO, ProductSEOAdmin)

class ProductVideoAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'video_type', 'video_url', 'title', 'is_active', 'created_at']

admin.site.register(ProductVideo, ProductVideoAdmin)

class Product360ViewAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_id', 'processing_status', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(Product360View, Product360ViewAdmin)

class ProductBulkOperationAdmin(admin.ModelAdmin):
    list_display = ['id', 'operation_id', 'status', 'created_at', 'created_by']

admin.site.register(ProductBulkOperation, ProductBulkOperationAdmin)

class SecurityRoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by', 'updated_at']

admin.site.register(SecurityRole, SecurityRoleAdmin)

class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'valid_from', 'valid_until', 'is_active', 'assigned_at', 'is_primary']

admin.site.register(UserRoleAssignment, UserRoleAssignmentAdmin)

class SecurityAuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'affected_object_id', 'username', 'event_type', 'severity', 'ip_address', 'request_method']

admin.site.register(SecurityAuditLog, SecurityAuditLogAdmin)

class TwoFactorAuthenticationAdmin(admin.ModelAdmin):
    list_display = ['id', 'email_address', 'status', 'created_at', 'updated_at']

admin.site.register(TwoFactorAuthentication, TwoFactorAuthenticationAdmin)

class IPWhitelistAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_at', 'created_by']

admin.site.register(IPWhitelist, IPWhitelistAdmin)

class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'session_key', 'ip_address', 'device_type', 'browser', 'operating_system']

admin.site.register(UserSession, UserSessionAdmin)

class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'attempt_type', 'ip_address', 'country', 'city', 'failure_reason']

admin.site.register(LoginAttempt, LoginAttemptAdmin)

class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'alert_id', 'title', 'status', 'alert_type', 'severity', 'affected_ip']

admin.site.register(SecurityAlert, SecurityAlertAdmin)

class DataAccessLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'record_id', 'table_name', 'access_type', 'ip_address', 'request_path', 'contains_pii']

admin.site.register(DataAccessLog, DataAccessLogAdmin)


# Webhook Logging Admin
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'event_type', 'payment_id', 'order_id', 'signature_valid', 'status', 'received_at']
    list_filter = ['event_type', 'signature_valid', 'status', 'received_at']
    search_fields = ['payment_id', 'order_id', 'event_type', 'raw_body']
    readonly_fields = ['raw_body', 'signature', 'signature_valid', 'received_at', 'processed_at']
    ordering = ['-received_at']
    
    fieldsets = (
        ('Event Info', {
            'fields': ('event_type', 'payment_id', 'order_id', 'received_at')
        }),
        ('Signature', {
            'fields': ('signature', 'signature_valid')
        }),
        ('Raw Content', {
            'fields': ('raw_body',),
            'classes': ('collapse',)
        }),
        ('Processing Status', {
            'fields': ('status', 'error_message', 'response_message', 'processed_at', 'processed_by_user')
        }),
    )

admin.site.register(WebhookLog, WebhookLogAdmin)


class VerificationTestLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'test_type', 'razorpay_order_id', 'webhook_received', 'created_at']
    list_filter = ['test_type', 'webhook_received', 'created_at']
    search_fields = ['user__username', 'razorpay_order_id', 'razorpay_payment_id']
    readonly_fields = ['created_at', 'webhook_received_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Test Info', {
            'fields': ('user', 'test_type', 'created_at')
        }),
        ('Test Details', {
            'fields': ('upi_id', 'bank_account', 'test_amount', 'test_status')
        }),
        ('Razorpay IDs', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_response')
        }),
        ('Results', {
            'fields': ('webhook_received', 'webhook_received_at', 'notes')
        }),
    )

admin.site.register(VerificationTestLog, VerificationTestLogAdmin)


# Load backup model admin registrations
from . import backup_admin  # noqa: E402,F401
