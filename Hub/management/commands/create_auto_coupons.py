from django.core.management.base import BaseCommand
from Hub.models import Coupon
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create automatic coupons for first order and spending milestones'
    
    def handle(self, *args, **kwargs):
        # First Order Coupon - 5% off
        first_coupon, created = Coupon.objects.get_or_create(
            code='FIRST5',
            defaults={
                'coupon_type': 'FIRST_ORDER',
                'description': '5% off on your first order! Welcome to VibeMall',
                'discount_type': 'PERCENTAGE',
                'discount_value': 5,
                'min_purchase_amount': 0,
                'max_discount_amount': 200,  # Max ₹200 discount
                'usage_per_user': 1,
                'valid_from': timezone.now(),
                'valid_to': timezone.now() + timedelta(days=365),
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created FIRST5 coupon'))
        else:
            self.stdout.write(self.style.WARNING(f'→ FIRST5 coupon already exists'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Auto-coupons setup complete!'))
        self.stdout.write(self.style.SUCCESS('  - FIRST5: 5% off for first-time customers'))
        self.stdout.write(self.style.SUCCESS('  - SPEND5K coupons will be auto-generated per user'))
