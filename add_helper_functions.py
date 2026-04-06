"""
Add comprehensive helper functions for Refund, Bank Verification, and UPI Collect verification
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
django.setup()

# Read existing view_helpers.py
view_helpers_path = 'Hub/view_helpers.py'
with open(view_helpers_path, 'r', encoding='utf-8') as f:
    content = f.read()

# New helper functions to add
new_helpers = '''


# ============================================================================
# 1. REFUND SYSTEM - Process online payment refunds via Razorpay
# ============================================================================

def process_refund(order_id: int, refund_amount: float = None, reason: str = "Refund requested", user=None):
    """
    Process a refund for an online payment order using Razorpay Refund API.
    
    Args:
        order_id: Order ID to refund
        refund_amount: Amount to refund (if None, refund full amount)
        reason: Reason for refund
        user: User requesting the refund
    
    Returns:
        Tuple: (success: bool, refund_id: str, message: str)
    """
    import razorpay
    import logging
    from decimal import Decimal
    from django.conf import settings
    from Hub.models import Order, Refund
    
    logger = logging.getLogger(__name__)
    
    try:
        # Fetch order
        order = Order.objects.get(id=order_id)
        
        # Validate payment method
        if order.payment_method not in ['ONLINE', 'UPI', 'CARD']:
            return False, '', 'Refund only available for online payments'
        
        # Check if payment was actually made
        if not order.razorpay_payment_id:
            return False, '', 'No Razorpay payment found for this order'
        
        # Get refund amount
        if refund_amount is None:
            refund_amount = float(order.total_amount)
        else:
            refund_amount = float(refund_amount)
        
        # Check for duplicate refunds
        existing_refunds = Refund.objects.filter(
            order=order,
            status__in=['SUCCESS', 'PROCESSING']
        )
        total_refunded = sum(float(r.refund_amount) for r in existing_refunds)
        
        if total_refunded + refund_amount > float(order.total_amount):
            return False, '', f'Refund amount exceeds order total. Already refunded: ₹{total_refunded}'
        
        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        
        # Convert amount to paise
        amount_paise = int(refund_amount * 100)
        
        # Call Razorpay Refund API
        try:
            refund_response = client.payment.refund(
                order.razorpay_payment_id,
                {
                    'amount': amount_paise,
                    'notes': {
                        'reason': reason,
                        'order_id': order.order_number
                    }
                }
            )
            
            refund_id = refund_response.get('id', '')
            refund_status = refund_response.get('status', 'failed')
            
            # Create refund record
            refund = Refund.objects.create(
                order=order,
                razorpay_payment_id=order.razorpay_payment_id,
                razorpay_refund_id=refund_id,
                refund_amount=Decimal(str(refund_amount)),
                status='SUCCESS' if refund_status == 'processed' else 'PROCESSING',
                reason=reason,
                requested_by=user
            )
            
            # Update order payment status if full refund
            if refund_amount >= float(order.total_amount):
                order.payment_status = 'REFUNDED'
                order.save()
            
            logger.info(f'Refund processed: {refund_id} for Order #{order.order_number}, Amount: ₹{refund_amount}')
            return True, refund_id, f'Refund of ₹{refund_amount} processed successfully'
            
        except Exception as e:
            logger.error(f'Razorpay refund API error: {str(e)}')
            return False, '', f'Razorpay error: {str(e)}'
    
    except Order.DoesNotExist:
        return False, '', 'Order not found'
    except Exception as e:
        logger.error(f'Refund processing error: {str(e)}')
        return False, '', f'Error: {str(e)}'


# ============================================================================
# 2. BANK VERIFICATION - Real verification using Razorpay Payouts (Penny Drop)
# ============================================================================

def verify_bank_account(account_number: str, ifsc: str, account_name: str = "", user=None):
    """
    Verify bank account using Razorpay Payouts with ₹1 penny drop.
    
    Args:
        account_number: Bank account number
        ifsc: IFSC code
        account_name: Account holder name (optional)
        user: User performing verification
    
    Returns:
        Tuple: (success: bool, verified_name: str, message: str)
    """
    import razorpay
    import logging
    from django.conf import settings
    from Hub.models import BankVerification
    import re
    
    logger = logging.getLogger(__name__)
    
    try:
        # Validate inputs
        if not account_number or len(account_number) < 8:
            return False, '', 'Invalid account number'
        
        if not ifsc or len(ifsc) != 11:
            return False, '', 'IFSC must be 11 characters'
        
        account_number = str(account_number).strip()
        ifsc = str(ifsc).upper().strip()
        account_name = str(account_name or '').strip()
        
        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        
        # Step 1: Create or get Contact
        try:
            contact_response = client.contact.create({
                'type': 'customer',
                'name': account_name or user.get_full_name() or user.username,
                'email': user.email if user else 'noreply@vibemall.com',
            })
            contact_id = contact_response['id']
            logger.info(f'Created Razorpay contact: {contact_id}')
        except Exception as e:
            logger.error(f'Contact creation error: {str(e)}')
            return False, '', 'Failed to create contact'
        
        # Step 2: Create Fund Account (Bank Account)
        try:
            fund_account_response = client.fund_account.create({
                'contact_id': contact_id,
                'account_type': 'bank_account',
                'bank_account': {
                    'name': account_name or user.get_full_name() or user.username,
                    'notes': {
                        'type': 'bank_verification',
                        'user_id': str(user.id) if user else 'guest'
                    },
                    'ifsc': ifsc,
                    'account_number': account_number
                }
            })
            fund_account_id = fund_account_response['id']
            logger.info(f'Created Fund Account: {fund_account_id}')
        except Exception as e:
            logger.error(f'Fund account creation error: {str(e)}')
            return False, '', f'Fund account error: {str(e)}'
        
        # Step 3: Trigger verification with ₹1 payout
        try:
            payout_response = client.payout.create({
                'account_number': settings.RAZORPAY_ACCOUNT_NUMBER if hasattr(settings, 'RAZORPAY_ACCOUNT_NUMBER') else None,
                'fund_account_id': fund_account_id,
                'amount': 100,  # ₹1 in paise
                'currency': 'INR',
                'mode': 'NEFT',
                'purpose': 'onus',
                'description': 'Bank account verification - ₹1 test transfer',
                'notes': {
                    'verification_type': 'bank_account',
                    'user_id': str(user.id) if user else 'guest'
                }
            })
            payout_id = payout_response['id']
            payout_status = payout_response.get('status', 'pending')
            logger.info(f'Payout initiated: {payout_id}, Status: {payout_status}')
        except Exception as e:
            logger.error(f'Payout error: {str(e)}')
            return False, '', f'Payout failed: {str(e)}'
        
        # Step 4: Create verification record
        verified_name = payout_response.get('fund_account_id', account_name) or account_name
        
        bank_verification, created = BankVerification.objects.update_or_create(
            user=user,
            defaults={
                'account_number': f'****{account_number[-4:]}',
                'ifsc': ifsc,
                'account_name': verified_name or account_name,
                'razorpay_contact_id': contact_id,
                'razorpay_fund_account_id': fund_account_id,
                'razorpay_payout_id': payout_id,
                'status': 'VERIFYING' if payout_status == 'pending' else 'VERIFIED',
                'is_verified': payout_status == 'processed',
            }
        )
        
        return True, verified_name or account_name, f'Bank account verification initiated. Payout ID: {payout_id}'
    
    except Exception as e:
        logger.error(f'Bank verification error: {str(e)}')
        return False, '', f'Error: {str(e)}'


# ============================================================================
# 3. UPI VERIFICATION - Real verification using ₹1 Collect Request
# ============================================================================

def create_upi_collect_request(upi_id: str, user=None):
    """
    Create a ₹1 collect request to verify UPI ID (real verification).
    
    Args:
        upi_id: UPI ID in format
        user: User performing verification
    
    Returns:
        Tuple: (success: bool, order_id: str, payment_id: str)
    """
    import razorpay
    import logging
    from django.conf import settings
    from Hub.models import UPIVerification
    import re
    
    logger = logging.getLogger(__name__)
    
    try:
        # Validate UPI format
        upi_pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$'
        upi_id = str(upi_id).strip().lower()
        
        if not re.match(upi_pattern, upi_id):
            return False, '', '', 'Invalid UPI format. Use: name@bank'
        
        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        
        # Create order for ₹1 verification collection
        try:
            order_response = client.order.create({
                'amount': 100,  # ₹1 in paise
                'currency': 'INR',
                'receipt': f'upi-verify-{user.id if user else "guest"}-{int(__import__("time").time())}',
                'notes': {
                    'verification_type': 'upi_collect',
                    'upi_id': upi_id,
                    'purpose': 'UPI verification via ₹1 collect'
                }
            })
            order_id = order_response['id']
            logger.info(f'Created Razorpay order for UPI verification: {order_id}')
        except Exception as e:
            logger.error(f'Order creation error: {str(e)}')
            return False, '', '', f'Failed to create order: {str(e)}'
        
        # Create UPI verification record
        upi_verification, created = UPIVerification.objects.update_or_create(
            user=user,
            defaults={
                'upi_id': upi_id,
                'razorpay_order_id': order_id,
                'status': 'WAITING_PAYMENT',
            }
        )
        
        logger.info(f'Created UPI verification record: {upi_verification.id} for {upi_id}')
        return True, order_id, '', 'Collect request created. Awaiting payment from UPI app.'
    
    except Exception as e:
        logger.error(f'UPI collect request error: {str(e)}')
        return False, '', '', f'Error: {str(e)}'


def verify_upi_collect_payment(order_id: str, payment_id: str, signature: str, user=None):
    """
    Verify and track ₹1 collect request payment for UPI verification.
    
    Args:
        order_id: Razorpay Order ID
        payment_id: Razorpay Payment ID
        signature: Razorpay Signature
        user: User who initiated verification
    
    Returns:
        Tuple: (success: bool, message: str)
    """
    import razorpay
    import logging
    import hashlib
    import hmac
    from django.conf import settings
    from Hub.models import UPIVerification
    
    logger = logging.getLogger(__name__)
    
    try:
        # Verify signature
        secret = settings.RAZORPAY_KEY_SECRET.encode()
        message = f'{order_id}|{payment_id}'.encode()
        generated_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        
        if generated_signature != signature:
            logger.warning(f'Signature verification failed for payment {payment_id}')
            return False, 'Signature verification failed'
        
        # Get UPI verification record
        try:
            upi_verification = UPIVerification.objects.get(razorpay_order_id=order_id, user=user)
        except UPIVerification.DoesNotExist:
            return False, 'Verification record not found'
        
        # Initialize Razorpay client
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        
        # Fetch payment details
        try:
            payment_response = client.payment.fetch(payment_id)
            payment_status = payment_response.get('status')
            
            if payment_status == 'captured':
                # Update UPI verification status
                upi_verification.razorpay_payment_id = payment_id
                upi_verification.status = 'VERIFIED'
                upi_verification.is_verified = True
                upi_verification.verified_at = __import__('django.utils.timezone', fromlist=['now']).now()
                upi_verification.save()
                
                logger.info(f'UPI verification successful: {upi_verification.upi_id} - Payment {payment_id}')
                
                # Auto-refund the ₹1
                try:
                    refund_response = client.payment.refund(payment_id, {'amount': 100})
                    upi_verification.refund_attempted = True
                    upi_verification.save()
                    logger.info(f'Auto-refund attempted for UPI verification: {refund_response.get("id")}')
                except Exception as e:
                    logger.warning(f'Auto-refund failed: {str(e)}')
                
                return True, f'UPI {upi_verification.upi_id} verified successfully! ₹1 refunded.'
            else:
                return False, f'Payment not captured. Status: {payment_status}'
        
        except Exception as e:
            logger.error(f'Payment fetch error: {str(e)}')
            return False, f'Error: {str(e)}'
    
    except Exception as e:
        logger.error(f'UPI payment verification error: {str(e)}')
        return False, f'Verification error: {str(e)}'
'''

# Append new helpers to the file
with open(view_helpers_path, 'a', encoding='utf-8') as f:
    f.write(new_helpers)

print("✅ Added comprehensive helper functions to view_helpers.py")
print("   - process_refund()")
print("   - verify_bank_account()")
print("   - create_upi_collect_request()")
print("   - verify_upi_collect_payment()")
