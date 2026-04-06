"""
Loyalty Points Utilities - Fixed implementation
Handles all loyalty points operations correctly
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger('vibemall')

# Loyalty Points Configuration
POINTS_PER_RUPEE = Decimal('33')  # ₹1 spent = 33 points
RUPEES_PER_POINT = Decimal('0.03')  # 1 point = ₹0.03


class LoyaltyPointsManager:
    """Centralized loyalty points management"""
    
    @staticmethod
    @transaction.atomic
    def add_points(user, points, transaction_type='EARNED', description='', order=None):
        """
        Add points to user's loyalty account
        
        Args:
            user: User instance
            points: Number of points to add (integer)
            transaction_type: Type of transaction (EARNED, ADJUSTED, etc.)
            description: Transaction description
            order: Related Order instance (optional)
            
        Returns:
            tuple: (LoyaltyPoints object, PointsTransaction object, success_bool)
        """
        try:
            from .models import LoyaltyPoints, PointsTransaction
            
            # Get or create loyalty account
            loyalty, created = LoyaltyPoints.objects.get_or_create(user=user)
            
            # Increment points correctly
            loyalty.total_points += int(points)
            loyalty.points_available += int(points)
            loyalty.updated_at = timezone.now()
            loyalty.save()
            
            # Create transaction record
            transaction_record = PointsTransaction.objects.create(
                user=user,
                points=int(points),
                transaction_type=transaction_type,
                description=description,
                order=order
            )
            
            logger.info(
                f"Added {points} loyalty points to {user.username} | "
                f"Type: {transaction_type} | Available: {loyalty.points_available}"
            )
            
            return loyalty, transaction_record, True
            
        except Exception as e:
            logger.error(f"Error adding loyalty points for {user.username}: {str(e)}")
            return None, None, False
    
    @staticmethod
    @transaction.atomic
    def redeem_points(user, points, order=None, description=''):
        """
        Redeem (deduct) points from user's loyalty account
        
        Args:
            user: User instance
            points: Number of points to redeem
            order: Related Order instance (optional)
            description: Redemption description
            
        Returns:
            tuple: (success_bool, loyalty_object, transaction_object, error_message)
        """
        try:
            from .models import LoyaltyPoints, PointsTransaction
            
            # Get loyalty account
            try:
                loyalty = LoyaltyPoints.objects.get(user=user)
            except LoyaltyPoints.DoesNotExist:
                return False, None, None, "User has no loyalty account"
            
            points = int(points)
            
            # Validate points available
            if loyalty.points_available < points:
                return False, loyalty, None, f"Insufficient points. Available: {loyalty.points_available}, Required: {points}"
            
            # Deduct points
            loyalty.points_used += points
            loyalty.points_available -= points
            loyalty.updated_at = timezone.now()
            loyalty.save()
            
            # Create transaction record
            transaction_record = PointsTransaction.objects.create(
                user=user,
                points=points,
                transaction_type='REDEEMED',
                description=description or f"Redeemed for Order",
                order=order
            )
            
            logger.info(
                f"Redeemed {points} loyalty points from {user.username} | "
                f"Available remaining: {loyalty.points_available}"
            )
            
            return True, loyalty, transaction_record, None
            
        except Exception as e:
            logger.error(f"Error redeeming loyalty points for {user.username}: {str(e)}")
            return False, None, None, str(e)
    
    @staticmethod
    def calculate_points_earned(order_amount):
        """Calculate points earned for an order amount"""
        return int(Decimal(str(order_amount)) * POINTS_PER_RUPEE)
    
    @staticmethod
    def calculate_rupee_value(points):
        """Calculate rupee value of points (for redemption)"""
        return Decimal(str(points)) * RUPEES_PER_POINT
    
    @staticmethod
    @transaction.atomic
    def process_order_delivery_points(order):
        """
        Award loyalty points when order is delivered
        
        Args:
            order: Order instance
            
        Returns:
            tuple: (success_bool, points_awarded, error_message)
        """
        try:
            from .models import LoyaltyPoints, PointsTransaction
            
            # Skip if order not delivered
            if order.order_status != 'DELIVERED':
                return False, 0, "Order not delivered"
            
            # Skip if points already awarded
            existing_transaction = PointsTransaction.objects.filter(
                user=order.user,
                order=order,
                transaction_type='EARNED'
            ).exists()
            
            if existing_transaction:
                return False, 0, "Points already awarded for this order"
            
            # Calculate points (using delivered order total)
            points_earned = LoyaltyPointsManager.calculate_points_earned(order.total_amount)
            
            if points_earned <= 0:
                return False, 0, "Order amount too small to earn points"
            
            # Award points
            _, _, success = LoyaltyPointsManager.add_points(
                user=order.user,
                points=points_earned,
                transaction_type='EARNED',
                description=f"Order #{order.order_number} delivered",
                order=order
            )
            
            if success:
                return True, points_earned, None
            else:
                return False, 0, "Failed to process points"
            
        except Exception as e:
            logger.error(f"Error processing delivery points for order {order.order_number}: {str(e)}")
            return False, 0, str(e)
    
    @staticmethod
    def get_loyalty_summary(user):
        """Get complete loyalty summary for a user"""
        try:
            from .models import LoyaltyPoints, PointsTransaction
            
            loyalty = LoyaltyPoints.objects.get(user=user)
            recent_transactions = PointsTransaction.objects.filter(
                user=user
            ).order_by('-created_at')[:5]
            
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
                        'date': t.created_at.strftime('%Y-%m-%d %H:%M')
                    }
                    for t in recent_transactions
                ]
            }
        except Exception:
            return None


def award_loyalty_points_on_delivery(sender, instance, update_fields=None, **kwargs):
    """
    Signal handler to award loyalty points when order status changes to DELIVERED
    
    Usage in models.py Order model:
        post_save.connect(award_loyalty_points_on_delivery, sender=Order)
    """
    from .models import Order
    
    try:
        # Get the old instance to check if status changed to DELIVERED
        if instance.pk:
            old_instance = Order.objects.get(pk=instance.pk)
            if old_instance.order_status != 'DELIVERED' and instance.order_status == 'DELIVERED':
                success, points, error = LoyaltyPointsManager.process_order_delivery_points(instance)
                if success:
                    logger.info(f"Awarded {points} points to {instance.user.username} for order {instance.order_number}")
    except Exception as e:
        logger.warning(f"Could not process loyalty points in signal: {str(e)}")
