"""
Custom Reel Admin with improved ordering functionality
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from .models import Reel, ReelImage


class ReelImageInline(admin.TabularInline):
    """Inline editor for reel images"""
    model = ReelImage
    extra = 0
    fields = ('image', 'order', 'text_overlay', 'text_position', 'text_color', 'text_size', 'image_preview')
    readonly_fields = ('image_preview',)
    ordering = ['order']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 80px; height: 100px; border-radius: 5px; object-fit: cover; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return '—'
    image_preview.short_description = 'Preview'


@admin.register(Reel)
class ReelAdminImproved(admin.ModelAdmin):
    """Reel management with improved ordering and display"""
    
    # List display customization
    list_display = (
        'order_badge',
        'title_with_status',
        'reel_preview',
        'video_info',
        'published_status',
        'created_date',
        'quick_actions'
    )
    
    # Filtering options
    list_filter = (
        'is_published',
        'is_processing',
        'created_at',
        'transition_type'
    )
    
    # Search functionality
    search_fields = ('title', 'description')
    
    # Editable fields in list view - removed 'order' as it uses drag-drop ordering instead
    list_editable = ()
    
    # Fieldsets organization
    fieldsets = (
        ('📋 BASIC INFO', {
            'fields': ('title', 'description', 'product'),
            'description': 'Reel title and basic information'
        }),
        ('🎬 VIDEO FILE', {
            'fields': ('video_file', 'video_preview_large', 'thumbnail', 'thumbnail_preview_large', 'duration'),
            'description': 'Video and thumbnail files'
        }),
        ('⚙️ CONFIGURATION', {
            'fields': (
                'duration_per_image',
                'transition_type',
                'background_music'
            ),
            'description': 'Video generation settings'
        }),
        ('🎨 BRANDING', {
            'fields': (
                'watermark_logo',
                'watermark_position',
                'watermark_opacity',
                'add_end_screen',
                'end_screen_duration'
            ),
            'description': 'Watermark and branding options',
            'classes': ('collapse',)
        }),
        ('📊 ENGAGEMENT', {
            'fields': ('view_count', 'like_count'),
            'description': 'View and like statistics'
        }),
        ('🔍 DISPLAY & STATUS', {
            'fields': ('order', 'is_published', 'is_processing'),
            'description': 'Homepage display order and publishing status',
            'classes': ('wide',)
        }),
        ('👤 METADATA', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'description': 'Creation and modification details',
            'classes': ('collapse',)
        }),
    )
    
    # Read-only fields
    readonly_fields = (
        'duration',
        'is_processing',
        'created_by',
        'created_at',
        'updated_at',
        'video_preview_large',
        'thumbnail_preview_large'
    )
    
    # Inline editing
    inlines = [ReelImageInline]
    
    # Custom ordering
    ordering = ['order', '-created_at']
    
    # Actions
    actions = ['publish_reels', 'unpublish_reels', 'move_to_top']
    
    def order_badge(self, obj):
        """Display order as a badge"""
        return format_html(
            '<span style="background: #696cff; color: white; padding: 6px 12px; border-radius: 20px; font-weight: 600; font-size: 12px;">#{}</span>',
            obj.order
        )
    order_badge.short_description = 'Position'
    order_badge.admin_order_field = 'order'
    
    def title_with_status(self, obj):
        """Display title with processing status indicator"""
        if obj.is_processing:
            status_icon = '⏳'
            status_text = 'Generating'
            status_color = '#FFA500'
        elif obj.is_published:
            status_icon = '✅'
            status_text = 'Published'
            status_color = '#28a745'
        else:
            status_icon = '📋'
            status_text = 'Draft'
            status_color = '#6c757d'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;"><strong>{}</strong> <span style="display: inline-block; background: {}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; white-space: nowrap;">{} {}</span></div>',
            obj.title,
            status_color,
            status_icon,
            status_text
        )
    title_with_status.short_description = 'Title & Status'
    title_with_status.admin_order_field = 'title'
    
    def reel_preview(self, obj):
        """Display video thumbnail preview"""
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="width: 80px; height: 120px; border-radius: 8px; object-fit: cover; border: 2px solid #ddd;" title="{}"/>',
                obj.thumbnail.url,
                obj.title
            )
        elif obj.video_file:
            return format_html(
                '<video style="width: 80px; height: 120px; border-radius: 8px; object-fit: cover; border: 2px solid #ddd;" controls><source src="{}" type="video/mp4"></video>',
                obj.video_file.url
            )
        return format_html(
            '<div style="width: 80px; height: 120px; border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center;"><i class="fas fa-image" style="font-size: 32px; color: white; opacity: 0.5;"></i></div>'
        )
    reel_preview.short_description = 'Preview'
    
    def video_info(self, obj):
        """Display video information"""
        image_count = obj.images.count()
        return format_html(
            '<div style="white-space: nowrap;"><strong>Duration:</strong> {}s<br><strong>Images:</strong> {}</div>',
            obj.duration,
            image_count
        )
    video_info.short_description = 'Video Info'
    
    def published_status(self, obj):
        """Display publication status"""
        if obj.is_published:
            return format_html(
                '<span style="background: #d4edda; color: #155724; padding: 6px 12px; border-radius: 20px; font-weight: 600; border: 1px solid #c3e6cb;">✅ Published</span>'
            )
        else:
            return format_html(
                '<span style="background: #f8d7da; color: #721c24; padding: 6px 12px; border-radius: 20px; font-weight: 600; border: 1px solid #f5c6cb;">📋 Draft</span>'
            )
    published_status.short_description = 'Status'
    published_status.admin_order_field = 'is_published'
    
    def created_date(self, obj):
        """Display creation date"""
        return obj.created_at.strftime('%b %d, %Y<br>%I:%M %p')
    created_date.short_description = 'Created'
    created_date.admin_order_field = 'created_at'
    
    def quick_actions(self, obj):
        """Display quick action buttons"""
        from django.urls import reverse
        
        generate_url = reverse('admin:Hub_reel_generatevideo', args=[obj.id])
        
        if obj.is_processing:
            action_btn = '<span style="color: #FFA500; font-weight: 600;">⏳ Generating...</span>'
        elif not obj.video_file:
            action_btn = f'<a href="{generate_url}" class="button" style="background: #17a2b8; color: white;">Generate Video</a>'
        else:
            action_btn = '<span style="color: #28a745; font-weight: 600;">✓ Ready</span>'
        
        return format_html(action_btn)
    quick_actions.short_description = 'Actions'
    
    def get_urls(self):
        """Add custom URLs for reel actions"""
        urls = super().get_urls()
        custom_urls = [
            path('reorder/', self.admin_site.admin_view(self.reorder_view), name='Hub_reel_reorder'),
        ]
        return custom_urls + urls
    
    def reorder_view(self, request):
        """View for displaying drag-and-drop reorder interface"""
        reels = Reel.objects.all().order_by('order', '-created_at')
        context = {
            'title': 'Reorder Reels',
            'reels': reels,
            'opts': Reel._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return TemplateResponse(request, 'admin/reel_reorder.html', context)
    
    @require_http_methods(["POST"])
    def update_reel_order(self, request):
        """AJAX endpoint to update reel order"""
        try:
            data = json.loads(request.body)
            new_orders = data.get('orders', [])
            
            for index, reel_id in enumerate(new_orders):
                Reel.objects.filter(id=reel_id).update(order=index)
            
            return JsonResponse({
                'success': True,
                'message': f'Updated order for {len(new_orders)} reels'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    def save_model(self, request, obj, form, change):
        """Auto-set created_by to current user"""
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def video_preview(self, obj):
        """Small video preview for list"""
        if obj.video_file:
            return format_html(
                '<video width="120" height="80" style="border-radius: 5px; object-fit: cover;"><source src="{}" type="video/mp4"></video>',
                obj.video_file.url
            )
        return '—'
    video_preview.short_description = 'Video'
    
    def video_preview_large(self, obj):
        """Large video preview for detail view"""
        if obj.video_file:
            return format_html(
                '<video width="400" controls style="border-radius: 10px; border: 2px solid #ddd;"><source src="{}" type="video/mp4"></video>',
                obj.video_file.url
            )
        return 'No video generated yet. Add images and generate reel.'
    video_preview_large.short_description = 'Video Preview'
    
    def thumbnail_preview(self, obj):
        """Small thumbnail preview for list"""
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="width: 60px; height: 80px; border-radius: 5px; object-fit: cover;" />',
                obj.thumbnail.url
            )
        return '—'
    thumbnail_preview.short_description = 'Thumbnail'
    
    def thumbnail_preview_large(self, obj):
        """Large thumbnail preview for detail view"""
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-width: 300px; border-radius: 10px; border: 2px solid #ddd;" />',
                obj.thumbnail.url
            )
        return 'No thumbnail available'
    thumbnail_preview_large.short_description = 'Thumbnail Preview'
    
    def publish_reels(self, request, queryset):
        """Bulk action to publish reels"""
        count = queryset.update(is_published=True)
        self.message_user(request, f'{count} reel(s) published successfully.')
    publish_reels.short_description = '✅ Publish selected reels'
    
    def unpublish_reels(self, request, queryset):
        """Bulk action to unpublish reels"""
        count = queryset.update(is_published=False)
        self.message_user(request, f'{count} reel(s) unpublished.')
    unpublish_reels.short_description = '📋 Unpublish selected reels'
    
    def move_to_top(self, request, queryset):
        """Move selected reels to top of display order"""
        if not queryset.exists():
            return
        
        min_order = Reel.objects.exclude(id__in=queryset).aggregate(min_order=models.Min('order'))['min_order']
        if min_order is None:
            min_order = -queryset.count()
        else:
            min_order = min_order - queryset.count()
        
        for index, reel in enumerate(queryset.order_by('order')):
            reel.order = min_order + index
            reel.save()
        
        self.message_user(request, f'{queryset.count()} reel(s) moved to top.')
    move_to_top.short_description = '⬆️ Move to top (in display order)'


@admin.register(ReelImage)
class ReelImageAdminImproved(admin.ModelAdmin):
    """Reel image management"""
    list_display = ('reel', 'order', 'image_preview', 'text_overlay', 'text_position')
    list_filter = ('reel',)
    list_editable = ('order',)
    search_fields = ('reel__title', 'text_overlay')
    ordering = ['reel', 'order']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 80px; height: 100px; border-radius: 5px; object-fit: cover; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return '—'
    image_preview.short_description = 'Image Preview'
