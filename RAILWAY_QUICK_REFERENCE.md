# 🚂 Railway Deployment - Quick Reference Card

## ⚡ 5-Minute Deployment Checklist

### Before You Start
- [ ] Code pushed to GitHub
- [ ] All tests passing locally
- [ ] SECRET_KEY ready (generate new one)
- [ ] Gmail App Password ready
- [ ] Razorpay TEST keys ready

---

## 🎯 Deployment Steps

### 1️⃣ Railway Account (1 min)
```
1. Visit: https://railway.app
2. Sign up with GitHub
3. Authorize Railway
```

### 2️⃣ Create Project (1 min)
```
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose: VibeMall2026/VibeMall
4. Click "Deploy Now"
```

### 3️⃣ Add Database (30 sec)
```
1. Click "+ New"
2. Select "Database"
3. Choose "Add PostgreSQL"
4. Done! (DATABASE_URL auto-set)
```

### 4️⃣ Set Environment Variables (2 min)
```
Click Variables tab → Add:

DEBUG=False
SECRET_KEY=(generate new one)
ALLOWED_HOSTS=*.railway.app
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=your_secret
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
```

### 5️⃣ Get Your URL (30 sec)
```
1. Settings tab
2. Click "Generate Domain"
3. Copy URL: https://xxx.railway.app
```

### 6️⃣ Create Admin User (1 min)
```bash
# Install Railway CLI:
npm i -g @railway/cli

# Login & link:
railway login
railway link

# Create superuser:
railway run python manage.py createsuperuser
```

---

## 🧪 Test Your Deployment

### Basic Tests
- [ ] Homepage loads: `https://your-url.railway.app`
- [ ] Admin works: `https://your-url.railway.app/admin/`
- [ ] Login works
- [ ] Images load
- [ ] No 500 errors

### Feature Tests
- [ ] Register new user
- [ ] Browse products
- [ ] Add to cart
- [ ] Test payment (Razorpay test card)
- [ ] Check email delivery

---

## 📊 Monitor Your App

### View Logs
```
Railway Dashboard → Your Service → Deployments → Logs
```

### Check Errors
```bash
# Filter errors in logs
Look for: [ERROR] or [CRITICAL]
```

### Database Status
```
Railway Dashboard → PostgreSQL → Metrics
```

---

## 🔧 Common Commands

### Deploy Latest Code
```bash
git push origin main
# Railway auto-deploys (2-3 min)
```

### Run Django Commands
```bash
railway run python manage.py <command>
```

### View Logs
```bash
railway logs
```

### Database Shell
```bash
railway run python manage.py dbshell
```

### Django Shell
```bash
railway run python manage.py shell
```

---

## 🆘 Quick Troubleshooting

### Issue: 500 Error
**Check:** Railway logs for Python errors
**Fix:** Fix code, push to GitHub

### Issue: Static files missing
**Check:** WhiteNoise in MIDDLEWARE (settings.py)
**Fix:** Already added in latest update

### Issue: Database error
**Check:** DATABASE_URL auto-set by Railway
**Fix:** Don't manually set DATABASE_URL

### Issue: Email not sending
**Check:** Gmail App Password correct
**Fix:** Generate new App Password

---

## 💰 Cost Estimate

| Traffic | Monthly Cost |
|---------|--------------|
| Testing (low) | $0-5 (free tier) |
| Small (< 1K users) | $5-10 |
| Medium (< 10K users) | $10-20 |
| Large (> 10K users) | $20-50+ |

**Free tier:** $5 credits/month (great for testing!)

---

## 🔗 Important Links

- **Railway Dashboard:** https://railway.app/dashboard
- **Documentation:** https://docs.railway.app
- **Full Guide:** See RAILWAY_DEPLOYMENT_GUIDE.md
- **Support:** https://discord.gg/railway

---

## ✅ Success Checklist

- [ ] Project deployed on Railway
- [ ] PostgreSQL database added
- [ ] Environment variables set
- [ ] Domain generated
- [ ] Admin user created
- [ ] Homepage loads (no errors)
- [ ] Admin panel accessible
- [ ] Test features working
- [ ] Logs show no critical errors
- [ ] Team notified of URL

---

## 🎉 You're Live!

**Your VibeMall is now accessible at:**
```
https://your-app-name.up.railway.app
```

**Share with your team and start testing! 🚀**

---

## 📖 Need More Details?

See complete guide: **RAILWAY_DEPLOYMENT_GUIDE.md**

---

**Quick Reference Version 1.0**
**Updated: March 2, 2026**
