import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

now = timezone.now()
context = {
    'newsletter_title': 'New Collection Arriving Soon',
    'newsletter_body': 'We are thrilled to announce our latest artisan collection is launching this week.\n\nExplore handcrafted pieces curated with care.',
    'cta_text': 'Explore Collection',
    'cta_url': 'https://vibemall.in/shop/',
    'site_logo_url': '',
    'site_settings': type('S', (), {'site_name': 'VibeMall', 'contact_email': 'info@vibemall.in'})(),
    'recipient_email': 'rajpaladiya2023@gmail.com',
    'now': now,
}

html = render_to_string('emails/newsletter_campaign.html', context)
email = EmailMultiAlternatives(
    subject='[Preview] Newsletter - VibeMall',
    body='Newsletter preview',
    from_email='info@vibemall.in',
    to=['rajpaladiya2023@gmail.com'],
)
email.attach_alternative(html, 'text/html')
email.send()
print('Newsletter sent!')
