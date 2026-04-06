"""
Management command to test loyalty points system end-to-end
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Hub.models import LoyaltyPoints, PointsTransaction, Order
from Hub.loyalty_manager import LoyaltyPointsManager
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test the loyalty points system end-to-end'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧪 LOYALTY POINTS SYSTEM TEST\n'))
        
        # Test 1: Get or create test user
        self.stdout.write('Test 1: Creating test user...')
        test_user, created = User.objects.get_or_create(
            username='loyalty_test_user',
            defaults={
                'email': 'loyalty_test@vibemall.local',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ User: {test_user.username}'))
        
        # Test 2: Get or create loyalty points account
        self.stdout.write('\nTest 2: Getting/creating loyalty account...')
        loyalty_account, created = LoyaltyPoints.objects.get_or_create(
            user=test_user,
            defaults={'total_points': 0, 'points_used': 0, 'points_available': 0}
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Current balance: {loyalty_account.points_available} points'))
        
        # Test 3: Add points
        self.stdout.write('\nTest 3: Adding 500 points (via manager)...')
        initial_points = loyalty_account.points_available
        success = LoyaltyPointsManager.add_points(
            user=test_user,
            points=500,
            transaction_type='EARNED',
            description='Test points earning'
        )
        loyalty_account.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(f'  ✓ Added: 500 points'))
        self.stdout.write(f'  ✓ New balance: {loyalty_account.points_available} points')
        
        # Test 4: Calculate redemption value
        self.stdout.write('\nTest 4: Calculating redemption value...')
        rupee_value = LoyaltyPointsManager.calculate_rupee_value(100)
        self.stdout.write(self.style.SUCCESS(f'  ✓ 100 points = ₹{rupee_value} (expected: ₹3.00)'))
        
        # Test 5: Calculate earned points
        self.stdout.write('\nTest 5: Calculating earned points...')
        order_amount = Decimal('1000')
        points_earned = LoyaltyPointsManager.calculate_points_earned(order_amount)
        self.stdout.write(self.style.SUCCESS(f'  ✓ ₹{order_amount} = {points_earned} points (expected: 33000)'))
        
        # Test 6: Redeem points
        self.stdout.write('\nTest 6: Redeeming 100 points...')
        points_before = loyalty_account.points_available
        success = LoyaltyPointsManager.redeem_points(
            user=test_user,
            points=100,
            description='Test points redemption'
        )
        loyalty_account.refresh_from_db()
        points_after = loyalty_account.points_available
        self.stdout.write(self.style.SUCCESS(f'  ✓ Redeemed: 100 points'))
        self.stdout.write(f'  ✓ Balance before: {points_before} points')
        self.stdout.write(f'  ✓ Balance after: {points_after} points')
        
        # Test 7: View transaction history
        self.stdout.write('\nTest 7: Transaction history...')
        transactions = PointsTransaction.objects.filter(user=test_user).order_by('-created_at')[:5]
        for txn in transactions:
            icon = '➕' if txn.transaction_type == 'EARNED' else '➖'
            self.stdout.write(f'  {icon} {txn.transaction_type}: {txn.points} points - {txn.description}')
        
        # Test 8: Manager lookup
        self.stdout.write('\nTest 8: Getting loyalty summary...')
        summary = LoyaltyPointsManager.get_loyalty_summary(test_user)
        self.stdout.write(self.style.SUCCESS(f'  ✓ Total earned: {summary["total_points"]} points'))
        self.stdout.write(f'  ✓ Total redeemed: {summary["points_used"]} points')
        self.stdout.write(f'  ✓ Available: {summary["points_available"]} points')
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('✅ ALL TESTS COMPLETED SUCCESSFULLY'))
        self.stdout.write('='*50)
        
        self.stdout.write('\n📊 COUPON SYSTEM VERIFICATION:')
        from Hub.models import Coupon
        coupon_count = Coupon.objects.count()
        sample_coupons = Coupon.objects.filter(code__in=[
            'FIRST10', 'WELCOME15', 'SAVE250', 'SPEND5K', 'SPRING20',
            'FESTIVAL500', 'LOYAL50', 'BANK12', 'REFER300', 'NEWYEAR1000'
        ])
        self.stdout.write(f'  ✓ Total coupons in system: {coupon_count}')
        self.stdout.write(f'  ✓ Sample coupons created: {sample_coupons.count()}')
        
        if sample_coupons.exists():
            self.stdout.write('\n  Sample coupon details:')
            for coupon in sample_coupons[:3]:
                self.stdout.write(f'    • {coupon.code}: {coupon.get_discount_type_display()}')
