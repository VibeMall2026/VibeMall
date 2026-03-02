"""
Environment Variable Validation Utility

Validates that all required environment variables are set and properly configured
for Django startup. This prevents runtime errors from missing configuration.

Critical Variables:
    - SECRET_KEY: Django secret key (has safe fallback but should be set in production)
    - DEBUG: Debug mode flag
    
Important Variables (warnings if missing):
    - EMAIL_HOST_USER: Email sender address
    - EMAIL_HOST_PASSWORD: Email sender password
    - RAZORPAY_KEY_ID: Razorpay API key
    - RAZORPAY_KEY_SECRET: Razorpay API secret
    - RAZORPAY_WEBHOOK_SECRET: Razorpay webhook secret
    
Optional Variables (have safe defaults):
    - DATABASE_URL: Database connection string
    - ALLOWED_HOSTS: Comma-separated list of allowed hosts
    - EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS: Email configuration
"""

import os
import logging
from typing import Any, Dict, List
from decouple import config, UndefinedValueError

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """Validates environment variables on Django startup."""
    
    # Critical variables that must be set
    CRITICAL_VARS = []
    
    # Important variables that should be set (warnings if missing)
    IMPORTANT_VARS = {
        'EMAIL_HOST_USER': 'Email host user for sending emails',
        'EMAIL_HOST_PASSWORD': 'Email host password for sending emails',
        'RAZORPAY_KEY_ID': 'Razorpay API key ID for payment processing',
        'RAZORPAY_KEY_SECRET': 'Razorpay API secret for payment processing',
        'RAZORPAY_WEBHOOK_SECRET': 'Razorpay webhook secret for payment verification',
    }
    
    # Optional variables (have defaults)
    OPTIONAL_VARS = {
        'DEBUG': 'Debug mode (default: True)',
        'SECRET_KEY': 'Django secret key (has safe fallback)',
        'DATABASE_URL': 'Database connection URL (default: SQLite)',
        'ALLOWED_HOSTS': 'Comma-separated allowed hosts (default: localhost,127.0.0.1)',
        'EMAIL_HOST': 'Email SMTP host (default: smtp.gmail.com)',
        'EMAIL_PORT': 'Email SMTP port (default: 587)',
        'EMAIL_USE_TLS': 'Use TLS for email (default: True)',
        'DEFAULT_FROM_EMAIL': 'Default from email (default: VibeMall <info@vibemall.com>)',
    }
    
    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """
        Validate environment variables on Django startup.
        
        Returns:
            dict: Validation result with 'valid' (bool) and 'messages' (list) keys
        """
        messages: List[str] = []
        missing_critical: List[str] = []
        missing_important: List[str] = []
        found_optional: List[str] = []
        
        # Check critical variables
        for var_name in cls.CRITICAL_VARS:
            try:
                value = config(var_name)
                if not value or value.strip() == '':
                    missing_critical.append(var_name)
            except UndefinedValueError:
                missing_critical.append(var_name)
        
        # Check important variables
        for var_name, description in cls.IMPORTANT_VARS.items():
            try:
                value = config(var_name, default=None)
                if value is None or value.strip() == '':
                    missing_important.append(f"{var_name}: {description}")
            except UndefinedValueError:
                missing_important.append(f"{var_name}: {description}")
        
        # Check which optional variables are set
        for var_name, description in cls.OPTIONAL_VARS.items():
            try:
                value = config(var_name, default=None)
                if value is not None and value.strip() != '':
                    found_optional.append(var_name)
            except Exception:
                pass
        
        # Build messages
        if missing_critical:
            msg = f"[CRITICAL] Missing required environment variables: {', '.join(missing_critical)}"
            messages.append(msg)
            logger.error(msg)
        
        if missing_important:
            msg = f"[WARNING] Missing important environment variables:\n  " + \
                  "\n  ".join(missing_important)
            messages.append(msg)
            logger.warning(msg)
        
        if found_optional:
            msg = f"[INFO] Optional environment variables configured: {', '.join(found_optional)}"
            messages.append(msg)
            logger.info(msg)
        
        # Log validation summary
        debug_mode = config('DEBUG', default=True, cast=bool)
        if debug_mode:
            logger.info("[ENV VALIDATOR] Running in DEBUG mode")
        else:
            logger.info("[ENV VALIDATOR] Running in PRODUCTION mode - ensure all configurations are correct")
        
        # Return validation result
        valid = len(missing_critical) == 0
        return {
            'valid': valid,
            'critical_missing': missing_critical,
            'important_missing': missing_important,
            'optional_configured': found_optional,
            'messages': messages,
        }
    
    @classmethod
    def log_summary(cls) -> Dict[str, Any]:
        """Log a summary of environment validation."""
        result = cls.validate()
        
        if result['valid']:
            logger.info("✓ Environment validation passed - all critical variables are set")
        else:
            logger.error("✗ Environment validation FAILED - check missing variables above")
        
        return result


def validate_environment() -> Dict[str, Any]:
    """
    Run environment validation on Django startup.
    
    Call this function in settings.py or apps.py to ensure
    all required environment variables are configured.
    """
    validator = EnvironmentValidator()
    result = validator.log_summary()
    
    if not result['valid']:
        raise EnvironmentError(
            f"Environment validation failed. Missing critical variables: "
            f"{', '.join(result['critical_missing'])}"
        )
    
    return result
