# Render Par Deploy Karva Ni Guide

## Step 1: GitHub Push Karo
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

## Step 2: Render Account Banao
1. https://render.com par ja
2. GitHub account diye signup karo
3. Authorize render-app

## Step 3: Database Setup Karo
1. Render Dashboard ma PostgreSQL select karo
2. Create database:
   - Name: vibemall_db
   - User: vibemall_user
   - Database URL copy karo (DATABASE_URL)

## Step 4: Web Service Create Karo
1. New -> Web Service
2. GitHub repo select karo (rajpaladiya2004/VibeMall)
3. Settings:
   - Name: vibemall
   - Environment: Python 3.11
   - Region: Singapore (ya closest)
   - Build Command: bash build.sh
   - Start Command: gunicorn VibeMall.wsgi:application
   - Plan: Free

## Step 5: Environment Variables Set Karo
Render dashboard ma environment variables add karo:

```
DEBUG=False
SECRET_KEY=generate-new-secret-key-here
DATABASE_URL=postgresql://user:password@host/dbname
ALLOWED_HOSTS=your-app-name.onrender.com

RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

EMAIL_HOST_USER=rajpaladiya2023@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## Step 6: Deploy Karo
1. Create Web Service button click karo
2. Deployment logs dekho (~5-10 minutes)
3. App URL copy karo: https://your-app-name.onrender.com

## Step 7: Admin Panel Access Karo
```
https://your-app-name.onrender.com/admin/
```

Username/Password: Local database se use karo ya navi banao

## Step 8: Razorpay Webhook Update Karo
1. Razorpay Dashboard -> Settings -> Webhooks
2. Webhook URL: https://your-app-name.onrender.com/razorpay-webhook/
3. Events select karo: payment.authorized, payment.failed, etc.

---

## Important Notes:

- Database: Render's free PostgreSQL 90 days baad auto-delete hoy
- Media files: Render restart hoy to media delete hoy jashe (later object storage lagasho)
- Domain: Pachi tara own domain connect karo:
  - Render -> Settings -> Custom Domain
  - Tara domain provider ma CNAME add karo

## Testing Checklist:
- Homepage load hoy che?
- Admin panel open hoy che?
- Products dikhay chhe?
- Razorpay payment work kare?
- Email send hoy che?

Kai problem aave to bolo!
