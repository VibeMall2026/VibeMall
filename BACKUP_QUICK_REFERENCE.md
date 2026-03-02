# VibeMall Local Backup System - Quick Reference Guide

## 🚀 Quick Start

### Access the Backup Dashboard
1. Log in to admin panel: `http://127.0.0.1:8000/admin-panel/`
2. Click **Backup** in the left sidebar
3. Choose **Backup Dashboard** or **ITR Reports**

### Create a Manual Backup
Navigate to Backup Dashboard and click **"Create Manual Backup"** button.

OR use command line:
```bash
python manage.py create_backup --type manual --mode regular
```

### Create a Special Backup
1. Go to Backup Dashboard
2. Select data types from the checklist:
   - ☑ Users
   - ☑ Orders
   - ☑ Payments
   - ☑ Transactions
   - ☑ Products
   - ☑ Returns
   - ☑ Analytics
   - ☑ Product Images & Videos
3. Click **"Create Special Backup"**

OR use command line:
```bash
python manage.py create_backup --type special --mode special --data-types users,orders,payments
```

### Generate ITR Financial Report
1. Click **ITR Reports** in Backup submenu
2. Select report type:
   - Monthly (current month)
   - 6-Month
   - Yearly
   - Custom Range (specify dates)
3. Click **"Generate Report"**
4. Excel file downloads automatically

## 📁 Where Are My Backups?

All backups are stored in: **`D:\VibeMallBackUp`**

### Folder Structure:
```
D:\VibeMallBackUp\
├── RegularBackUp\          ← Monthly automated backups
│   ├── 2026-03\           ← March 2026 backups
│   ├── 2026-04\           ← April 2026 backups
│   └── ...
└── SpecialBackup\          ← Manual/special backups
    ├── 2026-03\
    └── ...
```

### Backup File Names:
- `users_backup_20260302_083816.xlsx`
- `orders_backup_20260302_083816.xlsx`
- `payments_backup_20260302_083816.xlsx`
- `transactions_backup_20260302_083816.xlsx`
- `products_backup_20260302_083816.xlsx`
- `returns_backup_20260302_083816.xlsx`
- `analytics_backup_20260302_083816.xlsx`
- `product_media_backup_20260302_083816.xlsx`

## 🗑️ Cleanup Confirmation Workflow

### How It Works:
1. **New Month Backup Completes** → System detects old month folder exists
2. **Email Sent to Admin** → Contains unique confirmation link
3. **Admin Clicks Link** → Opens web page with folder details
4. **Admin Chooses**:
   - ✅ **Confirm** → Old month folder deleted
   - ❌ **Decline** → Old month folder kept

### Check Pending Cleanups:
1. Go to Backup Dashboard
2. See **"Cleanup Requests Pending"** count
3. Click to view details
4. Approve or decline each request

## 📧 Email Configuration (Required for Notifications)

Add to your `.env` file:
```env
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

Emails sent for:
- Backup completion (success/failure)
- Cleanup confirmation requests

## ⚙️ Configuration Settings

### Access: `/admin-panel/backup/configuration/`

**Backup Frequency:**
- Daily
- Weekly (choose weekday)
- Monthly (choose day of month)
- Custom (specify dates)

**Schedule Time:** Set backup execution time (e.g., 02:00 AM)

**Local Storage Paths:**
- Backup Root Path: `D:\VibeMallBackUp` (default)
- Regular Folder Name: `RegularBackUp` (default)
- Special Folder Name: `SpecialBackup` (default)

**Email Notifications:**
- ☑ Send email on success
- ☑ Send email on failure
- Enter recipient emails (comma-separated)

**Active Status:**
- ☑ Enable automated backups
- ☐ Disable automated backups

## 🔍 View Backup History

### Access: `/admin-panel/backup/history/`

**Features:**
- List of all backups (paginated)
- Filter by status: SUCCESS / FAILED / IN_PROGRESS
- Filter by type: SCHEDULED / MANUAL / ITR_REPORT
- Click any backup to view details

**Backup Details Include:**
- Start/end time
- Duration
- File size
- Record counts (users, orders, etc.)
- Error messages (if failed)
- Local file path

## 📊 Analytics Dashboard

### Access: `/admin-panel/backup/analytics/`

**View:**
- Success rate percentage
- Daily backup counts
- Total records backed up
- File size trends
- Status distribution charts

**Time Range Filter:** 7 days / 30 days / 90 days

## 💡 Pro Tips

### 1. Test Before Relying On It
```bash
# Test with users only
python manage.py create_backup --type manual --mode regular --data-types users
```

### 2. Verify Excel Files
Open backup Excel files in Microsoft Excel or LibreOffice to verify data integrity.

### 3. Backup Before Major Changes
Create a special backup before:
- Database migrations
- Bulk product updates
- Major order processing
- Version upgrades

### 4. Regular Cleanup
Don't let old backups pile up endlessly. Approve cleanup requests regularly or manually delete old month folders from `D:\VibeMallBackUp`.

### 5. Monitor Backup Status
Check Backup Dashboard weekly to ensure automated backups are running successfully.

## 🐛 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'pandas'"
**Solution:**
```bash
venv\Scripts\activate
pip install pandas openpyxl
```

### Problem: Backup command hanging
**Cause:** Large dataset taking time to export  
**Solution:** Be patient or use `--data-types` flag to backup selectively

### Problem: Excel file corrupted or empty
**Cause:** Backup interrupted or database connection lost  
**Solution:** Run backup again, check database connectivity

### Problem: Email notifications not received
**Cause:** Email configuration missing  
**Solution:** Add EMAIL_HOST_USER and EMAIL_HOST_PASSWORD to .env file

### Problem: "Access denied" when opening backup dashboard
**Cause:** Not logged in as admin/staff user  
**Solution:** Log in with superuser account

### Problem: Old month folder not deleted after confirmation
**Cause:** Folder in use by another process or permissions issue  
**Solution:** Close Excel files, restart backup process, or manually delete folder

## 📞 Need Help?

### Check Logs:
```bash
# View backup command output
python manage.py create_backup --type manual --mode regular

# Check Django logs
tail -f logs/django.log  # Linux/Mac
type logs\django.log     # Windows
```

### Django Admin Site:
Access Django's built-in admin: `http://127.0.0.1:8000/admin/`
- View BackupLog entries
- View BackupConfiguration settings
- View BackupCleanupRequest records

## 🎯 Common Use Cases

### Use Case 1: Monthly IT Reports for Tax Filing
1. Go to ITR Reports page
2. Select "Monthly" → Previous month
3. Download Excel file
4. Submit to accountant

### Use Case 2: Backup Before Database Migration
1. Create Special Backup
2. Select all data types
3. Wait for completion
4. Proceed with migration
5. If migration fails, restore from backup

### Use Case 3: Export Customer Data for Analysis
1. Create Special Backup
2. Select "Users" and "Orders" only
3. Open Excel files
4. Analyze data in Excel/Python/R

### Use Case 4: Automated Monthly Backups
1. Go to Configuration
2. Set frequency to "Monthly"
3. Set day to 1st of month
4. Set time to 2:00 AM
5. Enable "Active" checkbox
6. Save
7. System runs backups automatically every month

## ✅ Success Checklist

Before considering backup system operational:
- [ ] Manual backup completed successfully
- [ ] Excel files created in D:\VibeMallBackUp
- [ ] Opened Excel files and verified data
- [ ] Special backup tested with selected data types
- [ ] ITR report generated and downloaded
- [ ] Email configuration tested (if using notifications)
- [ ] Backup history page shows successful backups
- [ ] Cleanup confirmation workflow understood

---
**Last Updated**: March 2, 2026  
**Version**: 1.0.0  
**Status**: Production-Ready ✅
