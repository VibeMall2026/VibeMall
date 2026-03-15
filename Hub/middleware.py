from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from datetime import timedelta


class ComingSoonModeMiddleware:
    """
    When COMING_SOON_MODE is enabled, redirect all public traffic
    to the coming-soon page while keeping admin and static assets available.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_prefixes = (
            '/coming-soon/',
            '/admin-panel/',
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/newsletter/subscribe/',
        )

    def __call__(self, request):
        if not getattr(settings, 'COMING_SOON_MODE', False):
            return self.get_response(request)

        path = request.path or '/'

        if any(path.startswith(prefix) for prefix in self.allowed_prefixes):
            return self.get_response(request)

        # Check if user is authenticated (only if user attribute exists)
        if hasattr(request, 'user') and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return self.get_response(request)

        return redirect('coming_soon')


class BlockedUserMiddleware:
    """
    Middleware to prevent blocked users from accessing the site.
    Checks if user is authenticated and if their profile is blocked.
    Also updates last_activity timestamp.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Allow access to login, logout, and static files
        allowed_paths = [
            reverse('login'),
            reverse('logout'),
            '/static/',
            '/media/',
            '/order/download-invoice/',
        ]
        
        # Check if current path is allowed
        is_allowed_path = any(request.path.startswith(path) for path in allowed_paths)
        
        # If user is authenticated and not on allowed path
        if request.user.is_authenticated and not is_allowed_path:
            try:
                # Check if user profile exists and is blocked
                if hasattr(request.user, 'userprofile'):
                    profile = request.user.userprofile
                    
                    # Update last activity timestamp (only for non-admin panel requests to avoid overhead)
                    if not request.path.startswith('/admin-panel/'):
                        now = timezone.now()
                        should_update = (
                            profile.last_activity is None or
                            profile.last_activity < (now - timedelta(minutes=5))
                        )
                        if should_update:
                            profile.last_activity = now
                            profile.save(update_fields=['last_activity'])
                    
                    # Check if blocked
                    if profile.is_blocked:
                        # Don't block staff/admin users
                        if not request.user.is_staff and not request.user.is_superuser:
                            logout(request)
                            messages.error(request, 'Your account has been blocked. Please contact support for assistance.')
                            return redirect('login')
            except Exception:
                # If profile doesn't exist, allow access
                pass
        
        response = self.get_response(request)
        return response



class ResellLinkMiddleware:
    """
    Middleware to capture and validate resell links from URL parameters.
    Stores resell link information in session for checkout process.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check for resell code in query parameters
        resell_code = request.GET.get('resell')
        
        if resell_code:
            try:
                from .models import ResellLink
                from django.utils import timezone
                
                # Validate resell link
                resell_link = ResellLink.objects.select_related('reseller', 'product').get(
                    resell_code=resell_code
                )
                
                # Check if link is active
                if resell_link.is_active and resell_link.product.is_active:
                    # Check expiration
                    if not resell_link.expires_at or resell_link.expires_at > timezone.now():
                        # Store resell link ID in session
                        request.session['resell_link_id'] = resell_link.id
                        request.session['resell_code'] = resell_link.resell_code
                        
                        # Increment views count
                        resell_link.views_count += 1
                        resell_link.save(update_fields=['views_count'])
                        
                        # Store resell link in request for easy access
                        request.resell_link = resell_link
                    else:
                        # Link expired, deactivate it
                        resell_link.is_active = False
                        resell_link.save(update_fields=['is_active'])
                        
            except ResellLink.DoesNotExist:
                # Invalid resell code, ignore
                pass
            except Exception:
                # Any other error, ignore and continue
                pass
        
        # Check if there's a resell link in session
        elif 'resell_link_id' in request.session:
            try:
                from .models import ResellLink
                
                resell_link = ResellLink.objects.select_related('reseller', 'product').get(
                    id=request.session['resell_link_id']
                )
                
                # Verify link is still active
                if resell_link.is_active and resell_link.product.is_active:
                    request.resell_link = resell_link
                else:
                    # Link no longer active, clear from session
                    del request.session['resell_link_id']
                    if 'resell_code' in request.session:
                        del request.session['resell_code']
                        
            except ResellLink.DoesNotExist:
                # Link deleted, clear from session
                del request.session['resell_link_id']
                if 'resell_code' in request.session:
                    del request.session['resell_code']
            except Exception:
                pass
        
        response = self.get_response(request)
        return response
