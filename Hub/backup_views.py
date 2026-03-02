"""
Backup Admin Views for local backup management.
"""

import os
import json
import logging
from datetime import timedelta, datetime, time
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.management import call_command
from django.db.models import Sum, Count, Avg
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

from Hub.backup_utils import ensure_backup_directories, get_month_folder, delete_folder_if_exists, calculate_next_backup_time, normalize_dataframe_for_excel
from Hub.itr_utils import generate_itr_excel
from Hub.models import (
    BackupConfiguration,
    BackupLog,
    BackupCleanupRequest,
    Order,
    Product,
    User as DjangoUser,
    ReturnRequest,
    OrderItem,
)

logger = logging.getLogger(__name__)


def admin_required(view_func):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Access denied")
        return view_func(request, *args, **kwargs)
    return wrapped


@admin_required
def backup_dashboard(request):
    config, _ = BackupConfiguration.objects.get_or_create(pk=1)
    _, regular_root, special_root = ensure_backup_directories(config)
    recent_backups = BackupLog.objects.all()[:10]
    cleanup_pending_count = BackupCleanupRequest.objects.filter(status='PENDING').count()

    context = {
        'config': config,
        'recent_backups': recent_backups,
        'successful_backups': BackupLog.objects.filter(status='SUCCESS').count(),
        'failed_backups': BackupLog.objects.filter(status='FAILED').count(),
        'total_backups': BackupLog.objects.count(),
        'last_backup': BackupLog.objects.order_by('-start_time').first(),
        'users_count': DjangoUser.objects.count(),
        'orders_count': Order.objects.count(),
        'products_count': Product.objects.count(),
        'next_backup_time': calculate_next_backup_time(config),
        'backup_root': config.backup_root_path,
        'regular_root': regular_root,
        'special_root': special_root,
        'cleanup_pending_count': cleanup_pending_count,
    }
    return render(request, 'admin_panel/backup_dashboard.html', context)


@admin_required
def backup_configuration(request):
    config, _ = BackupConfiguration.objects.get_or_create(pk=1)

    if request.method == 'POST':
        config.backup_frequency = request.POST.get('backup_frequency', config.backup_frequency)

        posted_schedule_time = request.POST.get('schedule_time')
        if posted_schedule_time:
            try:
                config.schedule_time = datetime.strptime(posted_schedule_time, '%H:%M').time()
            except ValueError:
                messages.error(request, 'Invalid schedule time format. Please use HH:MM.')
                return redirect('admin_backup_configuration')
        elif not config.schedule_time:
            config.schedule_time = time(3, 0)

        config.schedule_weekday = int(request.POST.get('schedule_weekday', config.schedule_weekday or 0))
        config.custom_dates = request.POST.get('custom_dates', config.custom_dates)
        config.backup_root_path = request.POST.get('backup_root_path', config.backup_root_path)
        config.regular_folder_name = request.POST.get('regular_folder_name', config.regular_folder_name)
        config.special_folder_name = request.POST.get('special_folder_name', config.special_folder_name)
        config.notification_emails = request.POST.get('notification_emails', config.notification_emails)
        config.send_success_email = request.POST.get('send_success_email') == 'on'
        config.send_failure_email = request.POST.get('send_failure_email') == 'on'
        config.is_active = request.POST.get('is_active') == 'on'
        config.enable_terabox_backup = False
        config.save()

        config.next_backup_at = calculate_next_backup_time(config)
        config.save(update_fields=['next_backup_at', 'updated_at'])
        ensure_backup_directories(config)
        messages.success(request, 'Backup configuration saved successfully.')
        return redirect('admin_backup_configuration')

    return render(
        request,
        'admin_panel/backup_configuration.html',
        {
            'config': config,
            'frequency_choices': BackupConfiguration.FREQUENCY_CHOICES,
            'weekdays': [(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')],
        },
    )


@admin_required
def backup_history(request):
    page = int(request.GET.get('page', 1))
    filter_status = request.GET.get('status', '')
    filter_type = request.GET.get('type', '')

    backups = BackupLog.objects.all().order_by('-start_time')
    if filter_status:
        backups = backups.filter(status=filter_status)
    if filter_type:
        backups = backups.filter(backup_type=filter_type)

    per_page = 20
    total = backups.count()
    start = (page - 1) * per_page
    end = start + per_page

    context = {
        'backups': backups[start:end],
        'total': total,
        'page': page,
        'total_pages': (total + per_page - 1) // per_page,
        'filter_status': filter_status,
        'filter_type': filter_type,
        'status_choices': BackupLog.STATUS_CHOICES,
        'type_choices': BackupLog.BACKUP_TYPE_CHOICES,
    }
    return render(request, 'admin_panel/backup_history.html', context)


@admin_required
def create_manual_backup(request):
    try:
        output = StringIO()
        call_command('create_backup', '--type', 'manual', '--mode', 'regular', stdout=output, stderr=output)
        messages.success(request, 'Regular backup created successfully.')
    except Exception as exc:
        logger.error("Manual backup failed: %s", exc, exc_info=True)
        messages.error(request, f'Backup failed: {exc}')
    return redirect('admin_backup_dashboard')


@admin_required
def create_special_backup(request):
    if request.method != 'POST':
        return redirect('admin_backup_dashboard')

    selected_types = request.POST.getlist('data_types')
    if not selected_types:
        messages.error(request, 'Please select at least one data type for special backup.')
        return redirect('admin_backup_dashboard')

    try:
        output = StringIO()
        call_command(
            'create_backup',
            '--type', 'special',
            '--mode', 'special',
            '--data-types', ','.join(selected_types),
            stdout=output,
            stderr=output,
        )
        messages.success(request, 'Special backup created successfully in SpecialBackup folder.')
    except Exception as exc:
        logger.error("Special backup failed: %s", exc, exc_info=True)
        messages.error(request, f'Special backup failed: {exc}')

    return redirect('admin_backup_dashboard')


def _compute_report_range(report_type, custom_from=None, custom_to=None):
    now = timezone.now()
    if report_type == 'monthly':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif report_type == 'six_month':
        start = now - timedelta(days=183)
        end = now
    elif report_type == 'yearly':
        start = now - timedelta(days=365)
        end = now
    else:
        start = datetime.strptime(custom_from, '%Y-%m-%d')
        end = datetime.strptime(custom_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


@admin_required
def itr_reports(request):
    """Generate comprehensive Indian Income Tax Return (ITR-3) compliant reports."""
    if request.method == 'POST':
        report_type = request.POST.get('report_type', 'monthly')
        custom_from = request.POST.get('date_from')
        custom_to = request.POST.get('date_to')
        start, end = _compute_report_range(report_type, custom_from, custom_to)

        config, _ = BackupConfiguration.objects.get_or_create(pk=1)
        _, _, special_root = ensure_backup_directories(config)
        month_dir, month_label = get_month_folder(special_root)
        report_time = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ITR_Report_{report_type}_{report_time}.xlsx"
        report_path = os.path.join(month_dir, filename)

        try:
            # Generate comprehensive ITR report
            generate_itr_excel(start, end, report_path)
            
            log = BackupLog.objects.create(
                backup_type='ITR_REPORT',
                backup_scope='ITR',
                backup_frequency=config.backup_frequency,
                status='SUCCESS',
                start_time=timezone.now(),
                end_time=timezone.now(),
                local_file_path=report_path,
                monthly_folder_label=month_label,
                backup_data_types='itr_report,financial_analysis,tax_computation',
                file_size_mb=round(os.path.getsize(report_path) / (1024 * 1024), 2),
            )

            messages.success(request, f'ITR Report generated successfully: {filename}')

            with open(report_path, 'rb') as fp:
                response = HttpResponse(
                    fp.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename={filename}'
                return response
        
        except Exception as exc:
            logger.error(f"ITR report generation failed: {exc}", exc_info=True)
            messages.error(request, f'ITR report generation failed: {str(exc)}')
            return redirect('admin_backup_dashboard')

    return render(request, 'admin_panel/itr_reports.html')


@admin_required
def cleanup_confirmation(request, token):
    cleanup = get_object_or_404(BackupCleanupRequest, confirmation_token=token)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            removed = delete_folder_if_exists(cleanup.folder_path)
            cleanup.status = 'COMPLETED' if removed else 'DECLINED'
            cleanup.confirmed_at = timezone.now()
            cleanup.confirmed_by = request.user
            cleanup.save()
            messages.success(request, 'Old backup folder cleaned successfully.' if removed else 'Cleanup skipped (folder missing).')
        else:
            cleanup.status = 'DECLINED'
            cleanup.confirmed_at = timezone.now()
            cleanup.confirmed_by = request.user
            cleanup.save()
            messages.info(request, 'Cleanup request declined. Old data retained.')
        return redirect('admin_backup_dashboard')

    return render(request, 'admin_panel/cleanup_confirmation.html', {'cleanup': cleanup})


@admin_required
def backup_detail(request, backup_id):
    backup = get_object_or_404(BackupLog, id=backup_id)
    return render(
        request,
        'admin_panel/backup_detail.html',
        {
            'backup': backup,
            'data_summary': backup.get_data_summary(),
            'duration_formatted': f"{backup.duration_seconds} seconds" if backup.duration_seconds else 'N/A',
        },
    )


@admin_required
def backup_analytics(request):
    days = int(request.GET.get('days', 30))
    cutoff_date = timezone.now() - timedelta(days=days)
    backups = BackupLog.objects.filter(start_time__gte=cutoff_date).order_by('start_time')

    total_backups = backups.count()
    successful_backups = backups.filter(status='SUCCESS').count()
    success_rate = (successful_backups / total_backups * 100) if total_backups else 0

    daily_data = []
    for i in range(days + 1):
        date = timezone.now().date() - timedelta(days=days - i)
        day_backups = backups.filter(start_time__date=date)
        records = sum(item.get_total_records() for item in day_backups)
        daily_data.append({'date': date.strftime('%Y-%m-%d'), 'count': day_backups.count(), 'records': records})

    size_trend = backups.values('start_time__date').annotate(total_size=Sum('file_size_mb')).order_by('start_time__date')
    status_dist = backups.values('status').annotate(count=Count('id'))

    return render(
        request,
        'admin_panel/backup_analytics.html',
        {
            'backups': backups,
            'total_backups': total_backups,
            'successful_backups': successful_backups,
            'success_rate': success_rate,
            'daily_data_json': json.dumps(daily_data, cls=DjangoJSONEncoder),
            'size_trend_json': json.dumps(list(size_trend.values()), cls=DjangoJSONEncoder),
            'status_dist_json': json.dumps(list(status_dist.values()), cls=DjangoJSONEncoder),
            'days': days,
        },
    )


@admin_required
def api_backup_status(request):
    backup_id = request.GET.get('backup_id')
    backup = get_object_or_404(BackupLog, id=backup_id) if backup_id else BackupLog.objects.order_by('-start_time').first()
    if not backup:
        return JsonResponse({'status': 'no_backup'})

    return JsonResponse({
        'id': backup.id,
        'status': backup.status,
        'start_time': backup.start_time.isoformat(),
        'end_time': backup.end_time.isoformat() if backup.end_time else None,
        'duration': backup.duration_seconds,
        'records': backup.get_total_records(),
        'file_size_mb': float(backup.file_size_mb),
        'scope': backup.backup_scope,
        'monthly_folder_label': backup.monthly_folder_label,
    })


@admin_required
def api_data_stats(request):
    data = {
        'users': DjangoUser.objects.count(),
        'orders': Order.objects.count(),
        'order_items': OrderItem.objects.count(),
        'products': Product.objects.count(),
        'returns': ReturnRequest.objects.count(),
        'total_revenue': float(Order.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
        'avg_order_value': float(Order.objects.filter(total_amount__isnull=False).aggregate(Avg('total_amount'))['total_amount__avg'] or 0),
    }
    return JsonResponse(data)
