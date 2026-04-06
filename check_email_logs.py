import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import EmailLog

print("\n===== Latest Order Confirmation Email Logs =====\n")
logs = EmailLog.objects.filter(email_type='ORDER_CONFIRMATION').order_by('-id')[:10]

if not logs:
    print("No order confirmation email logs found.")
else:
    for log in logs:
        print(f"Date: {log.created_at if hasattr(log, 'created_at') else 'N/A'}")
        print(f"To: {log.email_to}")
        print(f"Order: {log.order.order_number if log.order else 'N/A'}")
        print(f"Success: {log.sent_successfully}")
        if not log.sent_successfully:
            print(f"Error: {log.error_message}")
        print("-"*40)
