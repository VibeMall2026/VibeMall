"""
Backup System Admin Configuration
Register backup-related models in Django admin panel
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from datetime import timedelta
from django.utils import timezone

from Hub.models import BackupConfiguration, BackupLog, TeraboxSettings, BackupCleanupRequest


@admin.register(BackupConfiguration)
class BackupConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for BackupConfiguration model."""
    
    list_display = [
        'frequency_display', 'status_indicator', 'schedule_time',
        'terabox_status', 'next_backup_indicator', 'actions_buttons'
    ]
    
    list_filter = ['is_active', 'backup_frequency', 'enable_terabox_backup']
    readonly_fields = ['created_at', 'updated_at', 'last_backup_at', 'next_backup_at', 'summary_info']
    
    fieldsets = (
        ('🕐 Scheduling', {
            'fields': (
                'backup_frequency',
                'schedule_time',
                'schedule_weekday',
                'custom_dates',
            ),
            'description': 'Configure when backups should run'
        }),
        ('☁ Terabox Cloud', {
            'fields': (
                'enable_terabox_backup',
                'terabox_auto_folder_create',
            ),
            'description': 'Legacy cloud options (keep disabled for local backup mode)'
        }),
        ('📁 Local Storage', {
            'fields': (
                'backup_root_path',
                'regular_folder_name',
                'special_folder_name',
            ),
            'description': 'Local backup root and subfolder configuration'
        }),
        ('📧 Email Notifications', {
            'fields': (
                'notification_emails',
                'send_success_email',
                'send_failure_email',
            ),
            'description': 'Configure email notifications for backup completion'
        }),
        ('🗑 Data Retention', {
            'fields': (
                'keep_local_backups_days',
                'keep_cloud_backups_days',
            ),
            'description': 'How long to keep backups before deletion'
        }),
        ('ℹ Status', {
            'fields': (
                'is_active',
                'last_backup_at',
                'next_backup_at',
                'created_at',
                'updated_at',
                'summary_info',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def frequency_display(self, obj):
        """Display frequency with icon."""
        icons = {
            'DAILY': '📅',
            'WEEKLY': '📆',
            'BIWEEKLY': '📊',
            'MONTHLY': '🗓',
            'CUSTOM': '⚙',
        }
        icon = icons.get(obj.backup_frequency, '❓')
        return format_html(
            '{} <strong>{}</strong>',
            icon,
            obj.get_backup_frequency_display()
        )
    frequency_display.short_description = 'Frequency'
    
    def status_indicator(self, obj):
        """Display active/inactive status with indicator."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-size: 16px;">●</span> <strong>Active</strong>'
            )
        else:
            return format_html(
                '<span style="color: red; font-size: 16px;">●</span> <strong>Inactive</strong>'
            )
    status_indicator.short_description = 'Status'
    
    def terabox_status(self, obj):
        """Display Terabox status."""
        if obj.enable_terabox_backup:
            return format_html('☁ <strong>Enabled</strong>')
        else:
            return format_html('☁ <em>Disabled</em>')
    terabox_status.short_description = 'Cloud'
    
    def next_backup_indicator(self, obj):
        """Display next backup time."""
        if obj.next_backup_at:
            from django.utils.timezone import now
            time_delta = obj.next_backup_at - now()
            
            if time_delta.total_seconds() < 0:
                color = 'red'
                text = '⏰ Overdue'
            else:
                color = 'green'
                days = time_delta.days
                hours = time_delta.seconds // 3600
                text = f'⏰ {days}d {hours}h'
            
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                text
            )
        return '—'
    next_backup_indicator.short_description = 'Next Backup'
    
    def actions_buttons(self, obj):
        """Display quick action buttons."""
        return format_html(
            '<a class="button" href="#" onclick="triggerBackup()">▶ Backup Now</a>'
        )
    actions_buttons.short_description = 'Actions'
    
    def summary_info(self, obj):
        """Display configuration summary."""
        from Hub.models import BackupLog
        
        last_backup = BackupLog.objects.filter(status='SUCCESS').order_by('-start_time').first()
        total_logs = BackupLog.objects.count()
        
        info = '<div style="font-family: monospace; background: #f0f0f0; padding: 10px;>'
        info += '<strong>Configuration Summary:</strong><br>'
        info += f'Frequency: {obj.get_backup_frequency_display()}<br>'
        info += f'Schedule Time: {obj.schedule_time}<br>'
        info += f'Backup Root: {obj.backup_root_path}<br>'
        info += f'Regular Folder: {obj.regular_folder_name}<br>'
        info += f'Special Folder: {obj.special_folder_name}<br>'
        info += f'Emails: {obj.notification_emails or "Not configured"}<br><br>'
        info += '<strong>Backup Statistics:</strong><br>'
        info += f'Total Backups: {total_logs}<br>'
        if last_backup:
            info += f'Last Successful: {last_backup.start_time.strftime("%Y-%m-%d %H:%M:%S")}<br>'
        info += '</div>'
        
        return format_html(info)
    summary_info.short_description = 'Summary'


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    """Admin interface for BackupLog entries."""
    
    list_display = [
        'id', 'backup_type_icon', 'status_badge', 'start_time_short',
        'duration_display', 'records_count', 'size_display', 'terabox_indicator'
    ]
    
    list_filter = [
        'status', 'backup_type', 'start_time', 'terabox_synced', 'email_sent'
    ]
    
    search_fields = ['backup_frequency', 'error_message']
    readonly_fields = [
        'start_time', 'end_time', 'duration_display', 'data_summary_table',
        'terabox_synced', 'email_sent', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('📋 Backup Info', {
            'fields': (
                'backup_type',
                'backup_frequency',
                'status',
                'start_time',
                'end_time',
                'duration_display',
            )
        }),
        ('📦 Data Summary', {
            'fields': (
                'data_summary_table',
            )
        }),
        ('💾 File Info', {
            'fields': (
                'local_file_path',
                'terabox_file_path',
                'file_size_mb',
            )
        }),
        ('🔄 Sync Status', {
            'fields': (
                'terabox_synced',
                'email_sent',
            )
        }),
        ('⚠ Error Tracking', {
            'fields': (
                'error_message',
                'error_trace',
            ),
            'classes': ('collapse',)
        }),
        ('📝 Notes', {
            'fields': (
                'notes',
            ),
            'classes': ('collapse',)
        }),
        ('⏰ Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def backup_type_icon(self, obj):
        """Display backup type with icon."""
        icons = {
            'MANUAL': '👤',
            'SCHEDULED': '📅',
            'ON_DEMAND': '🚀',
        }
        icon = icons.get(obj.backup_type, '❓')
        return format_html('{} {}', icon, obj.get_backup_type_display())
    backup_type_icon.short_description = 'Type'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'PENDING': '#FFA500',
            'IN_PROGRESS': '#4169E1',
            'SUCCESS': '#28A745',
            'FAILED': '#DC3545',
            'PARTIAL': '#FF6347',
        }
        color = colors.get(obj.status, '#808080')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def start_time_short(self, obj):
        """Display start time in short format."""
        return obj.start_time.strftime('%Y-%m-%d %H:%M')
    start_time_short.short_description = 'Started'
    
    def duration_display(self, obj):
        """Display backup duration."""
        if obj.duration_seconds:
            mins = obj.duration_seconds // 60
            secs = obj.duration_seconds % 60
            return f'{mins}m {secs}s'
        return '—'
    duration_display.short_description = 'Duration'
    
    def records_count(self, obj):
        """Display total records backed up."""
        total = obj.get_total_records()
        return format_html(
            '<strong>{}</strong> records',
            total
        )
    records_count.short_description = 'Records'
    
    def size_display(self, obj):
        """Display file size."""
        if obj.file_size_mb:
            return f'{obj.file_size_mb:.2f} MB'
        return '—'
    size_display.short_description = 'Size'
    
    def terabox_indicator(self, obj):
        """Display Terabox sync status."""
        if obj.terabox_synced:
            return format_html('☁ <span style="color: green;">✓</span>')
        else:
            return format_html('☁ <span style="color: red;">✗</span>')
    terabox_indicator.short_description = 'Cloud'
    
    def data_summary_table(self, obj):
        """Display data summary as HTML table."""
        summary = obj.get_data_summary()
        
        html = '<table style="border-collapse: collapse; width: 100%;"><tr style="background-color: #f0f0f0;">'
        for key in summary.keys():
            html += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: right;">{key.upper()}</th>'
        html += '</tr><tr>'
        for value in summary.values():
            html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: right;"><strong>{value:,}</strong></td>'
        html += '</tr></table>'
        
        return format_html(html)
    data_summary_table.short_description = 'Data Backed Up'
    
    def has_add_permission(self, request):
        return False  # Backup logs are created automatically
    
    def has_delete_permission(self, request, obj=None):
        return False  # Don't allow manual deletion of logs


@admin.register(TeraboxSettings)
class TeraboxSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Terabox settings."""
    
    list_display = ['connection_status', 'last_sync_indicator', 'storage_usage', 'token_status']
    readonly_fields = [
        'api_access_token', 'refresh_token', 'last_sync_time',
        'total_backups_synced', 'account_info_display', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('🔐 Authentication', {
            'fields': (
                'is_connected',
                'connection_status_message',
                'api_access_token',
                'refresh_token',
                'token_expires_at',
            ),
            'description': 'Terabox API authentication details'
        }),
        ('📁 Folder Configuration', {
            'fields': (
                'folder_root_path',
                'auto_create_folders',
            )
        }),
        ('📊 Usage Statistics', {
            'fields': (
                'last_sync_time',
                'total_backups_synced',
                'cloud_storage_used_mb',
            )
        }),
        ('👤 Account Info', {
            'fields': (
                'account_info_display',
            ),
            'classes': ('collapse',)
        }),
        ('⏰ Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def connection_status(self, obj):
        """Display connection status."""
        if obj.is_connected:
            return format_html(
                '<span style="color: green; font-size: 16px;">●</span> <strong>Connected</strong>'
            )
        else:
            return format_html(
                '<span style="color: red; font-size: 16px;">●</span> <strong>Not Connected</strong>'
            )
    connection_status.short_description = 'Status'
    
    def last_sync_indicator(self, obj):
        """Display last sync time."""
        if obj.last_sync_time:
            from django.utils.timezone import now
            time_delta = now() - obj.last_sync_time
            
            if time_delta.total_seconds() < 3600:
                return format_html('⏰ Just now')
            elif time_delta.total_seconds() < 86400:
                hours = int(time_delta.total_seconds() / 3600)
                return format_html(f'⏰ {hours} hours ago')
            else:
                days = time_delta.days
                return format_html(f'⏰ {days} days ago')
        return '—'
    last_sync_indicator.short_description = 'Last Sync'
    
    def storage_usage(self, obj):
        """Display storage usage."""
        if obj.cloud_storage_used_mb:
            if obj.cloud_storage_used_mb > 1024:
                gb = obj.cloud_storage_used_mb / 1024
                return format_html(f'💾 {gb:.2f} GB')
            else:
                return format_html(f'💾 {obj.cloud_storage_used_mb:.2f} MB')
        return '💾 0 MB'
    storage_usage.short_description = 'Storage Used'
    
    def token_status(self, obj):
        """Display token expiry status."""
        if not obj.is_connected:
            return '—'
        
        hours = obj.token_expiry_in_hours()
        if hours > 24:
            return format_html('<span style="color: green;">🔐 Valid</span>')
        elif hours > 0:
            return format_html(f'<span style="color: orange;">🔐 Expires in {hours}h</span>')
        else:
            return format_html('<span style="color: red;">🔐 Expired</span>')
    token_status.short_description = 'Token'
    
    def account_info_display(self, obj):
        """Display account information."""
        if not obj.account_info:
            return '—'
        
        try:
            import json
            info = json.loads(obj.account_info)
            html = '<pre style="background: #f0f0f0; padding: 10px; border-radius: 5px;">'
            html += json.dumps(info, indent=2)
            html += '</pre>'
            return format_html(html)
        except:
            return obj.account_info
    account_info_display.short_description = 'Account Info'
    
    def has_add_permission(self, request):
        return not TeraboxSettings.objects.exists()  # Only one instance
    
    def has_delete_permission(self, request, obj=None):
        return False  # Don't delete settings


@admin.register(BackupCleanupRequest)
class BackupCleanupRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'folder_label', 'status', 'email_sent', 'requested_at', 'confirmed_at', 'confirmed_by']
    list_filter = ['status', 'email_sent', 'requested_at']
    search_fields = ['folder_label', 'folder_path']
    readonly_fields = ['backup_log', 'folder_path', 'folder_label', 'confirmation_token', 'requested_at', 'confirmed_at', 'confirmed_by']
