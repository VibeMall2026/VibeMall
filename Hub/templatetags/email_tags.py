"""
Custom template tags for email templates
"""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def absolute_url(relative_url):
    """
    Convert a relative URL to an absolute URL for use in emails
    
    Args:
        relative_url: Relative URL path (e.g., /media/products/image.jpg)
    
    Returns:
        Absolute URL (e.g., http://127.0.0.1:8000/media/products/image.jpg)
    """
    if not relative_url:
        return ''
    
    # If already absolute URL, return as is
    if relative_url.startswith('http://') or relative_url.startswith('https://'):
        return relative_url
    
    # Get site URL from settings
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    
    # Remove trailing slash from site_url
    site_url = site_url.rstrip('/')
    
    # Ensure relative_url starts with /
    if not relative_url.startswith('/'):
        relative_url = '/' + relative_url
    
    return f"{site_url}{relative_url}"


@register.filter
def get_product_image_url(product):
    """
    Get absolute URL for product image
    
    Args:
        product: Product instance
    
    Returns:
        Absolute URL to product image or empty string
    """
    if not product:
        return ''
    
    if hasattr(product, 'image') and product.image:
        return absolute_url(product.image.url)
    
    return ''
