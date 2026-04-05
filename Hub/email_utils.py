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

        # Render HTML email template
        html_content = render_to_string('emails/order_confirmation.html', {
            'order': order,
            'site_url': site_url,
            'order_items': order_items,
            'hero_title': hero_title,
            'hero_message': hero_message,
            'shipping_cost_display': shipping_cost_display,
            'current_year': datetime.now().year,
        })
        
        # Plain text fallback
        try:
            order_path = reverse('order_details', args=[order.order_number])
        except Exception:
            order_path = f"/orders/{order.order_number}/"

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
        from_email = _get_from_email()
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
        if str(configured_host_user).startswith('replace_with_') or str(configured_host_password).startswith('replace_with_'):
            raise ValueError("Email SMTP is using placeholder values. Please set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env")

        from_email = configured_host_user or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
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
        
        status_config = {
            'PROCESSING': {
                'title': 'Order is Being Processed',
                'message': 'Your order is now being prepared for shipment.',
                'type': 'PROCESSING'
            },
            'SHIPPED': {
                'title': 'Order Shipped!',
                'message': f'Your order has been shipped via {order.courier_name or "our delivery partner"}.',
                'type': 'SHIPPED'
            },
            'DELIVERED': {
                'title': 'Order Delivered Successfully',
                'message': 'Your order has been delivered. We hope you enjoy your purchase!',
                'type': 'DELIVERED'
            },
            'CANCELLED': {
                'title': 'Order Cancelled',
                'message': 'Your order has been cancelled.',
                'type': 'CANCELLED'
            },
        }
        
        if new_status not in status_config:
            return False
        
        status_info = status_config[new_status]

        tracking_url = f"{site_url}{reverse('order_tracking', args=[order.order_number])}" if order.tracking_number else f'{site_url}/orders/{order.id}/'
        order_details_url = f"{site_url}{reverse('order_details', args=[order.order_number])}"
        past_orders_url = f"{site_url}{reverse('order_list')}"
        first_review_product = next((item.product for item in order.items.select_related('product').all() if item.product_id), None)
        review_url = f"{site_url}{reverse('product-details', args=[first_review_product.id])}" if first_review_product else order_details_url
        shipping_address_lines = [
            line.strip()
            for line in str(order.shipping_address or '').replace('\r', '').split('\n')
            if line.strip()
        ]
        if not shipping_address_lines and order.shipping_address:
            shipping_address_lines = [part.strip() for part in str(order.shipping_address).split(',') if part.strip()]

        status_badge = {
            'PROCESSING': 'ORDER IN ATELIER',
            'SHIPPED': 'SHIPPING UPDATE',
            'DELIVERED': 'DELIVERY CONFIRMED',
            'CANCELLED': 'ORDER UPDATE',
        }.get(new_status, 'ORDER UPDATE')

        hero_title = {
            'PROCESSING': 'Your Order is Being Prepared',
            'SHIPPED': 'Your Order is En Route',
            'DELIVERED': 'Your Order Has Arrived',
            'CANCELLED': 'Your Order Was Cancelled',
        }.get(new_status, status_info['title'])

        hero_body = {
            'PROCESSING': 'The artisanal pieces you selected are being prepared with care in our studio.',
            'SHIPPED': 'The artisanal pieces you selected have been carefully packed and are now making their way to your sanctuary.',
            'DELIVERED': 'Your curated order has reached its destination. We hope every piece feels special when unboxed.',
            'CANCELLED': 'Your latest order update is below. If you need help, our concierge team is here for you.',
        }.get(new_status, status_info['message'])

        cta_label = 'Track My Package' if order.tracking_number else 'View My Order'
        timeline_label = 'Estimated Arrival'
        timeline_value = 'We will update you shortly'
        if new_status == 'DELIVERED':
            timeline_label = 'Delivered On'
            timeline_value = order.delivery_date.strftime('%B %d, %Y').upper() if order.delivery_date else 'Delivered'
        elif new_status == 'SHIPPED':
            timeline_value = order.delivery_date.strftime('%B %d, %Y').upper() if order.delivery_date else 'Carrier update pending'
        elif new_status == 'PROCESSING':
            timeline_label = 'Current Stage'
            timeline_value = 'Preparing for Dispatch'
        elif new_status == 'CANCELLED':
            timeline_label = 'Current Stage'
            timeline_value = 'Cancelled'

        carrier_label = order.courier_name or 'VibeMall Logistics'
        
        # Render HTML email template
        html_content = render_to_string('emails/order_status_update.html', {
            'order': order,
            'order_items': order_items,
            'status_type': status_info['type'],
            'status_title': status_info['title'],
            'status_message': status_info['message'],
            'order_url': order_details_url,
            'tracking_url': tracking_url,
            'past_orders_url': past_orders_url,
            'review_url': review_url,
            'shipping_address_lines': shipping_address_lines,
            'status_badge': status_badge,
            'hero_title': hero_title,
            'hero_body': hero_body,
            'cta_label': cta_label,
            'timeline_label': timeline_label,
            'timeline_value': timeline_value,
            'carrier_label': carrier_label,
            'item_count': sum(int(item['quantity'] or 0) for item in order_items),
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
            from_email=_get_from_email(),
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
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen import canvas

        pdf_file = BytesIO()
        pdf = canvas.Canvas(pdf_file, pagesize=A4)
        width, height = A4
        left_margin = 18 * mm
        right_margin = width - (18 * mm)
        usable_width = right_margin - left_margin
        cursor_y = height - (20 * mm)

        def new_page():
            nonlocal cursor_y
            pdf.showPage()
            cursor_y = height - (20 * mm)

        def ensure_space(required_height):
            if cursor_y - required_height < 18 * mm:
                new_page()

        def draw_wrapped(text, font_name='Helvetica', font_size=10, leading=14):
            nonlocal cursor_y
            lines = simpleSplit(str(text), font_name, font_size, usable_width)
            ensure_space(max(len(lines), 1) * leading)
            pdf.setFont(font_name, font_size)
            for line in lines:
                pdf.drawString(left_margin, cursor_y, line)
                cursor_y -= leading

        pdf.setTitle('VibeMall Terms and Conditions')
        pdf.setAuthor('VibeMall')

        pdf.setFont('Helvetica-Bold', 20)
        pdf.drawString(left_margin, cursor_y, 'VIBEMALL TERMS AND CONDITIONS')
        cursor_y -= 20

        draw_wrapped(f"Effective Date: {context['current_date']}", 'Helvetica', 10, 14)
        draw_wrapped(f"Last Updated: {context['current_date']}", 'Helvetica', 10, 14)
        cursor_y -= 8

        sections = [
            (
                '1. Acceptance of Terms',
                [
                    'By registering or using VibeMall, you agree to be bound by our Terms and Conditions in accordance with applicable Indian law.',
                ],
            ),
            (
                '2. User Account',
                [
                    'You must provide accurate registration details and keep your account credentials secure.',
                    'VibeMall may suspend accounts that violate platform policies or applicable law.',
                ],
            ),
            (
                '3. Orders and Payments',
                [
                    'Orders placed on VibeMall are subject to acceptance, availability, and payment verification.',
                    'Payments are processed through approved third-party gateways.',
                ],
            ),
            (
                '4. Shipping, Returns, and Refunds',
                [
                    'Delivery timelines are estimates and may vary.',
                    'Return and refund eligibility depends on product category, item condition, and the published return window.',
                ],
            ),
            (
                '5. Acceptable Use',
                [
                    'You may not use the platform for illegal, fraudulent, abusive, or unauthorized activities.',
                ],
            ),
            (
                '6. Liability and Governing Law',
                [
                    'VibeMall liability is limited to the amount paid for the relevant transaction, subject to applicable law.',
                    'These terms are governed by the laws of India.',
                ],
            ),
            (
                '7. Contact',
                [
                    'For questions about these Terms and Conditions, contact info.vibemall@gmail.com.',
                ],
            ),
        ]

        for heading, paragraphs in sections:
            ensure_space(28)
            pdf.setFont('Helvetica-Bold', 13)
            pdf.drawString(left_margin, cursor_y, heading)
            cursor_y -= 16
            for paragraph in paragraphs:
                draw_wrapped(paragraph, 'Helvetica', 10, 14)
            cursor_y -= 6

        ensure_space(30)
        pdf.setFont('Helvetica-Oblique', 9)
        pdf.drawString(left_margin, cursor_y, f"© {context['current_year']} VibeMall. All rights reserved.")
        cursor_y -= 12
        pdf.drawString(left_margin, cursor_y, 'By registering on VibeMall, you acknowledge and accept these Terms and Conditions.')

        pdf.save()
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
