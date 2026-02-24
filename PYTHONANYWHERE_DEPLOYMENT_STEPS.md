# PythonAnywhere Deployment - Step by Step Guide

## તમારું Account: VibeMall
## Status: ✅ Account Created

---

## 📋 Next Steps (Follow in Order)

---

## Step 1: Upload Code to GitHub (5 minutes)

### તમારા local computer પર:

```bash
# Git initialize કરો (જો પહેલેથી નથી)
git init

# .gitignore file બનાવો
echo "*.pyc
__pycache__/
db.sqlite3
.env
staticfiles/
media/
test_invoice.pdf
test_weasyprint.py
simple_test.py" > .gitignore

# બધી files add કરો
git add .

# Commit કરો
git commit -m "VibeMall - Ready for deployment"
```

### GitHub પર repository બનાવો:

1. https://github.com પર જાઓ
2. "New repository" click કરો
3. Repository name: `vibemall`
4. Public/Private select કરો
5. "Create repository" click કરો

### Code push કરો:

```bash
# GitHub repository link add કરો
git remote add origin https://github.com/your-username/vibemall.git

# Code push કરો
git branch -M main
git push -u origin main
```

---

## Step 2: PythonAnywhere Console Setup (10 minutes)

### PythonAnywhere Dashboard પર:

1. **"Consoles" tab** પર જાઓ
2. **"Bash"** console open કરો

### Console માં આ commands run કરો:

```bash
# 1. Clone your repository
git clone https://github.com/your-username/vibemall.git
cd vibemall

# 2. Create virtual environment
mkvirtualenv --python=/usr/bin/python3.10 vibemall-env

# 3. Install dependencies
pip install django pillow weasyprint gunicorn whitenoise python-decouple

# 4. Create .env file
nano .env
```

### .env file માં આ add કરો:

```
DEBUG=False
SECRET_KEY=your-new-secret-key-here
ALLOWED_HOSTS=vibemall.pythonanywhere.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
RAZORPAY_KEY_ID=your-razorpay-key
RAZORPAY_KEY_SECRET=your-razorpay-secret
```

**Save કરો:** Ctrl+X, then Y, then Enter

### Continue in console:

```bash
# 5. Update settings.py for production
nano VibeMall/settings.py
```

### settings.py માં આ changes કરો:

```python
# Top of file માં add કરો
from decouple import config

# DEBUG change કરો
DEBUG = config('DEBUG', default=False, cast=bool)

# SECRET_KEY change કરો
SECRET_KEY = config('SECRET_KEY', default='fallback-secret-key')

# ALLOWED_HOSTS update કરો
ALLOWED_HOSTS = ['vibemall.pythonanywhere.com', 'localhost', '127.0.0.1']

# SITE_URL update કરો
SITE_URL = 'https://vibemall.pythonanywhere.com'

# Static files configuration add કરો
STATIC_URL = '/static/'
STATIC_ROOT = '/home/VibeMall/vibemall/staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = '/home/VibeMall/vibemall/media'

# CSRF trusted origins add કરો
CSRF_TRUSTED_ORIGINS = ['https://vibemall.pythonanywhere.com']
```

**Save કરો:** Ctrl+X, then Y, then Enter

### Database setup:

```bash
# 6. Run migrations
python manage.py migrate

# 7. Create superuser
python manage.py createsuperuser
# Username: admin (or your choice)
# Email: info.vibemall@gmail.com
# Password: (choose strong password)

# 8. Collect static files
python manage.py collectstatic --noinput

# 9. Create auto coupons
python manage.py create_auto_coupons
```

---

## Step 3: Web App Configuration (5 minutes)

### PythonAnywhere Dashboard પર:

1. **"Web" tab** પર જાઓ
2. **"Add a new web app"** click કરો
3. Domain: `vibemall.pythonanywhere.com` (automatically filled)
4. **"Next"** click કરો
5. **"Manual configuration"** select કરો
6. **"Python 3.10"** select કરો
7. **"Next"** click કરો

---

## Step 4: WSGI File Configuration (5 minutes)

### Web tab પર:

1. **"Code"** section માં જાઓ
2. **"WSGI configuration file"** link click કરો (e.g., `/var/www/vibemall_pythonanywhere_com_wsgi.py`)

### WSGI file ને આ content થી replace કરો:

```python
import os
import sys

# Add your project directory to the sys.path
path = '/home/VibeMall/vibemall'
if path not in sys.path:
    sys.path.insert(0, path)

# Set environment variable for Django settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'VibeMall.settings'

# Activate virtual environment
activate_this = '/home/VibeMall/.virtualenvs/vibemall-env/bin/activate_this.py'
with open(activate_this) as f:
    exec(f.read(), {'__file__': activate_this})

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**Save કરો:** Click "Save" button

---

## Step 5: Static & Media Files Configuration (3 minutes)

### Web tab પર scroll down કરો:

### "Static files" section માં:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/VibeMall/vibemall/staticfiles` |
| `/media/` | `/home/VibeMall/vibemall/media` |

**Add કરો:**
1. URL: `/static/` → Directory: `/home/VibeMall/vibemall/staticfiles`
2. URL: `/media/` → Directory: `/home/VibeMall/vibemall/media`

---

## Step 6: Virtual Environment Configuration (2 minutes)

### Web tab પર:

**"Virtualenv"** section માં:

```
/home/VibeMall/.virtualenvs/vibemall-env
```

Enter કરો અને **checkmark** click કરો

---

## Step 7: Reload Web App (1 minute)

### Web tab પર:

1. Top પર **green "Reload" button** click કરો
2. Wait for reload to complete (10-20 seconds)

---

## Step 8: Test Your Website! 🎉

### Browser માં open કરો:

```
https://vibemall.pythonanywhere.com
```

### Test કરો:

- [ ] Homepage loads
- [ ] Products display
- [ ] Images show
- [ ] Login works
- [ ] Cart works
- [ ] Checkout works
- [ ] Admin panel: `https://vibemall.pythonanywhere.com/admin/`

---

## Step 9: Gmail App Password Setup (5 minutes)

### Email functionality માટે:

1. **Google Account** → Security
2. **2-Step Verification** enable કરો
3. **App Passwords** → Generate
4. **"Mail"** select કરો
5. Password copy કરો

### PythonAnywhere Console માં:

```bash
cd ~/vibemall
nano .env
```

### EMAIL_HOST_PASSWORD update કરો:

```
EMAIL_HOST_PASSWORD=your-16-digit-app-password
```

**Save and reload:**

```bash
# Web tab પર જઈને "Reload" button click કરો
```

---

## Step 10: Test Order & Email (5 minutes)

### Test order place કરો:

1. Website પર product add કરો
2. Checkout કરો
3. Order place કરો
4. Email check કરો
5. Invoice PDF verify કરો

---

## Troubleshooting

### Issue: Website not loading

**Check:**
1. Error log: Web tab → "Error log" link
2. Server log: Web tab → "Server log" link
3. WSGI file path correct છે?
4. Virtual environment path correct છે?

### Issue: Static files not loading

**Check:**
1. Static files path: `/home/VibeMall/vibemall/staticfiles`
2. Run: `python manage.py collectstatic`
3. Reload web app

### Issue: Database error

**Check:**
1. Migrations run થયા છે? `python manage.py migrate`
2. Database file permissions
3. Path correct છે?

### Issue: Import errors

**Check:**
1. Virtual environment activated છે?
2. Dependencies installed છે? `pip list`
3. Python version correct છે? (3.10)

---

## Important Commands

### Console માં:

```bash
# Activate virtual environment
workon vibemall-env

# Go to project directory
cd ~/vibemall

# Pull latest code
git pull origin main

# Install new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Check for errors
python manage.py check --deploy
```

### After any code change:

1. Console માં: `cd ~/vibemall && git pull`
2. Web tab માં: Click "Reload" button

---

## Free Tier Limitations

### PythonAnywhere Free Account:

- ✅ 1 web app
- ✅ 512 MB disk space
- ✅ 100 seconds CPU time per day
- ✅ HTTPS included
- ❌ No custom domain (only .pythonanywhere.com)
- ❌ No outbound internet access (except whitelist)
- ❌ No scheduled tasks

### Upgrade to Paid ($5/month):

- ✅ Custom domain support
- ✅ More CPU time
- ✅ More disk space
- ✅ Scheduled tasks
- ✅ Outbound internet access

---

## Custom Domain Setup (Paid Plan Only)

### If you upgrade:

1. **Web tab** → "Add a new web app"
2. Enter your domain: `yourdomain.com`
3. **DNS Settings** (at domain registrar):
   ```
   Type: CNAME
   Name: www
   Value: webapp-XXXXX.pythonanywhere.com
   ```
4. Wait for DNS propagation (24-48 hours)

---

## Backup Strategy

### Manual Backup:

```bash
# Console માં
cd ~/vibemall

# Database backup
python manage.py dumpdata > backup_$(date +%Y%m%d).json

# Download from Files tab
```

### Automatic Backup (Paid plan):

```bash
# Schedule daily task
cd ~/vibemall && python manage.py dumpdata > backups/backup_$(date +%Y%m%d).json
```

---

## Performance Tips

### Optimize Images:

```bash
# Install Pillow-SIMD (faster)
pip uninstall pillow
pip install pillow-simd
```

### Enable Caching:

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

### Compress Static Files:

```python
# settings.py
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
```

---

## Monitoring

### Check Logs:

1. **Web tab** → "Error log" (errors)
2. **Web tab** → "Server log" (access logs)
3. **Web tab** → "Access log" (requests)

### Email Logs:

```bash
# Console માં
cd ~/vibemall
python manage.py shell

# In shell:
from Hub.models import EmailLog
EmailLog.objects.filter(sent_successfully=False)
```

---

## Security Checklist

- [ ] DEBUG = False
- [ ] SECRET_KEY changed
- [ ] ALLOWED_HOSTS configured
- [ ] CSRF_TRUSTED_ORIGINS set
- [ ] Strong admin password
- [ ] Gmail App Password (not regular password)
- [ ] .env file not in Git
- [ ] Razorpay live keys (not test)

---

## Support

### PythonAnywhere Help:

- Forum: https://www.pythonanywhere.com/forums/
- Help: https://help.pythonanywhere.com/
- Email: support@pythonanywhere.com

### Django Help:

- Documentation: https://docs.djangoproject.com/
- Forum: https://forum.djangoproject.com/

---

## Quick Reference

### File Paths:

```
Project: /home/VibeMall/vibemall
Virtual Env: /home/VibeMall/.virtualenvs/vibemall-env
Static: /home/VibeMall/vibemall/staticfiles
Media: /home/VibeMall/vibemall/media
Database: /home/VibeMall/vibemall/db.sqlite3
```

### Important URLs:

```
Website: https://vibemall.pythonanywhere.com
Admin: https://vibemall.pythonanywhere.com/admin/
Dashboard: https://www.pythonanywhere.com/user/VibeMall/
```

---

## Estimated Time

- **Total Setup Time:** 30-40 minutes
- **Testing Time:** 10-15 minutes
- **Total:** ~1 hour

---

## Success Checklist ✅

After deployment:

- [ ] Website accessible
- [ ] Homepage loads
- [ ] Products display
- [ ] Images show
- [ ] Static files load
- [ ] Admin panel works
- [ ] Login/Register works
- [ ] Cart works
- [ ] Checkout works
- [ ] Payment gateway works
- [ ] Order confirmation email sent
- [ ] Invoice PDF attached
- [ ] Coupon system works
- [ ] Mobile responsive
- [ ] No errors in logs

---

## 🎉 Congratulations!

જ્યારે બધું કામ કરે ત્યારે તમારું VibeMall website live છે!

**Website:** https://vibemall.pythonanywhere.com

Share કરો અને enjoy કરો! 🚀

---

**Need Help?** Check error logs or contact PythonAnywhere support!

**Status:** Ready to Deploy  
**Platform:** PythonAnywhere  
**Date:** February 23, 2026
