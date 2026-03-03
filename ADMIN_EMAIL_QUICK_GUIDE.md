# ⚡ QUICK REFERENCE: ORDER APPROVAL EMAIL SYSTEM

## ✅ Status: FIXED & DEPLOYED (Feb 20, 2025)

---

## 📧 How Order Approval Emails Work Now

### When You Approve an Order in Admin Panel:
1. ✅ Email sent to customer automatically
2. ✅ Email tracked in database (EmailLog)
3. ✅ Customer gets in-app notification
4. ✅ Success/failure logged for debugging

---

## 🔍 How to Verify Emails Were Sent

### Option 1: Check Admin Panel
- Go to **Django Admin** → **EmailLog**
- Filter by `Email Type: ORDER_APPROVED`
- Check `Sent Successfully` column (should show True/False)

### Option 2: Database Query
```python
from Hub.models import EmailLog

# Recent approval emails (last 24 hours)
recent = EmailLog.objects.filter(
    email_type='ORDER_APPROVED'
).order_by('-created_at')[:20]

for log in recent:
    print(f"✅" if log.sent_successfully else "❌", 
          log.email_to, 
          log.subject)
```

### Option 3: Check Production Logs
```bash
# View recent error logs
tail -f /var/log/vibemall/django.log | grep "approval"
```

---

## 🚨 Troubleshooting

### "Email not received by customer"

**Step 1: Check EmailLog**
- Go to Admin Panel
- Search EmailLog for that order
- Look for `ORDER_APPROVED` entry

**Step 2: Check if Email Was Sent**
- If `Sent Successfully = True` → Check spam folder
- If `Sent Successfully = False` → Check `Error Message` field

**Step 3: Common Issues & Fixes**

| Issue | Solution |
|-------|----------|
| Email marked sent but not received | Check customer spam folder, Gmail filters |
| `Sent Successfully = False` with SMTP error | Check Gmail app password in `.env` |
| No EmailLog record exists | Customer email address may be blank |
| Multiple failed attempts | May indicate Gmail rate limiting or auth issue |

---

## 🔧 How to Re-Send Failed Approval Emails

### Django Shell Command
```python
from Hub.models import Order, EmailLog
from Hub.email_utils import send_order_approval_email

# Find the order
order = Order.objects.get(order_number='ORD20260215001')

# Re-send email
send_order_approval_email(order, approved_by=admin_user)

# Check if successful
was_sent = EmailLog.objects.filter(
    order=order,
    email_type='ORDER_APPROVED',
    sent_successfully=True
).exists()

print("✅ Email re-sent" if was_sent else "❌ Failed to re-send")
```

---

## 📊 Key Database Tables

### EmailLog Table
**Purpose:** Track all email sending attempts  
**Columns:**
- `email_to` - Recipient email
- `email_type` - Type of email (ORDER_APPROVED, etc.)
- `sent_successfully` - True/False
- `error_message` - Error details if failed
- `created_at` - When email was sent

**Query:** Filter by `email_type='ORDER_APPROVED'`

### Notification Table
**Purpose:** Store in-app notifications for customers  
**Type:** `ORDER_APPROVED` when order is approved

---

## 🎯 Best Practices

1. **Always approve from admin panel** - Ensures email is sent automatically
2. **Check EmailLog after bulk approvals** - Verify all emails queued
3. **Monitor error patterns** - Look for recurring SMTP issues
4. **Keep .env credentials fresh** - Gmail app passwords may expire
5. **Test with a test order** - Before critical operations

---

## 📞 Support

### For Email Issues:
1. Check EmailLog dashboard
2. Review error message in database
3. Check production logs
4. Verify Gmail credentials in `.env`

### Files Modified:
- `Hub/email_utils.py` - New `send_order_approval_email()` function
- `Hub/views.py` - Updated `admin_approve_order()` 
- `Hub/admin.py` - Enhanced bulk `approve_orders` action

**Last Updated:** 2025-02-20  
**Status:** ✅ Production Live
