"""
Backup utilities for VibeMall local backup workflow.
"""

import os
import shutil
import logging
from datetime import datetime, timedelta, time

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def ensure_backup_directories(config):
    """Ensure root, regular, and special directories exist."""
    root = config.backup_root_path or r"D:\VibeMallBackUp"
    regular = os.path.join(root, config.regular_folder_name or "RegularBackUp")
    special = os.path.join(root, config.special_folder_name or "SpecialBackup")
    os.makedirs(root, exist_ok=True)
    os.makedirs(regular, exist_ok=True)
    os.makedirs(special, exist_ok=True)
    return root, regular, special


def get_month_folder(base_dir, dt=None):
    """Get/create monthly folder in YYYY-MM format under base_dir."""
    when = dt or timezone.now()
    month_label = when.strftime("%Y-%m")
    month_dir = os.path.join(base_dir, month_label)
    os.makedirs(month_dir, exist_ok=True)
    return month_dir, month_label


def send_backup_notification_email(backup_log, backup_files, recipient_emails):
    """Send plain-text backup completion notification to admins."""
    try:
        if not recipient_emails:
            return False

        status = backup_log.get_status_display()
        summary = backup_log.get_data_summary()
        body = (
            f"Backup #{backup_log.id} completed.\n"
            f"Type: {backup_log.get_backup_type_display()}\n"
            f"Scope: {backup_log.get_backup_scope_display()}\n"
            f"Status: {status}\n"
            f"Started: {backup_log.start_time}\n"
            f"Ended: {backup_log.end_time}\n"
            f"Duration: {backup_log.duration_seconds or 'N/A'} seconds\n"
            f"Month Folder: {backup_log.monthly_folder_label or '-'}\n"
            f"Files: {len(backup_files)}\n"
            f"Users: {summary['users']} | Orders: {summary['orders']} | Payments: {summary['payments']}\n"
            f"Products: {summary['products']} | Returns: {summary['returns']} | Transactions: {summary['transactions']}\n"
            f"Total Records: {summary['total']}\n"
            f"Local Path: {backup_log.local_file_path}\n"
        )
        if backup_log.error_message:
            body += f"\nError: {backup_log.error_message}\n"

        send_mail(
            subject=f"VibeMall Backup #{backup_log.id} - {status}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipient_emails,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error("Failed to send backup notification email: %s", exc, exc_info=True)
        return False


def send_cleanup_confirmation_email(cleanup_request, recipient_emails, confirmation_url):
    """Send confirmation request email before deleting old backup data."""
    try:
        if not recipient_emails:
            return False

        body = (
            "A new monthly backup has completed successfully.\n\n"
            f"Cleanup candidate folder: {cleanup_request.folder_path}\n"
            "As per policy, old data will only be deleted after admin confirmation.\n\n"
            f"Confirm cleanup: {confirmation_url}\n"
            "(Open this link as admin and click confirm.)\n"
        )

        send_mail(
            subject=f"VibeMall Cleanup Confirmation Required - {cleanup_request.folder_label}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipient_emails,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error("Failed to send cleanup confirmation email: %s", exc, exc_info=True)
        return False


def delete_folder_if_exists(folder_path):
    """Delete a folder recursively if present."""
    if folder_path and os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        return True
    return False


def normalize_dataframe_for_excel(df):
    """Strip timezone info from all datetime columns in a DataFrame for Excel compatibility."""
    import pandas as pd
    df = df.copy()  # Work on a copy to avoid modifying original
    for col in df.select_dtypes(include=['datetime64']).columns:
        # Check if column is timezone-aware
        if hasattr(df[col].dtype, 'tz') and df[col].dtype.tz is not None:
            # Remove timezone by converting to UTC then removing tz info
            df[col] = df[col].dt.tz_convert('UTC').dt.tz_localize(None)
        elif pd.api.types.is_datetime64tz_dtype(df[col]):
            # Fallback for other timezone-aware formats
            df[col] = df[col].dt.tz_localize(None)
    return df


def calculate_next_backup_time(backup_config):
    """Calculate next execution time based on configuration."""
    now = timezone.now()
    today = now.date()
    schedule_time = backup_config.schedule_time

    if isinstance(schedule_time, str):
        schedule_time = schedule_time.strip()
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                schedule_time = datetime.strptime(schedule_time, fmt).time()
                break
            except ValueError:
                continue
        else:
            schedule_time = time(3, 0)
    elif schedule_time is None:
        schedule_time = time(3, 0)

    if backup_config.backup_frequency == 'DAILY':
        next_date = today + timedelta(days=1)

    elif backup_config.backup_frequency == 'WEEKLY':
        target_weekday = backup_config.schedule_weekday or 0
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7
        next_date = today + timedelta(days=days_ahead)

    elif backup_config.backup_frequency == 'BIWEEKLY':
        next_date = today + timedelta(days=14)

    elif backup_config.backup_frequency == 'MONTHLY':
        if today.month == 12:
            next_date = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_date = today.replace(month=today.month + 1, day=1)

    elif backup_config.backup_frequency == 'CUSTOM':
        custom_dates = sorted(backup_config.get_custom_dates()) or [1, 7, 15, 30]
        candidate = None
        for day in custom_dates:
            if day > today.day:
                candidate = day
                break

        if candidate is not None:
            try:
                next_date = today.replace(day=candidate)
            except ValueError:
                next_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        else:
            first_custom = min(custom_dates)
            if today.month == 12:
                year, month = today.year + 1, 1
            else:
                year, month = today.year, today.month + 1
            try:
                next_date = today.replace(year=year, month=month, day=first_custom)
            except ValueError:
                next_date = today.replace(year=year, month=month, day=1)
    else:
        next_date = today + timedelta(days=1)

    naive = datetime.combine(next_date, schedule_time)
    return timezone.make_aware(naive)