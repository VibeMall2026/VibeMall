# Environment Variable Configuration Guide

This guide explains how to configure environment variables for the VibeMall application. Environment variables are validated on Django startup to catch configuration issues early.

## Configuration File

Create a `.env` file in the project root directory (same level as `manage.py`):

```bash
touch .env
```

## Environment Variables

### Critical Variables

These variables are essential for application functionality:

#### `SECRET_KEY`
Django secret key for cryptographic signing. Should be a long, random string in production.

```env
SECRET_KEY=your-very-long-random-secret-key-here-at-least-50-characters
```

**Generation:**
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

#### `DEBUG`
Enable/disable debug mode. Should be `False` in production.

```env
DEBUG=False
```

---

### Important Variables

These variables should be configured for production deployment:

#### Email Configuration

Required for sending verification emails, password reset, and notifications.

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
DEFAULT_FROM_EMAIL=VibeMall <noreply@vibemall.com>
```

**For Gmail:**
- Enable 2-factor authentication on your Google Account
- Generate an [App Password](https://support.google.com/accounts/answer/185833)
- Use the app password as `EMAIL_HOST_PASSWORD`

**For AWS SES:**
```env
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-ses-user
EMAIL_HOST_PASSWORD=your-ses-password
```

#### Razorpay Payment Gateway

Required for payment processing functionality.

```env
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your-razorpay-secret-key
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret
```

**Getting Razorpay Credentials:**
1. Sign up at [Razorpay Dashboard](https://dashboard.razorpay.com)
2. Navigate to Settings → API Keys
3. Copy Key ID and Key Secret
4. Generate Webhook Secret in Settings → Webhooks

---

### Optional Variables

These variables have sensible defaults and are optional:

#### `DATABASE_URL`
Database connection string. Defaults to SQLite if not set.

```env
# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/vibemall

# MySQL
DATABASE_URL=mysql://user:password@localhost:3306/vibemall

# SQLite (default)
# Leave unset to use SQLite at db.sqlite3
```

**Format:** `engine://user:password@host:port/database`

#### `ALLOWED_HOSTS`
Comma-separated list of allowed host/domain names.

```env
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com,www.yourdomain.com
```

#### `ALLOWED_HOSTS` (Advanced)
For development, you can use wildcard:

```env
ALLOWED_HOSTS=*
```

**Warning:** Never use wildcard in production.

---

## Environment Variable Validation

### During Startup

When Django starts, it validates environment variables and logs:

```
[INFO] Environment validation passed - all critical variables are set
[WARNING] Missing important environment variables:
  EMAIL_HOST_USER: Email host user for sending emails
  RAZORPAY_KEY_ID: Razorpay API key ID for payment processing
[INFO] Optional environment variables configured: DEBUG, SECRET_KEY
```

### Validation Output

The validator logs:
- **CRITICAL**: Variables required for application to function
- **WARNING**: Variables that should be configured for production
- **INFO**: Optional variables that are configured

### Common Issues

#### Missing EMAIL Configuration
**Error:**
```
[WARNING] Missing important environment variables:
  EMAIL_HOST_USER: Email host user for sending emails
```

**Solution:**
```env
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

#### Missing Razorpay Keys
**Error:**
```
[WARNING] Missing important environment variables:
  RAZORPAY_KEY_ID: Razorpay API key ID for payment processing
```

**Solution:**
1. Get keys from [Razorpay Dashboard](https://dashboard.razorpay.com/app/settings/api-keys)
2. Set in `.env`:
```env
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=xxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxx
```

---

## Development vs Production

### Development Setup

Minimum required `.env`:
```env
DEBUG=True
SECRET_KEY=dev-key-can-be-anything-for-development
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Production Setup

Complete `.env` with all variables:
```env
DEBUG=False
SECRET_KEY=<long-random-production-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@host:5432/vibemall

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL=VibeMall <noreply@vibemall.com>

# Razorpay
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=xxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxx
```

---

## Loading Environment Variables

The application uses `python-decouple` to load environment variables:

```bash
pip install python-decouple
```

This automatically reads from:
1. Environment variables set in your system
2. Variables in `.env` file in project root
3. Fallback defaults specified in code

---

## Security Best Practices

### 1. Never commit `.env`

Add to `.gitignore`:
```
.env
.env.local
.env.*.local
```

Use `.env.example` for documentation:
```bash
cp .env .env.example
# Remove sensitive values from .env.example
git add .env.example
```

### 2. Use Separate Credentials

- Development `.env`: test credentials
- Production `.env`: production credentials stored securely
- Never copy production `.env` to development machine

### 3. Rotate Secrets Regularly

- Change Razorpay API keys regularly
- Update email passwords when expiry approaches
- Rotate SECRET_KEY if compromised

### 4. Environment-Specific Validation

In production, consider making all variables required:

```python
# In settings.py for production only
if not DEBUG:
    from VibeMall.env_validator import validate_environment
    validate_environment()  # Raises error if variables missing
```

---

## Testing Configuration

To test your environment variables:

```bash
python manage.py shell

# In the shell:
from decouple import config
print(config('SECRET_KEY'))
print(config('EMAIL_HOST_USER'))
print(config('RAZORPAY_KEY_ID'))
```

---

## Deployment Platforms

### PythonAnywhere

Set environment variables in **Web** tab → **Environment variables**:
```
DJANGO_SETTINGS_MODULE=VibeMall.settings
SECRET_KEY=your-secret-key
DEBUG=False
/Email and Razorpay configs/
```

### Heroku

```bash
heroku config:set DEBUG=False
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DATABASE_URL=postgresql://...
heroku config:set EMAIL_HOST_USER=your-email@gmail.com
# ... etc
```

### AWS/Docker

Create environment file:
```bash
# .env.production
DEBUG=False
SECRET_KEY=your-secret-key
/All required variables/
```

Mount as volume in container or pass to Docker:
```dockerfile
ENV_FILE=.env.production
```

---

## Troubleshooting

### validate_environment() raises EnvironmentError

**Reason:** Critical environment variable is missing

**Solution:** Add the missing variable to `.env`

### Django won't start with env_validator

**Error:** `ImportError: No module named 'env_validator'`

**Solution:** Ensure `env_validator.py` is in the `VibeMall` app directory

### Variables not being read

**Solution:**
1. Verify `.env` file exists in project root
2. Check `.env` file permissions (should be readable)
3. Ensure you're using correct variable name (case-sensitive on Linux)
4. Restart Django server after editing `.env`

---

## Reference

- [python-decouple Documentation](https://github.com/henriquebastos/python-decouple)
- [Django Security Documentation](https://docs.djangoproject.com/en/5.2/topics/security/)
- [Razorpay API Documentation](https://razorpay.com/docs/api/)
