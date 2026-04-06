"""Run: python check_email_config.py"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()
from django.conf import settings

print("EMAIL_HOST        :", settings.EMAIL_HOST)
print("EMAIL_PORT        :", settings.EMAIL_PORT)
print("EMAIL_USE_TLS     :", settings.EMAIL_USE_TLS)
print("EMAIL_HOST_USER   :", settings.EMAIL_HOST_USER)
print("EMAIL_HOST_PASSWORD:", settings.EMAIL_HOST_PASSWORD[:10], "...")
print("DEFAULT_FROM_EMAIL:", settings.DEFAULT_FROM_EMAIL)
