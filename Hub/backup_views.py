"""
Backup Admin Views
Handles all admin panel backup operations: dashboard, configuration, history
"""

from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta, datetime
from django.core.management import call_command
from io import StringIO
import json
import logging

from Hub.models import (
    BackupConfiguration, BackupLog, TeraboxSettings, Order,
    Product, User as DjangoUser, Payment, ReturnRequest, OrderItem
)

logger = logging.getLogger(__name__)


def admin_required(view_func):
    """Decorator to check if user is admin."""
    def check_admin(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Access denied")
        return view_func(request, *args, **kwargs)
    return check_admin


@admin_required
def backup_dashboard(request):
    """Display backup dashboard with status and quick stats."""
    try:
        # Get configuration
        config = BackupConfiguration.objects.first()
        if not config:
            config = BackupConfiguration.objects.create()
        
        # Get Terabox settings
        terabox = TeraboxSettings.objects.first()
        if not terabox:
            terabox = TeraboxSettings.objects.create()
        
        # Get recent backups
        recent_backups = BackupLog.objects.all()[:10]
        
        # Calculate stats
        successful_backups = BackupLog.objects.filter(status='SUCCESS').count()
        failed_backups = BackupLog.objects.filter(status='FAILED').count()
        total_backups = BackupLog.objects.count()
        
        # Last backup info
        last_backup = BackupLog.objects.order_by('-start_time').first()
        
        # Current data counts
        users_count = DjangoUser.objects.count()
        orders_count = Order.objects.count()
        products_count = Product.objects.count()
        
        # Calculate next backup time
        from Hub.backup_utils import calculate_next_backup_time
        next_backup_time = calculate_next_backup_time(config) if config else None
        
        context = {
            'config': config,
            'terabox': terabox,
            'recent_backups': recent_backups,
            'successful_backups': successful_backups,
            'failed_backups': failed_backups,
            'total_backups': total_backups,
            'last_backup': last_backup,
            'users_count': users_count,
            'orders_count': orders_count,
            'products_count': products_count,
            'next_backup_time': next_backup_time,
            'terabox_connected': terabox.is_connected,
        }
        
        return render(request, 'admin_panel/backup_dashboard.html', context)
    
    except Exception as e:
        logger.error(f"Error loading backup dashboard: {str(e)}", exc_info=True)
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return redirect('admin:index')


@admin_required
def backup_history(request):
    """Display backup history and logs."""
    try:
        page = int(request.GET.get('page', 1))
        filter_status = request.GET.get('status', '')
        filter_type = request.GET.get('type', '')
        
        # Base queryset
        backups = BackupLog.objects.all().order_by('-start_time')
        
        # Apply filters
        if filter_status:
            backups = backups.filter(status=filter_status)
        if filter_type:
            backups = backups.filter(backup_type=filter_type)
        
        # Pagination
        per_page = 20
        total = backups.count()
        start = (page - 1) * per_page
        end = start + per_page
        backups_page = backups[start:end]
        
        total_pages = (total + per_page - 1) // per_page
        
        context = {
            'backups': backups_page,
            'total': total,
            'page': page,
            'total_pages': total_pages,
            'filter_status': filter_status,
            'filter_type': filter_type,
            'status_choices': BackupLog.STATUS_CHOICES,
            'type_choices': BackupLog.BACKUP_TYPE_CHOICES,
        }
        
        return render(request, 'admin_panel/backup_history.html', context)
    
    except Exception as e:
        logger.error(f"Error loading backup history: {str(e)}", exc_info=True)
        messages.error(request, f"Error loading history: {str(e)}")
        return redirect('admin:backup-dashboard')


@admin_required
def backup_configuration(request):
    """Manage backup configuration and scheduling."""
    try:
        config = BackupConfiguration.objects.first()
        if not config:
            config = BackupConfiguration.objects.create()
        
        if request.method == 'POST':
            # Update configuration
            config.backup_frequency = request.POST.get('backup_frequency', config.backup_frequency)
            config.schedule_time = request.POST.get('schedule_time', config.schedule_time)
            config.schedule_weekday = int(request.POST.get('schedule_weekday', config.schedule_weekday or 0))
            config.custom_dates = request.POST.get('custom_dates', config.custom_dates)
            
            config.enable_terabox_backup = request.POST.get('enable_terabox_backup') == 'on'
            config.terabox_auto_folder_create = request.POST.get('terabox_auto_folder_create') == 'on'
            
            config.notification_emails = request.POST.get('notification_emails', config.notification_emails)
            config.send_success_email = request.POST.get('send_success_email') == 'on'
            config.send_failure_email = request.POST.get('send_failure_email') == 'on'
            
            config.keep_local_backups_days = int(request.POST.get('keep_local_backups_days', 30))
            config.keep_cloud_backups_days = int(request.POST.get('keep_cloud_backups_days', 365))
            
            config.is_active = request.POST.get('is_active') == 'on'
            
            config.save()
            
            # Recalculate next backup time
            from Hub.backup_utils import calculate_next_backup_time
            config.next_backup_at = calculate_next_backup_time(config)
            config.save()
            
            messages.success(request, 'Backup configuration updated successfully!')
            return redirect('admin:backup-configuration')
        
        context = {
            'config': config,
            'frequency_choices': BackupConfiguration.FREQUENCY_CHOICES,
            'weekdays': [
                (0, 'Monday'),
                (1, 'Tuesday'),
                (2, 'Wednesday'),
                (3, 'Thursday'),
                (4, 'Friday'),
                (5, 'Saturday'),
                (6, 'Sunday'),
            ],
        }
        
        return render(request, 'admin_panel/backup_configuration.html', context)
    
    except Exception as e:
        logger.error(f"Error in backup configuration: {str(e)}", exc_info=True)
        messages.error(request, f"Error: {str(e)}")
        return redirect('admin:backup-dashboard')


@admin_required
def terabox_settings(request):
    """Manage Terabox cloud storage settings."""
    try:
        terabox = TeraboxSettings.objects.first()
        if not terabox:
            terabox = TeraboxSettings.objects.create()
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'update':
                terabox.folder_root_path = request.POST.get('folder_root_path', terabox.folder_root_path)
                terabox.auto_create_folders = request.POST.get('auto_create_folders') == 'on'
                terabox.save()
                messages.success(request, 'Terabox settings updated!')
            
            return redirect('admin:terabox-settings')
        
        # Parse account info if exists
        account_info = {}
        if terabox.account_info:
            try:
                account_info = json.loads(terabox.account_info)
            except:
                pass
        
        context = {
            'terabox': terabox,
            'account_info': account_info,
            'token_expiry_hours': terabox.token_expiry_in_hours() if terabox.is_connected else 0,
        }
        
        return render(request, 'admin_panel/terabox_settings.html', context)
    
    except Exception as e:
        logger.error(f"Error in Terabox settings: {str(e)}", exc_info=True)
        messages.error(request, f"Error: {str(e)}")
        return redirect('admin:backup-dashboard')


@admin_required
def create_manual_backup(request):
    """Trigger manual backup immediately."""
    try:
        # Run backup command in background
        output = StringIO()
        call_command('create_backup', '--type', 'manual', stdout=output, stderr=output)
        
        messages.success(request, 'Backup created successfully!')
        logger.info("Manual backup triggered by admin")
        
    except Exception as e:
        logger.error(f"Error creating manual backup: {str(e)}", exc_info=True)
        messages.error(request, f"Backup failed: {str(e)}")
    
    return redirect('admin:backup-dashboard')


@admin_required
def backup_detail(request, backup_id):
    """View detailed backup information."""
    try:
        backup = get_object_or_404(BackupLog, id=backup_id)
        
        context = {
            'backup': backup,
            'data_summary': backup.get_data_summary(),
            'duration_formatted': f"{backup.duration_seconds} seconds" if backup.duration_seconds else 'N/A',
        }
        
        return render(request, 'admin_panel/backup_detail.html', context)
    
    except Exception as e:
        logger.error(f"Error loading backup detail: {str(e)}", exc_info=True)
        messages.error(request, "Error loading backup details")
        return redirect('admin:backup-history')


@admin_required
def backup_analytics(request):
    """Display backup analytics and statistics."""
    try:
        # Time period selection
        days = int(request.GET.get('days', 30))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get data for charts
        backups = BackupLog.objects.filter(start_time__gte=cutoff_date).order_by('start_time')
        
        # Success rate
        total_backups = backups.count()
        successful_backups = backups.filter(status='SUCCESS').count()
        success_rate = (successful_backups / total_backups * 100) if total_backups > 0 else 0
        
        # Data backed up over time
        daily_data = []
        for i in range(days + 1):
            date = timezone.now().date() - timedelta(days=days - i)
            day_backups = backups.filter(start_time__date=date)
            
            total_records = 0
            for backup in day_backups:
                total_records += backup.get_total_records()
            
            daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': day_backups.count(),
                'records': total_records,
            })
        
        # Backup size trend
        size_trend = backups.values('start_time__date').annotate(
            total_size=Sum('file_size_mb')
        ).order_by('start_time__date')
        
        # Status distribution
        status_dist = backups.values('status').annotate(count=Count('id'))
        
        context = {
            'backups': backups,
            'total_backups': total_backups,
            'successful_backups': successful_backups,
            'success_rate': success_rate,
            'daily_data_json': json.dumps(daily_data),
            'size_trend_json': json.dumps(list(size_trend.values())),
            'status_dist_json': json.dumps(list(status_dist.values())),
            'days': days,
        }
        
        return render(request, 'admin_panel/backup_analytics.html', context)
    
    except Exception as e:
        logger.error(f"Error loading backup analytics: {str(e)}", exc_info=True)
        messages.error(request, "Error loading analytics")
        return redirect('admin:backup-dashboard')


@admin_required
def api_backup_status(request):
    """API endpoint for getting current backup status (AJAX)."""
    try:
        backup_id = request.GET.get('backup_id')
        
        if backup_id:
            backup = get_object_or_404(BackupLog, id=backup_id)
            data = {
                'id': backup.id,
                'status': backup.status,
                'start_time': backup.start_time.isoformat(),
                'end_time': backup.end_time.isoformat() if backup.end_time else None,
                'duration': backup.duration_seconds,
                'records': backup.get_total_records(),
                'file_size_mb': float(backup.file_size_mb),
                'terabox_synced': backup.terabox_synced,
                'error_message': backup.error_message,
            }
        else:
            # Get latest backup
            backup = BackupLog.objects.order_by('-start_time').first()
            if backup:
                data = {
                    'id': backup.id,
                    'status': backup.status,
                    'start_time': backup.start_time.isoformat(),
                    'end_time': backup.end_time.isoformat() if backup.end_time else None,
                    'duration': backup.duration_seconds,
                    'records': backup.get_total_records(),
                    'file_size_mb': float(backup.file_size_mb),
                    'terabox_synced': backup.terabox_synced,
                }
            else:
                data = {'status': 'no_backup'}
        
        return JsonResponse(data)
    
    except Exception as e:
        logger.error(f"Error in backup status API: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=400)


@admin_required
def api_data_stats(request):
    """API endpoint for getting current data statistics."""
    try:
        data = {
            'users': DjangoUser.objects.count(),
            'orders': Order.objects.count(),
            'order_items': OrderItem.objects.count(),
            'products': Product.objects.count(),
            'returns': ReturnRequest.objects.count(),
            'total_revenue': float(Order.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
            'avg_order_value': float(Order.objects.filter(total_amount__isnull=False).aggregate(models.Avg('total_amount'))['total_amount__avg'] or 0),
        }
        return JsonResponse(data)
    
    except Exception as e:
        logger.error(f"Error in data stats API: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=400)
