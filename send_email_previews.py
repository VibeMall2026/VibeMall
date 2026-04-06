"""
Send all VibeMall email templates as previews to a test address.
Usage: python send_email_previews.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

TO_EMAIL = 'rajpaladiya2023@gmail.com'
FROM_EMAIL = 'info@vibemall.in'

# Shared dummy context
now = timezone.now()

templates = [
    (
        'Welcome Email',
        'emails/welcome_email.html',
        {
            'user_name': 'Raj',
            'username': 'raj_test',
            'email': TO_EMAIL,
            'registration_date': now.strftime('%d %b %Y'),
            'hero_image_url': 'https://images.unsplash.com/photo-1528459105426-b954836706fc?w=600',
            'shop_url': 'https://vibemall.in',
            'verify_url': 'https://vibemall.in/verify/test-token/',
            'verification_required': True,
            'current_year': now.year,
        }
    ),
    (
        'Verify Email',
        'emails/verify_email.html',
        {
            'user': type('User', (), {'first_name': 'Raj', 'username': 'raj_test'})(),
            'verify_url': 'https://vibemall.in/verify/test-token/',
            'now': now,
            'site_settings': type('S', (), {'site_name': 'VibeMall'})(),
        }
    ),
    (
        'Order Received',
        'emails/order_received.html',
        {
            'order': type('O', (), {
                'order_number': 'VM-2026-001',
                'total_amount': 2499.00,
                'subtotal': 2299.00,
                'tax': 200.00,
                'coupon_discount': 0,
                'shipping_address': '123, MG Road, Surat, Gujarat - 395001',
                'get_payment_method_display': lambda: 'Razorpay',
                'user': type('U', (), {'get_full_name': lambda: 'Raj Paladiya', 'username': 'raj_test'})(),
            })(),
            'order_date': now.strftime('%d %b %Y'),
            'payment_status_display': 'PAID',
            'order_items': [
                {'product_name': 'Artisan Silk Kurta', 'variant_text': 'Size: M | Color: Ivory', 'quantity': 1, 'subtotal': 1499.00, 'image_url': ''},
                {'product_name': 'Handwoven Dupatta', 'variant_text': 'Color: Gold', 'quantity': 1, 'subtotal': 800.00, 'image_url': ''},
            ],
            'shipping_cost_display': 'Free',
            'estimated_delivery': '10 Apr 2026',
            'track_order_url': 'https://vibemall.in/track/',
            'order_details_url': 'https://vibemall.in/orders/',
            'contact_url': 'https://vibemall.in/contact/',
            'returns_policy_url': 'https://vibemall.in/returns/',
            'invoice_download_url': 'https://vibemall.in/invoice/VM-2026-001/',
            'current_year': now.year,
        }
    ),
    (
        'Order Confirmation',
        'emails/order_confirmation.html',
        {
            'order': type('O', (), {
                'order_number': 'VM-2026-001',
                'total_amount': 2499.00,
                'subtotal': 2299.00,
                'tax': 200.00,
                'coupon_discount': 0,
                'shipping_address': '123, MG Road, Surat, Gujarat - 395001',
                'get_payment_method_display': lambda: 'Razorpay',
                'user': type('U', (), {'get_full_name': lambda: 'Raj Paladiya', 'username': 'raj_test'})(),
            })(),
            'hero_title': 'Your Order Is Confirmed',
            'hero_message': 'We have verified your order and our atelier has begun preparing your selections.',
            'order_date': now.strftime('%d %b %Y'),
            'confirmation_date': now.strftime('%d %b %Y'),
            'payment_status_display': 'PAID',
            'order_items': [
                {'product_name': 'Artisan Silk Kurta', 'variant_text': 'Size: M', 'quantity': 1, 'subtotal': 1499.00, 'image_url': ''},
            ],
            'shipping_cost_display': 'Free',
            'estimated_dispatch_date': '08 Apr 2026',
            'estimated_delivery': '10 Apr 2026',
            'track_order_url': 'https://vibemall.in/track/',
            'order_details_url': 'https://vibemall.in/orders/',
            'contact_url': 'https://vibemall.in/contact/',
            'returns_policy_url': 'https://vibemall.in/returns/',
            'invoice_download_url': 'https://vibemall.in/invoice/VM-2026-001/',
            'current_year': now.year,
        }
    ),
    (
        'Newsletter',
        'emails/newsletter_campaign.html',
        {
            'newsletter_title': 'New Collection Arriving Soon',
            'newsletter_body': 'We are thrilled to announce our latest artisan collection is launching this week.\n\nExplore handcrafted pieces curated with care.',
            'cta_text': 'Explore Collection',
            'cta_url': 'https://vibemall.in/shop/',
            'site_logo_url': '',
            'site_settings': type('S', (), {'site_name': 'VibeMall', 'contact_email': 'info@vibemall.in'})(),
            'recipient_email': TO_EMAIL,
            'now': now,
        }
    ),
]

print(f"Sending {len(templates)} email previews to {TO_EMAIL}...\n")

for subject, template, context in templates:
    try:
        html_content = render_to_string(template, context)
        email = EmailMultiAlternatives(
            subject=f'[Preview] {subject} - VibeMall',
            body=f'Preview of: {subject}',
            from_email=FROM_EMAIL,
            to=[TO_EMAIL],
        )
        email.attach_alternative(html_content, 'text/html')
        email.send()
        print(f'  ✓ Sent: {subject}')
    except Exception as e:
        print(f'  ✗ Failed: {subject} → {e}')

print('\nDone.')
