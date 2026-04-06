#!/usr/bin/env python
import json

# Read the current views.py
with open(r"Hub\views.py", 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new verify_upi view
verify_upi_view = '''

# ===== UPI VERIFICATION ENDPOINT =====
@login_required(login_url='login')
@require_POST
def verify_upi(request):
    """Verify UPI ID and fetch customer name via Razorpay"""
    from .view_helpers import _verify_upi_with_razorpay
    import logging
    
    try:
        data = json.loads(request.body)
        upi_id = data.get('upi_id', '').strip()
        
        if not upi_id:
            return JsonResponse({'valid': False, 'error': 'UPI ID is required'})
        
        # Validate UPI format (basic check)
        if '@' not in upi_id or len(upi_id) < 5:
            return JsonResponse({'valid': False, 'error': 'Invalid UPI ID format'})
        
        # Call the helper function to verify UPI
        logger = logging.getLogger(__name__)
        is_valid, name, error = _verify_upi_with_razorpay(upi_id, logger=logger)
        
        if is_valid:
            return JsonResponse({'valid': True, 'name': name})
        else:
            return JsonResponse({'valid': False, 'error': error or 'UPI verification failed'})
    
    except json.JSONDecodeError:
        return JsonResponse({'valid': False, 'error': 'Invalid request'}, status=400)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'UPI verification error: {str(e)}')
        return JsonResponse({'valid': False, 'error': 'Verification failed'}, status=500)
'''

# Append the new view to the end
content = content + verify_upi_view

# Write back
with open(r"Hub\views.py", 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added verify_upi view to views.py")
