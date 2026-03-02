#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

from Hub.models import Order

order = Order.objects.filter(order_number='ORD20260301001').first()
if order:
    print(f"Order ID: {order.id}")
    print(f"Order Number: {order.order_number}")
    print(f"Payment Status: {order.payment_status}")
    print(f"Payment Method: {order.payment_method}")
    print(f"Razorpay Payment ID: '{order.razorpay_payment_id}'")
    print(f"Total Amount: {order.total_amount}")
    print(f"User: {order.user.username if order.user else 'N/A'}")
else:
    print("Order not found")
    # Try to find similar orders
    orders = Order.objects.filter(order_number__icontains='ORD202603020').first()
    if orders:
        print(f"Found similar order: {orders.order_number}")
