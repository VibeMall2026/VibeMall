# VibeMall Backup System - Complete Roadmap

## 🎯 Project Overview
Enterprise-grade automated backup system for VibeMall with Terabox cloud integration, customizable scheduling, email notifications, and comprehensive data analytics dashboard.

---

## 📋 Phase 1: Requirements & Architecture

### 1.1 Data to Backup
- **User Data**: All users, profiles, addresses, preferences
- **Payment Data**: Razorpay transactions, payment logs, payment status
- **Order Data**: Orders, order items, order history, status tracking
- **Delivery Data**: Shipping addresses, delivery status, tracking
- **Product Data**: Products, categories, stock levels, pricing history
- **Return/Exchange**: Return requests, return status, refund tracking
- **Financial**: Total profit, revenue, order-wise breakdown

### 1.2 System Architecture

```
Admin Panel
    ├── Backup Menu (Sidebar)
    │   ├── Dashboard (Backup Status)
    │   ├── Create Manual Backup
    │   ├── Backup History & Logs
    │   ├── Configuration & Scheduling
    │   └── Cloud Storage Settings
    │
    └── Database Models
        ├── BackupConfiguration (Frequency, Schedule)
        ├── BackupLog (Timestamp, Status, File Path)
        ├── TeraboxSettings (API Keys, Folder Mapping)
        └── BackupHistory (Metadata, File Size, Duration)
```

### 1.3 Backup Frequency Options
- **Daily**: 24-hour interval (choose specific time)
- **Weekly**: 7-day interval (choose day & time)
- **Bi-weekly**: 14-day interval (choose day & time)
- **Monthly**: Last day of month (choose time)
- **Custom Dates**: 1st, 7th, 15th, 30th (can toggle each)

---

## 📊 Phase 2: Data Models

### Model 1: BackupConfiguration
```python
BackupConfiguration:
    - backup_frequency (daily, weekly, biweekly, monthly, custom)
    - schedule_time (HH:MM format)
    - custom_dates (JSON: list of dates like [1, 7, 15, 30])
    - enable_terabox_backup (Boolean)
    - terabox_auto_folder_create (Boolean)
    - terabox_folder_structure (JSON: mapping of data types to folders)
    - notification_email (admin email list)
    - is_active (Boolean)
    - created_at, updated_at
```

### Model 2: BackupLog
```python
BackupLog:
    - backup_type (manual, scheduled, on_demand)
    - backup_frequency (which schedule triggered it)
    - start_time
    - end_time
    - duration_seconds
    - status (success, failed, in_progress)
    - total_records_backed_up (JSON: counts per data type)
    - file_path (local storage)
    - terabox_path (cloud storage path)
    - file_size_mb
    - error_message (if failed)
    - email_sent (Boolean)
    - created_at
```

### Model 3: TeraboxSettings
```python
TeraboxSettings:
    - api_access_token
    - refresh_token
    - folder_root_path
    - auto_create_folders (Boolean)
    - folder_mapping (JSON: {users: 'Users', orders: 'Orders', etc})
    - last_sync_time
    - is_connected (Boolean)
    - created_at, updated_at
```

---

## 🎨 Phase 3: Admin UI Components

### 3.1 Backup Dashboard
- **Quick Stats**: Last backup date/time, next scheduled, success rate, total backed up
- **Status Indicator**: Green (on-time), Yellow (overdue), Red (failed)
- **Recent Backups**: Table showing last 10 backups with status
- **Action Buttons**: 
  - "Create Manual Backup Now" (with overlay showing progress)
  - "View Full History"
  - "Download Latest Backup"
  - "Settings"

### 3.2 Configuration Page
- **Frequency Selection**: Radio buttons (Daily, Weekly, Bi-weekly, Monthly, Custom)
- **Time Selection**: Time picker for schedule time
- **Custom Dates**: Checkboxes for 1st, 7th, 15th, 30th (appeared only if "Custom" selected)
- **Terabox Settings**: 
  - Enable/Disable toggle
  - Connect Terabox button
  - Auto folder creation toggle
  - Folder mapping configuration
- **Email Notifications**:
  - List of recipient emails
  - Send test email button
  - Email template preview

### 3.3 Backup History Page
- **Filters**: Date range, status, backup type
- **Table Columns**: 
  - Date/Time
  - Duration
  - Status (badge)
  - Data count (users/orders/etc)
  - File size
  - Cloud status
  - Actions (download, delete, view log)

### 3.4 Data Analytics Section
- **Monthly View**: Chart showing backup frequency over time
- **Data Overview**: 
  - Total users backed up
  - Total orders backed up
  - Total transactions
  - Total revenue
  - Total profit
  - Return/Exchange count
- **Storage Stats**: 
  - Local storage used
  - Terabox storage used
  - Growth trend

---

## 💻 Phase 4: Implementation Components

### 4.1 Management Commands
```
python manage.py create_backup --type manual
python manage.py create_backup --type scheduled --frequency daily
python manage.py restore_backup --date 2026-01-15 --data-type orders
python manage.py terabox_sync --backup-id <id>
```

### 4.2 Background Job Scheduler
**Options**:
- **APScheduler** (Recommended - no separate service)
- **Celery** (If scalable queue needed)

**Job Structure**:
```
- Daily job: Check if backup scheduled for today
- Execute scheduled backups
- Upload to Terabox
- Send notifications
- Clean old backups (keep 90 days local, 1 year cloud)
```

### 4.3 Database Export Functions

```python
export_functions = {
    'users': export_all_users(),
    'payments': export_all_payments(),
    'orders': export_orders_detailed(),
    'products': export_products_inventory(),
    'deliveries': export_delivery_data(),
    'returns': export_return_orders(),
    'transactions': export_transactions(),
    'analytics': export_financial_analytics(),
}
```

### 4.4 Terabox Integration
```python
terabox_operations = {
    'connect': authenticate_terabox(),
    'create_folder': create_dated_folder(),
    'upload_file': upload_to_terabox(),
    'list_files': list_remote_backups(),
    'delete_old': cleanup_old_backups(),
}
```

### 4.5 Email Notifications
```
Email Template:
- Subject: "✅ Backup Successful - VibeMall {date}"
- Summary of data backed up
- File size
- Cloud sync status
- Next scheduled backup
- Quick action buttons
- Download link (valid for 7 days)
```

---

## 🔧 Phase 5: Technology Stack

| Component | Technology | Why? |
|-----------|-----------|------|
| **Scheduling** | APScheduler | No external service, works with Django |
| **Excel Export** | pandas + openpyxl | Already in use, handles multi-sheet |
| **Cloud Storage** | Terabox SDK | Direct API integration |
| **Email** | Django Email + Celery | Async, reliable delivery |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Existing setup |
| **Frontend** | Bootstrap + Chart.js | Responsive, real-time stats |
| **Storage** | Local: `/backups/` + Cloud: Terabox | Hybrid redundancy |

---

## 📈 Phase 6: File Structure

```
Hub/
├── management/
│   └── commands/
│       ├── create_backup.py (Main backup command)
│       ├── restore_backup.py (Restore functionality)
│       ├── terabox_sync.py (Cloud sync)
│       └── cleanup_old_backups.py (Maintenance)
├── backup_scheduler.py (APScheduler setup)
├── backup_utils.py (Helper functions)
├── terabox_api.py (Terabox integration)
├── models.py (Add 3 new models)
├── admin.py (Register models)
├── views.py (Add backup views)
├── urls.py (Add backup URLs)
├── templates/admin_panel/
│   ├── backup_dashboard.html
│   ├── backup_configuration.html
│   ├── backup_history.html
│   └── includes/backup_card.html
└── static/admin/
    └── js/backup_chart.js

backups/ (directory - .gitignored)
├── excel/ (Excel exports)
├── data/ (CSV/JSON exports)
├── logs/ (Activity logs)
└── temp/ (Temporary files)
```

---

## 🚀 Phase 7: Implementation Sequence

### Step 1: Database Models
- Create BackupConfiguration model
- Create BackupLog model
- Create TeraboxSettings model
- Run migrations

### Step 2: Terabox Integration Layer
- Implement terabox_api.py with connection logic
- Add authentication mechanism
- Test folder creation and file upload

### Step 3: Backup Core Logic
- Create management commands
- Implement all export functions
- Add error handling and logging
- Test manual backups

### Step 4: Scheduling System
- Set up APScheduler
- Create backup_scheduler.py
- Implement frequency-based triggering
- Add configuration persistence

### Step 5: Admin Views & URLs
- Create admin backup views
- Add URL routing
- Implement AJAX endpoints for manual triggers

### Step 6: Admin Templates
- Create backup dashboard template
- Create configuration template
- Create history/logs template
- Add sidebar menu item

### Step 7: Email Notifications
- Create email templates
- Implement notification sender
- Add email logs tracking

### Step 8: Frontend Enhancement
- Add charts for backup analytics
- Add real-time progress indicators
- Add download/restore functionality

### Step 9: Testing & Deployment
- Unit tests for backup functions
- Integration tests for scheduler
- Load testing for large datasets
- Production deployment steps

---

## 🎯 Key Features Checklist

- ✅ Manual backup trigger
- ✅ Automated scheduling (daily/weekly/monthly)
- ✅ Custom date scheduling (1,7,15,30)
- ✅ Terabox auto folder creation
- ✅ Email notifications
- ✅ Backup history & logs
- ✅ Data analytics dashboard
- ✅ Restore functionality
- ✅ Storage management (cleanup old)
- ✅ Error handling & recovery
- ✅ Admin menu integration
- ✅ Configuration UI
- ✅ Real-time status updates

---

## 📊 Data Backup Details

### User Data
```python
- user_id, username, email, first_name, last_name
- phone, address, city, state, zip_code, country
- date_joined, last_login, is_active
- total_orders, total_spent, loyalty_points
```

### Payment Data
```python
- order_id, payment_id, amount, currency
- payment_method (razorpay, etc)
- status (pending, success, failed)
- transaction_id, receipt_url
- created_at, updated_at
- refund_status, refund_amount
```

### Order Data
```python
- order_id, user_id, order_date
- total_amount, discount, tax, shipping_cost
- status (pending, processing, shipped, delivered, cancelled)
- items_count, delivery_date, return_status
- payment_status, notes
```

### Product Data
```python
- product_id, name, sku, category
- price, cost_price, discount_percent
- stock_quantity, sold_count, rating
- created_date, last_updated
- is_active, visibility_status
```

### Financial Analytics
```python
- total_revenue, total_profit
- total_orders, average_order_value
- repeat_customer_rate
- return_rate, churn_rate
- monthly breakdown
- top selling products
- top customers
```

---

## 🔒 Security Considerations

1. **Access Control**: Only super-admin can access backup settings
2. **Data Encryption**: Encrypt before Terabox upload
3. **Token Management**: Secure storage of Terabox API keys
4. **Audit Trail**: Log all backup operations
5. **Backup Verification**: Checksum validation after upload
6. **Retention Policy**: Auto-delete backups older than 90 days (local), 1 year (cloud)

---

## 💡 Advanced Features (Future)

1. **Incremental Backups**: Only backup changed data
2. **Database Snapshots**: Direct database backup (not just Excel)
3. **Backup Comparison**: Diff between two backups
4. **Automated Rollback**: One-click restore to previous state
5. **Multiple Cloud Providers**: AWS S3, Google Drive, Microsoft OneDrive
6. **Backup Verification**: Weekly integrity checks
7. **Disaster Recovery Plan**: Documented recovery procedures
8. **Compliance Reports**: GDPR compliance, data retention reports
9. **Backup Sharing**: Share specific backup with team member
10. **Backup Analytics**: Predict storage needs, cost optimization

---

## 📞 Support & Troubleshooting

### Common Issues
1. **Terabox Connection Failed**
   - Solution: Re-authenticate, check token expiry
   
2. **Backup Taking Too Long**
   - Solution: Optimize export queries, enable incremental backup
   
3. **Storage Full**
   - Solution: Configure cleanup policy, archive old backups
   
4. **Email Not Sent**
   - Solution: Check email configuration, verify SMTP settings

---

## 🎓 Best Practices

1. **Frequency**: Daily backups for mission-critical data, weekly for others
2. **Retention**: Keep 30 days local, 1 year in cloud
3. **Verification**: Test restore process monthly
4. **Documentation**: Maintain backup recovery procedures
5. **Monitoring**: Set up alerts for failed backups
6. **Scalability**: Plan for data growth, optimize storage

---

## 📅 Timeline Estimate

| Phase | Duration | Priority |
|-------|----------|----------|
| Models & Migrations | 2 hours | High |
| Terabox Integration | 3 hours | High |
| Backup Core Logic | 4 hours | High |
| Scheduling System | 3 hours | High |
| Admin Interface | 5 hours | High |
| Email Notifications | 2 hours | Medium |
| Testing & Refinement | 4 hours | Medium |
| **Total** | **23 hours** | - |

---

## ✅ Success Metrics

1. ✅ 100% data backed up daily with no errors
2. ✅ Backups automatically synced to Terabox within 1 hour
3. ✅ Admin receives success notification email within 10 minutes
4. ✅ Full data restore capability verified monthly
5. ✅ Dashboard shows real-time backup status
6. ✅ Storage optimized with <500MB local, <5GB cloud per month

