"""Run: python test_brevo.py"""
import smtplib

HOST = 'smtp-relay.brevo.com'
PORT = 587
USER = 'info.vibemall@gmail.com'
PASS = 'xsmtpsib-1f13a1b811fb973594e6696fb9101fbb39ad69ca4cfb45ef1822eec4bbda3a39-CgLiiodmSjEVmsE4'

try:
    with smtplib.SMTP(HOST, PORT, timeout=10) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(USER, PASS)
        print("✓ Brevo SMTP login successful!")
except smtplib.SMTPAuthenticationError as e:
    print(f"✗ Auth failed: {e}")
    print("\nFix: Go to Brevo dashboard → Senders & IP → verify info.vibemall@gmail.com")
except Exception as e:
    print(f"✗ Connection error: {e}")
