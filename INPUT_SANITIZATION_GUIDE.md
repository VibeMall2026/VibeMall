# Input Sanitization for XSS Prevention

## Overview

The VibeMall application now includes a comprehensive input sanitization system to prevent Cross-Site Scripting (XSS) attacks. This guide explains how to use the sanitizer throughout the application.

## Installation

The sanitizer requires the `bleach` library for HTML cleaning:

```bash
pip install bleach==6.1.0
```

Or install from requirements:

```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
from Hub.sanitizer import sanitize_html, sanitize_text, sanitize_url

# Remove dangerous HTML/script tags
user_input = '<p>Hello <script>alert("XSS")</script></p>'
safe_html = sanitize_html(user_input)
# Result: '<p>Hello &lt;script&gt;alert("XSS")&lt;/script&gt;</p>'

# Remove all HTML tags
content = '<p>Hello <b>World</b></p>'
plain_text = sanitize_text(content)
# Result: 'Hello World'

# Validate URLs
url = 'javascript:alert("XSS")'
safe_url = sanitize_url(url)
# Result: None (blocked)
```

## Sanitization Functions

### 1. `sanitize_html(content, allowed_tags=None, allowed_attributes=None)`

**Purpose:** Sanitize HTML content while allowing safe tags

**Default Allowed Tags:**
- `p, br, strong, b, em, i, u, a, ul, ol, li, blockquote, code, pre, h1-h6`

**Default Allowed Attributes:**
- `a`: href, title, target
- `img`: src, alt, title

**Example:**
```python
from Hub.sanitizer import sanitize_html

# Product description from user
description = '<p>Great <script>alert("xss")</script> product!</p>'
clean_desc = sanitize_html(description)

# For comments with more limited formatting
comment = '<p>Love this! <a href="/bad">Click here</a></p>'
clean_comment = sanitize_html(comment)
```

### 2. `sanitize_text(content)`

**Purpose:** Remove all HTML tags, keep only plain text

**Example:**
```python
from Hub.sanitizer import sanitize_text

# Review text from user
review = 'Great product<script>vulnerable</script>!'
clean_review = sanitize_text(review)
# Result: 'Great product vulnerable!'
```

### 3. `sanitize_url(url, allowed_schemes=None)`

**Purpose:** Validate URLs and prevent javascript: and data: URIs

**Default Allowed Schemes:** http, https, mailto

**Blocked Patterns:**
- `javascript:`
- `data:`
- `vbscript:`
- Event handlers (onclick=, etc.)

**Example:**
```python
from Hub.sanitizer import sanitize_url

# Affiliate link from user
url1 = 'https://example.com/ref=123'
clean_url1 = sanitize_url(url1)  # Returns URL

# Malicious link
url2 = 'javascript:stealCookies()'
clean_url2 = sanitize_url(url2)  # Returns None (blocked)
```

### 4. `sanitize_filename(filename, max_length=200)`

**Purpose:** Sanitize filenames to prevent directory traversal

**Blocks:**
- Directory traversal: `../../../etc/passwd`
- Path separators: `/` and `\`
- Null bytes: `\x00`
- Special characters

**Example:**
```python
from Hub.sanitizer import sanitize_filename

# User upload filename
original = '../../../etc/passwd.jpg'
safe_name = sanitize_filename(original)
# Result: 'etc_passwd.jpg'
```

### 5. `sanitize_email(email)`

**Purpose:** Validate and normalize email addresses

**Example:**
```python
from Hub.sanitizer import sanitize_email

email1 = '  User@Example.COM  '
clean_email1 = sanitize_email(email1)  # Result: 'user@example.com'

email2 = 'invalid@domain'
clean_email2 = sanitize_email(email2)  # Result: None (invalid)
```

### 6. `sanitize_phone(phone)`

**Purpose:** Sanitize phone numbers

**Example:**
```python
from Hub.sanitizer import sanitize_phone

phone = '+1 (555) 123-4567'
clean_phone = sanitize_phone(phone)
# Result: '+15551234567'
```

## Integration with Django Forms

### Method 1: Override form `clean()` method

```python
from django import forms
from Hub.sanitizer import sanitize_text, sanitize_html

class ProductReviewForm(forms.Form):
    title = forms.CharField(max_length=200)
    content = forms.CharField(widget=forms.Textarea)
    rating = forms.IntegerField(min_value=1, max_value=5)
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        return sanitize_text(title)  # Remove HTML, keep text only
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        return sanitize_html(content)  # Allow safe HTML tags
```

### Method 2: Use custom field

```python
from django import forms
from Hub.sanitizer import sanitize_text

class CleanCharField(forms.CharField):
    """CharField that automatically sanitizes input"""
    def to_python(self, value):
        value = super().to_python(value)
        return sanitize_text(value)

class ProductReviewForm(forms.Form):
    title = CleanCharField(max_length=200)
    content = forms.CharField(widget=forms.Textarea)
```

## Integration with Django Models

### Method 1: Save method override

```python
from django.db import models
from Hub.sanitizer import sanitize_text, sanitize_html

class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    
    def save(self, *args, **kwargs):
        # Sanitize user input before saving
        self.title = sanitize_text(self.title)
        self.content = sanitize_html(self.content)
        super().save(*args, **kwargs)
```

### Method 2: Form validation

```python
from django.contrib.admin import ModelAdmin, register
from django import forms
from Hub.sanitizer import sanitize_text

class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['title', 'content', 'rating']
    
    def clean_title(self):
        return sanitize_text(self.cleaned_data['title'])
    
    def clean_content(self):
        return sanitize_html(self.cleaned_data['content'])

@register(ProductReview)
class ProductReviewAdmin(ModelAdmin):
    form = ProductReviewForm
```

## Real-World Examples

### 1. Product Description

```python
# In views.py
from Hub.sanitizer import sanitize_html

def update_product_description(request, product_id):
    product = Product.objects.get(id=product_id)
    
    if request.method == 'POST':
        description = request.POST.get('description', '')
        # Sanitize before saving
        product.description = sanitize_html(description)
        product.save()
        
    return render(request, 'edit_product.html', {'product': product})
```

### 2. User Comments

```python
# In models.py
class Comment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    
    def save(self, *args, **kwargs):
        # Remove all HTML from comments
        self.text = sanitize_text(self.text)
        super().save(*args, **kwargs)
```

### 3. Affiliate Links

```python
# In models.py
from Hub.sanitizer import sanitize_url

class AffiliateLink(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    url = models.URLField()
    
    def clean(self):
        # Validate URL during form validation
        safe_url = sanitize_url(self.url)
        if safe_url is None:
            raise ValidationError('Invalid or dangerous URL')
        self.url = safe_url
```

### 4. File Uploads

```python
# In views.py
from Hub.sanitizer import sanitize_filename
import os

def upload_product_image(request, product_id):
    if 'image' in request.FILES:
        uploaded_file = request.FILES['image']
        
        # Sanitize filename
        safe_name = sanitize_filename(uploaded_file.name)
        upload_path = os.path.join('products', str(product_id), safe_name)
        
        # Save file
        with open(upload_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
```

## Template Display

### Safe HTML Rendering

```django
{# Template #}

{# For HTML content that was sanitized in view #}
<div class="product-description">
    {{ product.description|safe }}
</div>

{# For user input that might contain HTML #}
{# First sanitize in view, then use |safe #}
<div class="review">
    {{ review.content|safe }}
</div>
```

### Escaping HTML

```django
{# This automatically escapes HTML - safe #}
<p>{{ user_comment }}</p>

{# Only use |safe for already-sanitized content #}
<p>{{ pre_sanitized_content|safe }}</p>
```

## Security Best Practices

### 1. Always Sanitize User Input

```python
# ✅ Good
user_input = sanitize_text(request.POST.get('comment'))

# ❌ Bad - don't trust user input
user_input = request.POST.get('comment')  # Could have XSS
```

### 2. Choose Right Sanitization Method

```python
# ✅ For comments/reviews - plain text only
review = sanitize_text(user_review)

# ✅ For descriptions - allow formatting
description = sanitize_html(user_description)

# ✅ For URLs - validate scheme
url = sanitize_url(user_url)
```

### 3. Sanitize Early, Use Safe Late

```python
# Save sanitized version
self.content = sanitize_html(raw_user_input)
self.save()

# Template can safely use it
{{ object.content|safe }}
```

### 4. Default Deny for URLs

```python
# ✅ Only allow known safe URLs
safe_url = sanitize_url(user_url)
if safe_url is None:
    return "Invalid URL"

# ❌ Don't pre-pend domain to user URLs
url = f"https://example.com/{user_input}"  # Unsafe
```

## Testing Sanitization

### Unit Tests

```python
from django.test import TestCase
from Hub.sanitizer import sanitize_html, sanitize_text, sanitize_url

class SanitizationTests(TestCase):
    def test_sanitize_html_removes_scripts(self):
        content = '<p>Safe <script>alert("xss")</script></p>'
        result = sanitize_html(content)
        self.assertNotIn('script', result)
    
    def test_sanitize_text_removes_all_html(self):
        content = '<p><b>Bold</b></p>'
        result = sanitize_text(content)
        self.assertEqual(result, 'Bold')
    
    def test_sanitize_url_blocks_javascript(self):
        url = 'javascript:alert("xss")'
        result = sanitize_url(url)
        self.assertIsNone(result)
```

### Manual Testing

```bash
python manage.py shell

from Hub.sanitizer import *

# Test HTML sanitization
test_html = '<p>Safe <script>alert("xss")</script></p>'
print(sanitize_html(test_html))

# Test URL sanitization
print(sanitize_url('javascript:alert("xss")'))  # Should be None
print(sanitize_url('https://example.com'))  # Should return URL
```

## Troubleshooting

### Bleach Not Installing

```bash
# Install with pip
pip install bleach==6.1.0

# Or update requirements
pip install -r requirements.txt
```

### HTML Tags Being Stripped

Check if you're using the right function:

```python
# ✅ Returns <p>content</p>
sanitize_html('<p>content</p>')

# ❌ Returns just content (strips all tags)
sanitize_text('<p>content</p>')
```

### Allowed Tags Missing

Extend ALLOWED_TAGS in sanitizer.py:

```python
# In Hub/sanitizer.py
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'a', 'ul', 'ol',
    'li', 'blockquote', 'code', 'pre', 'h1', 'h2', 'h3', 'div',  # Added div
]
```

## Reference

- **Sanitizer Code:** [Hub/sanitizer.py](Hub/sanitizer.py)
- **Bleach Documentation:** https://bleach.readthedocs.io/
- **OWASP XSS Prevention:** https://owasp.org/www-community/attacks/xss/
- **Django Security:** https://docs.djangoproject.com/en/5.2/topics/security/
