# Production Deployment Checklist - VibeMall

## તારીખ: February 23, 2026

---

## 📋 Production માટે જરૂરી Steps

---

## 1. Django Settings Configuration ⚠️ CRITICAL

### settings.py માં આ changes કરો:

```python
# DEBUG = True થી બદલીને False કરો
DEBUG = False

# ALLOWED_HOSTS add કરો (તમારું domain name)
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com', 'your-server-ip']

# SECRET_KEY ને secure કરો (નવી generate કરો)
# આ command run કરો:
# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = 'your-new-production-secret-key-here'

# SITE_URL update કરો
SITE_URL = 'https://yourdomain.com'

# CSRF_TRUSTED_ORIGINS add કરો
CSRF_TRUSTED_ORIGINS = [
    'https://yourdomain.com',
    'https://www.yourdomain.com',
]

# SECURE_SSL_REDIRECT = True (જો HTTPS છે)
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Session Security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

---

## 2. Database Configuration 🗄️

### Option A: SQLite (Small Scale)
```python
# Current setup - OK for small traffic
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### Option B: PostgreSQL (Recommended for Production)
```python
# Install: pip install psycopg2-binary

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'vibemall_db',
        'USER': 'vibemall_user',
        'PASSWORD': 'your-secure-password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Option C: MySQL
```python
# Install: pip install mysqlclient

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'vibemall_db',
        'USER': 'vibemall_user',
        'PASSWORD': 'your-secure-password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

---

## 3. Email Configuration 📧 CRITICAL

### Gmail SMTP (Current Setup)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'info.vibemall@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-specific-password'  # NOT regular password!
DEFAULT_FROM_EMAIL = 'VibeMall <info.vibemall@gmail.com>'
```

### Gmail App Password Generate કરો:
1. Google Account → Security
2. 2-Step Verification enable કરો
3. App Passwords → Generate
4. "Mail" select કરો
5. Generated password copy કરો
6. settings.py માં use કરો

### Alternative: SendGrid (Professional)
```python
# Install: pip install sendgrid

EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
SENDGRID_API_KEY = 'your-sendgrid-api-key'
DEFAULT_FROM_EMAIL = 'info.vibemall@gmail.com'
```

---

## 4. Static Files Configuration 📁

### settings.py માં add કરો:
```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise for static files (recommended)
# Install: pip install whitenoise

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this
    # ... other middleware
]

# Static files compression
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### Static files collect કરો:
```bash
python manage.py collectstatic --noinput
```

---

## 5. Razorpay Payment Configuration 💳

### settings.py માં verify કરો:
```python
# Production keys use કરો (Test keys નહીં!)
RAZORPAY_KEY_ID = 'rzp_live_xxxxxxxxxxxxx'  # Live key
RAZORPAY_KEY_SECRET = 'your_live_secret_key'  # Live secret
```

### Razorpay Dashboard માં:
1. Test Mode થી Live Mode માં switch કરો
2. Live API Keys generate કરો
3. Webhook URL set કરો: `https://yourdomain.com/payment/webhook/`
4. Payment methods enable કરો
5. Business details complete કરો

---

## 6. Environment Variables (.env file) 🔐

### .env file બનાવો (sensitive data માટે):
```bash
# Install: pip install python-decouple

# .env file
DEBUG=False
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:password@localhost/dbname
EMAIL_HOST_PASSWORD=your-email-password
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=your_secret
```

### settings.py માં use કરો:
```python
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET')
```

### .gitignore માં add કરો:
```
.env
db.sqlite3
*.pyc
__pycache__/
staticfiles/
media/
```

---

## 7. Server Setup Options 🖥️

### Option A: Shared Hosting (Beginner Friendly)
**Providers:**
- PythonAnywhere (Easy Django hosting)
- Heroku (Free tier available)
- Railway.app (Modern, easy)

**Steps for PythonAnywhere:**
1. Account બનાવો: https://www.pythonanywhere.com
2. Code upload કરો (Git થી)
3. Virtual environment setup કરો
4. Dependencies install કરો
5. WSGI file configure કરો
6. Static files setup કરો
7. Database migrate કરો

### Option B: VPS (More Control)
**Providers:**
- DigitalOcean (₹400/month)
- Linode (₹400/month)
- AWS EC2 (Variable pricing)
- Google Cloud (Variable pricing)

**Required Software:**
- Ubuntu Server 22.04
- Python 3.11
- Nginx (Web server)
- Gunicorn (WSGI server)
- PostgreSQL (Database)
- Supervisor (Process manager)

### Option C: Cloud Platform
**Providers:**
- AWS Elastic Beanstalk
- Google App Engine
- Azure App Service

---

## 8. Web Server Configuration (VPS માટે)

### Nginx Configuration:
```nginx
# /etc/nginx/sites-available/vibemall

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Certificate (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Static files
    location /static/ {
        alias /home/user/vibemall/staticfiles/;
    }
    
    # Media files
    location /media/ {
        alias /home/user/vibemall/media/;
    }
    
    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Gunicorn Configuration:
```bash
# Install
pip install gunicorn

# Run
gunicorn VibeMall.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

### Supervisor Configuration:
```ini
# /etc/supervisor/conf.d/vibemall.conf

[program:vibemall]
command=/home/user/venv/bin/gunicorn VibeMall.wsgi:application --bind 127.0.0.1:8000 --workers 3
directory=/home/user/vibemall
user=user
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/user/vibemall/logs/gunicorn.log
```

---

## 9. SSL Certificate (HTTPS) 🔒

### Let's Encrypt (Free):
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

---

## 10. Database Backup 💾

### Automatic Backup Script:
```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/user/backups"

# Database backup
python manage.py dumpdata > $BACKUP_DIR/db_backup_$DATE.json

# Media files backup
tar -czf $BACKUP_DIR/media_backup_$DATE.tar.gz media/

# Keep only last 7 days
find $BACKUP_DIR -name "*.json" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Cron Job (Daily backup):
```bash
# crontab -e
0 2 * * * /home/user/vibemall/backup.sh
```

---

## 11. Monitoring & Logging 📊

### Django Logging Configuration:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/django_errors.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
```

### Monitoring Tools:
- **Sentry** - Error tracking (https://sentry.io)
- **New Relic** - Performance monitoring
- **Google Analytics** - User analytics
- **Uptime Robot** - Website uptime monitoring

---

## 12. Performance Optimization ⚡

### Caching:
```python
# Install Redis
# pip install django-redis

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

### Database Optimization:
```python
# Connection pooling
DATABASES = {
    'default': {
        # ... other settings
        'CONN_MAX_AGE': 600,  # 10 minutes
    }
}
```

---

## 13. Security Checklist ✅

### Django Security:
```bash
# Run security check
python manage.py check --deploy
```

### Additional Security:
- [ ] DEBUG = False
- [ ] SECRET_KEY changed
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enabled
- [ ] CSRF protection enabled
- [ ] SQL injection protection (Django ORM)
- [ ] XSS protection enabled
- [ ] Strong passwords enforced
- [ ] Rate limiting implemented
- [ ] File upload validation
- [ ] Admin panel secured (/admin/ URL change કરો)

---

## 14. Testing Before Launch 🧪

### Checklist:
- [ ] User registration works
- [ ] Login/Logout works
- [ ] Product browsing works
- [ ] Add to cart works
- [ ] Checkout process works
- [ ] Payment gateway works (test mode)
- [ ] Order confirmation email received
- [ ] Invoice PDF attached
- [ ] Coupon system works
- [ ] Admin panel accessible
- [ ] Mobile responsive
- [ ] All pages load correctly
- [ ] Images display properly
- [ ] Forms validate correctly

---

## 15. Domain & DNS Configuration 🌐

### Domain Purchase:
- GoDaddy
- Namecheap
- Google Domains
- Hostinger

### DNS Settings:
```
Type    Name    Value               TTL
A       @       your-server-ip      3600
A       www     your-server-ip      3600
```

---

## 16. Post-Launch Monitoring 📈

### Daily Tasks:
- Check error logs
- Monitor email delivery
- Check payment transactions
- Review order processing
- Monitor server resources

### Weekly Tasks:
- Database backup verification
- Security updates
- Performance review
- User feedback review

### Monthly Tasks:
- Full system backup
- Security audit
- Performance optimization
- Feature updates

---

## 17. Required Python Packages

### requirements.txt બનાવો:
```bash
# Generate requirements
pip freeze > requirements.txt
```

### Essential Packages:
```
Django==4.2.x
Pillow==10.2.0
weasyprint==68.1
gunicorn==21.2.0
whitenoise==6.6.0
python-decouple==3.8
psycopg2-binary==2.9.9  # For PostgreSQL
django-redis==5.4.0  # For caching
```

---

## 18. Deployment Commands Summary

### Local to Production:
```bash
# 1. Update code
git pull origin main

# 2. Install dependencies
pip install -r requirements.txt

# 3. Collect static files
python manage.py collectstatic --noinput

# 4. Run migrations
python manage.py migrate

# 5. Create superuser (first time only)
python manage.py createsuperuser

# 6. Restart server
sudo supervisorctl restart vibemall
# OR
sudo systemctl restart gunicorn
```

---

## 19. Cost Estimation 💰

### Minimum Setup (Monthly):
- Domain: ₹100-500
- Shared Hosting: ₹300-1000
- Email (Gmail): Free
- SSL Certificate: Free (Let's Encrypt)
- **Total: ₹400-1500/month**

### Recommended Setup (Monthly):
- Domain: ₹500
- VPS (DigitalOcean): ₹400-800
- Database: Included
- Email (SendGrid): Free (100 emails/day)
- SSL: Free
- Backup Storage: ₹200
- **Total: ₹1100-1500/month**

### Professional Setup (Monthly):
- Domain: ₹500
- VPS (2GB RAM): ₹800-1500
- Managed Database: ₹500-1000
- Email Service: ₹500-1000
- CDN: ₹300-500
- Monitoring: ₹500
- **Total: ₹3100-4500/month**

---

## 20. Emergency Contacts & Resources 📞

### Support:
- Django Documentation: https://docs.djangoproject.com
- Stack Overflow: https://stackoverflow.com
- Django Forum: https://forum.djangoproject.com

### Hosting Support:
- PythonAnywhere: help@pythonanywhere.com
- DigitalOcean: https://www.digitalocean.com/support
- Heroku: https://help.heroku.com

---

## Quick Start Guide (PythonAnywhere - Easiest)

### Step-by-Step:

1. **Account બનાવો:**
   - https://www.pythonanywhere.com
   - Free account select કરો

2. **Code Upload:**
   ```bash
   # Git repository create કરો
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin your-repo-url
   git push -u origin main
   ```

3. **PythonAnywhere Console:**
   ```bash
   # Clone repository
   git clone your-repo-url
   cd vibemall
   
   # Virtual environment
   mkvirtualenv --python=/usr/bin/python3.10 vibemall-env
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Migrations
   python manage.py migrate
   python manage.py collectstatic
   python manage.py createsuperuser
   ```

4. **Web App Setup:**
   - Web tab → Add new web app
   - Manual configuration → Python 3.10
   - Source code: /home/username/vibemall
   - WSGI file configure કરો
   - Static files: /static/ → /home/username/vibemall/staticfiles
   - Media files: /media/ → /home/username/vibemall/media

5. **Environment Variables:**
   - WSGI file માં add કરો
   - settings.py update કરો

6. **Reload Web App:**
   - Green "Reload" button click કરો

7. **Test:**
   - your-username.pythonanywhere.com visit કરો

---

## ✅ Final Checklist

Before going live:

- [ ] DEBUG = False
- [ ] SECRET_KEY changed
- [ ] ALLOWED_HOSTS configured
- [ ] Database configured
- [ ] Email configured and tested
- [ ] Static files collected
- [ ] Media files configured
- [ ] Razorpay live keys configured
- [ ] SSL certificate installed
- [ ] Domain configured
- [ ] Backup system setup
- [ ] Monitoring setup
- [ ] All features tested
- [ ] Mobile responsive verified
- [ ] Payment gateway tested
- [ ] Email delivery tested
- [ ] Invoice PDF tested

---

## 🎯 Recommended Approach

### For Beginners:
1. Start with **PythonAnywhere** (easiest)
2. Use SQLite database (included)
3. Use Gmail SMTP (free)
4. Use free subdomain (username.pythonanywhere.com)
5. Upgrade later as needed

### For Intermediate:
1. Use **DigitalOcean Droplet** (₹400/month)
2. PostgreSQL database
3. Nginx + Gunicorn
4. Custom domain
5. Let's Encrypt SSL

### For Advanced:
1. AWS/Google Cloud
2. Load balancing
3. CDN integration
4. Redis caching
5. Celery for async tasks
6. Elasticsearch for search
7. Docker containers

---

## 📞 Need Help?

જો કોઈ પણ step માં problem આવે તો:

1. Documentation વાંચો
2. Error message Google કરો
3. Stack Overflow પર search કરો
4. Django forum પર પૂછો
5. મને contact કરો: info.vibemall@gmail.com

---

**Good Luck with your Production Deployment! 🚀**

**Status:** Ready for Production  
**Date:** February 23, 2026  
**Version:** 1.0
