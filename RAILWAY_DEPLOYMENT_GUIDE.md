# 🚂 Railway.app Deployment Guide - VibeMall

## Why Railway?

- ✅ **$5 free credits/month** (perfect for testing)
- ✅ **5-minute deployment** (fastest option)
- ✅ **Auto-deploy on git push** (CI/CD built-in)
- ✅ **PostgreSQL included** (free tier)
- ✅ **No credit card required** (for free tier)
- ✅ **Automatic HTTPS**

---

## Prerequisites (5 minutes)

### ✅ Checklist Before Starting

- [ ] **GitHub account** with VibeMall repo pushed
- [ ] **All code committed** and pushed to main branch
- [ ] **Local testing complete** (Django runs without errors)
- [ ] **Environment variables ready** (see list below)

### Required Environment Variables

Prepare these values (you'll need them in Railway):

```env
# Django Settings
DEBUG=False
SECRET_KEY=django-insecure-your-secret-key-change-this-in-production
ALLOWED_HOSTS=*.railway.app

# Database (Railway auto-provides this - DO NOT SET)
# DATABASE_URL=(auto-generated)

# Razorpay (Use TEST keys for testing)
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_test_secret_key

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password

# Optional
DJANGO_SETTINGS_MODULE=VibeMall.settings
```

---

## Step-by-Step Deployment

### Step 1: Prepare Your Project (Local - 2 minutes)

#### 1.1 Create `railway.json` (Railway Configuration)

```bash
# Navigate to project root
cd "d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall"
```

Create a file named `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn VibeMall.wsgi:application",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

#### 1.2 Create `Procfile` (Alternative startup)

Create a file named `Procfile`:

```
web: python manage.py migrate && gunicorn VibeMall.wsgi:application --bind 0.0.0.0:$PORT
```

#### 1.3 Update `requirements.txt`

Make sure these are in your `requirements.txt`:

```txt
Django==5.0.9
gunicorn==21.2.0
psycopg2-binary==2.9.9
whitenoise==6.6.0
dj-database-url==2.1.0
razorpay==1.4.1
Pillow==10.2.0
python-decouple==3.8
```

#### 1.4 Update `settings.py` (Railway-specific)

Add to the **bottom** of your `VibeMall/settings.py`:

```python
# Railway.app Configuration
import dj_database_url

if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )

# Static files (Railway)
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Allow Railway domain
if 'RAILWAY_STATIC_URL' in os.environ:
    ALLOWED_HOSTS.append('.railway.app')
```

#### 1.5 Commit and Push

```bash
git add .
git commit -m "Railway deployment configuration"
git push origin main
```

---

### Step 2: Create Railway Account (1 minute)

1. **Go to:** https://railway.app
2. **Click:** "Start a New Project"
3. **Sign in with GitHub** (or email)
4. **Authorize Railway** to access your GitHub repos

---

### Step 3: Deploy from GitHub (3 minutes)

#### 3.1 Create New Project

1. Click **"New Project"** button
2. Select **"Deploy from GitHub repo"**
3. **Choose repository:** `VibeMall2026/VibeMall`
4. Click **"Deploy Now"**

Railway will auto-detect Django and start building!

#### 3.2 Add PostgreSQL Database

1. In your project dashboard, click **"+ New"**
2. Select **"Database"**
3. Choose **"Add PostgreSQL"**
4. Railway automatically creates database and sets `DATABASE_URL` env variable

---

### Step 4: Configure Environment Variables (3 minutes)

#### 4.1 Access Variables

1. Click on your **Django service** (in Railway dashboard)
2. Go to **"Variables"** tab
3. Click **"+ Add Variable"**

#### 4.2 Add Each Variable

**Add these one by one:**

| Variable Name | Value | Notes |
|---------------|-------|-------|
| `DEBUG` | `False` | Must be False for production |
| `SECRET_KEY` | `your-django-secret-key` | Generate new one |
| `ALLOWED_HOSTS` | `*.railway.app` | Railway domains |
| `RAZORPAY_KEY_ID` | `rzp_test_xxxx` | Your test key |
| `RAZORPAY_KEY_SECRET` | `your_secret` | Your test secret |
| `EMAIL_HOST_USER` | `your-email@gmail.com` | Gmail address |
| `EMAIL_HOST_PASSWORD` | `your-app-password` | Gmail App Password |
| `EMAIL_HOST` | `smtp.gmail.com` | Gmail SMTP |
| `EMAIL_PORT` | `587` | TLS port |
| `EMAIL_USE_TLS` | `True` | Enable TLS |

**Note:** `DATABASE_URL` is auto-set by Railway PostgreSQL - don't add it manually!

#### 4.3 Generate New SECRET_KEY

```bash
# Run this locally to generate a secure key:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and use it for `SECRET_KEY`

---

### Step 5: Trigger Deployment (1 minute)

1. **Click "Deploy"** button in Railway dashboard
2. Watch the build logs (bottom of screen)
3. Wait for **"Build Successful"** message (2-3 minutes)

**Expected logs:**
```
Installing dependencies...
Collecting Django==5.0.9
Successfully installed Django-5.0.9 gunicorn-21.2.0 ...
Running migrations...
Operations to perform: Apply all migrations
Running migrations: [OK]
Collecting static files...
Deployed successfully!
```

---

### Step 6: Get Your URL and Test (2 minutes)

#### 6.1 Find Your URL

1. In Railway dashboard, click **"Settings"** tab
2. Scroll to **"Domains"** section
3. Click **"Generate Domain"**
4. You'll get: `vibemall-production-xxxx.up.railway.app`

#### 6.2 First Access

1. **Open your Railway URL** in browser
2. You should see your homepage!

---

### Step 7: Run Database Setup (One-time - 5 minutes)

#### 7.1 Create Superuser

Railway doesn't have a built-in shell by default, so we'll use a workaround:

**Option A: Using Railway CLI (Recommended)**

```bash
# Install Railway CLI locally
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run Django shell
railway run python manage.py createsuperuser

# Follow prompts:
# Username: admin
# Email: admin@vibemall.com
# Password: (choose strong password)
```

**Option B: Using Django Command (Alternative)**

Add this to `Hub/management/commands/createdefaultadmin.py`:

```python
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@vibemall.com',
                password=os.environ.get('ADMIN_PASSWORD', 'ChangeThis123!')
            )
            self.stdout.write('Admin user created')
```

Then add to Railway environment:
```
ADMIN_PASSWORD=YourStrongPassword123!
```

Update `railway.json` start command:
```json
"startCommand": "python manage.py migrate && python manage.py createdefaultadmin && python manage.py collectstatic --noinput && gunicorn VibeMall.wsgi:application"
```

Push and redeploy!

#### 7.2 Populate Initial Data (Optional)

```bash
# If you have populate scripts
railway run python manage.py populate_categories
railway run python manage.py populate_products
```

---

### Step 8: Test Your Deployment (10 minutes)

#### 8.1 Basic Tests

Visit your Railway URL and test:

- [ ] **Homepage loads** (no 500 error)
- [ ] **Static files work** (CSS/JS loading)
- [ ] **Images display** (if any uploaded)
- [ ] **User registration works**
- [ ] **Login/logout works**
- [ ] **Product browsing works**

#### 8.2 Admin Panel Test

1. Go to: `https://your-railway-url.railway.app/admin/`
2. Login with superuser credentials
3. Verify dashboard loads
4. Check: Users, Products, Orders visible

#### 8.3 Payment Test (Razorpay)

1. Add product to cart
2. Proceed to checkout
3. Use Razorpay test card:
   - Card: `4111 1111 1111 1111`
   - CVV: `123`
   - Expiry: Any future date
4. Complete payment
5. Verify order created

#### 8.4 Email Test

1. Register new user
2. Check welcome email arrives
3. Or trigger forgot password
4. Verify email delivery

---

## Post-Deployment Configuration

### Enable Custom Domain (Optional)

1. Buy domain from GoDaddy/Namecheap/etc.
2. In Railway **Settings** → **Domains**
3. Click **"Custom Domain"**
4. Enter: `vibemall.com`
5. Add CNAME record in your domain registrar:
   ```
   Type: CNAME
   Name: @
   Value: your-railway-url.railway.app
   ```
6. Wait for DNS propagation (5-30 minutes)
7. Railway auto-provisions SSL certificate

---

## Monitoring & Maintenance

### View Logs

1. Railway Dashboard → Your service
2. Click **"Deployments"** tab
3. Click latest deployment
4. View **"Logs"** in real-time

**Look for errors:**
```bash
# Filter by error level
grep "ERROR" logs
grep "CRITICAL" logs
```

### Database Backups

Railway PostgreSQL includes automatic backups:
- **Free tier:** No automatic backups
- **Hobby plan ($5/mo):** Daily backups, 7-day retention

**Manual backup:**
```bash
# Export database locally
railway run pg_dump $DATABASE_URL > backup.sql
```

### Resource Monitoring

1. Railway Dashboard → **Metrics** tab
2. Check:
   - CPU usage (< 80%)
   - Memory usage (< 500MB for free tier)
   - Request count
   - Response times

---

## Troubleshooting

### Problem: "Application failed to respond"

**Solution:**
```bash
# Check logs in Railway dashboard
# Common issues:
1. Missing environment variable
2. Database not connected
3. Migration failed
4. Port binding issue (use $PORT)
```

**Fix:**
- Ensure `gunicorn` binds to `0.0.0.0:$PORT`
- Check `Procfile` or `railway.json` start command

### Problem: "Static files not loading (CSS missing)"

**Solution:**
```python
# In settings.py, ensure:
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# In MIDDLEWARE, add after SecurityMiddleware:
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this
    # ... other middleware
]
```

Then redeploy.

### Problem: "Database connection failed"

**Solution:**
```bash
# Check DATABASE_URL is set (auto by Railway)
railway variables

# Should show:
# DATABASE_URL=postgresql://user:pass@host:port/dbname

# If missing, recreate PostgreSQL service
```

### Problem: "ALLOWED_HOSTS error"

**Solution:**
```python
# In settings.py:
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.railway.app',  # All Railway domains
    'your-custom-domain.com',  # If custom domain
]

# Or use environment variable:
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
```

Then set in Railway variables:
```
ALLOWED_HOSTS=.railway.app,yourdomain.com
```

### Problem: "Migrations not applied"

**Solution:**
```bash
# Railway CLI:
railway run python manage.py migrate --run-syncdb

# Or update start command in railway.json:
"startCommand": "python manage.py migrate && gunicorn VibeMall.wsgi:application"
```

### Problem: "502 Bad Gateway"

**Solution:**
```bash
# Check if service is running
# In Railway logs, should see:
# "Booting worker with pid: 123"
# "Listening at: http://0.0.0.0:8000"

# If not, check:
1. gunicorn installed (in requirements.txt)
2. WSGI application path correct (VibeMall.wsgi:application)
3. Port binding: --bind 0.0.0.0:$PORT
```

---

## Cost Management

### Free Tier Limits

Railway free tier includes:
- **$5 credits/month**
- **Usage-based pricing**
- **Spend estimate:** ~$5-8/month for small traffic

**When free credits expire:**
- Service stops automatically
- Add payment method to continue

### Upgrade Options

| Plan | Price | Resources |
|------|-------|-----------|
| **Hobby** | $5/month | 8GB RAM, 500GB bandwidth |
| **Pro** | $20/month | 32GB RAM, 1TB bandwidth |

**Recommendation:** Start with free tier for testing, upgrade to Hobby ($5/mo) when ready for production.

---

## Auto-Deploy on Git Push

Railway watches your GitHub repo. Any push to `main` triggers auto-deploy!

**Workflow:**
```bash
# Local development
git add .
git commit -m "New feature"
git push origin main

# Railway automatically:
# 1. Detects push
# 2. Pulls latest code
# 3. Rebuilds
# 4. Runs migrations
# 5. Deploys new version
# (takes 2-3 minutes)
```

**Disable auto-deploy:**
1. Railway Dashboard → Settings
2. Uncheck "Automatic Deployments"
3. Manual deploy: Click "Deploy" button

---

## Comparison: Railway vs Others

| Feature | Railway | Render | Fly.io | Heroku |
|---------|---------|--------|--------|--------|
| **Free Tier** | $5 credits | Limited | 3 VMs | None |
| **Ease of Use** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Deploy Time** | 2-3 min | 3-5 min | 5-10 min | 3-5 min |
| **PostgreSQL** | Included | 90 days free | Included | $9/mo |
| **Auto HTTPS** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Credit Card** | ❌ Not required | ❌ Not required | ✅ Required | ✅ Required |

**Verdict:** Railway is the easiest for testing Django projects!

---

## Security Checklist

Before going live:

- [ ] `DEBUG=False` in Railway variables
- [ ] `SECRET_KEY` is unique and secure (not the one in git)
- [ ] `ALLOWED_HOSTS` properly configured
- [ ] HTTPS enabled (automatic on Railway)
- [ ] Database backups configured
- [ ] Environment variables not in git
- [ ] Razorpay keys are TEST keys (for testing)
- [ ] Error logging configured
- [ ] Rate limiting enabled (if implemented)

---

## Next Steps

1. **Test thoroughly** (spend 1 hour testing all features)
2. **Monitor for issues** (check logs daily for first week)
3. **Share with team** (get feedback)
4. **Load test** (use tools like Apache Bench)
5. **Upgrade plan** (when ready for production traffic)
6. **Custom domain** (buy domain and configure)
7. **Monitoring** (setup Sentry.io for error tracking)

---

## Quick Reference

### Useful Commands

```bash
# Deploy with Railway CLI
railway up

# View logs
railway logs

# Run Django commands
railway run python manage.py <command>

# Shell access
railway run python manage.py shell

# Database shell
railway run python manage.py dbshell

# Check service status
railway status
```

### Important URLs

- **Railway Dashboard:** https://railway.app/dashboard
- **Your Project:** https://railway.app/project/your-project-id
- **Documentation:** https://docs.railway.app
- **Support:** https://help.railway.app

---

## Success Checklist

- [ ] Code pushed to GitHub
- [ ] Railway account created
- [ ] Project deployed from GitHub
- [ ] PostgreSQL database added
- [ ] Environment variables configured
- [ ] Domain generated
- [ ] Site loads without errors
- [ ] Admin panel accessible
- [ ] Database migrations applied
- [ ] Superuser created
- [ ] Static files loading
- [ ] Test payment successful
- [ ] Email sending working
- [ ] Logs monitored (no errors)

**🎉 Congratulations! Your VibeMall is deployed on Railway!**

---

## Support

**Issues with deployment?**
1. Check Railway logs first
2. Review troubleshooting section above
3. Railway Discord: https://discord.gg/railway
4. Documentation: https://docs.railway.app

**Issues with Django?**
1. Check `logs/vibemall.log` locally
2. Run `python manage.py check --deploy`
3. Review Django docs: https://docs.djangoproject.com

---

## Document Info

```
Guide Version: 1.0
Platform: Railway.app
Django Version: 5.0.9
Last Updated: March 2, 2026
Tested: ✅ Working
Estimated Time: 15-20 minutes
Difficulty: ⭐⭐ (Easy)
```

**Ready to deploy? Start with Step 1! 🚀**
