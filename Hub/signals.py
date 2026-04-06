from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Order, Cart, Wishlist, ProductReview, Product



@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Order)
def update_activity_on_order(sender, instance, created, **kwargs):
    """Update user's last activity when they place an order"""
    if created:
        try:
            profile = instance.user.userprofile
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_activity'])
        except:
            pass


@receiver(post_save, sender=Cart)
def update_activity_on_cart(sender, instance, created, **kwargs):
    """Update user's last activity when they add to cart"""
    if created:
        try:
            profile = instance.user.userprofile
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_activity'])
        except:
            pass


@receiver(post_save, sender=Wishlist)
def update_activity_on_wishlist(sender, instance, created, **kwargs):
    """Update user's last activity when they add to wishlist"""
    if created:
        try:
            profile = instance.user.userprofile
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_activity'])
        except:
            pass


@receiver(post_save, sender=ProductReview)
def update_activity_on_review(sender, instance, created, **kwargs):
    """Update user's last activity when they submit a review"""
    if created:
        try:
            profile = instance.user.userprofile
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_activity'])
        except:
            pass


# ============================================
# COUPON SYSTEM SIGNALS
# ============================================

@receiver(post_save, sender=Order)
def update_user_spending_tracker(sender, instance, created, **kwargs):
    """Track user spending for automatic coupon generation"""
    from .models import UserSpendTracker
    
    # Only track paid orders
    if instance.payment_status == 'PAID':
        tracker, _ = UserSpendTracker.objects.get_or_create(user=instance.user)
        
        # Update total spent
        tracker.total_spent += instance.total_amount
        tracker.current_cycle_spent += instance.total_amount
        
        # Reset cycle if 5K coupon was used
        if instance.coupon and instance.coupon.coupon_type == 'SPEND_5K':
            tracker.current_cycle_spent = 0
            tracker.last_5k_coupon_at = timezone.now()
        
        tracker.save()



# ============================================
# RESELL SYSTEM SIGNALS
# ============================================

@receiver(post_save, sender=Order)
def auto_confirm_reseller_earnings(sender, instance, created, **kwargs):
    """Automatically confirm reseller earnings when order is delivered"""
    # Only process if order status changed to DELIVERED and it's a resell order
    if not created and instance.order_status == 'DELIVERED' and instance.is_resell:
        try:
            from .resell_services import confirm_reseller_earnings
            from .models import ResellerEarning
            
            # Check if earning exists and is still PENDING
            try:
                earning = ResellerEarning.objects.get(order=instance, status='PENDING')
                # Confirm the earning
                confirm_reseller_earnings(instance)
            except ResellerEarning.DoesNotExist:
                # Earning already confirmed or doesn't exist
                pass
        except Exception as e:
            # Log error but don't raise - don't block order status update
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to auto-confirm earnings for order {instance.order_number}: {str(e)}")


@receiver(post_save, sender=Order)
def auto_cancel_reseller_earnings(sender, instance, created, **kwargs):
    """Automatically cancel reseller earnings when a resell order is cancelled."""
    if created or instance.order_status != 'CANCELLED' or not instance.is_resell:
        return

    try:
        from .models import ResellerEarning
        from .resell_services import cancel_resell_order

        earning = ResellerEarning.objects.filter(order=instance).first()
        if not earning or earning.status == 'CANCELLED':
            return
        cancel_resell_order(instance)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to cancel reseller earnings for order {instance.order_number}: {str(e)}")


# ============================================
# LOYALTY POINTS SYSTEM SIGNALS
# ============================================

@receiver(post_save, sender=Order)
def award_loyalty_points_on_delivery(sender, instance, created, update_fields=None, **kwargs):
    """
    Award loyalty points when order status changes to DELIVERED.
    Uses LoyaltyPointsManager for atomic, consistent point operations.
    
    Award formula: ₹1 spent = 33 points earned
    Only awards on first delivery (checks delivery_points_awarded flag)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Only process existing orders (not newly created)
    if created:
        return
    
    # Only process if order_status was actually updated
    if update_fields and 'order_status' not in update_fields:
        return
    
    # Only award points on DELIVERED status
    if instance.order_status != 'DELIVERED':
        return
    
    # Don't re-process orders that already awarded delivery points
    if instance.delivery_points_awarded:
        return
    
    try:
        from .loyalty_manager import LoyaltyPointsManager
        from .models import Order
        from django.core.exceptions import ObjectDoesNotExist
        
        # Refresh to ensure we have latest data
        order = Order.objects.get(id=instance.id)
        
        # Calculate points based on order amount (excluding discounts)
        # Use base_amount for resell orders, subtotal for regular orders
        if order.is_resell and order.base_amount:
            order_amount = float(order.base_amount)
        else:
            order_amount = float(order.subtotal)
        
        # Calculate points earned (₹1 = 33 points)
        points_earned = LoyaltyPointsManager.calculate_points_earned(order_amount)
        
        if points_earned > 0:
            # Award points using centralized manager with atomic transaction
            success = LoyaltyPointsManager.add_points(
                user=order.user,
                points=points_earned,
                transaction_type='EARNED',
                description=f"Delivery bonus on Order #{order.order_number}",
                order=order
            )
            
            if success:
                # Mark that delivery points have been awarded
                order.delivery_points_awarded = True
                order.admin_notes += f"\n[AUTO] Loyalty Points Awarded: {points_earned} points (Order delivered)"
                order.save(update_fields=['delivery_points_awarded', 'admin_notes'])
                
                logger.info(f"✓ Awarded {points_earned} loyalty points to user {order.user.id} for order {order.order_number}")
            else:
                logger.warning(f"✗ Failed to award loyalty points for order {order.order_number}")
                
    except ObjectDoesNotExist:
        logger.warning(f"Order or User not found when trying to award loyalty points")
    except Exception as e:
        logger.error(f"Error awarding loyalty points on delivery: {str(e)}", exc_info=True)
