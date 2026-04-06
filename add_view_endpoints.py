"""
Script to add 3 new view endpoints to views.py:
1. POST /refund - Process online payment refunds
2. POST /verify-bank - Bank account verification with penny drop
3. POST /verify-upi-collect - Create ₹1 collect request for UPI verification
4. POST /verify-upi-collect-status - Check collect request payment status
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')

# Read the current views.py
views_file_path = 'Hub/views.py'
with open(views_file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# New view endpoints to add
new_endpoints = '''

# ============================================================================
# REFUND SYSTEM - Process online payment refunds
# ============================================================================

@login_required
@require_http_methods(["POST"])
def process_refund_endpoint(request):
    """
    Process refund for an order.
    
    POST /api/refund/
    Body: {
        "order_id": 123,
        "refund_amount": 1000.50,  // optional, defaults to full amount
        "reason": "Customer requested refund"
    }
    """
    from .view_helpers import process_refund
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        refund_amount = data.get('refund_amount')
        reason = data.get('reason', 'Refund requested')
        
        if not order_id:
            return JsonResponse({'status': 'failed', 'message': 'Order ID required'}, status=400)
        
        # Call helper function
        success, refund_id, message = process_refund(
            order_id=order_id,
            refund_amount=refund_amount,
            reason=reason,
            user=request.user
        )
        
        if success:
            return JsonResponse({
                'status': 'success',
                'refund_id': refund_id,
                'message': message
            })
        else:
            return JsonResponse({
                'status': 'failed',
                'message': message
            }, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'failed', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'Refund endpoint error: {str(e)}')
        return JsonResponse({'status': 'failed', 'message': str(e)}, status=500)


# ============================================================================
# BANK VERIFICATION - Real bank account verification via penny drop
# ============================================================================

@login_required
@require_http_methods(["POST"])
def verify_bank_endpoint(request):
    """
    Verify bank account using ₹1 penny drop test.
    
    POST /api/verify-bank/
    Body: {
        "account_number": "12345678901234",
        "ifsc": "HDFC0000001",
        "account_name": "John Doe"  // optional
    }
    
    Response: {
        "status": "verified" or "failed",
        "account_name": "Name from bank",
        "message": "..."
    }
    """
    from .view_helpers import verify_bank_account
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = json.loads(request.body)
        account_number = data.get('account_number', '').strip()
        ifsc = data.get('ifsc', '').strip()
        account_name = data.get('account_name', '').strip()
        
        if not account_number or not ifsc:
            return JsonResponse({
                'status': 'failed',
                'message': 'Account number and IFSC required'
            }, status=400)
        
        # Call helper function
        success, verified_name, message = verify_bank_account(
            account_number=account_number,
            ifsc=ifsc,
            account_name=account_name,
            user=request.user
        )
        
        if success:
            return JsonResponse({
                'status': 'verified',
                'account_name': verified_name,
                'message': message
            })
        else:
            return JsonResponse({
                'status': 'failed',
                'message': message
            }, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'failed', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'Bank verification endpoint error: {str(e)}')
        return JsonResponse({'status': 'failed', 'message': str(e)}, status=500)


# ============================================================================
# UPI VERIFICATION - Real ₹1 collect request verification
# ============================================================================

@login_required
@require_http_methods(["POST"])
def create_upi_collect_endpoint(request):
    """
    Create a ₹1 collect request for UPI verification.
    User will receive payment request in their UPI app.
    
    POST /api/verify-upi-collect/
    Body: {
        "upi_id": "john.doe@okhdfcbank"
    }
    
    Response: {
        "status": "success" or "failed",
        "order_id": "order_xxxxx",
        "message": "Collect request created...",
        "next_action": "user_payment"  // User needs to complete payment in UPI app
    }
    """
    from .view_helpers import create_upi_collect_request
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = json.loads(request.body)
        upi_id = data.get('upi_id', '').strip().lower()
        
        if not upi_id:
            return JsonResponse({
                'status': 'failed',
                'message': 'UPI ID required'
            }, status=400)
        
        # Call helper function to create collect request
        success, order_id, payment_id, message = create_upi_collect_request(
            upi_id=upi_id,
            user=request.user
        )
        
        if success:
            return JsonResponse({
                'status': 'success',
                'order_id': order_id,
                'payment_id': payment_id,
                'message': message,
                'next_action': 'user_payment'
            })
        else:
            return JsonResponse({
                'status': 'failed',
                'message': message
            }, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'failed', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'UPI collect endpoint error: {str(e)}')
        return JsonResponse({'status': 'failed', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def verify_upi_collect_status_endpoint(request):
    """
    Verify and confirm UPI collect request payment.
    Called after user completes payment in UPI app.
    
    POST /api/verify-upi-collect-status/
    Body: {
        "order_id": "order_xxxxx",
        "payment_id": "pay_xxxxx",
        "signature": "signature_from_razorpay"
    }
    
    Response: {
        "status": "verified" or "failed",
        "message": "UPI verified successfully!"
    }
    """
    from .view_helpers import verify_upi_collect_payment
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id', '').strip()
        payment_id = data.get('payment_id', '').strip()
        signature = data.get('signature', '').strip()
        
        if not all([order_id, payment_id, signature]):
            return JsonResponse({
                'status': 'failed',
                'message': 'order_id, payment_id, and signature required'
            }, status=400)
        
        # Call helper function to verify payment
        success, message = verify_upi_collect_payment(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            user=request.user
        )
        
        if success:
            return JsonResponse({
                'status': 'verified',
                'message': message
            })
        else:
            return JsonResponse({
                'status': 'failed',
                'message': message
            }, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'failed', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'UPI collect status endpoint error: {str(e)}')
        return JsonResponse({'status': 'failed', 'message': str(e)}, status=500)
'''

# Append new endpoints
with open(views_file_path, 'a', encoding='utf-8') as f:
    f.write(new_endpoints)

print("✅ Added 4 new view endpoints to views.py")
print("   - POST /api/refund/")
print("   - POST /api/verify-bank/")
print("   - POST /api/verify-upi-collect/")  
print("   - POST /api/verify-upi-collect-status/")
