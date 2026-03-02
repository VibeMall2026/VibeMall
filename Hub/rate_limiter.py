# VibeMall Rate Limiting System
# Protects against brute force attacks and abuse on critical endpoints

from datetime import datetime
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from functools import wraps
from typing import Any, Callable, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Rate Limit Configurations
RATE_LIMITS = {
    'login': {'limit': 5, 'period': 300},  # 5 attempts per 5 minutes
    'password_reset': {'limit': 3, 'period': 3600},  # 3 attempts per hour
    'password_reset_confirm': {'limit': 10, 'period': 3600},  # 10 attempts per hour
    'register': {'limit': 5, 'period': 3600},  # 5 registrations per hour per IP
    'verify_email': {'limit': 10, 'period': 3600},  # 10 verification attempts per hour
    'submit_review': {'limit': 10, 'period': 86400},  # 10 reviews per day
    'submit_question': {'limit': 20, 'period': 86400},  # 20 questions per day
    'add_to_cart': {'limit': 100, 'period': 3600},  # 100 cart adds per hour
    'product_search': {'limit': 100, 'period': 3600},  # 100 searches per hour
    'chat_message': {'limit': 50, 'period': 3600},  # 50 messages per hour
    'subscribe_newsletter': {'limit': 5, 'period': 3600},  # 5 subscriptions per hour per IP
    'checkout': {'limit': 20, 'period': 3600},  # 20 checkout attempts per hour
    'api_general': {'limit': 200, 'period': 3600},  # General API limit
}


class RateLimiter:
    """
    Rate limiting utility for protecting endpoints against abuse.
    Uses Django cache backend for distributed rate limiting.
    """
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'
    
    @staticmethod
    def get_client_identifier(request, use_user: bool = True) -> str:
        """Get unique client identifier (user ID if logged in, otherwise IP)"""
        if use_user and request.user and request.user.is_authenticated:
            return f"user_{request.user.id}"
        return f"ip_{RateLimiter.get_client_ip(request)}"
    
    @staticmethod
    def check_rate_limit(client_id: str, limit_key: str) -> Dict[str, Any]:
        """
        Check if client has exceeded rate limit.
        
        Args:
            client_id: Unique client identifier
            limit_key: Key from RATE_LIMITS dict
            
        Returns:
            dict: {'allowed': bool, 'remaining': int, 'reset_in': int}
        """
        if limit_key not in RATE_LIMITS:
            logger.warning(f"Unknown rate limit key: {limit_key}")
            return {'allowed': True, 'remaining': 999, 'reset_in': 0}
        
        config = RATE_LIMITS[limit_key]
        limit = config['limit']
        period = config['period']
        
        cache_key = f"rate_limit:{limit_key}:{client_id}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            # Calculate reset time
            reset_key = f"rate_limit_reset:{limit_key}:{client_id}"
            reset_time = cache.get(reset_key)
            reset_in = max(0, (reset_time - int(datetime.now().timestamp())) if reset_time else period)
            
            return {
                'allowed': False,
                'remaining': 0,
                'reset_in': reset_in,
                'limit': limit
            }
        
        # Increment counter
        new_count = current_count + 1
        cache.set(cache_key, new_count, period)
        
        # Set reset time on first request
        if current_count == 0:
            reset_key = f"rate_limit_reset:{limit_key}:{client_id}"
            cache.set(reset_key, int(datetime.now().timestamp()) + period, period)
        
        return {
            'allowed': True,
            'remaining': limit - new_count,
            'reset_in': period,
            'limit': limit
        }
    
    @staticmethod
    def is_allowed(client_id: str, limit_key: str) -> bool:
        """Simple check if request is allowed"""
        result = RateLimiter.check_rate_limit(client_id, limit_key)
        return result['allowed']


def rate_limit(limit_key: str, use_user: bool = True, key_prefix: Optional[str] = None) -> Callable:
    """
    Decorator to apply rate limiting to views.
    
    Usage:
        @rate_limit('login')
        def login_view(request):
            ...
            
        @rate_limit('submit_review', use_user=False)  # Per IP rate limit
        def submit_review(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get client identifier
            client_id = RateLimiter.get_client_identifier(request, use_user=use_user)
            
            # Check rate limit
            result = RateLimiter.check_rate_limit(client_id, limit_key)
            
            if not result['allowed']:
                logger.warning(
                    f"Rate limit exceeded for {client_id} on {limit_key}. "
                    f"Reset in {result['reset_in']}s"
                )
                
                # Return error response
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                   request.path.startswith('/api/') or request.path.startswith('/admin-panel/api/'):
                    # AJAX/API request
                    response = JsonResponse({
                        'success': False,
                        'error': 'RATE_LIMIT_EXCEEDED',
                        'message': f'Too many requests. Please try again in {result["reset_in"]} seconds.',
                        'retry_after': result['reset_in']
                    }, status=429)
                    response['Retry-After'] = result['reset_in']
                    return response
                else:
                    # Regular HTML request - show error page
                    context = {
                        'error': 'Too Many Requests',
                        'message': f'You have exceeded the rate limit. Please try again in {result["reset_in"]} seconds.',
                        'retry_after': result['reset_in']
                    }
                    return render(request, 'rate_limit_error.html', context, status=429)
            
            # Call the original view
            response = view_func(request, *args, **kwargs)
            
            # Add rate limit headers to response
            response['X-RateLimit-Limit'] = str(result['limit'])
            response['X-RateLimit-Remaining'] = str(result['remaining'])
            response['X-RateLimit-Reset'] = str(int(datetime.now().timestamp()) + result['reset_in'])
            
            return response
        
        return wrapper
    
    return decorator


def rate_limit_by_field(field_name: str, limit_key: str) -> Callable:
    """
    Decorator to rate limit based on a specific field value (like email address).
    
    Usage:
        @rate_limit_by_field('email', 'password_reset')
        def password_reset(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            field_value = request.POST.get(field_name) or request.GET.get(field_name)
            
            if not field_value:
                return view_func(request, *args, **kwargs)
            
            # Use field value as identifier
            client_id = f"{field_name}_{field_value}"
            result = RateLimiter.check_rate_limit(client_id, limit_key)
            
            if not result['allowed']:
                logger.warning(
                    f"Rate limit exceeded for {field_name}={field_value} on {limit_key}. "
                    f"Reset in {result['reset_in']}s"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    response = JsonResponse({
                        'success': False,
                        'error': 'RATE_LIMIT_EXCEEDED',
                        'message': f'Please wait {result["reset_in"]} seconds before trying again.'
                    }, status=429)
                    response['Retry-After'] = result['reset_in']
                    return response
                else:
                    return render(request, 'rate_limit_error.html', {
                        'message': f'Please try again in {result["reset_in"]} seconds.'
                    }, status=429)
            
            response = view_func(request, *args, **kwargs)
            response['X-RateLimit-Remaining'] = str(result['remaining'])
            return response
        
        return wrapper
    
    return decorator


def check_rate_limit_middleware(get_response: Callable) -> Callable:
    """
    Middleware to apply global rate limiting.
    Responds quickly with 429 status before view is processed.
    """
    def middleware(request):
        # Skip rate limiting for static files and media
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return get_response(request)
        
        # Skip for certain paths
        skip_paths = ['/health/', '/status/', '/robots.txt', '/sitemap.xml']
        if any(request.path.startswith(path) for path in skip_paths):
            return get_response(request)
        
        # Get client IP
        client_ip = RateLimiter.get_client_ip(request)
        
        # Check global rate limit (for protection against DDoS)
        # Allow very high limit for general browsing
        global_key = f"global_rate:{client_ip}"
        global_limit = 5000  # 5000 requests per hour
        global_period = 3600
        
        current = cache.get(global_key, 0)
        if current >= global_limit:
            logger.warning(f"Global rate limit exceeded for IP: {client_ip}")
            return JsonResponse({
                'error': 'Too many requests',
                'message': 'Your IP address has made too many requests.'
            }, status=429)
        
        cache.set(global_key, current + 1, global_period)
        
        response = get_response(request)
        return response
    
    return middleware


# Utility function to reset rate limits (for admin use)
def reset_rate_limit(client_id: str, limit_key: Optional[str] = None) -> None:
    """
    Reset rate limit for a client.
    
    Usage:
        reset_rate_limit('ip_192.168.1.1', 'login')  # Reset specific limit
        reset_rate_limit('user_123')  # Reset all limits for user
    """
    if limit_key:
        cache_key = f"rate_limit:{limit_key}:{client_id}"
        cache.delete(cache_key)
        logger.info(f"Rate limit reset for {client_id} on {limit_key}")
    else:
        # Reset all limits for this client
        for key in RATE_LIMITS.keys():
            cache_key = f"rate_limit:{key}:{client_id}"
            cache.delete(cache_key)
        logger.info(f"All rate limits reset for {client_id}")


# Utility function to get rate limit status
def get_rate_limit_status(client_id: str, limit_key: str) -> Optional[Dict[str, Any]]:
    """Get current rate limit status for a client"""
    if limit_key not in RATE_LIMITS:
        return None
    
    config = RATE_LIMITS[limit_key]
    cache_key = f"rate_limit:{limit_key}:{client_id}"
    current_count = cache.get(cache_key, 0)
    time_remaining = cache.ttl(cache_key) if hasattr(cache, 'ttl') else config['period']
    
    return {
        'limit_key': limit_key,
        'limit': config['limit'],
        'current_count': current_count,
        'remaining': max(0, config['limit'] - current_count),
        'period': config['period'],
        'time_remaining': time_remaining
    }


# Utility function to list all active rate limits for debugging
def get_all_rate_limits(client_id: str) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get all rate limit statuses for a client"""
    statuses = {}
    for key in RATE_LIMITS.keys():
        statuses[key] = get_rate_limit_status(client_id, key)
    return statuses
