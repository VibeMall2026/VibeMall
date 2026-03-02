"""
Backup utilities for VibeMall
Handles email notifications, Terabox integration, and common backup operations
"""

import os
import json
import requests
import logging
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_backup_notification_email(backup_log, backup_files, recipient_emails):
    """
    Send backup completion notification email to admin(s).
    
    Args:
        backup_log: BackupLog instance
        backup_files: Dict of backup files created
        recipient_emails: List of recipient email addresses
    """
    try:
        # Prepare email context
        context = {
            'backup_id': backup_log.id,
            'backup_type': backup_log.get_backup_type_display(),
            'status': backup_log.get_status_display(),
            'start_time': backup_log.start_time,
            'end_time': backup_log.end_time,
            'duration': f"{backup_log.duration_seconds} seconds" if backup_log.duration_seconds else 'N/A',
            'data_summary': backup_log.get_data_summary(),
            'terabox_synced': backup_log.terabox_synced,
            'file_count': len(backup_files),
            'total_size_mb': backup_log.file_size_mb,
            'error_message': backup_log.error_message if backup_log.status == 'FAILED' else None,
        }
        
        # Render email template
        html_message = render_to_string('admin_panel/backup_email.html', context)
        text_message = render_to_string('admin_panel/backup_email.txt', context)
        
        # Create email
        subject = f"✅ VibeMall Backup #{backup_log.id} - {backup_log.get_status_display()}"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_emails,
        )
        email.attach_alternative(html_message, "text/html")
        
        # Attach backup logs
        if backup_log.status == 'FAILED' and backup_log.error_trace:
            email.attach('error_trace.txt', backup_log.error_trace, 'text/plain')
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Backup notification email sent to {len(recipient_emails)} recipients")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send backup notification email: {str(e)}", exc_info=True)
        return False


def upload_to_terabox(terabox_settings, file_path, file_name):
    """
    Upload a file to Terabox cloud storage.
    
    Args:
        terabox_settings: TeraboxSettings instance
        file_path: Full path to local file
        file_name: Name to use in Terabox
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        # Check token expiry
        if terabox_settings.is_token_expired():
            refresh_terabox_token(terabox_settings)
        
        # Create dated folder if enabled
        terabox_path = terabox_settings.folder_root_path
        
        if terabox_settings.auto_create_folders:
            today = datetime.now().day
            # Create folder for specific dates (01, 07, 15, 30)
            if today in [1, 7, 15, 30]:
                folder_name = f"{today:02d}_{datetime.now().strftime('%B')}"
                terabox_path = os.path.join(terabox_settings.folder_root_path, folder_name)
                
                # Create folder in Terabox
                create_terabox_folder(terabox_settings, terabox_path)
        
        # Upload file to Terabox
        upload_url = "https://api.terabox.com/drive/v1/files/upload"
        
        headers = {
            'Authorization': f"Bearer {terabox_settings.api_access_token}",
        }
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f)}
            data = {'path': terabox_path}
            
            response = requests.post(upload_url, headers=headers, files=files, data=data)
        
        if response.status_code == 200:
            logger.info(f"Successfully uploaded {file_name} to Terabox")
            return True
        else:
            logger.error(f"Terabox upload failed: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error uploading to Terabox: {str(e)}", exc_info=True)
        return False


def create_terabox_folder(terabox_settings, folder_path):
    """
    Create a folder in Terabox if it doesn't exist.
    
    Args:
        terabox_settings: TeraboxSettings instance
        folder_path: Path to create
    
    Returns:
        bool: True if successful or folder exists
    """
    try:
        url = "https://api.terabox.com/drive/v1/files/mkdir"
        
        headers = {
            'Authorization': f"Bearer {terabox_settings.api_access_token}",
        }
        
        data = {'path': folder_path}
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 409]:  # 409 = folder already exists
            logger.info(f"Terabox folder ready: {folder_path}")
            return True
        else:
            logger.warning(f"Failed to create Terabox folder: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error creating Terabox folder: {str(e)}", exc_info=True)
        return False


def refresh_terabox_token(terabox_settings):
    """
    Refresh Terabox access token using refresh token.
    
    Args:
        terabox_settings: TeraboxSettings instance
    
    Returns:
        bool: True if refresh successful
    """
    try:
        if not terabox_settings.refresh_token:
            logger.error("No refresh token available")
            return False
        
        # Note: Actual implementation depends on Terabox API
        # This is a placeholder for the token refresh logic
        logger.warning("Token refresh not yet implemented")
        return False
    
    except Exception as e:
        logger.error(f"Error refreshing Terabox token: {str(e)}", exc_info=True)
        return False


def authenticate_terabox(code, state):
    """
    Authenticate with Terabox using OAuth code.
    
    Args:
        code: Authorization code from Terabox OAuth
        state: State parameter for security
    
    Returns:
        dict: Token information if successful
    """
    try:
        from Hub.models import TeraboxSettings
        
        # Exchange code for token
        token_url = "https://api.terabox.com/oauth/2.0/token"
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': settings.TERABOX_CLIENT_ID,
            'client_secret': settings.TERABOX_CLIENT_SECRET,
            'redirect_uri': settings.TERABOX_REDIRECT_URI,
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Save token to database
            from django.utils import timezone
            from datetime import timedelta
            
            terabox_settings, _ = TeraboxSettings.objects.get_or_create(pk=1)
            terabox_settings.api_access_token = token_data['access_token']
            terabox_settings.refresh_token = token_data.get('refresh_token', '')
            terabox_settings.token_expires_at = timezone.now() + timedelta(
                seconds=token_data.get('expires_in', 3600)
            )
            terabox_settings.is_connected = True
            terabox_settings.connection_status_message = "Successfully authenticated"
            terabox_settings.save()
            
            logger.info("Successfully authenticated with Terabox")
            return token_data
        else:
            logger.error(f"Terabox authentication failed: {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"Error authenticating with Terabox: {str(e)}", exc_info=True)
        return None


def get_terabox_account_info(terabox_settings):
    """
    Get Terabox account information.
    
    Args:
        terabox_settings: TeraboxSettings instance
    
    Returns:
        dict: Account information
    """
    try:
        url = "https://api.terabox.com/drive/v1/user"
        
        headers = {
            'Authorization': f"Bearer {terabox_settings.api_access_token}",
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            account_data = response.json()
            
            # Save account info
            terabox_settings.account_info = json.dumps(account_data)
            terabox_settings.save()
            
            return account_data
        else:
            logger.error(f"Failed to fetch Terabox account info: {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"Error fetching Terabox account info: {str(e)}", exc_info=True)
        return None


def cleanup_old_backups(days_to_keep_local=30, days_to_keep_cloud=365):
    """
    Clean up old backup files based on retention policy.
    
    Args:
        days_to_keep_local: Keep local backups for this many days
        days_to_keep_cloud: Keep cloud backups for this many days
    """
    try:
        from Hub.models import BackupLog
        from datetime import timedelta
        from django.utils import timezone
        
        cutoff_date_local = timezone.now() - timedelta(days=days_to_keep_local)
        cutoff_date_cloud = timezone.now() - timedelta(days=days_to_keep_cloud)
        
        # Delete old local backups
        old_local_backups = BackupLog.objects.filter(
            created_at__lt=cutoff_date_local,
            local_file_path__isnull=False
        )
        
        deleted_count = 0
        for backup in old_local_backups:
            try:
                if os.path.exists(backup.local_file_path):
                    os.remove(backup.local_file_path)
                backup.delete()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting backup {backup.id}: {str(e)}")
        
        logger.info(f"Cleaned up {deleted_count} old local backups")
        
        # Note: Cloud cleanup would require Terabox API call
        logger.info(f"Cloud backup cleanup requires manual Terabox API implementation")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_backups: {str(e)}", exc_info=True)


def calculate_next_backup_time(backup_config):
    """
    Calculate next backup execution time based on configuration.
    
    Args:
        backup_config: BackupConfiguration instance
    
    Returns:
        datetime: Next backup time
    """
    from datetime import timedelta, time
    from django.utils import timezone
    today = timezone.now().date()
    
    schedule_time = backup_config.schedule_time  # TimeField
    
    if backup_config.backup_frequency == 'DAILY':
        next_time = timezone.make_aware(
            datetime.combine(today + timedelta(days=1), schedule_time)
        )
    
    elif backup_config.backup_frequency == 'WEEKLY':
        target_weekday = backup_config.schedule_weekday or 0
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7
        next_date = today + timedelta(days=days_ahead)
        next_time = timezone.make_aware(
            datetime.combine(next_date, schedule_time)
        )
    
    elif backup_config.backup_frequency == 'BIWEEKLY':
        next_time = timezone.make_aware(
            datetime.combine(today + timedelta(days=14), schedule_time)
        )
    
    elif backup_config.backup_frequency == 'MONTHLY':
        # Next month, on the same day
        if today.month == 12:
            next_date = today.replace(year=today.year + 1, month=1)
        else:
            next_date = today.replace(month=today.month + 1)
        next_time = timezone.make_aware(
            datetime.combine(next_date, schedule_time)
        )
    
    elif backup_config.backup_frequency == 'CUSTOM':
        # Find next custom date
        custom_dates = backup_config.get_custom_dates()
        today_day = today.day
        next_custom_date = None
        
        for d in sorted(custom_dates):
            if d > today_day:
                next_custom_date = d
                break
        
        if next_custom_date:
            try:
                next_date = today.replace(day=next_custom_date)
            except ValueError:
                # Day doesn't exist in this month, skip to next month
                next_date = (today.replace(day=1) + timedelta(days=32)).replace(day=next_custom_date)
        else:
            # Next month's first custom date
            first_custom = min(custom_dates)
            if today.month == 12:
                next_date = today.replace(year=today.year + 1, month=1, day=first_custom)
            else:
                next_date = today.replace(month=today.month + 1, day=first_custom)
        
        next_time = timezone.make_aware(
            datetime.combine(next_date, schedule_time)
        )
    
    else:
        next_time = timezone.now() + timedelta(days=1)
    
    return next_time
