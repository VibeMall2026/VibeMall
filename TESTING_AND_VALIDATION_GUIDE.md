# VibeMall Pre-Production Testing & Validation Guide

## 📋 Quick Start

```bash
# Run all tests in sequence
bash run_all_tests.sh

# Or run individually:
python manage.py test                           # Django tests
python run_production_tests.py                  # Production tests
bash validate_deployment.sh                     # Deployment validation
bash security_check.sh                          # Security check
```

---

## Test Suite Overview

### 1. Unit Tests
**Time:** ~5 minutes  
**Command:** `python manage.py test`

Tests:
- User authentication
- Product models
- Order processing
- Payment validation
- Backup system

**Expected Output:**
```
Ran XX tests in Xs
OK
```

### 2. Production Configuration Tests
**Time:** ~2 minutes  
**Command:** `python run_production_tests.py`

Tests:
- DEBUG mode off
- ALLOWED_HOSTS configured
- Database connected
- Email configured
- Security headers set
- Razorpay SDK available
- JSON serialization working

**Expected Output:**
```
✓ All 15 tests passed
Ready for production deployment!
```

### 3. Integration Tests
**Time:** ~10 minutes  
**Tests:**
- User registration flow
- Product browsing
- Cart operations
- Order creation
- Payment processing
- Refund handling
- Backup operations

### 4. Security Tests
**Time:** ~5 minutes  
**Tests:**
- CSRF protection
- XSS prevention
- SQL injection prevention
- Password hashing
- Authorization checks
- Rate limiting

### 5. Performance Tests
**Time:** ~10 minutes  
**Tests:**
- Page load time
- Database query count
- API response time
- Concurrent users
- Memory usage

---

## Step-by-Step Testing Process

### Step 1: Environment Validation (5 min)

```bash
# Check Python version (should be 3.10+)
python --version

# Check Django version
python -c "import django; print(django.VERSION)"

# Check all packages installed
pip list | grep -E "django|razorpay|psycopg2|pillow"

# Verify database connection
python manage.py dbshell < /dev/null
```

### Step 2: Code Quality Check (5 min)

```bash
# Check for syntax errors
python -m py_compile Hub/*.py
python -m py_compile Hub/views.py

# Check with Django system check
python manage.py check --deploy

# Check for security issues
pip install bandit
bandit -r Hub/
```

### Step 3: Run Unit Tests (5 min)

```bash
# Run all tests
python manage.py test

# Run specific test suite
python manage.py test Hub.tests.test_models
python manage.py test Hub.tests.test_views
python manage.py test Hub.tests.test_payments

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report --omit=venv/*
```

### Step 4: Run Production Tests (2 min)

```bash
# Complete production readiness check
python run_production_tests.py
```

**Should see:**
- ✓ DEBUG Mode: PASS
- ✓ Database Connection: PASS
- ✓ Email Configuration: PASS
- ✓ Razorpay Integration: PASS
- ✓ All Security Checks: PASS

### Step 5: Manual Feature Testing (30 min)

#### 5.1 User Registration
```
1. Go to /register
2. Fill form with valid data
3. Submit
4. Check email for verification link
5. Click verification link
6. Login with credentials
✓ Should be logged in
```

#### 5.2 Product Browsing
```
1. Go to homepage
2. Browse products
3. Search for product
4. Filter by category
5. Sort by price
6. View product details
✓ All should work without errors
```

#### 5.3 Shopping Cart
```
1. Add product to cart
2. View cart
3. Update quantity
4. Remove item
5. Clear cart
6. Close browser
7. Reopen browser
8. Check cart still has items
✓ Cart persistence working
```

#### 5.4 Order Creation
```
1. Add item to cart
2. Proceed to checkout
3. Select COD payment
4. Fill address
5. Review order
6. Place order
✓ Order created successfully
✓ Confirmation email sent
✓ Order visible in admin
```

#### 5.5 Payment Processing
```
1. Add item to cart
2. Checkout with Razorpay
3. Use test card: 4111 1111 1111 1111
4. Enter test OTP: 000000
5. Complete payment
✓ Payment successful
✓ Order status: PAID
✓ Confirmation email sent
```

#### 5.6 Refund Processing
```
1. Go to Admin Panel
2. Select PAID order
3. Click Refund
4. Enter refund amount
5. Submit
✓ Refund processes
✓ Order status: REFUND_PENDING
✓ No "SDK not found" error
```

#### 5.7 Admin Panel
```
1. Login to /admin
2. View Dashboard
3. View Orders
4. View Backup Analytics
5. Download Reports
6. Check all functions work
✓ No errors
✓ All data displays correctly
```

### Step 6: Security Validation (10 min)

```bash
# CSRF Protection Test
# Try POST without CSRF token - should fail

# XSS Prevention Test
# Try injecting: <script>alert('xss')</script> in search
# Should be escaped or sanitized

# SQL Injection Test
# Try: ' OR '1'='1 in search
# Should return no results or error

# Rate Limiting Test
# Make 100 requests in 1 minute
# Should get 429 Too Many Requests after threshold
```

### Step 7: Performance Validation (10 min)

```bash
# Check page load time
time curl https://localhost:8000/

# Check database query count
# Add to settings.py:
# LOGGING = { ... }
# Check logs for N+1 queries

# Memory profiling
pip install memory_profiler
python -m memory_profiler run_tests.py

# Load testing (optional)
pip install locust
locust -f locustfile.py --host=https://localhost:8000
```

### Step 8: Email Validation (5 min)

```python
# In Django shell
python manage.py shell

# Test email sending
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    'Production Test Email',
    'This is a test email from VibeMall production testing.',
    settings.EMAIL_HOST_USER,
    [settings.EMAIL_HOST_USER],
    fail_silently=False,
)
# Check your email - should arrive within 30 seconds
```

### Step 9: Backup Validation (5 min)

```bash
# Trigger manual backup
python manage.py backup_create

# Verify backup created
ls -la backups/

# Test backup restore (on test database)
python manage.py backup_restore backup_file.zip

# Verify data restored
python manage.py shell
# Check data count matches original
```

### Step 10: Final Checklist

```bash
# Run full test suite one more time
python manage.py test
python run_production_tests.py

# Collect static files
python manage.py collectstatic --noinput

# Check for any uncommitted changes
git status

# Tag release
git tag -a v1.0.0 -m "Production release"
git push origin v1.0.0
```

---

## Test Results Report Template

```
VibeMall Production Readiness Test Report
=========================================
Date: 2024-03-XX
Time: XX:XX
Tester: [Name]
Environment: [Local/Staging]

Test Results:
=============

Environment Validation:     ✓ PASS
Code Quality Check:         ✓ PASS
Unit Tests:                 ✓ PASS (XX/XX)
Production Tests:           ✓ PASS (XX/XX)
Manual Feature Tests:       ✓ PASS (X/X)
Security Tests:             ✓ PASS
Performance Tests:          ✓ PASS
Email Validation:           ✓ PASS
Backup Validation:          ✓ PASS
Django Check --deploy:      ✓ PASS (0 errors, X warnings)

Overall Score: 100%

Issues Found:
=============
None

Recommendation:
===============
✓ READY FOR PRODUCTION DEPLOYMENT

Signed by: [Tester Name]
Date: [Date]
```

---

## When Tests Fail

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `ImportError: No module named 'razorpay'` | Run `pip install razorpay` |
| `DatabaseError: relation does not exist` | Run `python manage.py migrate` |
| `FAIL: Test email configuration` | Check `.env` EMAIL_HOST_PASSWORD |
| `FAIL: DEBUG=True in production` | Set `DEBUG=False` in `.env` |
| `TypeError: datetime not JSON serializable` | Use `DjangoJSONEncoder` (already fixed) |
| `Connection refused: Razorpay` | Check RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET |

### Debug Mode

```bash
# Enable verbose output
python manage.py test --verbosity=2

# Check specific test
python manage.py test Hub.tests.test_payments -v 2

# Drop into debugger
import pdb; pdb.set_trace()
```

---

## Regression Testing

After each deployment, run:

```bash
# Quick smoke test (2 min)
python manage.py test --failfast

# Full test suite (10 min)
python manage.py test
python run_production_tests.py

# Manual validation of critical features (15 min)
# Follow Steps 5.1-5.7 above
```

---

## Continuous Integration (Optional)

### GitHub Actions Setup

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
    - run: pip install -r requirements.txt
    - run: python manage.py test
    - run: python manage.py check --deploy
```

---

## Testing Metrics

### Before Production
- **Test Coverage:** > 80%
- **Passing Tests:** 100%
- **Security Issues:** 0 critical
- **Performance:** < 2s page load
- **Uptime:** 99.9%

### After Production
- **Error Rate:** < 0.1%
- **Avg Response Time:** < 500ms
- **Failed Backups:** 0
- **Security Incidents:** 0

---

## Testing Timeline

| Phase | Duration | Task |
|-------|----------|------|
| Environment Setup | 15 min | Verify environment |
| Code Quality | 10 min | Run checks |
| Unit Tests | 10 min | Run full test suite |
| Production Tests | 5 min | Run production suite |
| Manual Tests | 45 min | Test features |
| Security Tests | 15 min | Verify security |
| Performance | 15 min | Load testing |
| Final Validation | 5 min | Check all pass |
| **TOTAL** | **2 hours** | **Ready to deploy** |

---

**Status:** Testing procedures ready  
**Next Step:** Execute testing plan from top to bottom
