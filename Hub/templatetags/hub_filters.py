"""
Custom template tags and filters for FashioHub
"""
from django import template
from django.utils.safestring import mark_safe
from decimal import Decimal
from datetime import timedelta

register = template.Library()

# Mapping of common color names (lowercase) to CSS color values
COLOR_MAP = {
    # Reds
    'red': '#e53935',
    'dark red': '#b71c1c',
    'crimson': '#dc143c',
    'maroon': '#800000',
    'wine': '#722f37',
    'burgundy': '#800020',
    'rust': '#b7410e',
    'brick red': '#cb4154',
    # Pinks
    'pink': '#e91e8c',
    'hot pink': '#ff69b4',
    'light pink': '#ffb6c1',
    'baby pink': '#f4c2c2',
    'rose': '#ff007f',
    'blush': '#de5d83',
    'peach': '#ffcba4',
    'salmon': '#fa8072',
    # Oranges
    'orange': '#ff6f00',
    'dark orange': '#e65100',
    'light orange': '#ffb74d',
    'amber': '#ffc107',
    'tangerine': '#f28500',
    # Yellows
    'yellow': '#fdd835',
    'golden': '#ffd700',
    'gold': '#ffd700',
    'mustard': '#ffdb58',
    'lemon': '#fff44f',
    'cream': '#fffdd0',
    'off white': '#faf9f6',
    'ivory': '#fffff0',
    # Greens
    'green': '#43a047',
    'dark green': '#1b5e20',
    'light green': '#81c784',
    'olive': '#808000',
    'lime': '#cddc39',
    'mint': '#98ff98',
    'teal': '#009688',
    'emerald': '#50c878',
    'bottle green': '#006a4e',
    'forest green': '#228b22',
    'sea green': '#2e8b57',
    'jade': '#00a86b',
    'mehendi': '#4a5240',
    # Blues
    'blue': '#1e88e5',
    'dark blue': '#0d47a1',
    'light blue': '#64b5f6',
    'sky blue': '#87ceeb',
    'navy': '#001f5b',
    'navy blue': '#001f5b',
    'royal blue': '#4169e1',
    'cobalt': '#0047ab',
    'powder blue': '#b0e0e6',
    'baby blue': '#89cff0',
    'denim': '#1560bd',
    'indigo': '#3f51b5',
    'cerulean': '#007ba7',
    'turquoise': '#40e0d0',
    'aqua': '#00bcd4',
    'cyan': '#00bcd4',
    # Purples
    'purple': '#e91e63',
    'dark purple': '#c2185b',
    'light purple': '#f48fb1',
    'violet': '#ec407a',
    'lavender': '#f8bbd0',
    'lilac': '#f48fb1',
    'mauve': '#f06292',
    'plum': '#d81b60',
    'magenta': '#e91e63',
    'fuchsia': '#ff00ff',
    # Neutrals
    'white': '#f5f5f5',
    'black': '#212121',
    'grey': '#757575',
    'gray': '#757575',
    'dark grey': '#424242',
    'light grey': '#bdbdbd',
    'charcoal': '#36454f',
    'silver': '#c0c0c0',
    'beige': '#f5f0e8',
    'khaki': '#c3b091',
    'camel': '#c19a6b',
    'tan': '#d2b48c',
    'brown': '#795548',
    'dark brown': '#4e342e',
    'chocolate': '#7b3f00',
    'coffee': '#6f4e37',
    'copper': '#b87333',
    # Misc
    'multicolor': 'linear-gradient(135deg, #f44336, #ff9800, #ffeb3b, #4caf50, #2196f3, #9c27b0)',
    'multi': 'linear-gradient(135deg, #f44336, #ff9800, #ffeb3b, #4caf50, #2196f3, #9c27b0)',
    'printed': 'linear-gradient(135deg, #f44336, #ff9800, #ffeb3b, #4caf50, #2196f3, #9c27b0)',
}


@register.filter
def color_swatch(color_name):
    """
    Returns an HTML span with a colored dot swatch next to the color name.
    Usage: {{ item.color|color_swatch }}
    Falls back to plain text if color is unknown.
    """
    if not color_name:
        return ''
    key = color_name.strip().lower()
    css_color = COLOR_MAP.get(key)
    if css_color:
        if css_color.startswith('linear-gradient'):
            dot_style = (
                f'display:inline-block;width:11px;height:11px;border-radius:50%;'
                f'background:{css_color};vertical-align:middle;'
                f'margin-right:4px;flex-shrink:0;'
                f'border:1px solid rgba(0,0,0,0.12);'
            )
        else:
            dot_style = (
                f'display:inline-block;width:11px;height:11px;border-radius:50%;'
                f'background:{css_color};vertical-align:middle;'
                f'margin-right:4px;flex-shrink:0;'
                f'border:1px solid rgba(0,0,0,0.12);'
            )
        return mark_safe(
            f'<span style="display:inline-flex;align-items:center;gap:0;">'
            f'<span style="{dot_style}" aria-hidden="true"></span>'
            f'{color_name}'
            f'</span>'
        )
    # Graceful fallback: just return the color name as-is
    return color_name

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
