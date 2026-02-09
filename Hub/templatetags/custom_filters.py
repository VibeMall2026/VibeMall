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