# PythonAnywhere Deployment - Visual Step-by-Step Guide

## તારીખ: February 24, 2026
## Status: Complete Visual Guide

---

## 🎯 Goal: VibeMall Website Live કરવી

---

# Part 1: Clean Start (Current Setup Delete કરો)

## Step 1: Web Tab Open કરો

```
1. PythonAnywhere Dashboard પર જાઓ
2. ઉપર "Web" tab click કરો
3. તમને આવું page દેખાશે:
   - vibemall.pythonanywhere.com
   - Configuration section
   - Code section
   - Static files section
```

## Step 2: Current Web App Delete કરો

```
1. Web page પર નીચે scroll કરો
2. "Delete web app" button શોધો (red color)
3. Click કરો
4. Confirmation popup આવશે
5. "Yes, delete it" click કરો
```

**Result:** Web app deleted થઈ જશે.

---

# Part 2: Fresh Django Web App બનાવો

## Step 3: New Web App Create કરો

```
1. Web tab પર "Add a new web app" button click કરો (green)
2. Domain confirmation page આવશે
   - Domain: vibemall.pythonanywhere.com
   - Click "Next"
```

## Step 4: Framework Select કરો

```
આ screen પર તમને options દેખાશે:
- Manual configuration
- Flask
- Django ← આ select કરો!
- web2py
- Bottle

"Django" પર click કરો
```

## Step 5: Python Version Select કરો

```
Python version select કરો:
- Python 3.10 ← આ select કરો!
- Python 3.9
- Python 3.8

"Python 3.10" click કરો
```

## Step 6: Project Path Enter કરો

```
Project path box માં type કરો:
VibeMall

(બસ એટલું જ, કંઈ વધારે નહીં)

"Next" click કરો
```

**Result:** Django project automatically setup થઈ જશે!

---

# Part 3: તમારા Files Upload કરો

## Step 7: Files Tab Open કરો

```
1. ઉપર "Files" tab click કરો
2. Path આવો હશે: /home/VibeMall/
3. "VibeMall" folder click કરો
```

## Step 8: Auto-Created Files Delete કરો

```
આ files delete કરો (એક-એક કરીને):
1. manage.py (trash icon click કરો)
2. VibeMall/ folder (trash icon click કરો)

Confirm deletion
```

## Step 9: તમારા Local Files Upload કરો

### Option A: Zip File Upload (Easiest)

```
તમારા computer પર:
1. VibeMall folder ને right-click કરો
2. "Send to" → "Compressed (zipped) folder"
3. VibeMall.zip file બનશે

PythonAnywhere Files tab પર:
1. "Upload a file" button click કરો
2. VibeMall.zip select કરો
3. Upload થશે

પછી:
1. "Open Bash console here" click કરો
2. Type: unzip VibeMall.zip
3. Enter press કરો
```

### Option B: Git Clone (If you have GitHub)

```
1. "Open Bash console here" click કરો
2. Type: git clone https://github.com/VibeMall2026/VibeMall.git
3. Enter press કરો
4. Type: mv VibeMall/* .
5. Enter press કરો
```

---

# Part 4: Virtual Environment Setup

## Step 10: Bash Console Open કરો

```
Files tab પર:
1. Path: /home/VibeMall/VibeMall/
2. "Open Bash console here" button click કરો (green)
3. નવો console window open થશે
```

## Step 11: Virtual Environment બનાવો

```
Console માં આ command copy-paste કરો:

mkvirtualenv --python=/usr/bin/python3.10 vibemall-env

Enter press કરો
Wait 1-2 minutes
```

**Result:** Virtual environment બની જશે અને activate થઈ જશે.
તમને આવું દેખાશે: `(vibemall-env) ~/VibeMall $`

## Step 12: Dependencies Install કરો

```
Console માં આ command copy-paste કરો:

pip install django pillow weasyprint python-decouple

Enter press કરો
Wait 2-3 minutes
```

**Result:** બધા packages install થઈ જશે.

---

# Part 5: Database Setup

## Step 13: Database Migrate કરો

```
Console માં આ command:

python manage.py migrate

Enter press કરો
```

**Result:** Database tables બની જશે.

## Step 14: Superuser બનાવો

```
Console માં આ command:

python manage.py createsuperuser

Enter press કરો

પછી enter કરો:
Username: admin
Email: info.vibemall@gmail.com
Password: (તમારો password - type કરતા દેખાશે નહીં)
Password (again): (same password)
```

**Result:** Admin user બની જશે.

## Step 15: Static Files Collect કરો

```
Console માં આ command:

python manage.py collectstatic --noinput

Enter press કરો
```

**Result:** Static files collect થઈ જશે.

## Step 16: Auto Coupons Create કરો

```
Console માં આ command:

python manage.py create_auto_coupons

Enter press કરો
```

**Result:** FIRST5 coupon બની જશે.

---

# Part 6: Web App Configuration

## Step 17: Web Tab પર પાછા જાઓ

```
1. Browser માં PythonAnywhere tab
2. "Web" click કરો
3. vibemall.pythonanywhere.com page open થશે
```

## Step 18: Virtual Environment Path Set કરો

```
Web page પર scroll down કરો:

"Virtualenv" section શોધો:
1. Path box માં type કરો:
   /home/VibeMall/.virtualenvs/vibemall-env
2. Checkmark icon click કરો
```

**Result:** Virtual environment linked થઈ જશે.

## Step 19: Static Files Path Set કરો

```
"Static files" section માં:

URL: /static/
Directory: /home/VibeMall/VibeMall/Hub/static

Add કરો (checkmark click કરો)

પછી add કરો:
URL: /media/
Directory: /home/VibeMall/VibeMall/media

Add કરો
```

## Step 20: WSGI File Check કરો

```
"Code" section માં:
1. "WSGI configuration file" link click કરો
2. File open થશે

Check કરો કે આ lines છે:

path = '/home/VibeMall/VibeMall'
os.environ['DJANGO_SETTINGS_MODULE'] = 'VibeMall.settings'

જો ખોટું છે તો correct કરો અને Save કરો
```

---

# Part 7: Settings.py Update કરો

## Step 21: settings.py Edit કરો

```
Files tab → /home/VibeMall/VibeMall/VibeMall/settings.py

આ changes કરો:

1. DEBUG = True → DEBUG = False

2. ALLOWED_HOSTS = [] → 
   ALLOWED_HOSTS = ['vibemall.pythonanywhere.com', 'localhost']

3. File ના end માં add કરો:

STATIC_URL = '/static/'
STATIC_ROOT = '/home/VibeMall/VibeMall/staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = '/home/VibeMall/VibeMall/media'

Save કરો
```

---

# Part 8: Reload અને Test

## Step 22: Web App Reload કરો

```
Web tab પર:
1. ઉપર green "Reload" button click કરો
2. Wait 10-20 seconds
3. "Reload successful" message આવશે
```

## Step 23: Website Test કરો

```
Browser માં નવો tab open કરો:

https://vibemall.pythonanywhere.com

Website load થવી જોઈએ!
```

---

# Troubleshooting Guide

## Issue 1: "Something went wrong" Error

**Solution:**
```
1. Web tab → "Error log" click કરો
2. Last 20 lines copy કરો
3. Check કરો:
   - ModuleNotFoundError? → WSGI file path ખોટો છે
   - Database error? → python manage.py migrate run કરો
   - Static files error? → Static files path check કરો
```

## Issue 2: Static Files Not Loading

**Solution:**
```
1. Bash console open કરો
2. cd /home/VibeMall/VibeMall
3. python manage.py collectstatic --noinput
4. Web tab → Reload
```

## Issue 3: Admin Panel Not Working

**Solution:**
```
1. Bash console
2. python manage.py createsuperuser
3. Create new admin user
4. Try login again
```

## Issue 4: Database Error

**Solution:**
```
1. Bash console
2. python manage.py migrate
3. python manage.py makemigrations
4. python manage.py migrate
5. Web tab → Reload
```

---

# Quick Commands Reference

## Bash Console Commands:

```bash
# Go to project directory
cd /home/VibeMall/VibeMall

# Activate virtual environment
workon vibemall-env

# Install packages
pip install package-name

# Database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Check for errors
python manage.py check

# Run management command
python manage.py command-name
```

## After Code Changes:

```bash
# Pull latest code (if using Git)
cd /home/VibeMall/VibeMall
git pull origin main

# Collect static files
python manage.py collectstatic --noinput

# Reload web app (Web tab → Reload button)
```

---

# Important Paths Reference

```
Project Root: /home/VibeMall/VibeMall/
Settings: /home/VibeMall/VibeMall/VibeMall/settings.py
Static Files: /home/VibeMall/VibeMall/Hub/static/
Media Files: /home/VibeMall/VibeMall/media/
Database: /home/VibeMall/VibeMall/db.sqlite3
Virtual Env: /home/VibeMall/.virtualenvs/vibemall-env/
WSGI File: /var/www/vibemall_pythonanywhere_com_wsgi.py
```

---

# Success Checklist

After deployment, verify:

- [ ] Website loads: https://vibemall.pythonanywhere.com
- [ ] Homepage displays correctly
- [ ] Images show properly
- [ ] Static files (CSS/JS) loading
- [ ] Admin panel works: /admin/
- [ ] Can login to admin
- [ ] Products display
- [ ] Cart works
- [ ] Checkout works
- [ ] No errors in error log

---

# Common Mistakes to Avoid

1. ❌ Using Python console instead of Bash console
2. ❌ Wrong virtual environment path
3. ❌ Forgetting to reload web app after changes
4. ❌ Wrong static files path
5. ❌ DEBUG = True in production
6. ❌ Empty ALLOWED_HOSTS
7. ❌ Not running collectstatic
8. ❌ Not running migrations

---

# Next Steps After Successful Deployment

1. Test all features thoroughly
2. Create test orders
3. Verify email delivery
4. Check invoice PDF generation
5. Test coupon system
6. Test on mobile devices
7. Get feedback from friends/family
8. Fix any bugs found
9. Consider upgrading to paid plan
10. Purchase custom domain

---

# Support Resources

## PythonAnywhere Help:
- Forum: https://www.pythonanywhere.com/forums/
- Help: https://help.pythonanywhere.com/
- Email: support@pythonanywhere.com

## Django Help:
- Documentation: https://docs.djangoproject.com/
- Forum: https://forum.djangoproject.com/

## VibeMall Documentation:
- Check .md files in project root
- PYTHONANYWHERE_DEPLOYMENT_STEPS.md
- PRODUCTION_DEPLOYMENT_CHECKLIST.md

---

# Estimated Time

- Part 1-2: 5 minutes (Delete & Create)
- Part 3: 10 minutes (Upload files)
- Part 4-5: 15 minutes (Setup & Database)
- Part 6-7: 10 minutes (Configuration)
- Part 8: 5 minutes (Test)

**Total: 45 minutes**

---

# Final Notes

- આ guide step-by-step follow કરો
- દરેક step પછી verify કરો કે સાચું થયું
- Error આવે તો Troubleshooting section જુઓ
- Bash console અને Python console માં ફરક સમજો
- Reload button ભૂલશો નહીં!

---

**Good Luck! 🚀**

તમારું VibeMall website live થઈ જશે!

**Status:** Ready to Deploy  
**Platform:** PythonAnywhere  
**Date:** February 24, 2026
