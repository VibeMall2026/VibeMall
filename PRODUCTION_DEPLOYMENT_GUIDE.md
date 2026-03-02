# VibeMall Production Deployment Guide

## Quick Summary
- **Deployment Time:** ~4 hours
- **Downtime:** ~15 minutes
- **Skill Level:** Intermediate
- **Cost:** $5-20/month minimum

---

## Pre-Deployment Checklist

### 1. Choose Hosting Provider

| Provider | Cost | Difficulty | Recommendation |
|----------|------|-----------|-----------------|
| **Render.com** | $7-50/mo | Easy | ⭐ Best for beginners |
| **PythonAnywhere** | $5-50/mo | Easy | Good alternative |
| **Digital Ocean** | $5-12/mo | Medium | More control |
| **AWS** | $5-100+/mo | Hard | Enterprise |
| **Heroku** | $7-50/mo | Easy | Simple but pricier |

**Recommended:** Render.com (easiest, cheapest, most reliable)

---

## Step 1: Prepare Your Local Project

### 1.1 Create Production `.env`
```bash
# Copy and update .env with production values
cp .env.example .env.production

# Edit .env.production with:
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SECRET_KEY=your-very-secret-random-string-min-50-chars
DATABASE_URL=postgresql://user:pass@host/dbname
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=xxxxx
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
```

### 1.2 Update Requirements
```bash
# Ensure requirements.txt has production packages
pip freeze > requirements.txt

# Add production-specific packages
echo "gunicorn>=20.1.0" >> requirements.txt
echo "psycopg2-binary>=2.9.0" >> requirements.txt
echo "whitenoise>=6.0.0" >> requirements.txt
echo "django-cors-headers>=3.11.0" >> requirements.txt
```

### 1.3 Verify Code
```bash
# Run all tests
python manage.py test

# Run production checks
python manage.py check --deploy

# Run custom production test suite
python run_production_tests.py
```

---

## Step 2: Database Migration

### 2.1 Create PostgreSQL Database
```bash
# If using local PostgreSQL for testing
createdb vibemall_prod
createuser vibemall_user

# Password: [your-secure-password]

# Grant permissions
psql -c "ALTER ROLE vibemall_user WITH PASSWORD 'your-password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE vibemall_prod TO vibemall_user;"
```

### 2.2 Run Migrations
```bash
# Using production database
python manage.py migrate --database=production

# Or with environment variable
DATABASE_URL="postgresql://user:pass@localhost/vibemall_prod" python manage.py migrate
```

### 2.3 Create Superuser
```bash
# Create admin account
python manage.py createsuperuser --username=admin --email=admin@yourdomain.com

# Then enter password when prompted
```

---

## Step 3: Deploy to Render.com (Recommended)

### 3.1 Create Render Account
1. Go to https://render.com
2. Sign up with GitHub
3. Create new Web Service

### 3.2 Create render.yaml
```yaml
# render.yaml in project root
services:
  - type: web
    name: vibemall
    env: python
    plan: starter
    buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
    startCommand: gunicorn VibeMall.wsgi:application --bind 0.0.0.0:$PORT
    envVars:
      - key: DEBUG
        value: "False"
      - key: ALLOWED_HOSTS
        value: "yourdomain.com,www.yourdomain.com"
      - key: DATABASE_URL
        fromDatabase:
          name: vibemall-db
          property: connectionString
      - key: PYTHON_VERSION
        value: "3.11.4"
  
  - type: pserv
    name: vibemall-db
    env: postgres
    plan: starter
    ipAllowList: []
    postgresMajorVersion: "14"
```

### 3.3 Push to GitHub
```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Production deployment"
git branch -M main
git remote add origin https://github.com/yourusername/vibemall.git
git push -u origin main
```

### 3.4 Configure in Render
1. Go to Render Dashboard
2. Click "New +" → "Web Service"
3. Connect GitHub repo
4. Configure environment variables
5. Deploy!

**Estimated time:** 15-20 minutes

---

## Step 4: Configure Domain

### 4.1 Get Domain
- Buy domain from GoDaddy, Namecheap, or Google Domains
- Cost: $8-15/year

### 4.2 Update DNS
1. Get Render DNS records from dashboard
2. Update domain DNS settings to point to Render
3. Wait 24-48 hours for propagation

### 4.3 Enable SSL
- Render auto-configures Let's Encrypt SSL
- All traffic automatically HTTPS

---

## Step 5: Post-Deployment Validation

### 5.1 Basic Checks
```bash
# Check site is live
curl -I https://yourdomain.com
# Should return: HTTP/2 200

# Check admin works
curl -I https://yourdomain.com/admin
# Should return: HTTP/2 200 or 302 (redirect to login)
```

### 5.2 Full Validation
1. **User Registration**
   - Register new account
   - Verify email works
   - Login/logout works

2. **Product Browsing**
   - Browse products
   - Search works
   - Filter works

3. **Shopping Experience**
   - Add items to cart
   - View cart
   - Proceed to checkout

4. **Payment Testing**
   - Process test payment (Razorpay test mode)
   - Verify order created
   - Check confirmation email

5. **Admin Functions**
   - Login to admin panel
   - View orders
   - Process refund (test)
   - Download reports

### 5.3 Performance Check
```bash
# Check page load times
time curl https://yourdomain.com > /dev/null

# Should load in < 2 seconds
```

---

## Step 6: Setup Monitoring & Alerts

### 6.1 Error Tracking (Sentry)
```bash
# Install Sentry
pip install sentry-sdk

# Add to settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=True
)
```

### 6.2 Application Monitoring
- Use Render's built-in monitoring
- Set up alerts for:
  - High error rate (> 5%)
  - High response time (> 2s)
  - Low memory (< 50MB available)

### 6.3 Backup Configuration
```bash
# Configure database backups
# In Render: Database → Backups → Enable automated backups

# Recommended: Daily backups, keep 30 days
```

---

## Step 7: Go Live!

### 7.1 Before Going Live
- [ ] All tests passing
- [ ] All features working
- [ ] Admin functions verified
- [ ] Backups configured
- [ ] Monitoring alerts set
- [ ] Team trained on maintenance

### 7.2 Notify Users
- [ ] Email announcement
- [ ] Update website
- [ ] Social media posts

### 7.3 Monitor First 24 Hours
- [ ] Check error logs hourly
- [ ] Monitor performance
- [ ] Watch for support tickets
- [ ] Verify backups running

---

## Troubleshooting

### Static Files Not Loading
```bash
# Collect and upload static files
python manage.py collectstatic --noinput

# Add to manage.py runserver in production
# Use whitenoise middleware
```

### Database Connection Error
```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1;"

# Check Render database is created
```

### Email Not Sending
```bash
# Verify Gmail App Password
python manage.py shell
from django.core.mail import send_mail
send_mail('Test', 'Test body', settings.EMAIL_HOST_USER, [settings.EMAIL_HOST_USER])

# Check Gmail less secure apps or App Passwords
```

### 404 Errors on Admin
```bash
# Ensure ALLOWED_HOSTS includes domain
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# Restart app after changing
```

---

## Maintenance Schedule

### Daily
- [ ] Check error logs
- [ ] Monitor performance metrics
- [ ] Verify backups completed

### Weekly
- [ ] Review user activity
- [ ] Check database performance
- [ ] Review support tickets

### Monthly
- [ ] Update dependencies
- [ ] Security audit
- [ ] Performance optimization
- [ ] Backup verification

### Quarterly
- [ ] Full security review
- [ ] Database maintenance
- [ ] Disaster recovery drill
- [ ] Update documentation

---

## Important Files

| File | Purpose |
|------|---------|
| `.env` | Production environment variables |
| `requirements.txt` | Python dependencies |
| `render.yaml` | Deployment configuration |
| `.gitignore` | Exclude sensitive files |
| `manage.py` | Django management |

---

## Support Contacts

- **Render Support:** support@render.com
- **Django Issues:** docs.djangoproject.com
- **PostgreSQL Help:** postgresql.org
- **Razorpay Help:** razorpay.com/support

---

## Deployment Costs

| Component | Cost |
|-----------|------|
| Render Web Service | $7/month |
| PostgreSQL Database | $7/month |
| Custom Domain | $10/year |
| SSL Certificate | Free (Let's Encrypt) |
| **Total Minimum** | **$14/month** |

---

## Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| Preparation | 1 hour | Database setup, env config |
| Testing | 1 hour | Run test suite, validate |
| Deployment | 30 min | Push to Render, configure |
| Validation | 1 hour | Test all features |
| **Total** | **3.5 hours** | - |

---

**Status:** Ready to deploy  
**Last Updated:** March 2, 2026  
**Next Step:** Follow Step 1
