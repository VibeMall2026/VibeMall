"""
n8n AI Product Ingestion API
============================
Endpoint: POST /api/n8n/product/

Receives structured product data from n8n HTTP Request node
and creates or updates products in the existing Product model.

Security: Uses API key authentication (set N8N_API_KEY in .env)
"""

import json
import logging
import requests
import tempfile
import os
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.text import slugify

from Hub.models import Product

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: API Key Authentication
# ---------------------------------------------------------------------------

def _verify_api_key(request):
    """
    Verify the API key from request header.
    Set N8N_API_KEY in your .env / Django settings.
    n8n should send: Authorization: Bearer <key>
    """
    expected_key = getattr(settings, 'N8N_API_KEY', None)
    if not expected_key:
        # If no key configured, skip auth (not recommended for production)
        logger.warning("N8N_API_KEY not set — endpoint is unprotected!")
        return True

    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return token == expected_key

    # Also accept as query param for testing
    return request.GET.get('api_key') == expected_key


# ---------------------------------------------------------------------------
# Helper: Parse & Validate Payload
# ---------------------------------------------------------------------------

def _parse_payload(request):
    """
    Parse JSON body from request.
    Returns (data_dict, error_string).
    """
    try:
        data = json.loads(request.body)
        return data, None
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"Invalid JSON: {str(e)}"


def _validate_required(data):
    """
    Validate required fields: title, price.
    Returns list of error messages (empty = valid).
    """
    errors = []
    if not data.get('title', '').strip():
        errors.append("'title' is required and cannot be empty.")
    try:
        price_val = float(data.get('price', ''))
        if price_val < 0:
            errors.append("'price' must be a non-negative number.")
    except (TypeError, ValueError):
        errors.append("'price' is required and must be a valid number.")
    return errors


# ---------------------------------------------------------------------------
# Helper: Map n8n payload → Product fields
# ---------------------------------------------------------------------------

def _map_to_product_fields(data):
    """
    Map incoming n8n JSON to existing Product model fields.

    n8n field        → Product field
    ─────────────────────────────────
    title            → name
    price            → price
    description      → description
    stock            → stock
    weight           → weight
    extra_details    → tags / brand (extracted)
    sizes            → size (joined as comma string)
    style_code       → sku
    fabric/work      → care_info (combined)
    product_type     → sub_category
    """
    fields = {}

    # --- Required ---
    fields['name'] = str(data['title']).strip()

    try:
        fields['price'] = Decimal(str(float(data['price']))).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        fields['price'] = Decimal('0.00')

    # --- Optional text fields ---
    fields['description'] = str(data.get('description') or '').strip()
    fields['stock'] = int(data.get('stock') or 0)
    fields['weight'] = str(data.get('weight') or '').strip()
    fields['sub_category'] = str(data.get('product_type') or '').strip()
    fields['sku'] = str(data.get('style_code') or '').strip() or None

    # --- Sizes: list → comma-separated string ---
    sizes = data.get('sizes') or []
    if isinstance(sizes, list):
        fields['size'] = ', '.join(str(s) for s in sizes)
    else:
        fields['size'] = str(sizes)

    # --- Care info: combine fabric + work ---
    care_parts = []
    if data.get('fabric'):
        care_parts.append(f"Fabric: {data['fabric']}")
    if data.get('work'):
        care_parts.append(f"Work: {data['work']}")
    fields['care_info'] = ' | '.join(care_parts)

    # --- Extra details: extract brand, build tags ---
    extra = data.get('extra_details') or {}
    if isinstance(extra, dict):
        fields['brand'] = str(extra.get('brand') or '').strip()
        # Store remaining extra keys as comma-separated tags
        tag_parts = [f"{k}:{v}" for k, v in extra.items() if k != 'brand' and v]
        fields['tags'] = ', '.join(tag_parts)
    else:
        fields['brand'] = ''
        fields['tags'] = ''

    return fields


# ---------------------------------------------------------------------------
# Helper: Download image from URL and attach to product
# ---------------------------------------------------------------------------

def _attach_image_from_url(product, image_url):
    """
    Download image from URL and save to product.image field.
    Skips silently on any error.
    """
    if not image_url:
        return

    try:
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()

        # Determine file extension from URL or content-type
        ext = os.path.splitext(image_url.split('?')[0])[-1] or '.jpg'
        if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            ext = '.jpg'

        filename = f"n8n_{slugify(product.name)}{ext}"
        product.image.save(filename, ContentFile(response.content), save=False)
        logger.info(f"[n8n] Image downloaded for product '{product.name}'")

    except Exception as e:
        logger.warning(f"[n8n] Could not download image from {image_url}: {e}")


# ---------------------------------------------------------------------------
# Main API View
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def n8n_product_ingest(request):
    """
    POST /api/n8n/product/

    Accepts product JSON from n8n, creates or updates Product.
    - If product with same title exists → UPDATE
    - Otherwise → CREATE
    - Downloads image from URL if provided
    """

    # 1. Auth check
    if not _verify_api_key(request):
        logger.warning("[n8n] Unauthorized product ingest attempt.")
        return JsonResponse(
            {'success': False, 'error': 'Unauthorized. Invalid or missing API key.'},
            status=401
        )

    # 2. Parse JSON
    data, parse_error = _parse_payload(request)
    if parse_error:
        logger.error(f"[n8n] JSON parse error: {parse_error}")
        return JsonResponse({'success': False, 'error': parse_error}, status=400)

    # 3. Validate required fields
    validation_errors = _validate_required(data)
    if validation_errors:
        logger.warning(f"[n8n] Validation failed: {validation_errors}")
        return JsonResponse(
            {'success': False, 'errors': validation_errors},
            status=422
        )

    # 4. Map payload to model fields
    product_fields = _map_to_product_fields(data)
    image_url = data.get('image', '')

    logger.info(f"[n8n] Processing product: '{product_fields['name']}'")

    # 5. Create or Update (upsert by name)
    try:
        product, created = Product.objects.get_or_create(
            name=product_fields['name'],
            defaults=product_fields
        )

        if not created:
            # Update existing product fields
            for field, value in product_fields.items():
                # Don't overwrite sku if already set and new one is empty
                if field == 'sku' and not value and product.sku:
                    continue
                setattr(product, field, value)
            logger.info(f"[n8n] Updating existing product ID={product.id}")
        else:
            logger.info(f"[n8n] Creating new product ID={product.id}")

        # 6. Handle image download
        if image_url and (created or not product.image):
            _attach_image_from_url(product, image_url)

        # 7. Save (triggers slug generation + sanitization in model.save())
        product.save()

        return JsonResponse({
            'success': True,
            'action': 'created' if created else 'updated',
            'product_id': product.id,
            'product_name': product.name,
            'slug': product.slug,
        }, status=201 if created else 200)

    except Exception as e:
        logger.exception(f"[n8n] Unexpected error saving product: {e}")
        return JsonResponse(
            {'success': False, 'error': f'Server error: {str(e)}'},
            status=500
        )
