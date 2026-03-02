"""
Email utility functions for VibeMall
Handles sending order confirmations, status updates, and other notifications
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import EmailLog, Notification
import logging

logger = logging.getLogger(__name__)


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
        except ImportError:
            logger.warning("WeasyPrint not installed. Invoice PDF will not be attached. Install with: pip install weasyprint")
            pdf_generation_available = False
        
        # Get site URL from settings or use default
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        # Render HTML email template
        html_content = render_to_string('emails/order_confirmation.html', {
            'order': order,
            'site_url': site_url,
        })
        
        # Plain text fallback
        text_content = f"""
        Order Confirmation - #{order.order_number}
        
        Dear {order.user.get_full_name() or order.user.username},
        
        Thank you for your order! Your order has been successfully placed.
        
        Order Details:
        - Order Number: {order.order_number}
        - Order Date: {order.order_date.strftime('%B %d, %Y')}
        - Total Amount: ₹{order.total_amount}
        - Payment Method: {order.get_payment_method_display()}
        
        You can track your order at: {site_url}/orders/{order.id}/
        
        Best regards,
        VibeMall Team
        """
        
        # Create email
        subject = f'Order Confirmation - #{order.order_number} - VibeMall'
        from_email = settings.EMAIL_HOST_USER
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
                invoice_context = {
                    'order': order,
                    'current_year': datetime.now().year,
                }
                
                # Render invoice HTML
                invoice_html = render_to_string('invoice_pdf.html', invoice_context)
                
                # Generate PDF from HTML
                pdf_file = BytesIO()
                HTML(string=invoice_html).write_pdf(pdf_file)
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
        
        # Render beautiful HTML template
        html_content = render_to_string('emails/order_status_update.html', {
            'order': order,
            'order_items': order_items,
            'status_type': status_info['type'],
            'status_title': status_info['title'],
            'status_message': status_info['message'],
            'order_url': f'{site_url}/orders/{order.id}/',
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
            from_email=settings.EMAIL_HOST_USER,
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



def send_welcome_email_with_terms(user, request):
    """
    Send welcome email with Terms & Conditions PDF attachment

    Args:
        user: User instance
        request: Django request object for building absolute URLs

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        from datetime import datetime
        from io import BytesIO

        # Try to import weasyprint for PDF generation
        try:
            from weasyprint import HTML, CSS
            pdf_generation_available = True
        except ImportError:
            logger.warning("WeasyPrint not installed. PDF will not be attached. Install with: pip install weasyprint")
            pdf_generation_available = False

        # Get site URL
        site_url = request.build_absolute_uri('/').rstrip('/')
        shop_url = f"{site_url}/shop/"

        # Prepare context for templates
        context = {
            'user_name': user.first_name or user.username,
            'username': user.username,
            'email': user.email,
            'registration_date': datetime.now().strftime('%B %d, %Y'),
            'shop_url': shop_url,
            'current_year': datetime.now().year,
            'current_date': datetime.now().strftime('%B %d, %Y'),
        }

        # Render welcome email HTML
        html_content = render_to_string('emails/welcome_email.html', context)

        # Plain text fallback
        text_content = f"""
Welcome to VibeMall!

Hello {context['user_name']}!

Thank you for joining VibeMall! We're excited to have you as part of our community.

Your Account Details:
- Username: {user.username}
- Email: {user.email}
- Registration Date: {context['registration_date']}

Start shopping now: {shop_url}

What You Can Do:
✓ Browse thousands of products
✓ Add items to wishlist
✓ Track your orders
✓ Get exclusive deals and offers

Need help? Contact us:
Email: support@vibemall.com

© {context['current_year']} VibeMall. All rights reserved.
        """

        # Create email
        subject = 'Welcome to VibeMall - Registration Successful! 🎉'
        from_email = settings.EMAIL_HOST_USER
        to_email = user.email

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")

        # Generate and attach Terms & Conditions PDF if weasyprint is available
        if pdf_generation_available:
            try:
                # Render Terms & Conditions HTML
                terms_html = render_to_string('terms_and_conditions_pdf.html', context)

                # Generate PDF from HTML
                pdf_file = BytesIO()
                HTML(string=terms_html).write_pdf(pdf_file)
                pdf_file.seek(0)

                # Attach PDF to email
                email.attach(
                    'VibeMall_Terms_and_Conditions.pdf',
                    pdf_file.read(),
                    'application/pdf'
                )

                logger.info(f"Terms & Conditions PDF generated and attached for {user.email}")
            except Exception as pdf_error:
                logger.error(f"Failed to generate/attach PDF for {user.email}: {str(pdf_error)}")
                # Continue sending email without PDF

        # Send email
        email.send(fail_silently=False)

        # Log successful email
        EmailLog.objects.create(
            user=user,
            email_to=to_email,
            email_type='WELCOME_EMAIL',
            subject=subject,
            sent_successfully=True
        )

        # Create in-app notification
        Notification.objects.create(
            user=user,
            notification_type='WELCOME',
            title='Welcome to VibeMall! 🎉',
            message='Thank you for registering. Start exploring amazing products now!',
            link='/shop/'
        )

        logger.info(f"Welcome email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")

        try:
            EmailLog.objects.create(
                user=user,
                email_to=user.email,
                email_type='WELCOME_EMAIL',
                subject='Welcome to VibeMall',
                sent_successfully=False,
                error_message=str(e)
            )
        except:
            pass

        return False




def send_welcome_email_with_terms(user, request):
    """
    Send welcome email with Terms & Conditions PDF attachment
    
    Args:
        user: User instance
        request: Django request object for building absolute URLs
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        from datetime import datetime
        from io import BytesIO
        
        # Try to import weasyprint for PDF generation
        try:
            from weasyprint import HTML, CSS
            pdf_generation_available = True
        except ImportError:
            logger.warning("WeasyPrint not installed. PDF will not be attached. Install with: pip install weasyprint")
            pdf_generation_available = False
        
        # Get site URL
        site_url = request.build_absolute_uri('/').rstrip('/')
        shop_url = f"{site_url}/shop/"
        
        # Prepare context for templates
        context = {
            'user_name': user.first_name or user.username,
            'username': user.username,
            'email': user.email,
            'registration_date': datetime.now().strftime('%B %d, %Y'),
            'shop_url': shop_url,
            'current_year': datetime.now().year,
            'current_date': datetime.now().strftime('%B %d, %Y'),
        }
        
        # Render welcome email HTML
        html_content = render_to_string('emails/welcome_email.html', context)
        
        # Plain text fallback
        text_content = f"""
Welcome to VibeMall!

Hello {context['user_name']}!

Thank you for joining VibeMall! We're excited to have you as part of our community.

Your Account Details:
- Username: {user.username}
- Email: {user.email}
- Registration Date: {context['registration_date']}

Start shopping now: {shop_url}

What You Can Do:
✓ Browse thousands of products
✓ Add items to wishlist
✓ Track your orders
✓ Get exclusive deals and offers

Need help? Contact us:
Email: support@vibemall.com

© {context['current_year']} VibeMall. All rights reserved.
        """
        
        # Create email
        subject = 'Welcome to VibeMall - Registration Successful! 🎉'
        from_email = settings.EMAIL_HOST_USER
        to_email = user.email
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Generate and attach Terms & Conditions PDF if weasyprint is available
        if pdf_generation_available:
            try:
                # Render Terms & Conditions HTML
                terms_html = render_to_string('terms_and_conditions_pdf.html', context)
                
                # Generate PDF from HTML
                pdf_file = BytesIO()
                HTML(string=terms_html).write_pdf(pdf_file)
                pdf_file.seek(0)
                
                # Attach PDF to email
                email.attach(
                    'VibeMall_Terms_and_Conditions.pdf',
                    pdf_file.read(),
                    'application/pdf'
                )
                
                logger.info(f"Terms & Conditions PDF generated and attached for {user.email}")
            except Exception as pdf_error:
                logger.error(f"Failed to generate/attach PDF for {user.email}: {str(pdf_error)}")
                # Continue sending email without PDF
        
        # Send email
        email.send(fail_silently=False)
        
        # Log successful email
        EmailLog.objects.create(
            user=user,
            email_to=to_email,
            email_type='WELCOME_EMAIL',
            subject=subject,
            sent_successfully=True
        )
        
        # Create in-app notification
        Notification.objects.create(
            user=user,
            notification_type='WELCOME',
            title='Welcome to VibeMall! 🎉',
            message='Thank you for registering. Start exploring amazing products now!',
            link='/shop/'
        )
        
        logger.info(f"Welcome email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        
        try:
            EmailLog.objects.create(
                user=user,
                email_to=user.email,
                email_type='WELCOME_EMAIL',
                subject='Welcome to VibeMall',
                sent_successfully=False,
                error_message=str(e)
            )
        except:
            pass
        
        return False
