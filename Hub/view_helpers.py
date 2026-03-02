from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.http import HttpRequest

from .models import Cart, Product


def _split_full_name(full_name: Optional[str]) -> Tuple[str, str]:
    """Split a full name into first and last name parts."""
    parts = (full_name or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def _get_checkout_items(request: HttpRequest) -> Tuple[List[Any], Optional[Dict[str, Any]], float]:
    """Return checkout items, buy-now item (if present), and total price."""
    cart_items: List[Any] = []
    buy_now_item: Optional[Dict[str, Any]] = None
    total_price: float = 0

    if 'buy_now_item' in request.session:
        buy_now_data = request.session['buy_now_item']
        try:
            product = Product.objects.get(id=buy_now_data['product_id'])
            buy_now_item = {
                'product': product,
                'quantity': buy_now_data['quantity'],
                'price': float(buy_now_data['price']),
                'subtotal': float(buy_now_data['price']) * buy_now_data['quantity']
            }
            total_price = buy_now_item['subtotal']
            cart_items = [buy_now_item]
        except Product.DoesNotExist:
            del request.session['buy_now_item']
    else:
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        total_price = sum(item.get_total_price() for item in cart_items)

    return cart_items, buy_now_item, total_price


def _get_checkout_total_quantity(cart_items: List[Any]) -> int:
    """Compute total quantity from cart model items or buy-now dict items."""
    total_qty = 0
    for item in cart_items:
        if isinstance(item, dict):
            total_qty += int(item.get('quantity', 0) or 0)
        else:
            total_qty += int(getattr(item, 'quantity', 0) or 0)
    return max(total_qty, 0)


def _get_checkout_item_product_and_qty(item: Any) -> Tuple[Optional[Product], int]:
    """Extract product and quantity from a cart item or buy-now dict item."""
    if isinstance(item, dict):
        product = item.get('product')
        quantity = int(item.get('quantity', 0) or 0)
    else:
        product = getattr(item, 'product', None)
        quantity = int(getattr(item, 'quantity', 0) or 0)
    return product, max(quantity, 0)


def _get_resell_link_matching_quantity(cart_items: List[Any], resell_link: Any) -> int:
    """Return total quantity that matches the active resell-link product."""
    if not resell_link or not getattr(resell_link, 'product_id', None):
        return 0
    total_qty = 0
    for item in cart_items:
        product, quantity = _get_checkout_item_product_and_qty(item)
        if product and getattr(product, 'id', None) == resell_link.product_id:
            total_qty += quantity
    return max(total_qty, 0)


def _get_checkout_min_unit_price(cart_items: List[Any]) -> Decimal:
    """Return minimum unit price across checkout items."""
    prices: List[Decimal] = []
    for item in cart_items:
        product, _quantity = _get_checkout_item_product_and_qty(item)
        if product is not None:
            prices.append(Decimal(str(getattr(product, 'price', 0) or 0)))
    if not prices:
        return Decimal('0')
    return min(prices)


def _verify_upi_with_razorpay(upi_id: str, logger: Any = None) -> Tuple[bool, str, str]:
    """Validate a UPI ID via Razorpay and return (is_valid, name, error)."""
    razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
    razorpay_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not razorpay_key or not razorpay_secret:
        return False, '', 'Razorpay keys missing'

    url = 'https://api.razorpay.com/v1/payments/validate/vpa'
    payload = urlencode({'vpa': upi_id}).encode('utf-8')
    auth = base64.b64encode(f"{razorpay_key}:{razorpay_secret}".encode('utf-8')).decode('utf-8')
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth}',
    }

    request = Request(url, data=payload, headers=headers, method='POST')
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        if logger and getattr(settings, 'RAZORPAY_UPI_DEBUG', False):
            masked_upi = f"{upi_id[:3]}***{upi_id[upi_id.find('@'):]}" if '@' in upi_id else '***'
            logger.info('Razorpay UPI validate response for %s: %s', masked_upi, data)
    except HTTPError as exc:
        body = ''
        try:
            body = exc.read().decode('utf-8')
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {}
        if logger and getattr(settings, 'RAZORPAY_UPI_DEBUG', False):
            logger.warning('Razorpay UPI validate HTTPError %s: %s', exc.code, body)
        message = (
            parsed.get('error', {}).get('description')
            if isinstance(parsed, dict)
            else ''
        )
        return False, '', message or f'Validation failed: {exc.code}'
    except URLError:
        return False, '', 'Unable to reach Razorpay'
    except Exception:
        return False, '', 'Validation failed'

    name = (data.get('customer_name') or data.get('name') or '').strip()
    valid = data.get('success') is True or data.get('valid') is True or bool(name)
    if not valid:
        return False, '', 'UPI ID not found'

    return True, name, ''


def _validate_indian_pincode(pincode: Optional[str]) -> bool:
    """Validate an Indian pincode using external postal API."""
    if not re.fullmatch(r"[0-9]{6}", pincode or ''):
        return False

    url = f"https://api.postalpincode.in/pincode/{pincode}"
    request = Request(url, method='GET')
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
        result = data[0] if isinstance(data, list) and data else None
        if not result or result.get('Status') != 'Success':
            return False
        return True
    except Exception:
        return False


def _lookup_ifsc_details(ifsc_code: Optional[str]) -> Tuple[bool, str, str, str]:
    """Lookup IFSC details and return (ok, bank, branch, error_message)."""
    if not ifsc_code:
        return False, '', '', 'IFSC code is required.'
    ifsc_code = ifsc_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc_code):
        return False, '', '', 'Please enter a valid IFSC code.'

    url = f"https://ifsc.razorpay.com/{ifsc_code}"
    try:
        with urlopen(url, timeout=6) as response:
            payload = json.loads(response.read().decode('utf-8'))
        bank = (payload.get('BANK') or '').strip()
        branch = (payload.get('BRANCH') or '').strip()
        if not bank and not branch:
            return False, '', '', 'IFSC details not found.'
        return True, bank, branch, ''
    except HTTPError as exc:
        if exc.code == 404:
            return False, '', '', 'IFSC details not found.'
        return False, '', '', 'Unable to fetch IFSC details.'
    except URLError:
        return False, '', '', 'Unable to reach IFSC service.'
    except Exception:
        return False, '', '', 'IFSC lookup failed. Try again later.'
