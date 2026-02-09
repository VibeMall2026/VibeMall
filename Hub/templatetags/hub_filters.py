"""
Custom template tags and filters for FashioHub
"""
from django import template
from decimal import Decimal
from datetime import timedelta

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get item from dictionary
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    try:
        return dictionary.get(int(key))
    except (ValueError, TypeError, AttributeError):
        try:
            return dictionary.get(key)
        except (TypeError, AttributeError):
            return None

@register.filter
def calc_discount(old_price, new_price):
    """
    Calculate discount percentage between old and new price
    Usage: {{ product.old_price|calc_discount:product.price }}
    """
    try:
        old = Decimal(str(old_price))
        new = Decimal(str(new_price))
        if old > 0 and new < old:
            discount = ((old - new) / old) * 100
            return int(discount)
        return 0
    except (ValueError, TypeError, AttributeError, ZeroDivisionError):
        return 0

@register.filter
def add_days(date, days):
    """
    Add days to a date
    Usage: {{ order.created_at|add_days:30 }}
    """
    try:
        return date + timedelta(days=int(days))
    except:
        return date
