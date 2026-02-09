from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from Hub.models import Product, Order, OrderItem, Wishlist
from datetime import timedelta
from django.utils import timezone


class Command(BaseCommand):
    help = 'Auto-update product categories based on sales, discounts, and popularity'

    def handle(self, *args, **kwargs):
        # AUTO CATEGORIZATION DISABLED - Use admin panel "Main Page Category" instead
        self.stdout.write(self.style.WARNING('⚠ Automatic product categorization is DISABLED'))
        self.stdout.write('Use the admin panel "Main Page Category" section to manually manage categories')
        return
