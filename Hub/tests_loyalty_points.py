from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from .loyalty_manager import (POINTS_PER_RUPEE, RUPEES_PER_POINT,
                              LoyaltyPointsManager)
from .models import LoyaltyPoints, PointsTransaction


@override_settings(SECURE_SSL_REDIRECT=False)
class LoyaltyRateTests(TestCase):
    """
    Rs.100 spent earns 10 points; 10 points redeem for Rs.1. A 1% return.

    The old rates were Rs.100 = 1 point and 1 point = Rs.10 - a 10% return, ten
    times more expensive to run.
    """

    def test_the_configured_rates(self):
        self.assertEqual(POINTS_PER_RUPEE, Decimal('0.10'))
        self.assertEqual(RUPEES_PER_POINT, Decimal('0.10'))

    # ── earning ──────────────────────────────────────────────────────────────

    def test_hundred_rupees_earns_ten_points(self):
        self.assertEqual(LoyaltyPointsManager.calculate_points_earned(100), 10)

    def test_earning_scales(self):
        for spend, points in ((10, 1), (250, 25), (999, 99), (1000, 100)):
            with self.subTest(spend=spend):
                self.assertEqual(
                    LoyaltyPointsManager.calculate_points_earned(spend), points)

    def test_part_points_are_rounded_down(self):
        """Rs.99 is 9.9 points; nobody is credited a point they did not earn."""
        self.assertEqual(LoyaltyPointsManager.calculate_points_earned(99), 9)

    def test_nothing_is_earned_on_a_zero_or_negative_amount(self):
        self.assertEqual(LoyaltyPointsManager.calculate_points_earned(0), 0)
        self.assertEqual(LoyaltyPointsManager.calculate_points_earned(-500), 0)

    # ── redeeming ────────────────────────────────────────────────────────────

    def test_ten_points_are_worth_one_rupee(self):
        self.assertEqual(LoyaltyPointsManager.calculate_rupee_value(10), Decimal('1.00'))

    def test_redemption_scales(self):
        for points, rupees in ((100, '10.00'), (55, '5.50'), (1, '0.10')):
            with self.subTest(points=points):
                self.assertEqual(
                    LoyaltyPointsManager.calculate_rupee_value(points), Decimal(rupees))

    def test_zero_points_are_worth_nothing(self):
        self.assertEqual(LoyaltyPointsManager.calculate_rupee_value(0), Decimal('0.00'))

    def test_points_needed_for_a_discount_rounds_up(self):
        """Rs.1.05 needs 11 points, not 10 - never hand out value unpaid for."""
        self.assertEqual(LoyaltyPointsManager.points_needed_for_rupees(1), 10)
        self.assertEqual(LoyaltyPointsManager.points_needed_for_rupees(Decimal('1.05')), 11)

    # ── the two rates agree ──────────────────────────────────────────────────

    def test_spending_a_hundred_earns_one_rupee_back(self):
        earned = LoyaltyPointsManager.calculate_points_earned(100)
        self.assertEqual(LoyaltyPointsManager.calculate_rupee_value(earned),
                         Decimal('1.00'))

    def test_the_scheme_returns_one_percent(self):
        for spend in (100, 500, 2000):
            with self.subTest(spend=spend):
                back = LoyaltyPointsManager.calculate_rupee_value(
                    LoyaltyPointsManager.calculate_points_earned(spend))
                self.assertEqual(back, (Decimal(spend) / 100).quantize(Decimal('0.01')))


@override_settings(SECURE_SSL_REDIRECT=False)
class LoyaltyResetCommandTests(TestCase):
    """Balances earned under the old rates are cleared, not carried over."""

    def setUp(self):
        self.users = []
        for index in range(3):
            user = User.objects.create_user(username=f"lp{index}", password="pass12345")
            LoyaltyPoints.objects.create(
                user=user, total_points=50, points_used=10, points_available=40)
            self.users.append(user)

    def _run(self, *args):
        out = StringIO()
        call_command('reset_loyalty_points', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self._run('--dry-run')
        self.assertIn('Dry run', output)
        self.assertIn('120', output, 'should report the 120 outstanding points')
        self.assertEqual(LoyaltyPoints.objects.get(user=self.users[0]).points_available, 40)

    def test_reset_zeroes_every_balance(self):
        self._run()
        for user in self.users:
            account = LoyaltyPoints.objects.get(user=user)
            self.assertEqual(account.points_available, 0)
            self.assertEqual(account.total_points, 0)
            self.assertEqual(account.points_used, 0)

    def test_reset_records_what_was_removed(self):
        self._run()
        for user in self.users:
            entry = PointsTransaction.objects.get(user=user, transaction_type='ADJUSTED')
            self.assertEqual(entry.points, 40)
            self.assertIn('rates changed', entry.description)

    def test_accounts_are_not_deleted(self):
        self._run()
        self.assertEqual(LoyaltyPoints.objects.count(), 3)

    def test_keep_history_skips_the_audit_rows(self):
        self._run('--keep-history')
        self.assertEqual(PointsTransaction.objects.filter(transaction_type='ADJUSTED').count(), 0)
        self.assertEqual(LoyaltyPoints.objects.get(user=self.users[0]).points_available, 0)

    def test_running_twice_is_harmless(self):
        self._run()
        output = self._run()
        self.assertIn('Nothing to reset', output)
