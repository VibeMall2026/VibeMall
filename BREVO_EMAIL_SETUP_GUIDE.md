# Brevo Email Configuration Guide for VibeMall

## 📧 Step-by-Step Setup Instructions

### Step 1: Create Brevo Account (If Not Already Done)

1. Go to https://www.brevo.com/
2. Click "Sign Up Free"
3. Complete registration
4. Verify your email address

---

### Step 2: Get Your Brevo SMTP Credentials

#### A. Login to Brevo Dashboard
- Go to https://app.brevo.com/
- Login with your credentials

#### B. Generate SMTP Key
1. Click on your **name/profile** (top right corner)
2. Select **"SMTP & API"** from dropdown
3. Click on **"SMTP"** tab
4. Click **"Generate a new SMTP key"** button
5. Enter a name: `VibeMall Production`
6. Click **"Generate"**
7. **IMPORTANT**: Copy the SMTP key immediately (you'll only see it once!)
   - It looks like: `xkeysib-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz`

#### C. Note Your Login Email
- This is the email you use to login to Brevo
- Example: `contact@vibemall.com` or `info@vibemall.com`

---

### Step 3: Verify Your Sender Email Address

**IMPORTANT**: You can only send emails FROM verified addresses in Brevo.

1. In Brevo dashboard, go to **"Senders & IP"** (left sidebar)
2. Click **"Add a sender"** button
3. Enter your sender details:
   - **Email**: `orders@vibemall.com` (or your preferred email)
   - **Name**: `VibeMall`
4. Click **"Add"**
5. Check your email inbox for verification link
6. Click the verification link to verify the sender

**You can add multiple sender emails** (e.g., `orders@vibemall.com`, `support@vibemall.com`, `info@vibemall.com`)

---

### Step 4: Configure Your `.env` File

Open the `.env` file in your project root directory and update these values:

```env
# ==============================
# BREVO EMAIL CONFIGURATION
# ==============================
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=contact@vibemall.com                          # ← Your Brevo login email
EMAIL_HOST_PASSWORD=xkeysib-abc123def456ghi789jkl012mno345    # ← Your SMTP key from Step 2
DEFAULT_FROM_EMAIL=VibeMall <orders@vibemall.com>             # ← Your verified sender email

# Admin Notification Emails (comma-separated, no spaces)
ADMIN_NOTIFICATION_EMAILS=admin@vibemall.com,orders@vibemall.com,manager@vibemall.com
ENABLE_ADMIN_ORDER_NOTIFICATIONS=True
```

---

### Step 5: Update Other Required Settings

Make sure to also update these settings in `.env`:

```env
# Django Settings
DEBUG=False
SECRET_KEY=your-actual-secret-key-here
DATABASE_URL=postgresql://username:password@host:5432/database_name
ALLOWED_HOSTS=vibemall.com,www.vibemall.com,localhost
SITE_URL=https://vibemall.com

# Razorpay (if using payment gateway)
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_razorpay_secret_key
```

---

## 📝 Configuration Examples

### Example 1: Single Admin Email
```env
EMAIL_HOST_USER=info@vibemall.com
EMAIL_HOST_PASSWORD=xkeysib-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
DEFAULT_FROM_EMAIL=VibeMall <orders@vibemall.com>
ADMIN_NOTIFICATION_EMAILS=admin@vibemall.com
```

### Example 2: Multiple Admin Emails
```env
EMAIL_HOST_USER=info@vibemall.com
EMAIL_HOST_PASSWORD=xkeysib-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
DEFAULT_FROM_EMAIL=VibeMall <orders@vibemall.com>
ADMIN_NOTIFICATION_EMAILS=admin@vibemall.com,orders@vibemall.com,manager@vibemall.com
```

### Example 3: Different Sender Email
```env
EMAIL_HOST_USER=contact@vibemall.com
EMAIL_HOST_PASSWORD=xkeysib-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
DEFAULT_FROM_EMAIL=VibeMall Support <support@vibemall.com>
ADMIN_NOTIFICATION_EMAILS=admin@vibemall.com
```

---

## ✅ Testing Your Configuration

### 1. Restart Django Server
```bash
# Stop the server (Ctrl+C)
# Then restart
python manage.py runserver
```

### 2. Place a Test Order
1. Go to your website
2. Add products to cart
3. Complete checkout process
4. Place an order

### 3. Check Email Delivery
- **Customer** should receive: Order confirmation email with invoice PDF
- **Admin(s)** should receive: Order notification email with approve/reject links

### 4. Check Brevo Dashboard
1. Go to https://app.brevo.com/
2. Click **"Statistics"** (left sidebar)
3. You should see sent emails in the dashboard
4. Click **"Logs"** to see detailed delivery status

---

## 🔍 Troubleshooting

### Issue 1: Emails Not Sending

**Check Django Logs:**
```bash
# Look for error messages in terminal
```

**Common Causes:**
- ❌ Wrong SMTP key (check for typos)
- ❌ Sender email not verified in Brevo
- ❌ Extra spaces in `.env` file
- ❌ Server not restarted after changing `.env`

**Solution:**
1. Verify SMTP key is correct (no spaces)
2. Verify sender email in Brevo dashboard
3. Restart Django server
4. Check Brevo logs for errors

---

### Issue 2: Authentication Failed

**Error Message:**
```
SMTPAuthenticationError: (535, b'Authentication failed')
```

**Causes:**
- Wrong `EMAIL_HOST_USER` (should be your Brevo login email)
- Wrong `EMAIL_HOST_PASSWORD` (should be SMTP key, not account password)

**Solution:**
1. Double-check `EMAIL_HOST_USER` matches your Brevo login email
2. Regenerate SMTP key in Brevo dashboard
3. Copy new key to `.env` file
4. Restart server

---

### Issue 3: Sender Not Verified

**Error Message:**
```
Sender email not verified
```

**Solution:**
1. Go to Brevo dashboard → "Senders & IP"
2. Check if your sender email is verified (green checkmark)
3. If not verified, click "Resend verification email"
4. Check inbox and click verification link
5. Wait 5 minutes and try again

---

### Issue 4: Daily Limit Exceeded

**Error Message:**
```
Daily sending limit exceeded
```

**Brevo Free Plan Limits:**
- 300 emails per day
- Resets at midnight UTC

**Solutions:**
- Wait until next day (limit resets)
- Upgrade to paid plan for higher limits
- Use email sparingly during testing

---

## 📊 Brevo Free Plan Features

✅ **Included:**
- 300 emails per day
- Unlimited contacts
- Email templates
- SMTP relay
- Email logs and statistics
- Sender verification

❌ **Not Included:**
- Advanced automation (paid)
- A/B testing (paid)
- Priority support (paid)

**Upgrade Options:**
- Starter: €25/month (20,000 emails/month)
- Business: €65/month (100,000 emails/month)
- Enterprise: Custom pricing

---

## 🔐 Security Best Practices

### 1. Keep `.env` File Secure
```bash
# Add to .gitignore (already done)
.env
```

### 2. Never Commit SMTP Keys
- ❌ Don't commit `.env` to Git
- ✅ Only commit `.env.example` (with placeholder values)

### 3. Use Different Keys for Development/Production
- Development: Use separate Brevo account or SMTP key
- Production: Use production SMTP key

### 4. Rotate Keys Regularly
- Regenerate SMTP keys every 3-6 months
- Update `.env` file with new key

---

## 📧 Email Types Sent by VibeMall

### 1. Order Confirmation (Customer)
- **Trigger**: When order is placed
- **Recipient**: Customer email
- **Content**: Order details, invoice PDF, tracking links
- **Template**: `emails/order_confirmation.html`

### 2. Order Notification (Admin)
- **Trigger**: When order is placed
- **Recipient**: Admin emails (from `ADMIN_NOTIFICATION_EMAILS`)
- **Content**: Order summary, approve/reject links
- **Template**: `emails/admin_order_notification.html`

### 3. Order Status Updates (Customer)
- **Trigger**: When order status changes
- **Recipient**: Customer email
- **Content**: Status update, tracking info
- **Template**: `emails/order_status_update.html`

### 4. Order Approval (Customer)
- **Trigger**: When admin approves order
- **Recipient**: Customer email
- **Content**: Approval confirmation
- **Template**: `emails/order_approved.html`

---

## 🎯 Quick Reference

### Brevo Dashboard URLs
- **Main Dashboard**: https://app.brevo.com/
- **SMTP & API**: https://app.brevo.com/settings/keys/smtp
- **Senders**: https://app.brevo.com/senders
- **Statistics**: https://app.brevo.com/statistics/email
- **Logs**: https://app.brevo.com/logs/email

### Required `.env` Variables
```env
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<your-brevo-login-email>
EMAIL_HOST_PASSWORD=<your-smtp-key>
DEFAULT_FROM_EMAIL=VibeMall <<your-verified-sender>>
ADMIN_NOTIFICATION_EMAILS=<comma-separated-admin-emails>
ENABLE_ADMIN_ORDER_NOTIFICATIONS=True
```

### Support
- **Brevo Support**: https://help.brevo.com/
- **Brevo Status**: https://status.brevo.com/

---

## ✨ Summary

1. ✅ Create Brevo account
2. ✅ Generate SMTP key
3. ✅ Verify sender email
4. ✅ Update `.env` file with credentials
5. ✅ Restart Django server
6. ✅ Test by placing an order
7. ✅ Check Brevo dashboard for sent emails

**Your email system is now ready!** 🚀

---

**Need Help?** Check Django logs and Brevo dashboard logs for detailed error messages.
