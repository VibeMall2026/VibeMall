from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Order, Cart, Wishlist, ProductReview, Product
from django.core.management import call_command
import threading


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


def run_category_update_async():
    """Run category update in background thread"""
    try:
        call_command('update_product_categories')
    except:
        pass


@receiver(post_save, sender=Order)
def auto_update_categories_on_order(sender, instance, created, **kwargs):
    """Auto-update product categories when order is completed"""
    if instance.order_status == 'DELIVERED':
        # Run in background to avoid blocking
        thread = threading.Thread(target=run_category_update_async)
        thread.daemon = True
        thread.start()


@receiver(post_save, sender=Wishlist)
def auto_update_categories_on_wishlist(sender, instance, created, **kwargs):
    """Auto-update RECOMMENDED when products added to wishlist"""
    if created:
        # Run in background
        thread = threading.Thread(target=run_category_update_async)
        thread.daemon = True
        thread.start()


@receiver(post_save, sender=Product)
def auto_update_categories_on_product(sender, instance, created, **kwargs):
    """Auto-update categories when product discount changes"""
    if not created and instance.discount_percent > 0:
        # Run in background
        thread = threading.Thread(target=run_category_update_async)
        thread.daemon = True
        thread.start()


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
