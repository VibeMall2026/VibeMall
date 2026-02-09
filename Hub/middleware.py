from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone


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
                        profile.last_activity = timezone.now()
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
