# .env Validation Implementation Guide

## Overview

The VibeMall application now includes automatic environment variable validation that runs on Django startup. This ensures all critical and important configuration is set correctly before the application initializes.

## What Was Added

### 1. Environment Validator Module
**File:** `VibeMall/env_validator.py`

A dedicated module that:
- Validates environment variables on Django startup
- Categorizes variables as CRITICAL, IMPORTANT, or OPTIONAL
- Logs validation results with appropriate severity levels
- Provides detailed information about missing or configured variables

### 2. Integration with Django
**Modified:** `VibeMall/settings.py`

Added validation call at the top of settings initialization:
```python
from VibeMall.env_validator import EnvironmentValidator
_env_validation = EnvironmentValidator()
_env_validation.log_summary()
```

### 3. Updated Configuration Files
- **`.env.example`**: Extended with comprehensive documentation
- **`ENV_CONFIGURATION.md`**: Complete configuration guide for all variables

## Variable Categories

### CRITICAL Variables (Empty list - no hard stops)
Currently no variables are marked as critical to allow flexible deployment. In production, you may want to add:
- `SECRET_KEY`
- `RAZORPAY_KEY_ID`

### IMPORTANT Variables (Warnings if missing)
These should be configured for production deployments:
- `EMAIL_HOST_USER` - For sending emails
- `EMAIL_HOST_PASSWORD` - Email authentication
- `RAZORPAY_KEY_ID` - Payment processing
- `RAZORPAY_KEY_SECRET` - Payment processing
- `RAZORPAY_WEBHOOK_SECRET` - Payment verification

### OPTIONAL Variables (Have defaults)
These have sensible defaults but can be configured:
- `DEBUG` (default: True)
- `SECRET_KEY` (has fallback)
- `DATABASE_URL` (defaults to SQLite)
- `ALLOWED_HOSTS` (defaults to localhost)
- `EMAIL_HOST` (default: smtp.gmail.com)
- `EMAIL_PORT` (default: 587)
- `EMAIL_USE_TLS` (default: True)
- `DEFAULT_FROM_EMAIL` (default: VibeMall <info@vibemall.com>)

## Usage Examples

### Development Setup

Create `.env` in project root:
```env
DEBUG=True
SECRET_KEY=dev-key-anything-works-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

Run Django:
```bash
python manage.py runserver
```

Expected log output:
```
[INFO] Running in DEBUG mode
[INFO] Optional environment variables configured: DEBUG, SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS
[INFO] ✓ Environment validation passed - all critical variables are set
```

### Production Setup

Create `.env` in project root with all variables:
```env
DEBUG=False
SECRET_KEY=<long-random-production-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:pass@host/db

EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=xxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxx
```

Expected log output:
```
[INFO] Running in PRODUCTION mode - ensure all configurations are correct
[WARNING] Missing important environment variables: ...
[INFO] Optional environment variables configured: DEBUG, SECRET_KEY, DATABASE_URL, ...
[INFO] ✓ Environment validation passed - all critical variables are set
```

## Validation Output Explained

### Startup Message
```
[ENV VALIDATOR] Running in DEBUG mode
```
Shows whether application is in development or production mode.

### Info Messages
```
[INFO] Optional environment variables configured: DEBUG, SECRET_KEY, ENVIRONMENT_PROFILE
```
Lists all configured optional variables.

### Warning Messages
```
[WARNING] Missing important environment variables:
  EMAIL_HOST_USER: Email host user for sending emails
  RAZORPAY_KEY_ID: Razorpay API key ID for payment processing
```

Variables that should be configured but are missing (non-blocking).

### Error Messages
```
[ERROR] Missing required environment variables: SECRET_KEY, DATABASE_URL
```

Critical variables that must be set (application may refuse to start if implemented).

## Making Variables Required (Production)

To make validation strict in production, modify `settings.py`:

```python
# At the end of settings.py
if not DEBUG:
    from VibeMall.env_validator import validate_environment
    try:
        validate_environment()
    except EnvironmentError as e:
        raise RuntimeError(f"Production setup failed: {e}")
```

This will raise an error and prevent Django from starting if any critical variable is missing.

## Extending Validator

To add custom variables to validation, edit `VibeMall/env_validator.py`:

### Adding IMPORTANT variables
```python
IMPORTANT_VARS = {
    'YOUR_NEW_VAR': 'Description of what this variable does',
    'EMAIL_HOST_USER': 'Email host user for sending emails',
    # ... existing variables
}
```

### Adding OPTIONAL variables
```python
OPTIONAL_VARS = {
    'YOUR_NEW_VAR': 'Description including default value',
    'DEBUG': 'Debug mode (default: True)',
    # ... existing variables
}
```

## Testing Validation

### In Python Shell
```bash
python manage.py shell

# In the shell:
from VibeMall.env_validator import EnvironmentValidator
validator = EnvironmentValidator()
result = validator.validate()

print(result['valid'])  # True/False
print(result['messages'])  # List of validation messages
```

### Check Logs
```bash
# After starting Django:
python manage.py runserver

# Look for [ENV VALIDATOR] messages in console
```

### Manual Variable Check
```bash
python -c "from decouple import config; print(config('EMAIL_HOST_USER', default='NOT SET'))"
```

## Troubleshooting

### Variables not being read
1. Ensure `.env` file is in project root (same as `manage.py`)
2. Check `.env` file is readable
3. Variable names are case-sensitive
4. Restart Django after editing `.env`

### Import error: env_validator not found
Ensure `env_validator.py` exists in `VibeMall/` directory

### Variables work locally but not on server
- Check server has `.env` file uploaded
- Verify environment variable names match exactly
- Some hosting platforms use different setup (e.g., Heroku uses `config vars` instead of `.env`)

## Security Considerations

1. **Never commit `.env`** - Add to `.gitignore`
2. **Use application-specific passwords** - For email services
3. **Rotate secrets regularly** - Razorpay keys, webhooks
4. **Separate environments** - Use different `.env` files for dev/staging/production
5. **Log validation but don't expose values** - Validator logs variable names, not values

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: Deploy
on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Create .env
        run: |
          cat > .env << EOF
          DEBUG=False
          SECRET_KEY=${{ secrets.SECRET_KEY }}
          EMAIL_HOST_USER=${{ secrets.EMAIL_HOST_USER }}
          # ... more variables
          EOF
      - run: python manage.py migrate
      - run: python manage.py runserver  # Validates .env on startup
```

## Reference

- **Validator Code:** [VibeMall/env_validator.py](VibeMall/env_validator.py)
- **Settings Integration:** [VibeMall/settings.py](VibeMall/settings.py#L19-L22)
- **Configuration Guide:** [ENV_CONFIGURATION.md](ENV_CONFIGURATION.md)
- **Example Configuration:** [.env.example](.env.example)
- **python-decouple Docs:** https://github.com/henriquebastos/python-decouple
