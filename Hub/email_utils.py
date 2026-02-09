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
    
    Args:
        order: Order instance
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
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
        from .models import LoyaltyPoints, PointsTransaction
        
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
        
        # Get site URL from settings
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
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
        
        # Create email
        subject = f"{status_info['title']} - Order #{order.order_number}"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.EMAIL_HOST_USER,
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
        
        EmailLog.objects.create(
            user=order.user,
            email_to=order.user.email,
            email_type='ORDER_STATUS_UPDATE',
            subject=subject,
            order=order,
            sent_successfully=True
        )
        
        logger.info(f"Status update email sent for order {order.order_number}: {old_status} -> {new_status}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send status update email: {str(e)}")
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

