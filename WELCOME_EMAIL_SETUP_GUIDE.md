# Welcome Email with Terms & Conditions PDF - Setup Guide

## ✅ Features Implemented

1. **Terms & Conditions Checkbox** on Register Form
   - Required checkbox before registration
   - Red error message if not checked
   - JavaScript validation prevents form submission
   - Links to Terms & Conditions and Privacy Policy pages

2. **Welcome Email** sent after registration
   - Beautiful HTML email template (matches order email format)
   - Personalized with user's name and details
   - Links to shop and account features
   - Professional gradient design

3. **Terms & Conditions PDF Attachment**
   - Comprehensive T&C document (India law compliant)
   - Auto-generated PDF from HTML template
   - Attached to welcome email
   - Includes all legal sections required for e-commerce

## 📦 Installation Steps

### Step 1: Install WeasyPrint (PDF Generation Library)

WeasyPrint requires some system dependencies on Windows:

```bash
# Install WeasyPrint
pip install weasyprint

# If you get errors, you may need GTK3 runtime for Windows
# Download from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
# Install the GTK3 runtime, then try pip install again
```

**Alternative**: If WeasyPrint installation fails, the system will still work but won't attach PDF to emails. Users will just receive the welcome email without the PDF attachment.

### Step 2: Update Requirements

```bash
pip install -r requirements.txt
```

### Step 3: Configure Email Settings

Make sure your `.env` file has email configuration:

```env
# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com
```

**For Gmail**: You need to create an "App Password":
1. Go to Google Account Settings
2. Security → 2-Step Verification (enable it)
3. App Passwords → Generate new password
4. Use that password in EMAIL_HOST_PASSWORD

### Step 4: Test Registration

1. Start your server: `python manage.py runserver`
2. Go to: http://localhost:8000/register/
3. Fill the form and check the Terms & Conditions checkbox
4. Submit the form
5. Check your email inbox for:
   - Verification email (existing)
   - Welcome email with PDF attachment (new)

## 📁 Files Modified/Created

### Created Files:
- `Hub/templates/terms_and_conditions_pdf.html` - Terms & Conditions HTML for PDF
- `Hub/templates/emails/welcome_email.html` - Welcome email template
- `WELCOME_EMAIL_SETUP_GUIDE.md` - This guide

### Modified Files:
- `Hub/views.py` - Added terms validation and welcome email call in register_view
- `Hub/email_utils.py` - Added send_welcome_email_with_terms() function
- `Hub/templates/register.html` - Already has terms checkbox (no changes needed)
- `requirements.txt` - Added weasyprint dependency

## 🔍 How It Works

1. **User Registration Flow**:
   ```
   User fills form → Checks Terms checkbox → Submits
   ↓
   Backend validates terms_accepted field
   ↓
   Creates user account
   ↓
   Sends verification email (existing)
   ↓
   Sends welcome email with PDF (new)
   ↓
   User receives both emails
   ```

2. **PDF Generation**:
   - Uses WeasyPrint to convert HTML to PDF
   - Renders `terms_and_conditions_pdf.html` with context
   - Generates PDF in memory (BytesIO)
   - Attaches to email as `VibeMall_Terms_and_Conditions.pdf`

3. **Error Handling**:
   - If WeasyPrint not installed: Email sent without PDF (warning logged)
   - If PDF generation fails: Email sent without PDF (error logged)
   - If email fails: Registration still succeeds (error logged)

## 🎨 Email Template Features

The welcome email includes:
- Professional gradient header
- Personalized greeting
- Account details box
- "Start Shopping" CTA button
- Feature list (browse, wishlist, track orders, deals)
- PDF attachment notice
- Contact information
- Footer with copyright

## 📋 Terms & Conditions Content

The PDF includes all required sections for India:
- Acceptance of Terms
- Definitions
- Eligibility (18+ years)
- User Account
- Product Listings & Pricing
- Orders & Payments
- Shipping & Delivery
- Returns & Refunds
- Cancellation Policy
- Intellectual Property
- User Conduct
- Privacy Policy
- Limitation of Liability
- Indemnification
- Dispute Resolution
- Governing Law (Indian laws)
- Contact Information

## 🐛 Troubleshooting

### WeasyPrint Installation Issues on Windows:

**Error**: "OSError: cannot load library 'gobject-2.0-0'"
**Solution**: Install GTK3 runtime from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

**Error**: "No module named 'weasyprint'"
**Solution**: Run `pip install weasyprint` in your virtual environment

### Email Not Sending:

1. Check `.env` file has correct email settings
2. For Gmail, use App Password (not regular password)
3. Check console/logs for error messages
4. Verify EMAIL_HOST_USER is correct

### PDF Not Attached:

1. Check if WeasyPrint is installed: `pip list | grep weasyprint`
2. Check logs for PDF generation errors
3. Email will still send without PDF if generation fails

## ✅ Testing Checklist

- [ ] Terms checkbox appears on register form
- [ ] Form shows error if checkbox not checked
- [ ] Registration succeeds when checkbox is checked
- [ ] Verification email received
- [ ] Welcome email received
- [ ] PDF attached to welcome email
- [ ] PDF opens correctly and shows all terms
- [ ] Email format matches order confirmation email style

## 🔐 Security Notes

- Terms acceptance is validated on backend (not just frontend)
- PDF is generated fresh for each registration
- Email sending errors don't block registration
- User data is protected in email templates
- Terms comply with Indian e-commerce laws

## 📞 Support

If you face any issues:
1. Check the logs: `python manage.py runserver` console output
2. Check EmailLog model in admin panel for email status
3. Verify email settings in `.env` file
4. Test with a different email provider if Gmail fails

---

**Status**: ✅ Implementation Complete
**Next Steps**: Install WeasyPrint and test registration flow
