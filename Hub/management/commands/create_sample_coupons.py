"""
Management command to create sample coupon codes
Usage: python manage.py create_sample_coupons
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from Hub.models import Coupon

class Command(BaseCommand):
    help = 'Create sample coupon codes for testing and promotion'

    def handle(self, *args, **options):
        """Create sample coupons"""
        
        # Delete existing sample coupons
        Coupon.objects.filter(coupon_type__in=['FIRST_ORDER', 'SPEND_5K']).delete()
        
        coupons_created = []
        
        # Coupon 1: First Order 10% OFF
        coupon1 = Coupon.objects.create(
            code='FIRST10',
            coupon_type='FIRST_ORDER',
            description='Get 10% OFF on your first order!',
            discount_type='PERCENTAGE',
            discount_value=10,
            min_purchase_amount=100,
            max_discount_amount=500,
            usage_limit=None,
            usage_per_user=1,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=365),
            is_active=True
        )
        coupons_created.append(coupon1.code)
        
        # Coupon 2: Welcome 15% OFF
        coupon2 = Coupon.objects.create(
            code='WELCOME15',
            coupon_type='FIRST_ORDER',
            description='Get 15% OFF on your first purchase over ₹500!',
            discount_type='PERCENTAGE',
            discount_value=15,
            min_purchase_amount=500,
            max_discount_amount=750,
            usage_limit=None,
            usage_per_user=1,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=365),
            is_active=True
        )
        coupons_created.append(coupon2.code)
        
        # Coupon 3: ₹250 OFF on ₹2000+
        coupon3 = Coupon.objects.create(
            code='SAVE250',
            coupon_type='MANUAL',
            description='Get flat ₹250 OFF on purchases above ₹2000!',
            discount_type='FIXED',
            discount_value=250,
            min_purchase_amount=2000,
            max_discount_amount=None,
            usage_limit=100,
            usage_per_user=3,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=60),
            is_active=True
        )
        coupons_created.append(coupon3.code)
        
        # Coupon 4: Spend ₹5000+ Get 5% OFF
        coupon4 = Coupon.objects.create(
            code='SPEND5K',
            coupon_type='SPEND_5K',
            description='Unlock 5% OFF when you spend ₹5000 or more!',
            discount_type='PERCENTAGE',
            discount_value=5,
            min_purchase_amount=5000,
            max_discount_amount=1000,
            usage_limit=500,
            usage_per_user=5,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=180),
            is_active=True
        )
        coupons_created.append(coupon4.code)
        
        # Coupon 5: Spring Sale - 20% OFF
        coupon5 = Coupon.objects.create(
            code='SPRING20',
            coupon_type='MANUAL',
            description='Spring Sale! Get 20% OFF on all products!',
            discount_type='PERCENTAGE',
            discount_value=20,
            min_purchase_amount=500,
            max_discount_amount=2000,
            usage_limit=200,
            usage_per_user=2,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=30),
            is_active=True
        )
        coupons_created.append(coupon5.code)
        
        # Coupon 6: Festival Offer - ₹500 OFF
        coupon6 = Coupon.objects.create(
            code='FESTIVAL500',
            coupon_type='MANUAL',
            description='Festival Special! Get flat ₹500 OFF on orders above ₹3500!',
            discount_type='FIXED',
            discount_value=500,
            min_purchase_amount=3500,
            max_discount_amount=None,
            usage_limit=300,
            usage_per_user=1,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=15),
            is_active=True
        )
        coupons_created.append(coupon6.code)
        
        # Coupon 7: Loyalty Reward - 50% OFF
        coupon7 = Coupon.objects.create(
            code='LOYAL50',
            coupon_type='MANUAL',
            description='Loyal Customer! Enjoy 50% OFF on select items!',
            discount_type='PERCENTAGE',
            discount_value=50,
            min_purchase_amount=1000,
            max_discount_amount=1000,
            usage_limit=100,
            usage_per_user=1,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=90),
            is_active=True
        )
        coupons_created.append(coupon7.code)
        
        # Coupon 8: Bank Partner - 12% OFF
        coupon8 = Coupon.objects.create(
            code='BANK12',
            coupon_type='MANUAL',
            description='Bank Partner Offer! Get 12% OFF with your bank card!',
            discount_type='PERCENTAGE',
            discount_value=12,
            min_purchase_amount=2500,
            max_discount_amount=1500,
            usage_limit=400,
            usage_per_user=4,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=120),
            is_active=True
        )
        coupons_created.append(coupon8.code)
        
        # Coupon 9: Referral Bonus - ₹300
        coupon9 = Coupon.objects.create(
            code='REFER300',
            coupon_type='MANUAL',
            description='Referral Bonus! Get ₹300 OFF using your friend\'s code!',
            discount_type='FIXED',
            discount_value=300,
            min_purchase_amount=1500,
            max_discount_amount=None,
            usage_limit=600,
            usage_per_user=1,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=180),
            is_active=True
        )
        coupons_created.append(coupon9.code)
        
        # Coupon 10: New Year Special - ₹1000
        coupon10 = Coupon.objects.create(
            code='NEWYEAR1000',
            coupon_type='MANUAL',
            description='New Year Extravaganza! Get flat ₹1000 OFF on orders above ₹5000!',
            discount_type='FIXED',
            discount_value=1000,
            min_purchase_amount=5000,
            max_discount_amount=None,
            usage_limit=150,
            usage_per_user=1,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=10),
            is_active=True
        )
        coupons_created.append(coupon10.code)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Successfully created {len(coupons_created)} sample coupon codes:\n' +
                '\n'.join([f'  • {code}' for code in coupons_created])
            )
        )
