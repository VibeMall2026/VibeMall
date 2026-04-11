"""
Email utility functions for VibeMall
Handles sending order confirmations, status updates, and other notifications
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .models import EmailLog, Notification, SiteSettings
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _get_from_email() -> str:
    return (
        getattr(settings, 'DEFAULT_FROM_EMAIL', '').strip() or
        getattr(settings, 'EMAIL_HOST_USER', '').strip() or
        'info.vibemall@gmail.com'
    )


def _validate_email_settings() -> str:
    configured_host_user = getattr(settings, 'EMAIL_HOST_USER', '').strip()
    configured_host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '').strip()
    default_from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '').strip()

    if not configured_host_user and not default_from_email:
        raise ValueError('Email sender is not configured. Set EMAIL_HOST_USER or DEFAULT_FROM_EMAIL in environment settings.')

    if configured_host_user.startswith('replace_with_') or configured_host_password.startswith('replace_with_'):
        raise ValueError('Email SMTP is using placeholder values. Please set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env.')

    # Prefer a clean DEFAULT_FROM_EMAIL if available for better deliverability;
    # otherwise, fall back to the SMTP login address.
    return default_from_email or configured_host_user


def _resolve_site_url(request=None) -> str:
    configured = getattr(settings, 'SITE_URL', '').strip().rstrip('/')
    if request is not None:
        try:
            return request.build_absolute_uri('/').rstrip('/')
        except Exception:
            pass
    return configured or 'http://127.0.0.1:8000'


def _build_verification_url(user, site_url: str) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{site_url}{reverse('verify_email', args=[uid, token])}"


def build_invoice_context(order):
    from datetime import datetime
    from decimal import Decimal

    site_settings = SiteSettings.get_settings()
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    parsed_site_url = urlparse(site_url)
    site_host = parsed_site_url.netloc or site_url.replace('https://', '').replace('http://', '')

    def split_address_lines(raw_value):
        address = str(raw_value or '').replace('\r', '').strip()
        if not address:
            return []

        newline_lines = [line.strip() for line in address.split('\n') if line.strip()]
        if newline_lines:
            return newline_lines

        return [part.strip() for part in address.split(',') if part.strip()]

    def absolute_media_url(raw_value):
        value = str(raw_value or '').strip()
        if not value:
            return ''
        if value.startswith(('http://', 'https://')):
            return value
        if value.startswith('/'):
            return f'{site_url}{value}'
        return f'{site_url}/{value.lstrip("/")}'

    user_profile = getattr(order.user, 'userprofile', None)
    customer_name = order.user.get_full_name() or order.user.username
    customer_phone = ''
    customer_address = order.billing_address or ''

    if user_profile:
        customer_phone = user_profile.mobile_number or user_profile.phone or ''
        if not customer_address:
            customer_address = user_profile.address or ''

    order_items = []
    for item in order.items.select_related('product').all():
        image_url = ''
        if item.product_image:
            image_url = absolute_media_url(item.product_image)
        elif item.product and getattr(item.product, 'image', None):
            try:
                image_url = absolute_media_url(item.product.image.url)
            except Exception:
                image_url = ''

        variant_parts = []
        if item.size:
            variant_parts.append(f'Size: {item.size}')
        if item.color:
            variant_parts.append(f'Color: {item.color}')

        order_items.append({
            'name': item.product_name or (item.product.name if item.product else 'Product'),
            'quantity': item.quantity,
            'unit_price': item.product_price,
            'line_total': item.subtotal,
            'variant_text': ' | '.join(variant_parts),
            'image_url': image_url,
        })

    shipping_amount = Decimal(str(order.shipping_cost or 0))
    tax_amount = Decimal(str(order.tax or 0))
    coupon_discount = Decimal(str(order.coupon_discount or 0))
    subtotal_amount = Decimal(str(order.subtotal or order.get_subtotal() or 0))
    grand_total = Decimal(str(order.total_amount or 0))
    invoice_date = order.order_date or order.created_at

    company_name = 'VibeMall'
    company_email = 'info.vibemall@gmail.com'
    company_phone = (getattr(site_settings, 'contact_phone', None) or '').strip()
    company_address_lines = [
        'katargam 395004 surat ,Gujarat',
    ]

    return {
        'order': order,
        'order_items': order_items,
        'invoice_date': invoice_date,
        'current_year': datetime.now().year,
        'site_url': site_url,
        'site_host': site_host,
        'company_name': company_name,
        'company_email': company_email,
        'company_phone': company_phone,
        'company_address_lines': company_address_lines,
        'customer_id': f'CU-{order.user_id:05d}',
        'customer_name': customer_name,
        'customer_email': order.user.email,
        'customer_phone': customer_phone,
        'billing_lines': split_address_lines(customer_address),
        'shipping_lines': split_address_lines(order.shipping_address or customer_address),
        'subtotal_amount': subtotal_amount,
        'tax_amount': tax_amount,
        'shipping_amount': shipping_amount,
        'coupon_discount': coupon_discount,
        'grand_total': grand_total,
        'shipping_is_free': shipping_amount <= 0,
        'payment_method_display': order.get_payment_method_display(),
        'payment_status_display': order.get_payment_status_display(),
        'order_status_display': order.get_order_status_display(),
    }


def send_order_confirmation_email(order):
    """
    Send order confirmation email to customer after successful order placement
    with PDF invoice attachment
    
    Args:
        order: Order instance
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        from datetime import datetime
        from io import BytesIO
        
        # Try to import weasyprint for PDF generation
        try:
            from weasyprint import HTML
            pdf_generation_available = True
        except (ImportError, OSError) as exc:
            logger.warning("WeasyPrint PDF dependencies unavailable. Invoice PDF will not be attached: %s", exc)
            pdf_generation_available = False
        
        if not order.user.email:
            raise ValueError(f"Order #{order.order_number} cannot send confirmation email because the customer account has no email address.")

        # Validate email configuration before sending
        from_email = _validate_email_settings()

        # Get site URL from settings or use default
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

        # Build email-friendly order items (with absolute image URLs)
        order_items = []
        for item in order.items.select_related('product').all():
            image_url = ''
            if item.product_image:
                image_url = str(item.product_image).strip()
            elif item.product and item.product.image:
                image_url = item.product.image.url

            if image_url:
                if image_url.startswith('/'):
                    image_url = f"{site_url}{image_url}"
                elif not image_url.startswith(('http://', 'https://')):
                    image_url = f"{site_url}/{image_url.lstrip('/')}"

            variant_parts = [part for part in [item.size, item.color] if part]

            order_items.append({
                'product_name': item.product_name,
                'quantity': item.quantity,
                'product_price': item.product_price,
                'subtotal': item.subtotal,
                'variant_text': ' - '.join(variant_parts),
                'image_url': image_url,
            })

        is_review_state = order.order_status in {'PENDING', 'PROCESSING'}
        hero_title = 'Your Order is Being Reviewed' if is_review_state else 'Your Order is Confirmed'
        hero_message = (
            'Your order has been successfully placed and is now awaiting final review. '
            'Once approved, you will receive a formal confirmation and shipping timeline.'
            if is_review_state else
            'Your order has been successfully placed and is now confirmed. '
            'You will receive shipping updates as soon as your package is dispatched.'
        )

        shipping_cost_display = 'Complimentary' if float(order.shipping_cost or 0) == 0 else f"₹{order.shipping_cost:.2f}"

        try:
            order_details_path = reverse('order_details', args=[order.order_number])
        except Exception:
            order_details_path = f"/orders/{order.order_number}/"

        try:
            track_order_path = reverse('order_tracking', args=[order.order_number])
        except Exception:
            track_order_path = '/track-order/'

        try:
            contact_path = reverse('contact')
        except Exception:
            contact_path = '/contact/'

        try:
            returns_policy_path = reverse('faq')
        except Exception:
            returns_policy_path = '/faq/'

        try:
            invoice_download_path = reverse('download_invoice', args=[order.order_number])
        except Exception:
            invoice_download_path = f"/order/download-invoice/{order.order_number}/"

        payment_status_display = order.get_payment_status_display()
        if order.delivery_date:
            estimated_delivery = order.delivery_date.strftime('%B %d, %Y')
        elif order.order_status == 'DELIVERED':
            estimated_delivery = 'Delivered'
        elif order.order_status == 'SHIPPED':
            estimated_delivery = 'On the Way'
        else:
            estimated_delivery = 'To Be Confirmed'

        # Confirmation timestamp (approved_at if set, else order_date, else now)
        confirmed_dt = getattr(order, 'approved_at', None) or order.order_date
        confirmation_date = confirmed_dt.strftime('%B %d, %Y') if confirmed_dt else datetime.now().strftime('%B %d, %Y')

        # Estimated dispatch: 1 business day after order date
        from datetime import timedelta
        dispatch_base = order.order_date or datetime.now().date() if not hasattr(datetime.now(), 'date') else datetime.now()
        if hasattr(dispatch_base, 'date'):
            dispatch_base = dispatch_base.date()
        estimated_dispatch_date = (dispatch_base + timedelta(days=1)).strftime('%B %d, %Y')

        # Route to correct template: pending/processing → order_received, else → order_confirmation
        email_template = 'emails/order_received.html' if is_review_state else 'emails/order_confirmation.html'

        # Render HTML email template
        html_content = render_to_string(email_template, {
            'order': order,
            'site_url': site_url,
            'order_items': order_items,
            'hero_title': hero_title,
            'hero_message': hero_message,
            'shipping_cost_display': shipping_cost_display,
            'order_date': order.order_date.strftime('%B %d, %Y') if order.order_date else '',
            'confirmation_date': confirmation_date,
            'estimated_dispatch_date': estimated_dispatch_date,
            'payment_status_display': payment_status_display,
            'estimated_delivery': estimated_delivery,
            'track_order_url': f"{site_url}{track_order_path}",
            'order_details_url': f"{site_url}{order_details_path}",
            'contact_url': f"{site_url}{contact_path}",
            'returns_policy_url': f"{site_url}{returns_policy_path}",
            'invoice_download_url': f"{site_url}{invoice_download_path}",
            'current_year': datetime.now().year,
        })
        
        # Plain text fallback
        order_path = order_details_path

        text_content = f"""
        {hero_title} - #{order.order_number}

        Dear {order.user.get_full_name() or order.user.username},

        {hero_message}

        Order Details:
        - Order Number: {order.order_number}
        - Order Date: {order.order_date.strftime('%B %d, %Y')}
        - Total Amount: ₹{order.total_amount}
        - Payment Method: {order.get_payment_method_display()}

        View your order: {site_url}{order_path}

        Best regards,
        VibeMall Team
        """
        
        # Create email
        subject = f'Order Confirmation - #{order.order_number} - VibeMall'
        to_email = order.user.email
        
        # Send email with both HTML and plain text versions
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Generate and attach Invoice PDF if weasyprint is available
        if pdf_generation_available:
            try:
                # Prepare context for invoice PDF
                invoice_context = build_invoice_context(order)
                
                # Render invoice HTML
                invoice_html = render_to_string('invoice_pdf.html', invoice_context)
                
                # Generate PDF from HTML
                pdf_file = BytesIO()
                HTML(string=invoice_html, base_url=invoice_context['site_url']).write_pdf(pdf_file)
                pdf_file.seek(0)
                
                # Attach PDF to email
                email.attach(
                    f'Invoice_{order.order_number}.pdf',
                    pdf_file.read(),
                    'application/pdf'
                )
                
                logger.info(f"Invoice PDF generated and attached for order {order.order_number}")
            except Exception as pdf_error:
                logger.error(f"Failed to generate/attach invoice PDF for order {order.order_number}: {str(pdf_error)}")
                # Continue sending email without PDF
        
        email.send(fail_silently=False)
        
        # Log successful email
        EmailLog.objects.create(
            user=order.user,
            email_to=to_email,
            email_type='ORDER_CONFIRMATION',
            subject=subject,
            order=order,
            sent_successfully=True
        )
        
        # Create in-app notification
        Notification.objects.create(
            user=order.user,
            notification_type='ORDER_PLACED',
            title=f'Order #{order.order_number} Confirmed',
            message=f'Your order of ₹{order.total_amount} has been confirmed and is being processed.',
            link=f'/orders/{order.id}/'
        )
        
        logger.info(f"Order confirmation email sent successfully to {to_email} for order {order.order_number}")
        return True
        
    except Exception as e:
        # Log failed email
        logger.error(f"Failed to send order confirmation email for order {order.order_number}: {str(e)}")
        
        EmailLog.objects.create(
            user=order.user,
            email_to=order.user.email,
            email_type='ORDER_CONFIRMATION',
            subject=f'Order Confirmation - #{order.order_number}',
            order=order,
            sent_successfully=False,
            error_message=str(e)
        )
        
        return False


def send_order_status_update_email(order, old_status, new_status):
    """
    Send email when order status changes
    
    Args:
        order: Order instance
        old_status: Previous order status
        new_status: New order status
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        from .models import LoyaltyPoints
        
        # Award loyalty points when order is delivered
        if new_status == 'DELIVERED' and old_status != 'DELIVERED':
            try:
                # Calculate points: ₹1 = 33 points (1 point = ₹0.03)
                points_earned = int(order.total_amount * 33)
                
                loyalty, _ = LoyaltyPoints.objects.get_or_create(user=order.user)
                loyalty.add_points(points_earned, f"Order #{order.order_number} delivered - ₹{order.total_amount}")
                
                logger.info(f"Awarded {points_earned} loyalty points to {order.user.username} for order #{order.order_number}")
            except Exception as e:
                logger.error(f"Failed to award loyalty points for order {order.order_number}: {str(e)}")
        
        # Validate recipient and sender configuration
        if not order.user.email:
            logger.warning(f"Skipping status email for order {order.order_number}: user has no email")
            return False

        configured_host_user = getattr(settings, 'EMAIL_HOST_USER', '')
        configured_host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        default_from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '').strip()
        if str(configured_host_user).startswith('replace_with_') or str(configured_host_password).startswith('replace_with_'):
            raise ValueError("Email SMTP is using placeholder values. Please set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env")

        from_email = default_from_email or configured_host_user
        if not from_email:
            raise ValueError("Email sender is not configured. Set EMAIL_HOST_USER or DEFAULT_FROM_EMAIL.")

        # Get site URL from settings
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

        # Build email-friendly order items (with absolute image URLs)
        order_items = []
        for item in order.items.select_related('product').all():
            image_url = ''

            if item.product_image:
                image_url = str(item.product_image).strip()
            elif item.product and item.product.image:
                image_url = item.product.image.url

            if image_url:
                if image_url.startswith('/'):
                    image_url = f"{site_url}{image_url}"
                elif not image_url.startswith(('http://', 'https://')):
                    image_url = f"{site_url}/{image_url.lstrip('/')}"

            order_items.append({
                'name': item.product_name or (item.product.name if item.product else 'Product'),
                'size': item.size,
                'color': item.color,
                'quantity': item.quantity,
                'image_url': image_url,
                'unit_price': item.product_price,
                'line_total': item.subtotal,
                'variant_text': ' / '.join([part for part in [item.color, item.size] if part]) or '',
            })
        
        # ── Status config for all 7 states ──────────────────────────────────
        status_config = {
            # Existing statuses
            'PROCESSING': {
                'title': 'Order is Being Processed',
                'message': 'The artisanal pieces you selected are being prepared with care in our studio.',
                'type': 'PROCESSING',
                'badge': 'ORDER IN ATELIER',
                'hero_title': 'Your Order is Being Prepared',
                'cta_label': 'View My Order',
            },
            'SHIPPED': {
                'title': 'Your Order is En Route',
                'message': 'Each piece has been carefully inspected and is now being transported with the utmost care to your doorstep.',
                'type': 'SHIPPED',
                'badge': 'SHIPPING UPDATE',
                'hero_title': 'Your Curations Are on the Way',
                'cta_label': 'Track Your Journey',
            },
            'OUT_FOR_DELIVERY': {
                'title': 'Out for Delivery Today',
                'message': 'Your order is with our delivery partner and will arrive at your doorstep today.',
                'type': 'OUT_FOR_DELIVERY',
                'badge': 'OUT FOR DELIVERY',
                'hero_title': 'Arriving Today',
                'cta_label': 'Track Your Journey',
            },
            'DELIVERED': {
                'title': 'Order Delivered Successfully',
                'message': 'Your curated order has reached its destination. We hope every piece feels special when unboxed.',
                'type': 'DELIVERED',
                'badge': 'DELIVERY CONFIRMED',
                'hero_title': 'Your Order Has Arrived',
                'cta_label': 'View My Order',
            },
            'CANCELLED': {
                'title': 'Order Cancelled',
                'message': 'Your order has been cancelled. If you need help, our concierge team is here for you.',
                'type': 'CANCELLED',
                'badge': 'ORDER UPDATE',
                'hero_title': 'Your Order Was Cancelled',
                'cta_label': 'View Order History',
            },
            # Return flow statuses
            'RETURN_SUBMITTED': {
                'title': 'Return Request Submitted',
                'message': 'We have received your return request and our team is reviewing it. You will hear from us shortly.',
                'type': 'RETURN_SUBMITTED',
                'badge': 'RETURN REQUEST',
                'hero_title': 'Return Request Received',
                'cta_label': 'View Return Status',
            },
            'RETURN_ACCEPTED': {
                'title': 'Return Request Accepted',
                'message': 'Your return has been approved. We will schedule a pickup at your convenience.',
                'type': 'RETURN_ACCEPTED',
                'badge': 'RETURN ACCEPTED',
                'hero_title': 'Your Return is Approved',
                'cta_label': 'View Return Details',
            },
            'PICKUP_SCHEDULED': {
                'title': 'Pickup Scheduled',
                'message': 'A pickup has been scheduled for your return. Please keep the items ready.',
                'type': 'PICKUP_SCHEDULED',
                'badge': 'PICKUP DATE CONFIRMED',
                'hero_title': 'Pickup is Scheduled',
                'cta_label': 'View Pickup Details',
            },
            'PICKUP_DONE': {
                'title': 'Pickup Successful',
                'message': 'Your items have been picked up successfully. Refund will be processed after quality check.',
                'type': 'PICKUP_DONE',
                'badge': 'PICKUP COMPLETE',
                'hero_title': 'Items Picked Up Successfully',
                'cta_label': 'Track Refund Status',
            },
            'PROCEED_TO_PAYMENT': {
                'title': 'Payment Required',
                'message': 'There is a pending balance on your order. Please complete the payment to proceed.',
                'type': 'PROCEED_TO_PAYMENT',
                'badge': 'ACTION REQUIRED',
                'hero_title': 'Complete Your Payment',
                'cta_label': 'Pay Now',
            },
        }

        if new_status not in status_config:
            return False

        status_info = status_config[new_status]

        # ── URLs ─────────────────────────────────────────────────────────────
        try:
            tracking_url = f"{site_url}{reverse('order_tracking', args=[order.order_number])}"
        except Exception:
            tracking_url = f'{site_url}/orders/{order.id}/'

        try:
            order_details_url = f"{site_url}{reverse('order_details', args=[order.order_number])}"
        except Exception:
            order_details_url = f'{site_url}/orders/{order.order_number}/'

        try:
            past_orders_url = f"{site_url}{reverse('order_list')}"
        except Exception:
            past_orders_url = f'{site_url}/orders/'

        try:
            contact_url = f"{site_url}{reverse('contact')}"
        except Exception:
            contact_url = f'{site_url}/contact/'

        try:
            returns_url = f"{site_url}{reverse('faq')}"
        except Exception:
            returns_url = f'{site_url}/faq/'

        payment_url = order_details_url  # override if dedicated payment URL exists

        # ── Delivery timeline ─────────────────────────────────────────────────
        if order.delivery_date:
            timeline_value = order.delivery_date.strftime('%B %d, %Y')
        elif new_status in ('SHIPPED', 'OUT_FOR_DELIVERY'):
            timeline_value = 'Carrier update pending'
        elif new_status == 'DELIVERED':
            timeline_value = 'Delivered'
        else:
            timeline_value = 'To Be Confirmed'

        # ── Primary CTA URL ───────────────────────────────────────────────────
        primary_cta_url = tracking_url if new_status in ('SHIPPED', 'OUT_FOR_DELIVERY') else order_details_url
        if new_status == 'PROCEED_TO_PAYMENT':
            primary_cta_url = payment_url

        # ── Return / pickup context ───────────────────────────────────────────
        return_obj = getattr(order, 'return_request', None)
        return_request_id = getattr(return_obj, 'id', '') or ''
        return_reason     = getattr(return_obj, 'reason', '') or ''
        return_status_display = getattr(return_obj, 'get_status_display', lambda: '')() if return_obj else ''
        pickup_date    = getattr(return_obj, 'pickup_date', None)
        pickup_date    = pickup_date.strftime('%B %d, %Y') if pickup_date else ''
        pickup_window  = getattr(return_obj, 'pickup_window', '') or ''
        pickup_partner = getattr(return_obj, 'pickup_partner', '') or order.courier_name or 'VibeMall Logistics'

        # ── Payment context ───────────────────────────────────────────────────
        payment_amount   = order.total_amount
        payment_due_date = ''
        if hasattr(order, 'payment_due_date') and order.payment_due_date:
            payment_due_date = order.payment_due_date.strftime('%B %d, %Y')

        # ── Shipping cost display ─────────────────────────────────────────────
        shipping_cost_display = (
            'Complimentary' if float(order.shipping_cost or 0) == 0
            else f"₹{order.shipping_cost:.2f}"
        )

        # ── Block visibility flags ────────────────────────────────────────────
        show_tracking = new_status in ('SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED')
        show_return   = new_status in ('RETURN_SUBMITTED', 'RETURN_ACCEPTED', 'PICKUP_SCHEDULED', 'PICKUP_DONE')
        show_pickup   = new_status in ('PICKUP_SCHEDULED', 'PICKUP_DONE')
        show_payment  = new_status == 'PROCEED_TO_PAYMENT'

        from datetime import datetime as _dt
        event_date = _dt.now().strftime('%b %d, %Y').upper()

        # ── Render ────────────────────────────────────────────────────────────
        html_content = render_to_string('emails/order_status_update.html', {
            'order': order,
            'order_items': order_items,
            'status_type': status_info['type'],
            'status_title': status_info['title'],
            'status_badge': status_info['badge'],
            'hero_title': status_info['hero_title'],
            'hero_body': status_info['message'],
            'primary_cta_label': status_info['cta_label'],
            'primary_cta_url': primary_cta_url,
            'order_url': past_orders_url,
            'tracking_url': tracking_url,
            'returns_url': returns_url,
            'contact_url': contact_url,
            'show_contact_link': True,
            'event_date': event_date,
            # Tracking block
            'show_tracking': show_tracking,
            'courier_name': order.courier_name or 'VibeMall Logistics',
            'tracking_number': order.tracking_number or '',
            'timeline_value': timeline_value,
            # Return block
            'show_return': show_return,
            'return_request_id': return_request_id,
            'return_reason': return_reason,
            'return_status_display': return_status_display,
            # Pickup block
            'show_pickup': show_pickup,
            'pickup_date': pickup_date,
            'pickup_window': pickup_window,
            'pickup_partner': pickup_partner,
            # Payment block
            'show_payment': show_payment,
            'payment_amount': payment_amount,
            'payment_due_date': payment_due_date,
            'payment_url': payment_url,
            # Totals
            'shipping_cost_display': shipping_cost_display,
            'current_year': _dt.now().year,
        })
        
        # Plain text fallback
        text_content = f"""
        {status_info['title']}
        
        Hi {order.user.get_full_name() or order.user.username},
        
        {status_info['message']}
        
        Order Number: {order.order_number}
        Total Amount: ₹{order.total_amount}
        """
        
        if order.tracking_number:
            text_content += f"\nTracking Number: {order.tracking_number}"
        
        text_content += f"\n\nTrack your order at: {site_url}/orders/{order.id}/"

        if order_items:
            text_content += "\n\nItems:\n"
            for item in order_items:
                meta = []
                if item['size']:
                    meta.append(f"Size: {item['size']}")
                if item['color']:
                    meta.append(f"Color: {item['color']}")
                meta_text = f" ({', '.join(meta)})" if meta else ''
                text_content += f"- {item['name']} x {item['quantity']}{meta_text}\n"
        
        # Create email
        subject = f"{status_info['title']} - Order #{order.order_number}"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[order.user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        # Log email
        EmailLog.objects.create(
            user=order.user,
            email_to=order.user.email,
            email_type=f'ORDER_{new_status}',
            subject=subject,
            order=order,
            sent_successfully=True
        )
        
        # Create notification
        Notification.objects.create(
            user=order.user,
            notification_type=f'ORDER_{new_status}',
            title=subject,
            message=status_info['message'],
            link=f'/orders/{order.id}/'
        )
        
        logger.info(f"Order status update email sent to {order.user.email} for order {order.order_number} (Status: {new_status})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send status update email for order {order.order_number}: {str(e)}")

        failed_subject = f"Order Status Update - #{order.order_number}"
        if 'status_info' in locals():
            failed_subject = f"{status_info['title']} - Order #{order.order_number}"

        EmailLog.objects.create(
            user=order.user,
            email_to=order.user.email,
            email_type='ORDER_STATUS_UPDATE',
            subject=failed_subject,
            order=order,
            sent_successfully=False,
            error_message=str(e)
        )
        return False


def send_admin_order_notification(order, request):
    """
    Send email notification to admin when new order is received
    Includes approve/reject links
    
    Args:
        order: Order instance
        request: Django request object for building absolute URLs
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        # Validate email configuration before sending
        from_email = _validate_email_settings()

        # Send to VibeMall admin email only
        admin_emails = ['info.vibemall@gmail.com']
        
        # Build absolute URLs
        site_url = request.build_absolute_uri('/').rstrip('/')
        approve_url = f"{site_url}/admin-panel/orders/{order.id}/approve/"
        reject_url = f"{site_url}/admin-panel/orders/{order.id}/reject/"
        order_details_url = f"{site_url}/admin-panel/orders/{order.id}/"
        
        # Render HTML email
        html_content = render_to_string('emails/admin_order_notification.html', {
            'order': order,
            'site_url': site_url,
            'approve_url': approve_url,
            'reject_url': reject_url,
            'order_details_url': order_details_url,
        })
        
        # Plain text fallback
        text_content = f"""
New Order Received - #{order.order_number}

Customer: {order.user.get_full_name() or order.user.username}
Email: {order.user.email}
Total Amount: ₹{order.total_amount}
Payment Method: {order.get_payment_method_display()}
Payment Status: {order.payment_status}

Order requires your approval.

Approve: {approve_url}
Reject: {reject_url}
View Details: {order_details_url}

Best regards,
VibeMall System
        """
        
        # Create and send email
        subject = f'🔔 New Order #{order.order_number} - ₹{order.total_amount}'
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=admin_emails
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        # Log email
        for admin_email in admin_emails:
            EmailLog.objects.create(
                email_to=admin_email,
                email_type='ADMIN_ORDER_NOTIFICATION',
                subject=subject,
                order=order,
                sent_successfully=True
            )
        
        logger.info(f"Admin notification sent for order {order.order_number} to {len(admin_emails)} admins")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send admin order notification: {str(e)}")
        EmailLog.objects.create(
            email_to='admin',
            email_type='ADMIN_ORDER_NOTIFICATION',
            subject=f'New Order #{order.order_number}',
            order=order,
            sent_successfully=False,
            error_message=str(e)
        )
        return False


def send_order_approval_email(order, request=None, approved_by=None):
    """
    Send order approval email to customer
    
    Args:
        order: Order instance
        request: Django request object (optional) for building absolute URLs
        approved_by: Admin user who approved (optional)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not order.user.email:
            logger.warning(f"Cannot send approval email: User {order.user.username} has no email")
            return False
        
        # Build site URL
        if request:
            site_url = request.build_absolute_uri('/').rstrip('/')
        else:
            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        # Get from email
        from_email = _get_from_email()
        to_email = order.user.email
        
        # Render HTML email
        html_content = render_to_string('emails/order_approved.html', {
            'order': order,
            'approved_by': approved_by.get_full_name() or approved_by.username if approved_by else 'Admin',
            'site_url': site_url,
        })
        
        # Plain text version
        text_content = f"""Dear {order.user.get_full_name() or order.user.username},

Good news! Your order {order.order_number} has been approved and is now being processed.

Order Details:
- Order Number: {order.order_number}
- Total Amount: ₹{order.total_amount}
- Status: Processing
- Approved on: {order.approved_at.strftime("%B %d, %Y") if order.approved_at else "Today"}

You can track your order here: {site_url}/orders/{order.id}/

Thank you for shopping with us!

Best regards,
VibeMall Team
        """
        
        # Create email
        subject = f'Order Approved - #{order.order_number} - VibeMall'
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        # Log successful email
        EmailLog.objects.create(
            user=order.user,
            email_to=to_email,
            email_type='ORDER_APPROVED',
            subject=subject,
            order=order,
            sent_successfully=True
        )
        
        # Create in-app notification
        Notification.objects.create(
            user=order.user,
            notification_type='ORDER_APPROVED',
            title=f'Order #{order.order_number} Approved!',
            message=f'Your order for ₹{order.total_amount} has been approved and is being processed.',
            link=f'/orders/{order.id}/'
        )
        
        logger.info(f"Order approval email sent successfully to {to_email} for order {order.order_number}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send order approval email for order {order.order_number}: {str(e)}", exc_info=True)
        
        try:
            EmailLog.objects.create(
                user=order.user,
                email_to=order.user.email if order.user.email else 'unknown',
                email_type='ORDER_APPROVED',
                subject=f'Order Approved - #{order.order_number}',
                order=order,
                sent_successfully=False,
                error_message=str(e)[:500]
            )
        except:
            pass
        
        return False



def _generate_terms_pdf_bytes(context):
    from io import BytesIO

    try:
        import importlib

        module_name = 'weasy' + 'print'
        HTML = importlib.import_module(module_name).HTML

        terms_html = render_to_string('terms_and_conditions_pdf.html', context)
        pdf_file = BytesIO()
        HTML(string=terms_html).write_pdf(pdf_file)
        return pdf_file.getvalue()
    except (ImportError, OSError) as exc:
        logger.warning("WeasyPrint unavailable for welcome terms PDF, using ReportLab fallback: %s", exc)
    except Exception as exc:
        logger.warning("WeasyPrint failed for welcome terms PDF, using ReportLab fallback: %s", exc)

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        pdf_file = BytesIO()
        doc = SimpleDocTemplate(
            pdf_file,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title='VibeMall Terms and Conditions',
            author='VibeMall',
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='VmEyebrow',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#6f5c37'),
            spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            name='VmBrand',
            parent=styles['Normal'],
            fontName='Times-BoldItalic',
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#171818'),
            spaceAfter=10,
        ))
        styles.add(ParagraphStyle(
            name='VmMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#5c6161'),
            spaceAfter=2,
        ))
        styles.add(ParagraphStyle(
            name='VmH2',
            parent=styles['Heading2'],
            fontName='Times-Bold',
            fontSize=15,
            leading=19,
            textColor=colors.HexColor('#171818'),
            spaceBefore=10,
            spaceAfter=6,
        ))
        styles.add(ParagraphStyle(
            name='VmBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor('#30312e'),
            spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            name='VmQuote',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#6f5c37'),
            spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            name='VmFooter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#747878'),
            spaceAfter=4,
        ))

        story = [
            Paragraph('ATELIER TERMS OF SERVICE', styles['VmEyebrow']),
            Paragraph('VIBEMALL', styles['VmBrand']),
            Paragraph(f"Effective Date: {context['current_date']}", styles['VmMeta']),
            Paragraph(f"Last Updated: {context['current_date']}", styles['VmMeta']),
            Spacer(1, 10),
        ]

        important = Table(
            [[Paragraph('<b>Important:</b> By registering or using VibeMall, you agree to these Terms of Service and related policies.', styles['VmBody'])]],
            colWidths=[doc.width],
        )
        important.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f3ee')),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#d7d9d9')),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.extend([important, Spacer(1, 12)])

        sections = [
            ('1. Introduction', [
                'Welcome to VIBEMALL (the "Atelier"). By accessing our curated collections or engaging with our digital storefront, you acknowledge that you are entering a space defined by craftsmanship, heritage, and mutual respect.',
                'These Terms of Service are legally binding and may be updated from time to time. Continued use of VIBEMALL signifies acceptance of the latest version.',
            ]),
            ('2. User Conduct', [
                'You agree to provide accurate account and order details, avoid abusive or unlawful behavior, and refrain from scraping, bot activity, or disruption of platform operations.',
            ]),
            ('3. Artisan Standards', [
                'Many pieces are handcrafted. Subtle variation in texture, weave, color, and finish is considered artisan character rather than defect.',
                '<i>"The imperfection is the evidence of the human hand."</i>',
            ]),
            ('4. Intellectual Property', [
                'All visual assets, copy, layout systems, and brand elements are owned by VIBEMALL or its licensors. Unauthorized reuse is prohibited.',
            ]),
            ('5. Custom Orders', [
                'Custom and made-to-order items are final once production begins. For structural issues outside expected artisan variation, contact concierge support within 48 hours of delivery.',
            ]),
            ('6. Orders, Payments, and Delivery', [
                'Orders are subject to acceptance and verification. Delivery timelines are estimates and may vary due to logistics or force majeure conditions.',
            ]),
            ('7. Returns and Refunds', [
                'Return and refund eligibility depends on product category, item condition, and published return windows. Non-returnable items cannot be returned.',
            ]),
            ('8. Governing Law and Contact', [
                'These terms are governed by applicable laws of India. For legal or policy queries, contact info.vibemall@gmail.com.',
            ]),
        ]

        for heading, paragraphs in sections:
            story.append(Paragraph(heading, styles['VmH2']))
            for paragraph in paragraphs:
                if paragraph.startswith('<i>'):
                    story.append(Paragraph(paragraph, styles['VmQuote']))
                else:
                    story.append(Paragraph(paragraph, styles['VmBody']))

        story.extend([
            Spacer(1, 12),
            Paragraph(f"© {context['current_year']} VIBEMALL ATELIER. All rights reserved.", styles['VmFooter']),
            Paragraph('By registering on VIBEMALL, you acknowledge and accept these Terms and Conditions.', styles['VmFooter']),
        ])

        doc.build(story)
        return pdf_file.getvalue()
    except Exception as exc:
        logger.error("ReportLab fallback failed for welcome terms PDF: %s", exc)
        return None


def send_welcome_email_with_terms(user, request=None):
    """Send the first-time registration welcome email with a Terms & Conditions PDF attachment."""
    try:
        from datetime import datetime

        site_url = _resolve_site_url(request)
        shop_url = f"{site_url}/shop/"
        verify_url = _build_verification_url(user, site_url)

        context = {
            'user_name': user.first_name or user.username,
            'username': user.username,
            'email': user.email,
            'registration_date': datetime.now().strftime('%B %d, %Y'),
            'shop_url': shop_url,
            'verify_url': verify_url,
            'verification_required': not bool(getattr(user, 'is_active', False)),
            'current_year': datetime.now().year,
            'current_date': datetime.now().strftime('%B %d, %Y'),
            'hero_image_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuCgUw0ejqeYxn8X2-6Til8hHby6JZ50mLnAH4lhKfMmHz3CuPMYTU8Po_r2AhYT1KtVGP09Ri7uDyNQpnfTqCvNpgT6roo4uIEWK9yOcaPRZSe0r2l9yA3fIVGs_HX4tnDn0TC5t44-lbvfjY3zMcIGtLOfvV4J8vCFmquLXQfsZlawsk7nsqGZ0lo9OjuIvWrUOIoKb1KHjeuF-VtAcDy-3HeH2s1zSDuasM6PKaT9ySZtiJctIsM9SA4iijoMkxJ6bsgbzZJEt-I',
        }

        html_content = render_to_string('emails/welcome_email.html', context)
        text_content = (
            f"Welcome to the Atelier, {context['user_name']}!\n\n"
            "Thank you for registering with VibeMall. Your account has been created successfully.\n\n"
            f"Username: {user.username}\n"
            f"Email: {user.email}\n"
            f"Registration Date: {context['registration_date']}\n\n"
            "You have entered a curated shopping space focused on artisanal heritage and contemporary silhouettes.\n\n"
            f"Verify your email: {verify_url}\n\n"
            f"Explore the collection: {shop_url}\n\n"
            "Our Terms & Conditions PDF is attached to this email for your records.\n\n"
            "With gratitude,\n"
            "The Curators of VIBEMALL ATELIER\n"
            f"© {context['current_year']} VibeMall. All rights reserved."
        )

        subject = 'Welcome to the Atelier | VibeMall'
        to_email = user.email

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=_get_from_email(),
            to=[to_email],
        )
        email.attach_alternative(html_content, 'text/html')

        terms_pdf = _generate_terms_pdf_bytes(context)
        if terms_pdf:
            email.attach('VibeMall_Terms_and_Conditions.pdf', terms_pdf, 'application/pdf')

        email.send(fail_silently=False)

        EmailLog.objects.create(
            user=user,
            email_to=to_email,
            email_type='WELCOME_EMAIL',
            subject=subject,
            sent_successfully=True,
        )

        Notification.objects.create(
            user=user,
            notification_type='WELCOME',
            title='Welcome to VibeMall! 🎉',
            message='Thank you for registering. Start exploring the atelier collection now!',
            link='/shop/',
        )

        logger.info("Welcome email sent successfully to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send welcome email to %s: %s", user.email, exc, exc_info=True)

        try:
            EmailLog.objects.create(
                user=user,
                email_to=user.email,
                email_type='WELCOME_EMAIL',
                subject='Welcome to the Atelier | VibeMall',
                sent_successfully=False,
                error_message=str(exc)[:500],
            )
        except Exception:
            pass

        return False
