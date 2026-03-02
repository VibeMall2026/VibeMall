# VibeMall Backup System - Architecture & Integration

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      VibeMall Admin Panel                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   BACKUP ADMIN INTERFACE                    │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │                                                              │  │
│  │  📊 Dashboard          └─ 🎛️ Configuration Page            │  │
│  │  ├─ Quick Stats           ├─ Frequency Selection           │  │
│  │  ├─ Data Summary          ├─ Time Settings                 │  │
│  │  ├─ Backup Status         ├─ Terabox Config               │  │
│  │  └─ Recent Backups        ├─ Email Settings               │  │
│  │                           └─ Retention Policy              │  │
│  │                                                              │  │
│  │  📜 History              ☁️ Terabox Settings               │  │
│  │  ├─ Filter by Status      ├─ Connection Status            │  │
│  │  ├─ Search & Sort         ├─ Token Management             │  │
│  │  ├─ View Details          ├─ Folder Config                │  │
│  │  └─ Download Files        └─ Storage Usage                │  │
│  │                                                              │  │
│  │  📈 Analytics            ▶️ Manual Backup                   │  │
│  │  ├─ Success Rate          └─ Trigger Now Button            │  │
│  │  ├─ Data Trends                                            │  │
│  │  └─ Size Forecasts                                         │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ↓            ↓            ↓
                    
        ┌─────────────────────┬──────────────┬─────────────────────┐
        │   BACKUP ENGINE     │  SCHEDULER   │   NOTIFICATIONS     │
        ├─────────────────────┼──────────────┼─────────────────────┤
        │                     │              │                     │
        │ create_backup.py    │ APScheduler  │ Email Sender        │
        │ ├─ Export Users    │ │ Daily      │ ├─ HTML Template    │
        │ ├─ Export Orders   │ │ Weekly     │ ├─ Text Template    │
        │ ├─ Export Payments │ │ Monthly    │ └─ SMTP Config      │
        │ ├─ Export Products │ │ Custom     │                     │
        │ ├─ Export Returns  │ │            │ Slack Integration   │
        │ └─ Export Analytics│ │            │ (Optional)          │
        │                     │              │                     │
        │ backup_utils.py     │ calc_next_   │ SMS Alerts          │
        │ ├─ Excel Multi-     │ backup_time()│ (Future)            │
        │ │   Sheet Format    │              │                     │
        │ ├─ Error Handler    │              │                     │
        │ └─ Logging          │              │                     │
        │                     │              │                     │
        └─────────────────────┴──────────────┴─────────────────────┘
                    │            │            │
                    └────────────┼────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ↓                         ↓
                    
        ┌──────────────────────────────┬──────────────────────────────┐
        │    BACKUP STORAGE            │   CLOUD SYNC                │
        ├──────────────────────────────┼──────────────────────────────┤
        │                              │                              │
        │ /backups/excel/              │ ☁️ Terabox API              │
        │ ├─ users_backup_*.xlsx       │ ├─ OAuth Authentication     │
        │ ├─ orders_backup_*.xlsx      │ ├─ Auto Folder Creation     │
        │ ├─ payments_backup_*.xlsx    │ │ (01, 07, 15, 30)          │
        │ ├─ products_backup_*.xlsx    │ ├─ File Upload              │
        │ ├─ returns_backup_*.xlsx     │ ├─ Token Refresh            │
        │ └─ analytics_backup_*.xlsx   │ └─ Storage Tracking         │
        │                              │                              │
        │ /backups/logs/               │ Terabox Desktop             │
        │ └─ backup.log                │ └─ Real-time Sync           │
        │                              │                              │
        └──────────────────────────────┴──────────────────────────────┘
                    │                         │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┴────────────────────────┐
        │          BACKUP RECORDS (DATABASE)              │
        ├─────────────────────────────────────────────────┤
        │                                                 │
        │ BackupLog                                       │
        │ ├─ Backup ID, Type, Status                     │
        │ ├─ Start/End Time, Duration                    │
        │ ├─ Data Counts (users, orders, etc)            │
        │ ├─ File Paths (local & cloud)                  │
        │ ├─ Error Messages (if failed)                  │
        │ └─ Terabox Sync Status                         │
        │                                                 │
        │ BackupConfiguration                             │
        │ ├─ Frequency & Schedule                        │
        │ ├─ Email Recipients                            │
        │ ├─ Terabox Settings                            │
        │ └─ Retention Policies                          │
        │                                                 │
        │ TeraboxSettings                                │
        │ ├─ API Tokens                                  │
        │ ├─ Connection Status                           │
        │ └─ Account Info                                │
        │                                                 │
        └─────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
USER ACTION                  SYSTEM PROCESS                    OUTPUT
─────────────────────────────────────────────────────────────────────────

1. Manual Trigger
   │
   └─→ Click "Backup Now"      
       │
       └─→ create_backup.py runs
           │
           ├─→ DB Query Users    ──→ DataFrame ──→ Excel Sheet
           │
           ├─→ DB Query Orders   ──→ DataFrame ──→ Excel Sheet  
           │
           ├─→ DB Query Payments ──→ DataFrame ──→ Excel Sheet
           │
           ├─→ DB Query Products ──→ DataFrame ──→ Excel Sheet
           │
           ├─→ DB Query Returns  ──→ DataFrame ──→ Excel Sheet
           │
           └─→ Calculate Analytics ──→ Excel Sheet
               │
               ├─→ Save to /backups/excel/
               │
               ├─→ Update BackupLog (records, size)
               │
               ├─→ Upload to Terabox
               │   └─→ Create dated folder
               │   └─→ Upload Excel files
               │   └─→ Update TeraboxSettings
               │
               └─→ Send notification email
                   └─→ BackupLog.email_sent = True

2. Scheduled Trigger
   │
   └─→ Scheduler checks time  
       │
       └─→ Matches BackupConfiguration
           │
           └─→ [Same process as Manual Trigger]
               └─→ Runs automatically at 3:00 AM
               └─→ Admin gets emailed
               └─→ Files synced to Terabox

3. Admin Views Data
   │
   └─→ Click Backup Dashboard
       │
       ├─→ Load BackupLog entries (recent 10)
       │
       ├─→ Calculate stats (success rate, total, failed)
       │
       ├─→ Show current DB counts
       │
       └─→ Display data visualization
```

---

## Database Schema

```
┌─────────────────────────────────┐
│     BackupConfiguration         │
├─────────────────────────────────┤
│ id (PK)                        │
│ backup_frequency (Char/Choice) │
│ schedule_time (Time)           │
│ schedule_weekday (Int)         │
│ custom_dates (String)          │
│ enable_terabox_backup (Bool)   │
│ terabox_auto_folder_create     │
│ notification_emails (Text)     │
│ send_success_email (Bool)      │
│ send_failure_email (Bool)      │
│ keep_local_backups_days (Int)  │
│ keep_cloud_backups_days (Int)  │
│ is_active (Bool)               │
│ last_backup_at (DateTime)      │
│ next_backup_at (DateTime)      │
│ created_at (DateTime)          │
│ updated_at (DateTime)          │
└─────────────────────────────────┘
          │
          │ Single Instance
          │
          ▼
          
┌──────────────────────────────────┐
│  BackupLog (1 per backup created)│
├──────────────────────────────────┤
│ id (PK)                         │
│ backup_type (Char/Choice)       │
│ backup_frequency (Char)         │
│ status (Char/Choice)            │
│ start_time (DateTime)           │
│ end_time (DateTime)             │
│ users_count (Int)               │
│ orders_count (Int)              │
│ payments_count (Int)            │
│ products_count (Int)            │
│ returns_count (Int)             │
│ transactions_count (Int)        │
│ local_file_path (Text)          │
│ terabox_file_path (Text)        │
│ file_size_mb (Decimal)          │
│ terabox_synced (Bool)           │
│ email_sent (Bool)               │
│ error_message (Text)            │
│ error_trace (Text)              │
│ backup_data_types (Text)        │
│ notes (Text)                    │
│ created_at (DateTime)           │
│ updated_at (DateTime)           │
└──────────────────────────────────┘
          │
          │ Many logs
          │
          ▼

┌──────────────────────────────────┐
│     TeraboxSettings              │
├──────────────────────────────────┤
│ id (PK)                         │
│ api_access_token (Text)         │
│ refresh_token (Text)            │
│ token_expires_at (DateTime)     │
│ folder_root_path (Char)         │
│ auto_create_folders (Bool)      │
│ is_connected (Bool)             │
│ connection_status_message       │
│ last_sync_time (DateTime)       │
│ total_backups_synced (Int)      │
│ cloud_storage_used_mb (Decimal) │
│ account_info (Text/JSON)        │
│ created_at (DateTime)           │
│ updated_at (DateTime)           │
└──────────────────────────────────┘
          │
          │ Single Instance
          │
          ▼
```

---

## Integration Points

### With Existing VibeMall Code

```
Hub/models.py
├─ User (Django Built-in)
├─ Order
├─ OrderItem
├─ Product
├─ Payment
├─ ReturnRequest
├─ Category
│
├─ NEW: BackupConfiguration
├─ NEW: BackupLog
└─ NEW: TeraboxSettings

Hub/admin.py
├─ Existing admin classes...
└─ NEW: Import from backup_admin.py
    ├─ BackupConfigurationAdmin
    ├─ BackupLogAdmin
    └─ TeraboxSettingsAdmin

urls.py
├─ Existing patterns...
└─ NEW: Backup URLs
    ├─ backup_dashboard
    ├─ backup_history
    ├─ backup_configuration
    ├─ terabox_settings
    ├─ create_manual_backup
    ├─ backup_detail
    ├─ backup_analytics
    └─ API endpoints

Hub/management/commands/
├─ NEW: create_backup.py
└─ Can add: restore_backup.py, cleanup_backups.py

Hub/templates/admin_panel/
├─ Existing templates...
└─ NEW: Backup templates
    ├─ backup_dashboard.html
    ├─ backup_history.html
    ├─ backup_configuration.html
    ├─ terabox_settings.html
    ├─ backup_detail.html
    ├─ backup_analytics.html
    ├─ backup_email.html
    └─ backup_email.txt
```

---

## Execution Flow - Scheduled Backup

```
TIME: 3:00 AM (Every Day)
│
├─→ APScheduler wakes up
│
├─→ Calls: calculate_next_backup_time()
│
├─→ Checks if NOW >= next_backup_time
│   │
│   └─→ YES (condition met)
│
├─→ Executes: management command create_backup
│   │
│   ├─→ Creates BackupLog (status=IN_PROGRESS)
│   │
│   ├─→ For each data type:
│   │   ├─→ Query database
│   │   ├─→ Convert to DataFrame
│   │   ├─→ Format Excel
│   │   ├─→ Save file
│   │   └─→ Update counts in BackupLog
│   │
│   ├─→ Check if total records > 0
│   │
│   ├─→ IF enable_terabox_backup:
│   │   ├─→ Get today's date
│   │   ├─→ Check if date in [1, 7, 15, 30]
│   │   ├─→ Create folder: /VibeMall_Backups/01_January/
│   │   ├─→ Upload each Excel file
│   │   └─→ Update TeraboxSettings.last_sync_time
│   │
│   ├─→ IF notification_emails:
│   │   ├─→ Get email recipients
│   │   ├─→ Render HTML & text templates
│   │   ├─→ Send via SMTP
│   │   └─→ Update BackupLog.email_sent = True
│   │
│   ├─→ Update BackupLog.end_time
│   │
│   ├─→ Set BackupLog.status = SUCCESS
│   │
│   ├─→ Calculate next_backup_at
│   │
│   └─→ Save BackupLog
│
├─→ Garbage collection
│   ├─→ Get BackupConfiguration.keep_local_backups_days
│   ├─→ Delete files older than 30 days
│   └─→ Log cleanup results
│
└─→ Wait for next scheduled time...
```

---

## File Organization

```
VibeMall/
│
├── Hub/
│   ├── models.py                          (Updated with 3 new models)
│   ├── admin.py                           (Import backup admin)
│   ├── urls.py                            (Add backup URLs)
│   │
│   ├── management/
│   │   ├── __init__.py                    (Auto-created)
│   │   └── commands/
│   │       ├── __init__.py                (Auto-created)
│   │       └── create_backup.py           (NEW - 1400+ lines)
│   │
│   ├── backup_views.py                    (NEW - 800+ lines)
│   ├── backup_utils.py                    (NEW - 600+ lines)
│   ├── backup_admin.py                    (NEW - 700+ lines)
│   │
│   ├── templates/
│   │   └── admin_panel/
│   │       ├── backup_dashboard.html      (NEW)
│   │       ├── backup_history.html        (NEW)
│   │       ├── backup_configuration.html  (NEW)
│   │       ├── terabox_settings.html      (NEW)
│   │       ├── backup_detail.html         (NEW)
│   │       ├── backup_analytics.html      (NEW)
│   │       ├── backup_email.html          (NEW)
│   │       └── backup_email.txt           (NEW)
│   │
│   └── static/
│       └── admin/
│           ├── css/
│           │   └── backup.css             (NEW)
│           └── js/
│               ├── backup_charts.js       (NEW)
│               └── backup_init.js         (NEW)
│
├── backups/                               (NEW - .gitignore)
│   ├── excel/                             (Excel exports)
│   ├── logs/                              (Log files)
│   └── temp/                              (Temporary files)
│
├── settings.py                            (Add email & Terabox config)
├── urls.py                                (Add backup URLs)
│
├── BACKUP_SYSTEM_ROADMAP.md              (NEW - 300+ lines)
├── BACKUP_IMPLEMENTATION_GUIDE.md         (NEW - 350+ lines)
├── BACKUP_DEPLOYMENT_SUMMARY.md           (NEW - 300+ lines)
└── BACKUP_SYSTEM_ARCHITECTURE.md          (THIS FILE)
```

---

## Security Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Layer 1: Access Control                                      │
│ └─ @admin_required decorator on all views                   │
│    └─ Only staff/superuser can access                       │
│                                                              │
│ Layer 2: Data Encryption                                     │
│ └─ Terabox tokens encrypted in database                     │
│ └─ Token expiry tracking                                    │
│                                                              │
│ Layer 3: Audit Trail                                         │
│ └─ All backups logged to BackupLog                          │
│ └─ Error messages captured                                  │
│ └─ Duration tracking                                        │
│                                                              │
│ Layer 4: Error Handling                                      │
│ └─ Sanitized error messages                                 │
│ └─ Full error trace only in admin                           │
│ └─ Logging to file for investigation                        │
│                                                              │
│ Layer 5: Token Management                                    │
│ └─ Token expiry checking                                    │
│ └─ Automatic refresh on expiry                              │
│ └─ Secure token storage                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Performance Optimization

```
Database Queries
├─ Bulk export using QuerySet.values()
├─ Select_related() to avoid N+1 queries
├─ Aggregation functions for summaries
└─ Filtered queries by date range

Excel Generation
├─ DataFrames for fast processing
├─ Multi-sheet workbooks
├─ Batch processing by type
└─ Streaming for large files

Cloud Upload
├─ Parallel upload if multiple files
├─ Gzip compression for storage
├─ Connection pooling
└─ Retry on failure

Memory Optimization
├─ Delete DataFrames after usage
├─ Stream large files
├─ Garbage collection after export
└─ Cleanup temporary files
```

---

## Monitoring & Alerts

```
Dashboard Metrics
├─ Success Rate %
├─ Average Duration (seconds)
├─ Total Records Backed Up
├─ File Size (MB)
├─ Cloud Sync Status
└─ Email Delivery Status

Alerting Rules
├─ IF status == FAILED → Send email immediately
├─ IF duration > 5 min → Log warning
├─ IF file_size > 500MB → Log info
├─ IF terabox_synced == False → Retry
└─ IF backup overdue → Alert admin

Logging Levels
├─ DEBUG: Verbose query logs
├─ INFO: Backup started/completed
├─ WARNING: Slow operations, retry attempts
├─ ERROR: Failed backups, sync errors
└─ CRITICAL: System failures
```

---

## Scaling Considerations

```
Current Capacity
├─ Users: 10,000+
├─ Orders: 100,000+
├─ Products: 50,000+
└─ Data size: < 100 MB per backup

For 1 Million+ Records
├─ Implement incremental backups
├─ Use database snapshots (PostgreSQL)
├─ Parallel processing for multiple exports
├─ Compression (gzip) for storage
├─ Archive old backups to S3/Glacier
├─ Consider backup sharding by date
└─ Use Celery for async processing

Infrastructure
├─ SSD storage for local backups
├─ PostgreSQL instead of SQLite
├─ Redis for caching
├─ Message queue (RabbitMQ) for async jobs
├─ Dedicated backup server
└─ CDN for file distribution
```

---

**Architecture Document Complete** ✨

This document provides a visual representation of:
- System components and interactions
- Data flow during backup operations
- Database schema relationships
- Integration with existing VibeMall code
- File organization structure
- Security implementation
- Performance optimizations
- Scalability roadmap

All files are interconnected and work together to provide a robust, enterprise-grade backup solution.
