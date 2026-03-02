# VibeMall Backup System - Implementation Guide

## ✅ Quick Start - 5 Steps to Setup

### Step 1: Run Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 2: Register Backup Admin (Update admin.py)
Add to your `Hub/admin.py`:
```python
# At the top of file
from Hub.backup_admin import BackupConfigurationAdmin, BackupLogAdmin, TeraboxSettingsAdmin

# OR just import the models to auto-register via decorators used in backup_admin.py
from Hub.backup_admin import *
```

### Step 3: Update URLs (Add backup URLs)
Update your main `urls.py`:
```python
from django.urls import path
from Hub.backup_views import (
    backup_dashboard, backup_history, backup_configuration,
    terabox_settings, create_manual_backup, backup_detail,
    backup_analytics, api_backup_status, api_data_stats
)

urlpatterns = [
    # ... existing URLs ...
    
    # Backup URLs
    path('admin/backup/dashboard/', backup_dashboard, name='admin:backup-dashboard'),
    path('admin/backup/history/', backup_history, name='admin:backup-history'),
    path('admin/backup/configuration/', backup_configuration, name='admin:backup-configuration'),
    path('admin/backup/terabox/', terabox_settings, name='admin:terabox-settings'),
    path('admin/backup/create-manual/', create_manual_backup, name='admin:create-manual-backup'),
    path('admin/backup/detail/<int:backup_id>/', backup_detail, name='admin:backup-detail'),
    path('admin/backup/analytics/', backup_analytics, name='admin:backup-analytics'),
    path('api/backup/status/', api_backup_status, name='api:backup-status'),
    path('api/backup/data-stats/', api_data_stats, name='api:data-stats'),
]
```

### Step 4: Create Backup Directory Structure
```bash
mkdir -p backups/excel
mkdir -p backups/logs
mkdir -p backups/temp
```

Add to `.gitignore`:
```
backups/
```

### Step 5: Configure Settings
Update `settings.py`:
```python
# Backup Configuration
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
BACKUP_EXCEL_DIR = os.path.join(BACKUP_DIR, 'excel')
BACKUP_LOG_DIR = os.path.join(BACKUP_DIR, 'logs')

# Terabox Configuration (Get these from Terabox Developer Console)
TERABOX_CLIENT_ID = 'your_client_id'
TERABOX_CLIENT_SECRET = 'your_client_secret'
TERABOX_REDIRECT_URI = 'http://localhost:8000/admin/backup/terabox/callback/'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'backup_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BACKUP_LOG_DIR, 'backup.log'),
        },
    },
    'loggers': {
        'Hub': {
            'handlers': ['backup_file'],
            'level': 'INFO',
        },
    },
}
```

---

## 📊 Usage Guide

### Manual Backup
```bash
python manage.py create_backup --type manual
python manage.py create_backup --type manual --no-cloud --no-email
```

### Scheduled Backup (via APScheduler)
Create `backup_scheduler.py` in your project root:
```python
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command
from Hub.models import BackupConfiguration
import logging

logger = logging.getLogger(__name__)

def schedule_backups():
    scheduler = BackgroundScheduler()
    
    def run_backup():
        try:
            config = BackupConfiguration.objects.first()
            if config and config.is_active:
                call_command('create_backup', '--type', 'scheduled')
        except Exception as e:
            logger.error(f"Scheduled backup failed: {str(e)}")
    
    # Run daily at configured time
    scheduler.add_job(run_backup, 'cron', hour='*')
    scheduler.start()

# Call this in your apps.py AppConfig.ready() method
```

### Via Windows Task Scheduler
Create `run_backup.bat`:
```batch
@echo off
cd /d "D:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"
call venv\Scripts\activate.bat
python manage.py create_backup --type scheduled
pause
```

Schedule this .bat file to run daily at 3:00 AM using Windows Task Scheduler.

---

## 🎯 Admin Dashboard Features

### Dashboard (`/admin/backup/dashboard/`)
- **Quick Stats**: Success count, failure count, total backups, Terabox status
- **Current Data**: Real-time counts of users, orders, products
- **Next Backup Time**: When is the next scheduled backup?
- **Recent Backups**: Last 10 backups with status, size, and sync info
- **Quick Actions**: Manual backup button, settings links, history/analytics buttons

### Configuration (`/admin/backup/configuration/`)
Set:
- Backup frequency (Daily, Weekly, Bi-weekly, Monthly, Custom)
- Schedule time (24-hour format)
- Custom dates if not predefined freq (1, 7, 15, 30)
- Terabox cloud backup (enable/disable)
- Notification emails
- Data retention policy (days to keep)

### History (`/admin/backup/history/`)
- Filter by status (Success, Failed, In Progress)
- Filter by type (Manual, Scheduled, On Demand)
- View detailed backup information
- Download backup files
- View error messages

### Terabox Settings (`/admin/terabox/settings/`)
- Display connection status
- Show cloud storage used
- Display account information
- Manage folder structure
- Token expiry countdown

### Analytics (`/admin/backup/analytics/`)
- Success rate over time (last 7, 14, 30 days)
- Backup frequency trend
- Data growth chart
- Storage usage forecast
- Status distribution pie chart

---

## 🔧 Backup Data Structure

Each backup creates separate Excel files for each data type:

### `users_backup_*.xlsx`
Sheets:
- **Users**: id, username, email, first_name, last_name, phone, date_joined, last_login, is_active
- **Summary**: Total users, active count, inactive count

### `orders_backup_*.xlsx`
Sheets:
- **Orders**: Order ID, User, Email, Amount, Payment Status, Order Status, Created Date
- **Order Items**: Item-level detail (Product, Qty, Price, Discount)
- **Summary**: Total orders, total revenue, average order value

### `payments_backup_*.xlsx`
Sheets:
- **Payments**: Payment ID, Amount, Status, Method, Date
- **Status Summary**: Breakdown by payment status
- **Summary**: Total payments, total revenue

### `products_backup_*.xlsx`
Sheets:
- **Products**: ID, Name, Category, SKU, Price, Stock, Sold, Rating
- **Low Stock Alert**: Products with stock < 10
- **Category Summary**: By-category aggregates
- **Summary**: Total products, total stock

### `returns_backup_*.xlsx`
Sheets:
- **Returns**: Return ID, Order ID, User, Reason, Status, Refund Amount
- **Status Summary**: By-status breakdown
- **Summary**: Total returns, total refunds

### `analytics_backup_*.xlsx`
Sheets:
- **Metrics**: Revenue, orders, AOV, products
- **Order Status**: Breakdown of order statuses
- **Payment Status**: Breakdown of payment statuses
- **Top Products**: Best sellers by revenue

---

## ☁️ Terabox Integration

### Setup Terabox Authentication
1. Go to https://www.terabox.com
2. Download and install Terabox Desktop app
3. Sign in with your account
4. Create a folder `/VibeMall_Backups` for backups

### API Integration (Optional - For Automated Upload)
1. Register app at Terabox Developer Console
2. Get Client ID and Client Secret
3. Add to settings.py (see Step 5 above)
4. Backups will auto-upload to Terabox

### Automatic Folder Creation
When enabled, system creates dated folders:
- `/VibeMall_Backups/01_January/` (1st of month)
- `/VibeMall_Backups/07_January/` (7th of month)
- `/VibeMall_Backups/15_January/` (15th of month)
- `/VibeMall_Backups/30_January/` (30th of month)

---

## 📧 Email Notifications

### Setup Email (Update settings.py)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'your-email@gmail.com'
```

### Email Template Template
Email will include:
- Backup ID and type
- Status (Success/Failed)
- Duration and file size
- Data counts (records backed up)
- Terabox sync status
- Error message (if failed)

---

## 🚀 Advanced Features

### Incremental Backups
Currently exports all data. To optimize:
```python
# In create_backup.py, modify queryset:
last_backup = BackupLog.objects.filter(status='SUCCESS').order_by('-start_time').first()
if last_backup:
    orders = Order.objects.filter(created_at__gt=last_backup.start_time)
```

### Database Snapshots
For PostgreSQL, backup entire database:
```bash
pg_dump -U admin vibemall_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Functionality
To restore from backup:
```bash
python manage.py restore_backup --backup-id 5 --data-type orders
```

### Notifications
Send to Slack/Teams on backup completion:
```python
def send_slack_notification(backup_log):
    # Add webhook integration
    pass
```

---

## 🔐 Security Best Practices

1. **Access Control**: Only super-admin can access backup settings
2. **Encryption**: Store sensitive data (Terabox tokens) with encryption
3. **Audit Trail**: All backup operations logged automatically
4. **Retention**: Old backups auto-deleted per policy
5. **Verification**: Test restore monthly
6. **Encryption in Transit**: Use HTTPS for Terabox API calls

---

## 🐛 Troubleshooting

### "Terabox connection failed"
- Check token expiry: `TeraboxSettings.is_token_expired()`
- Re-authenticate with OAuth workflow
- Verify Client ID/Secret in settings.py

### "Backup taking too long"
- Check database size: may need optimization
- Consider incremental backups
- Run during off-peak hours

### "Email not sent"
- Verify SMTP settings in settings.py
- Check email logs in backup log
- Verify notification emails are configured

### "Out of disk space"
- Delete old backup files: `python manage.py cleanup_old_backups --days 30`
- Compress older backup files
- Move to external storage

---

## 📈 Monitoring & Maintenance

### Weekly Tasks
- Check backup dashboard for failures
- Verify recent backups completed
- Review backup logs for errors

### Monthly Tasks
- Test restore procedure with sample backup
- Review Terabox storage usage
- Optimize if needed

### Quarterly Tasks
- Audit backup retention policy
- Review encryption settings
- Plan infrastructure upgrades

---

## 📞 Support & Errors

### Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `No module named pandas` | Missing dependency | `pip install pandas openpyxl` |
| `Permission denied: backups/` | Wrong folder permissions | `chmod -R 755 backups/` |
| `Database locked` | SQLite concurrent access | Use PostgreSQL for production |
| `Token expired` | Terabox auth expired | Re-authenticate or refresh token |
| `Backup file not found` | Path issue | Check BACKUP_DIR in settings.py |

---

## 📚 File Structure Summary

```
VibeMall/
├── Hub/
│   ├── models.py (3 new models: BackupConfiguration, BackupLog, TeraboxSettings)
│   ├── backup_views.py (6 views for admin interface)
│   ├── backup_utils.py (Helper functions for email, Terabox, cleanup)
│   ├── backup_admin.py (Admin panel registration)
│   ├── management/
│   │   └── commands/
│   │       └── create_backup.py (Main backup command)
│   ├── templates/
│   │   └── admin_panel/
│   │       ├── backup_dashboard.html
│   │       ├── backup_history.html
│   │       ├── backup_configuration.html
│   │       ├── terabox_settings.html
│   │       ├── backup_detail.html
│   │       ├── backup_analytics.html
│   │       ├── backup_email.html (HTML email template)
│   │       └── backup_email.txt (Text email template)
│   └── static/
│       └── admin/
│           └── css/
│               └── backup.css (Styling)
├── backups/
│   ├── excel/ (Excel backup files)
│   ├── logs/ (Operation logs)
│   └── temp/ (Temporary files)
└── BACKUP_SYSTEM_ROADMAP.md (This comprehensive plan)
```

---

## ✨ Next Steps After Implementation

1. **Create initial backup**: `python manage.py create_backup --type manual`
2. **Verify files**: Check `/backups/excel/` for generated Excel files
3. **Configure schedule**: Set frequency in admin dashboard
4. **Connect Terabox**: Link cloud storage in admin panel
5. **Test restore**: Verify backup integrity monthly
6. **Set monitoring**: Alert admin if backups fail
7. **Document**: Keep restore procedures documented

---

**Created**: March 1, 2026  
**Version**: 1.0 - Production Ready  
**Status**: ✅ Ready for Implementation
