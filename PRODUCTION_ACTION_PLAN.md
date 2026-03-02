# 📋 Production Preparation Action Items

## Quick Decision: Where Are You?

### ❓ Choose Your Starting Point

- **[A] Not yet started anything** → See Section 1 (Get Started Today)
- **[B] Already read the docs** → See Section 2 (Run Tests)
- **[C] Tests are passing** → See Section 3 (Deploy)
- **[D] Already in production** → See Section 4 (Monitor)

---

## Section 1: Get Started Today (First Time)

### ✅ Checklist for First-Time Setup

- [ ] **Step 1:** Make a copy of `.env.example` → `.env`
  ```bash
  cd d:\Iu University\OneDrive - IU International University of Applied Sciences\Desktop\VibeMall
  copy .env.example .env
  ```

- [ ] **Step 2:** Update `.env` with your settings
  - `DEBUG=False` (for production testing)
  - `SECRET_KEY=your-secret-key-here` (generate new one)
  - `ALLOWED_HOSTS=localhost,127.0.0.1` (add your domain later)
  - `DATABASE_URL=` (keep SQLite for local testing)

- [ ] **Step 3:** Start Django with correct startup script
  ```bash
  START_DJANGO.bat
  ```
  (This activates venv before starting)

- [ ] **Step 4:** Run migrations fresh
  ```bash
  python manage.py migrate --reset
  ```

- [ ] **Step 5:** Create test admin user
  ```bash
  python manage.py createsuperuser
  username: admin
  password: TestPassword123!
  ```

- [ ] **Step 6:** Read all 5 documentation files (in order)
  1. PRODUCTION_READINESS_CHECKLIST.md (60 min)
  2. TESTING_AND_VALIDATION_GUIDE.md (30 min)
  3. SECURITY_AUDIT_CHECKLIST.md (20 min)
  4. PRODUCTION_DEPLOYMENT_GUIDE.md (20 min)
  5. PRODUCTION_PREPARATION_PACKAGE.md (10 min)

**✓ Estimated Time: 2.5 hours**

**Next: Move to Section 2**

---

## Section 2: Run Tests (Ready to Validate)

### ✅ Automated Testing

**Run this command:**
```bash
python run_production_tests.py
```

**Expected output (all GREEN):**
```
✓ DEBUG mode is False
✓ ALLOWED_HOSTS configured
✓ SECRET_KEY set
✓ Database connected
✓ Email configured
✓ SSL enabled
✓ Razorpay SDK available
✓ JSON serialization working
✓ CSRF protection enabled
✓ Security middleware present
...
═══════════════════════════
PRODUCTION READINESS: PASS
═══════════════════════════
```

**If any RED (FAIL):** Refer to the test output and fix issues

**Time:** 5 minutes

### ✅ Manual Feature Testing

**Follow this order (1 hour total):**

1. **User Registration (10 min)**
   - [ ] Create new account
   - [ ] Verify email sent
   - [ ] Login with new account
   - [ ] View profile

2. **Product Browsing (10 min)**
   - [ ] View all products
   - [ ] Search for products
   - [ ] Apply filters (category, price)
   - [ ] View product details

3. **Shopping Cart (10 min)**
   - [ ] Add items to cart
   - [ ] Modify quantities
   - [ ] Remove items
   - [ ] View cart total

4. **Checkout & Payment (15 min)**
   - [ ] Proceed to checkout
   - [ ] Apply coupon (if available)
   - [ ] Initiate Razorpay payment
   - [ ] Complete test payment
   - [ ] Verify order created

5. **Refund Processing (10 min)**
   - [ ] Go to My Orders
   - [ ] Initiate refund request
   - [ ] Admin: Review refund
   - [ ] Admin: Approve/Reject
   - [ ] Verify refund status updates

6. **Admin Panel (10 min)**
   - [ ] Login as admin
   - [ ] View dashboard
   - [ ] View all orders
   - [ ] View all users
   - [ ] Check reports

### ✅ Security Validation (20 min)

**Quick security checks:**
- [ ] Can't submit HTML in forms (XSS protected)
- [ ] CSRF token present in all forms
- [ ] Admin requires login
- [ ] Non-admin can't access /admin/
- [ ] Rate limiting works (if implemented)
- [ ] SQL injection not possible
- [ ] Password properly hashed

### ✅ Performance Validation (10 min)

**Use browser DevTools:**
- [ ] Homepage loads in < 2 seconds
- [ ] Product page loads in < 2 seconds
- [ ] No console errors
- [ ] No 404 errors
- [ ] Images loading correctly
- [ ] Mobile responsive (test on phone or zoom 75%)

**Total Testing Time: 1.5 hours**

**Next Steps:**
- ✅ All tests PASS → Move to Section 3 (Deploy)
- ❌ Tests FAIL → Fix issues, then retry

---

## Section 3: Deploy to Production (Ready to Go Live)

### Prerequisites

Before deployment, ensure:
- [ ] All tests passing (Section 2)
- [ ] .env production config ready
- [ ] Database backups setup
- [ ] Email configured (contact us form works)
- [ ] Razorpay keys configured
- [ ] HTTPS certificate ready (or use Render's automatic)

### Deployment Steps

**Choose your hosting provider:**

#### Option A: Render.com (⭐ RECOMMENDED - Easiest)

1. **Create account:** https://render.com (free to signup)

2. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Production deployment"
   git push origin main
   ```

3. **Create PostgreSQL database on Render**
   - [ ] Click "New" → "PostgreSQL"
   - [ ] Accept defaults
   - [ ] Note connection string

4. **Create Web Service on Render**
   - [ ] Click "New" → "Web Service"
   - [ ] Connect GitHub repo (authorize Render)
   - [ ] Build command: `pip install -r requirements.txt`
   - [ ] Start command: `python manage.py runserver 0.0.0.0:$PORT`
   - [ ] Add environment variables (copy from .env)
   - [ ] Update DATABASE_URL to PostgreSQL connection
   - [ ] Click "Create Web Service"

5. **Wait for deployment** (3-5 min)
   - Render will build and deploy automatically
   - You'll get a .onrender.com URL

6. **Run migrations** (one time only)
   ```bash
   # In Render dashboard, click "Shell" and run:
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. **Configure domain** (optional but recommended)
   - [ ] Buy domain (GoDaddy, Namecheap, etc.)
   - [ ] Point to Render (see PRODUCTION_DEPLOYMENT_GUIDE.md)
   - [ ] Render auto-configures HTTPS

**Estimated Time: 1 hour** (including waiting for deployment)

#### Option B: PythonAnywhere (Alternative)

Follow: PYTHONANYWHERE_DEPLOYMENT_STEPS.md

#### Option C: AWS/DigitalOcean (Advanced)

Follow: PRODUCTION_DEPLOYMENT_GUIDE.md (Step 3+)

### Post-Deployment Validation

Once deployed:

1. **Access your site**
   - [ ] Open your Render URL in browser
   - [ ] Should see homepage
   - [ ] No 500 errors

2. **Test critical features**
   - [ ] User can register
   - [ ] Products display
   - [ ] Payment works (use Razorpay test keys)
   - [ ] Admin dashboard accessible (create test account)

3. **Check logs** (In Render dashboard)
   - [ ] Click "Logs"
   - [ ] Should see: "Starting development server"
   - [ ] No error messages

4. **Enable monitoring** (Optional but recommended)
   - [ ] Setup error tracking (Sentry.io)
   - [ ] Enable Render monitoring (free)

**✓ Deployment Complete!**

---

## Section 4: Post-Deployment (You're Live!)

### 🔴 First 24 Hours - CRITICAL Monitoring

**Set a timer for 24 hours. During this time:**

- [ ] Monitor error logs hourly
  - Render dashboard → Logs
  - Check for any ERROR or CRITICAL messages
  
- [ ] Test all features at least once
  - Register new user
  - Browse products
  - Make test order
  - Process refund request

- [ ] Check performance metrics
  - Page load times < 2 seconds
  - No timeouts
  - Emails sending correctly

- [ ] Verify backups running
  - Database auto-backups should be scheduled
  - Check at least one backup exists

**If issues found:** 
- Check error message (in logs)
- Fix code
- Deploy fix: `git push origin main` (auto-redeploys on Render)
- Test again

### ✅ Week 1 - Stabilization

- [ ] Monitor once per day
- [ ] Note any recurring issues
- [ ] Optimize slow endpoints if needed
- [ ] Train team on admin features
- [ ] Document any workarounds

### 🟢 Week 2+ - Production Ready

- [ ] Monitor weekly
- [ ] Setup automated health checks
- [ ] Plan database backups schedule
- [ ] Update documentation for your team
- [ ] Scale resources if needed (if getting traffic)

---

## Troubleshooting Quick Reference

### Problem: "500 Internal Server Error"
**Solution:**
1. Check logs: `Render Dashboard → Logs`
2. Look for Python error message
3. Fix code locally
4. Push to GitHub
5. Render auto-redeploys (wait 2-5 min)

### Problem: "Database connection error"
**Solution:**
1. Verify DATABASE_URL in Render environment
2. Check PostgreSQL service is running
3. Try: `python manage.py dbshell`
4. If no connection: restart PostgreSQL

### Problem: "Static files not loading (CSS/JS missing)"
**Solution:**
1. Run: `python manage.py collectstatic --noinput`
2. Check static/ folder exists
3. Update STATIC_URL and STATIC_ROOT in settings

### Problem: "Email not sending"
**Solution:**
1. Verify SMTP settings in .env
2. Check email not in spam folder
3. Try: `python manage.py shell`
   ```python
   from django.core.mail import send_mail
   send_mail('Test', 'Testing...', 'from@example.com', ['to@example.com'])
   ```

### Problem: "Razorpay failing 'SDK not found'"
**Solution:**
1. Run: `pip install razorpay`
2. Restart Django: Push to GitHub again
3. Verify RAZORPAY_KEY_ID in .env

---

## Success Metrics

Track these to ensure production is healthy:

| Metric | Target | Check How |
|--------|--------|-----------|
| Uptime | > 99% | Render dashboard |
| Page Load | < 2 sec | Browser DevTools |
| Error Rate | < 0.1% | Application logs |
| Database | Connected | Check logs |
| Email | Sending | Send test email |
| Backups | Daily | Database dashboard |

---

## Team Communication

### Tell your team:

1. **Go-Live Announcement**
   - Website is now live at: `https://yourdomain.com`
   - Use Razorpay test cards (during testing)
   - Report any issues immediately

2. **Access Information**
   - Admin dashboard: `https://yourdomain.com/admin/`
   - Username: `admin`
   - Password: (send separately via encrypted channel)

3. **Support Process**
   - Issues email: (create email like support@yourdomain.com)
   - Response time: Target 1 hour (adjust as needed)
   - Escalation: Contact DevOps/Admin

---

## Final Checklist

### Before You're "Done"

- [ ] All tests passing
- [ ] Deployed to production
- [ ] 24 hours monitoring complete
- [ ] Team trained
- [ ] Monitoring/alerts configured
- [ ] Backups verified
- [ ] Documentation updated
- [ ] Support process established

**✅ You're Production Ready!**

---

## Document Control

```
Version: 1.0
Created: March 2, 2026
Status: READY TO USE
Last Updated: March 2, 2026
```

Next file: PRODUCTION_READINESS_CHECKLIST.md

---

## 🎯 Right Now - Take Action!

```
Where you are now: Reading this file
What to do next:
  ↓
Read PRODUCTION_PREPARATION_PACKAGE.md (overview)
  ↓
Choose your section above (A, B, C, or D)
  ↓
Follow the steps
  ↓
Run tests
  ↓
Deploy
  ↓
Monitor
  ↓
✅ LIVE IN PRODUCTION!
```

**Estimated total time: 5-7 hours of focused work**

**Questions? Check:** PRODUCTION_DEPLOYMENT_GUIDE.md or TESTING_AND_VALIDATION_GUIDE.md

---

**Let's go live! 🚀**
