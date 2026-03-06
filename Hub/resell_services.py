"""
Resell Feature Services

This module contains service classes for managing resell functionality:
- ResellLinkGenerator: Creates and validates resell links
- MarginCalculator: Calculates pricing and margins
- ResellerPaymentManager: Manages earnings and payouts
- ResellOrderProcessor: Processes resell orders
"""

import random
import string
from decimal import Decimal
from typing import List, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    ResellLink, 
    ResellerProfile, 
    ResellerEarning, 
    PayoutTransaction,
    Order,
    Product,
    User
)
from .view_helpers import (
    _lookup_ifsc_details,
    _normalize_bank_account_number,
    _validate_bank_account_number_format,
    _validate_upi_format,
    _verify_upi_with_razorpay,
)


class ResellLinkGenerator:
    """Service class for creating and managing resell links"""
    
    @staticmethod
    def generate_unique_code(length: int = 8) -> str:
        """Generate a unique resell code"""
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=length))
            if not ResellLink.objects.filter(resell_code=code).exists():
                return code
    
    @staticmethod
    def validate_margin(margin_amount: Decimal, base_price: Decimal, max_percentage: Decimal = Decimal('50.0')) -> bool:
        """
        Validate margin amount against base price
        
        Args:
            margin_amount: The margin to validate
            base_price: The product's base price
            max_percentage: Maximum allowed margin percentage (default 50%)
        
        Returns:
            True if valid, raises ValidationError otherwise
        """
        if margin_amount <= 0:
            raise ValidationError("Margin must be greater than zero.")
        
        max_margin = base_price * (max_percentage / 100)
        if margin_amount > max_margin:
            raise ValidationError(
                f"Margin cannot exceed {max_percentage}% of product price (₹{max_margin})."
            )
        
        return True
    
    @classmethod
    def create_resell_link(cls, user_id: int, product_id: int, margin_amount: Decimal) -> ResellLink:
        """
        Create a new resell link
        
        Args:
            user_id: ID of the reseller user
            product_id: ID of the product to resell
            margin_amount: Margin amount to add to product price
        
        Returns:
            Created ResellLink instance
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            user = User.objects.get(id=user_id)
            product = Product.objects.get(id=product_id)
        except User.DoesNotExist:
            raise ValidationError("User not found.")
        except Product.DoesNotExist:
            raise ValidationError("Product not found.")
        
        # Check if user has reseller profile and is enabled
        try:
            reseller_profile = user.reseller_profile
            if not reseller_profile.is_reseller_enabled:
                raise ValidationError("User does not have reseller permissions enabled.")
        except ResellerProfile.DoesNotExist:
            raise ValidationError("User does not have a reseller profile.")
        
        # Validate product is active
        if not product.is_active:
            raise ValidationError("Product is not available for reselling.")
        
        # Validate margin
        cls.validate_margin(margin_amount, product.price)
        
        # Generate unique code
        resell_code = cls.generate_unique_code()
        
        # Calculate margin percentage
        margin_percentage = (margin_amount / product.price) * 100
        
        # Create resell link
        resell_link = ResellLink.objects.create(
            reseller=user,
            product=product,
            resell_code=resell_code,
            margin_amount=margin_amount,
            margin_percentage=margin_percentage,
            is_active=True
        )
        
        return resell_link
    
    @staticmethod
    def validate_resell_link(resell_code: str) -> ResellLink:
        """
        Validate a resell link by code
        
        Args:
            resell_code: The resell code to validate
        
        Returns:
            ResellLink instance if valid
        
        Raises:
            ValidationError: If link is invalid or inactive
        """
        try:
            resell_link = ResellLink.objects.select_related('reseller', 'product').get(
                resell_code=resell_code
            )
        except ResellLink.DoesNotExist:
            raise ValidationError("Invalid resell code.")
        
        if not resell_link.is_active:
            raise ValidationError("This resell link is no longer active.")
        
        if not resell_link.product.is_active:
            raise ValidationError("This product is no longer available.")
        
        # Check expiration
        if resell_link.expires_at and resell_link.expires_at < timezone.now():
            resell_link.is_active = False
            resell_link.save()
            raise ValidationError("This resell link has expired.")
        
        return resell_link
    
    @staticmethod
    def get_reseller_links(user_id: int, active_only: bool = False) -> List[ResellLink]:
        """
        Get all resell links for a user
        
        Args:
            user_id: ID of the reseller user
            active_only: If True, return only active links
        
        Returns:
            List of ResellLink instances
        """
        queryset = ResellLink.objects.filter(reseller_id=user_id).select_related('product')
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        return list(queryset.order_by('-created_at'))
    
    @staticmethod
    def deactivate_link(resell_link_id: int, user_id: int) -> ResellLink:
        """
        Deactivate a resell link
        
        Args:
            resell_link_id: ID of the resell link
            user_id: ID of the user (must be the owner)
        
        Returns:
            Updated ResellLink instance
        
        Raises:
            ValidationError: If link not found or user is not owner
        """
        try:
            resell_link = ResellLink.objects.get(id=resell_link_id, reseller_id=user_id)
        except ResellLink.DoesNotExist:
            raise ValidationError("Resell link not found or you don't have permission.")
        
        resell_link.is_active = False
        resell_link.save()
        
        return resell_link
    
    @staticmethod
    def reactivate_link(resell_link_id: int, user_id: int) -> ResellLink:
        """
        Reactivate a resell link
        
        Args:
            resell_link_id: ID of the resell link
            user_id: ID of the user (must be the owner)
        
        Returns:
            Updated ResellLink instance
        
        Raises:
            ValidationError: If link not found or user is not owner
        """
        try:
            resell_link = ResellLink.objects.get(id=resell_link_id, reseller_id=user_id)
        except ResellLink.DoesNotExist:
            raise ValidationError("Resell link not found or you don't have permission.")
        
        # Check if product is still active
        if not resell_link.product.is_active:
            raise ValidationError("Cannot reactivate link - product is no longer available.")
        
        resell_link.is_active = True
        resell_link.save()
        
        return resell_link


class MarginCalculator:
    """Service class for calculating margins and pricing"""
    
    @staticmethod
    def calculate_total_price(base_price: Decimal, margin: Decimal, quantity: int) -> Decimal:
        """
        Calculate total price including margin
        
        Args:
            base_price: Original product price
            margin: Margin amount per unit
            quantity: Number of units
        
        Returns:
            Total price (base + margin) * quantity
        """
        return (base_price + margin) * quantity
    
    @staticmethod
    def calculate_reseller_earnings(order: Order) -> Decimal:
        """
        Calculate total reseller earnings from an order
        
        Args:
            order: Order instance
        
        Returns:
            Total margin amount
        """
        if not order.is_resell:
            return Decimal('0.00')
        
        total_margin = Decimal('0.00')
        for item in order.items.all():
            total_margin += item.margin_amount * item.quantity
        
        return total_margin
    
    @staticmethod
    def validate_margin(margin: Decimal, base_price: Decimal) -> bool:
        """
        Validate margin amount
        
        Args:
            margin: Margin amount to validate
            base_price: Product base price
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If margin is invalid
        """
        if margin <= 0:
            raise ValidationError("Margin must be greater than zero.")
        
        max_margin = base_price * Decimal('0.5')
        if margin > max_margin:
            raise ValidationError(
                f"Margin cannot exceed 50% of product price (₹{max_margin})."
            )
        
        return True


class ResellerPaymentManager:
    """Service class for managing reseller earnings and payouts"""
    
    @staticmethod
    def get_reseller_balance(user_id: int) -> Decimal:
        """
        Get reseller's available balance
        
        Args:
            user_id: ID of the reseller user
        
        Returns:
            Available balance amount
        """
        try:
            profile = ResellerProfile.objects.get(user_id=user_id)
            return profile.available_balance
        except ResellerProfile.DoesNotExist:
            return Decimal('0.00')
    
    @staticmethod
    def get_earnings_history(user_id: int) -> List[ResellerEarning]:
        """
        Get earnings history for a reseller
        
        Args:
            user_id: ID of the reseller user
        
        Returns:
            List of ResellerEarning instances
        """
        return list(
            ResellerEarning.objects.filter(reseller_id=user_id)
            .select_related('order', 'resell_link', 'payout_transaction')
            .order_by('-created_at')
        )
    
    @staticmethod
    @transaction.atomic
    def process_payout(user_id: int, amount: Decimal, payout_method: str, payment_details: dict) -> PayoutTransaction:
        """
        Process a payout request
        
        Args:
            user_id: ID of the reseller user
            amount: Payout amount
            payout_method: Payment method (BANK_TRANSFER, UPI, WALLET)
            payment_details: Dictionary with payment details
        
        Returns:
            Created PayoutTransaction instance
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            user = User.objects.get(id=user_id)
            profile = user.reseller_profile
        except User.DoesNotExist:
            raise ValidationError("User not found.")
        except ResellerProfile.DoesNotExist:
            raise ValidationError("Reseller profile not found.")
        
        # Validate reseller is enabled
        if not profile.is_reseller_enabled:
            raise ValidationError("Reseller account is disabled.")
        
        # Validate amount
        if amount <= 0:
            raise ValidationError("Payout amount must be greater than zero.")
        
        if amount > profile.available_balance:
            raise ValidationError(
                f"Insufficient balance. Available: ₹{profile.available_balance}"
            )
        
        # Current model links payouts with whole earnings only (no split allocations),
        # so keep payout reconciliation deterministic by enforcing full-balance payouts.
        if amount != profile.available_balance:
            raise ValidationError(
                f"Please request full available balance only (₹{profile.available_balance})."
            )

        normalized_bank_account = _normalize_bank_account_number(
            payment_details.get('bank_account_number', '')
        )
        normalized_ifsc = (payment_details.get('bank_ifsc_code', '') or '').strip().upper()
        normalized_upi = (payment_details.get('upi_id', '') or '').strip().lower()

        # Validate payment details based on method
        if payout_method == 'BANK_TRANSFER':
            if not normalized_bank_account or not normalized_ifsc:
                raise ValidationError("Bank account details required for bank transfer.")
            if not _validate_bank_account_number_format(normalized_bank_account):
                raise ValidationError("Bank account number must be 6 to 34 digits.")
            valid_ifsc, _bank_name, _branch_name, ifsc_message = _lookup_ifsc_details(normalized_ifsc)
            if not valid_ifsc:
                raise ValidationError(ifsc_message or "Invalid IFSC code.")
        elif payout_method == 'UPI':
            if not normalized_upi:
                raise ValidationError("UPI ID required for UPI payout.")
            if not _validate_upi_format(normalized_upi):
                raise ValidationError("UPI ID format is invalid.")
            valid_upi, _upi_name, upi_message = _verify_upi_with_razorpay(normalized_upi)
            if not valid_upi:
                raise ValidationError(upi_message or "UPI ID could not be verified.")
        
        # Create payout transaction
        payout = PayoutTransaction.objects.create(
            reseller=user,
            amount=amount,
            payout_method=payout_method,
            status='INITIATED',
            bank_account=normalized_bank_account,
            upi_id=normalized_upi,
            initiated_at=timezone.now()
        )

        # Reserve current confirmed earnings for this payout to avoid paying
        # newly confirmed earnings that arrive after request initiation.
        reserved_count = ResellerEarning.objects.filter(
            reseller=user,
            status='CONFIRMED',
            payout_transaction__isnull=True
        ).update(payout_transaction=payout)
        if reserved_count == 0:
            raise ValidationError("No confirmed earnings available for payout.")
        
        # Deduct from available balance
        profile.available_balance -= amount
        profile.save()
        
        # Send notification
        send_resell_notification(
            user=user,
            notification_type='PAYOUT_INITIATED',
            title='Payout Request Initiated',
            message=f'Your payout request of ₹{amount} has been initiated and is pending admin approval.',
            link='/reseller/payout/'
        )
        
        return payout
    
    @staticmethod
    @transaction.atomic
    def complete_payout(payout_id: int, transaction_id: str = '', admin_notes: str = '') -> PayoutTransaction:
        """
        Complete a payout transaction (admin action)
        
        Args:
            payout_id: ID of the payout transaction
            transaction_id: External transaction ID from payment gateway
            admin_notes: Optional admin notes
        
        Returns:
            Updated PayoutTransaction instance
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            payout = PayoutTransaction.objects.select_related('reseller').get(id=payout_id)
        except PayoutTransaction.DoesNotExist:
            raise ValidationError("Payout transaction not found.")
        
        if payout.status != 'INITIATED':
            raise ValidationError(f"Cannot complete payout with status {payout.status}.")
        
        # Update payout status
        payout.status = 'COMPLETED'
        payout.transaction_id = transaction_id
        payout.admin_notes = admin_notes
        payout.completed_at = timezone.now()
        payout.save()
        
        # Update reserved earnings to PAID
        earnings = ResellerEarning.objects.filter(
            status='CONFIRMED',
            payout_transaction=payout
        )
        
        for earning in earnings:
            earning.status = 'PAID'
            earning.paid_at = timezone.now()
            earning.payout_transaction = payout
            earning.save()
        
        # Send notification
        send_resell_notification(
            user=payout.reseller,
            notification_type='PAYOUT_COMPLETED',
            title='Payout Completed',
            message=f'Your payout of ₹{payout.amount} has been completed successfully.',
            link='/reseller/payout/'
        )
        
        return payout
    
    @staticmethod
    @transaction.atomic
    def fail_payout(payout_id: int, admin_notes: str = '') -> PayoutTransaction:
        """
        Mark a payout as failed and refund balance (admin action)
        
        Args:
            payout_id: ID of the payout transaction
            admin_notes: Reason for failure
        
        Returns:
            Updated PayoutTransaction instance
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            payout = PayoutTransaction.objects.select_related('reseller', 'reseller__reseller_profile').get(id=payout_id)
        except PayoutTransaction.DoesNotExist:
            raise ValidationError("Payout transaction not found.")
        
        if payout.status not in ['INITIATED', 'PROCESSING']:
            raise ValidationError(f"Cannot fail payout with status {payout.status}.")
        
        # Update payout status
        payout.status = 'FAILED'
        payout.admin_notes = admin_notes
        payout.save()

        # Release reserved earnings for this payout.
        ResellerEarning.objects.filter(
            payout_transaction=payout,
            status='CONFIRMED'
        ).update(payout_transaction=None)
        
        # Refund balance to reseller
        profile = payout.reseller.reseller_profile
        profile.available_balance += payout.amount
        profile.save()
        
        # Send notification
        send_resell_notification(
            user=payout.reseller,
            notification_type='PAYOUT_FAILED',
            title='Payout Failed',
            message=f'Your payout request of ₹{payout.amount} has failed. Amount has been refunded to your balance. Reason: {admin_notes}',
            link='/reseller/payout/'
        )
        
        return payout


class ResellOrderProcessor:
    """Service class for processing resell orders"""
    
    @staticmethod
    @transaction.atomic
    def create_resell_order(cart_items, resell_link: ResellLink, customer, shipping_address, 
                           billing_address, payment_method: str, **kwargs) -> Order:
        """
        Create a resell order
        
        Args:
            cart_items: List of cart items
            resell_link: ResellLink instance
            customer: User instance (customer)
            shipping_address: Shipping address text
            billing_address: Billing address text
            payment_method: Payment method
            **kwargs: Additional order fields
        
        Returns:
            Created Order instance
        """
        from .models import OrderItem
        
        # Validate resell link
        if not resell_link.is_active:
            raise ValidationError("Resell link is no longer active.")
        
        # Normalize cart items and calculate amounts.
        # Margin is applied only to the product linked by the resell link.
        base_amount = Decimal('0.00')
        total_margin = Decimal('0.00')
        applicable_link_qty = 0
        normalized_items = []

        def _extract_item(item):
            if isinstance(item, dict):
                product = item.get('product')
                quantity = int(item.get('quantity', 0) or 0)
                size = item.get('size', '') or ''
                color = item.get('color', '') or ''
            else:
                product = getattr(item, 'product', None)
                quantity = int(getattr(item, 'quantity', 0) or 0)
                size = getattr(item, 'size', '') or ''
                color = getattr(item, 'color', '') or ''
            return product, quantity, size, color

        for raw_item in cart_items:
            product, quantity, size, color = _extract_item(raw_item)
            if not product or quantity <= 0:
                continue

            base_price = Decimal(str(product.price or 0))
            margin_amount = Decimal(str(resell_link.margin_amount or 0)) if product.id == resell_link.product_id else Decimal('0.00')
            if margin_amount > 0:
                applicable_link_qty += quantity

            base_amount += base_price * quantity
            total_margin += margin_amount * quantity
            normalized_items.append((product, quantity, size, color, base_price, margin_amount))

        if not normalized_items:
            raise ValidationError("No valid cart items found for creating order.")

        if applicable_link_qty <= 0:
            raise ValidationError("Linked resell product is not present in checkout items.")
        
        subtotal = base_amount + total_margin
        tax = kwargs.get('tax', Decimal('0.00'))
        shipping_cost = kwargs.get('shipping_cost', Decimal('0.00'))
        coupon_discount = kwargs.get('coupon_discount', Decimal('0.00'))
        points_discount = kwargs.get('points_discount', Decimal('0.00'))
        total_amount = subtotal + tax + shipping_cost - coupon_discount - points_discount
        if total_amount < Decimal('0.00'):
            total_amount = Decimal('0.00')
        
        # Create order
        order = Order.objects.create(
            user=customer,
            is_resell=True,
            reseller=resell_link.reseller,
            resell_link=resell_link,
            base_amount=base_amount,
            total_margin=total_margin,
            subtotal=subtotal,
            tax=tax,
            shipping_cost=shipping_cost,
            coupon_discount=coupon_discount,
            total_amount=total_amount,
            shipping_address=shipping_address,
            billing_address=billing_address,
            payment_method=payment_method,
            payment_status=kwargs.get('payment_status', 'PENDING'),
            order_status='PENDING',
            coupon=kwargs.get('coupon'),
        )
        
        # Create order items
        for product, quantity, size, color, base_price, margin_amount in normalized_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                base_price=base_price,
                margin_amount=margin_amount,
                product_price=base_price + margin_amount,
                product_image=product.image.url if getattr(product, 'image', None) else '',
                quantity=quantity,
                size=size,
                color=color,
            )
        
        # Create reseller earning record
        ResellerEarning.objects.create(
            reseller=resell_link.reseller,
            order=order,
            resell_link=resell_link,
            margin_amount=total_margin,
            status='PENDING'
        )
        
        # Update resell link statistics
        resell_link.orders_count += 1
        resell_link.total_earnings += total_margin
        resell_link.save()
        
        return order



def confirm_reseller_earnings(order):
    """
    Confirm reseller earnings after order delivery
    
    Args:
        order: Order instance (must be DELIVERED and is_resell=True)
    
    Returns:
        ResellerEarning instance
    
    Raises:
        ValidationError: If validation fails
    """
    from django.utils import timezone
    from django.core.exceptions import ValidationError
    
    # Validate order is a resell order
    if not order.is_resell:
        raise ValidationError("Order is not a resell order.")
    
    # Validate order status is DELIVERED
    if order.order_status != 'DELIVERED':
        raise ValidationError("Order must be DELIVERED to confirm earnings.")
    
    # Get reseller earning record
    try:
        earning = ResellerEarning.objects.get(order=order)
    except ResellerEarning.DoesNotExist:
        raise ValidationError("Reseller earning record not found for this order.")
    
    # Validate earning status is PENDING
    if earning.status != 'PENDING':
        raise ValidationError(f"Earning already {earning.status.lower()}. Cannot confirm again.")
    
    # Update earning status
    earning.status = 'CONFIRMED'
    earning.confirmed_at = timezone.now()
    earning.save(update_fields=['status', 'confirmed_at'])
    
    # Update reseller profile balance
    try:
        reseller_profile = earning.reseller.reseller_profile
    except ResellerProfile.DoesNotExist:
        raise ValidationError("Reseller profile not found.")
    
    reseller_profile.available_balance += earning.margin_amount
    reseller_profile.total_earnings += earning.margin_amount
    reseller_profile.total_orders += 1
    reseller_profile.save(update_fields=['available_balance', 'total_earnings', 'total_orders'])
    
    # Send notification to reseller
    send_resell_notification(
        user=earning.reseller,
        notification_type='EARNING_CONFIRMED',
        title='Earnings Confirmed',
        message=f'Your earnings of ₹{earning.margin_amount} from order #{order.order_number} have been confirmed and added to your available balance.',
        link=f'/reseller/earnings/'
    )
    
    return earning



def send_resell_notification(user, notification_type, title, message, link=''):
    """
    Send a notification to a reseller
    
    Args:
        user: User instance (reseller)
        notification_type: Type of notification (EARNING_CONFIRMED, PAYOUT_COMPLETED, etc.)
        title: Notification title
        message: Notification message
        link: Optional link to related page
    
    Returns:
        Notification instance or None if failed
    """
    try:
        from .models import Notification
        
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link
        )
        return notification
    except Exception as e:
        # Log error but don't raise - notifications are not critical
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send notification to {user.username}: {str(e)}")
        return None



def cancel_resell_order(order):
    """
    Handle cancellation of a resell order
    
    Args:
        order: Order instance (must be is_resell=True)
    
    Returns:
        ResellerEarning instance
    
    Raises:
        ValidationError: If validation fails
    """
    from django.utils import timezone
    from django.core.exceptions import ValidationError
    
    # Validate order is a resell order
    if not order.is_resell:
        raise ValidationError("Order is not a resell order.")
    
    # Get reseller earning record
    try:
        earning = ResellerEarning.objects.get(order=order)
    except ResellerEarning.DoesNotExist:
        raise ValidationError("Reseller earning record not found for this order.")
    
    # If already cancelled, skip
    if earning.status == 'CANCELLED':
        return earning
    
    # Store previous status for balance adjustment
    previous_status = earning.status
    
    # Update earning status to CANCELLED
    earning.status = 'CANCELLED'
    earning.save(update_fields=['status'])
    
    # If earning was CONFIRMED, deduct from available balance
    if previous_status == 'CONFIRMED':
        try:
            reseller_profile = earning.reseller.reseller_profile
        except ResellerProfile.DoesNotExist:
            raise ValidationError("Reseller profile not found.")
        
        # Deduct margin from available balance
        reseller_profile.available_balance -= earning.margin_amount
        # Ensure balance doesn't go negative
        if reseller_profile.available_balance < 0:
            reseller_profile.available_balance = Decimal('0.00')
        reseller_profile.save(update_fields=['available_balance'])
    
    # Update resell link statistics (if this earning came from a share link)
    resell_link = earning.resell_link
    if resell_link:
        if resell_link.orders_count > 0:
            resell_link.orders_count -= 1
        resell_link.total_earnings -= earning.margin_amount
        if resell_link.total_earnings < 0:
            resell_link.total_earnings = Decimal('0.00')
        resell_link.save(update_fields=['orders_count', 'total_earnings'])
    
    # Send notification to reseller
    send_resell_notification(
        user=earning.reseller,
        notification_type='ORDER_CANCELLED',
        title='Order Cancelled',
        message=f'Order #{order.order_number} has been cancelled. Your earnings of ₹{earning.margin_amount} have been reversed.',
        link=f'/reseller/earnings/'
    )
    
    return earning
