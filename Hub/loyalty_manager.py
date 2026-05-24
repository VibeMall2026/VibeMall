"""
Loyalty Points Utilities - Fixed implementation
Handles all loyalty points operations correctly
"""

from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger('vibemall')

# Loyalty Points Configuration
# Rs.100 spent = 1 coin | 1 coin = Rs.10
POINTS_PER_RUPEE = Decimal('0.01')
RUPEES_PER_POINT = Decimal('10.00')
DEFAULT_RETURN_WINDOW_DAYS = 7


class LoyaltyPointsManager:
    """Centralized loyalty points management"""

    @staticmethod
    @transaction.atomic
    def add_points(user, points, transaction_type='EARNED', description='', order=None):
        """Add points to user's loyalty account"""
        try:
            from .models import LoyaltyPoints, PointsTransaction

            loyalty, _ = LoyaltyPoints.objects.get_or_create(user=user)
            loyalty.total_points += int(points)
            loyalty.points_available += int(points)
            loyalty.updated_at = timezone.now()
            loyalty.save()

            transaction_record = PointsTransaction.objects.create(
                user=user,
                points=int(points),
                transaction_type=transaction_type,
                description=description,
                order=order,
            )

            logger.info(
                "Added %s loyalty points to %s | Type: %s | Available: %s",
                points,
                user.username,
                transaction_type,
                loyalty.points_available,
            )
            return loyalty, transaction_record, True
        except Exception as exc:
            logger.error("Error adding loyalty points for %s: %s", user.username, str(exc))
            return None, None, False

    @staticmethod
    @transaction.atomic
    def redeem_points(user, points, order=None, description=''):
        """Redeem (deduct) points from user's loyalty account"""
        try:
            from .models import LoyaltyPoints, PointsTransaction

            try:
                loyalty = LoyaltyPoints.objects.get(user=user)
            except LoyaltyPoints.DoesNotExist:
                return False, None, None, "User has no loyalty account"

            points = int(points)
            if loyalty.points_available < points:
                return False, loyalty, None, f"Insufficient points. Available: {loyalty.points_available}, Required: {points}"

            loyalty.points_used += points
            loyalty.points_available -= points
            loyalty.updated_at = timezone.now()
            loyalty.save()

            transaction_record = PointsTransaction.objects.create(
                user=user,
                points=points,
                transaction_type='REDEEMED',
                description=description or "Redeemed for Order",
                order=order,
            )

            logger.info(
                "Redeemed %s loyalty points from %s | Available remaining: %s",
                points,
                user.username,
                loyalty.points_available,
            )
            return True, loyalty, transaction_record, None
        except Exception as exc:
            logger.error("Error redeeming loyalty points for %s: %s", user.username, str(exc))
            return False, None, None, str(exc)

    @staticmethod
    def calculate_points_earned(order_amount):
        """Calculate points earned for an order amount"""
        amount = Decimal(str(order_amount or 0))
        if amount <= 0:
            return 0
        return int((amount * POINTS_PER_RUPEE).quantize(Decimal('1'), rounding=ROUND_DOWN))

    @staticmethod
    def calculate_rupee_value(points):
        """Calculate rupee value of points (for redemption)"""
        return Decimal(str(points)) * RUPEES_PER_POINT

    @staticmethod
    def _get_order_return_window_days(order):
        """Resolve return window for an order (max return_days among returnable items)."""
        max_days = 0
        try:
            for item in order.items.select_related('product').all():
                product = getattr(item, 'product', None)
                if not product or not getattr(product, 'is_returnable', True):
                    continue
                days = int(getattr(product, 'return_days', DEFAULT_RETURN_WINDOW_DAYS) or DEFAULT_RETURN_WINDOW_DAYS)
                max_days = max(max_days, days)
        except Exception:
            max_days = 0
        return max_days if max_days > 0 else DEFAULT_RETURN_WINDOW_DAYS

    @staticmethod
    def _is_eligible_after_return_window(order):
        if order.order_status != 'DELIVERED':
            return False, "Order not delivered yet"
        if not order.delivery_date:
            return False, "Delivery date not set"

        return_window_days = LoyaltyPointsManager._get_order_return_window_days(order)
        return_deadline = order.delivery_date + timedelta(days=return_window_days)
        if timezone.now() < return_deadline:
            return False, f"Return window active until {return_deadline.isoformat()}"

        has_non_rejected_return = order.return_requests.exclude(status__in=['CANCELLED', 'REJECTED']).exists()
        if has_non_rejected_return:
            return False, "Return request exists for this order"

        return True, None

    @staticmethod
    @transaction.atomic
    def process_order_delivery_points(order):
        """
        Award loyalty points only after return window is over.

        Returns:
            tuple: (success_bool, points_awarded, error_message)
        """
        try:
            from .models import PointsTransaction

            eligible, reason = LoyaltyPointsManager._is_eligible_after_return_window(order)
            if not eligible:
                return False, 0, reason or "Order not eligible yet"

            existing_transaction = PointsTransaction.objects.filter(
                user=order.user,
                order=order,
                transaction_type='EARNED',
            ).exists()
            if existing_transaction or order.delivery_points_awarded:
                return False, 0, "Points already awarded for this order"

            points_earned = LoyaltyPointsManager.calculate_points_earned(order.total_amount)
            if points_earned <= 0:
                return False, 0, "Order amount too small to earn points"

            _, _, success = LoyaltyPointsManager.add_points(
                user=order.user,
                points=points_earned,
                transaction_type='EARNED',
                description=f"Order #{order.order_number} delivered and return window closed",
                order=order,
            )
            if not success:
                return False, 0, "Failed to process points"

            order.delivery_points_awarded = True
            order.save(update_fields=['delivery_points_awarded'])
            return True, points_earned, None
        except Exception as exc:
            logger.error("Error processing delivery points for order %s: %s", order.order_number, str(exc))
            return False, 0, str(exc)

    @staticmethod
    def process_pending_delivery_points(limit=500):
        """Batch process delivered orders where return window is closed and points are pending."""
        from .models import Order

        processed = 0
        awarded = 0
        skipped = 0
        errors = 0

        qs = (
            Order.objects
            .filter(order_status='DELIVERED', delivery_points_awarded=False)
            .select_related('user')
            .order_by('delivery_date', 'id')[:limit]
        )

        for order in qs:
            processed += 1
            try:
                success, points, _ = LoyaltyPointsManager.process_order_delivery_points(order)
                if success and points > 0:
                    awarded += 1
                else:
                    skipped += 1
            except Exception:
                errors += 1

        return {
            'processed': processed,
            'awarded': awarded,
            'skipped': skipped,
            'errors': errors,
        }

    @staticmethod
    def get_loyalty_summary(user):
        """Get complete loyalty summary for a user"""
        try:
            from .models import LoyaltyPoints, PointsTransaction

            loyalty = LoyaltyPoints.objects.get(user=user)
            recent_transactions = PointsTransaction.objects.filter(user=user).order_by('-created_at')[:5]

            return {
                'total_points': loyalty.total_points,
                'points_used': loyalty.points_used,
                'points_available': loyalty.points_available,
                'rupee_value': float(LoyaltyPointsManager.calculate_rupee_value(loyalty.points_available)),
                'recent_transactions': [
                    {
                        'type': t.transaction_type,
                        'points': t.points,
                        'description': t.description,
                        'date': t.created_at.strftime('%Y-%m-%d %H:%M'),
                    }
                    for t in recent_transactions
                ],
            }
        except Exception:
            return None


def award_loyalty_points_on_delivery(sender, instance, update_fields=None, **kwargs):
    """Compatibility hook kept for legacy imports."""
    try:
        success, points, _ = LoyaltyPointsManager.process_order_delivery_points(instance)
        if success:
            logger.info("Awarded %s points to %s for order %s", points, instance.user.username, instance.order_number)
    except Exception as exc:
        logger.warning("Could not process loyalty points in hook: %s", str(exc))
