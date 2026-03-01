from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def add_days(date, days):
    """Add days to a date"""
    try:
        return date + timedelta(days=int(days))
    except:
        return date
@register.filter
def get_item(dictionary, key):
    """Get item from dictionary"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def calculate_margin_percentage(margin, base_amount):
    """Calculate margin percentage"""
    try:
        margin = float(margin)
        base_amount = float(base_amount)
        if base_amount > 0:
            return round((margin / base_amount) * 100, 1)
        return 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
