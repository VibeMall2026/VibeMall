"""
Input Sanitization Utility for XSS Prevention

This module provides functions to sanitize user input and prevent Cross-Site Scripting (XSS)
attacks. It uses the bleach library to strip potentially dangerous HTML/JavaScript.

Key Functions:
    - sanitize_html: Sanitize HTML content allowing safe tags
    - sanitize_text: Remove all HTML tags from text
    - sanitize_url: Validate and sanitize URLs
"""

import re
import logging
from typing import Optional
from urllib.parse import urlparse

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    import html

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Sanitizes user inputs to prevent XSS and injection attacks."""
    
    # Allowed HTML tags for rich text content (comments, descriptions)
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'a', 'ul', 'ol',
        'li', 'blockquote', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
    ]
    
    # Allowed HTML attributes for safe linking
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title'],
    }
    
    # Safe URL schemes
    SAFE_URL_SCHEMES = ['http', 'https', 'mailto']
    
    @staticmethod
    def sanitize_html(content: Optional[str], allowed_tags: list = None, 
                     allowed_attributes: dict = None) -> str:
        """
        Sanitize HTML content by removing potentially dangerous tags and attributes.
        
        Args:
            content: Raw HTML content from user
            allowed_tags: List of HTML tags to allow (default: ALLOWED_TAGS)
            allowed_attributes: Dict of allowed attributes per tag (default: ALLOWED_ATTRIBUTES)
        
        Returns:
            Sanitized HTML string safe for display
        
        Example:
            >>> content = '<p>Hello <script>alert("XSS")</script></p>'
            >>> sanitized = InputSanitizer.sanitize_html(content)
            >>> sanitized
            '<p>Hello &lt;script&gt;alert("XSS")&lt;/script&gt;</p>'
        """
        if not content:
            return ''
        
        if allowed_tags is None:
            allowed_tags = InputSanitizer.ALLOWED_TAGS
        
        if allowed_attributes is None:
            allowed_attributes = InputSanitizer.ALLOWED_ATTRIBUTES
        
        if not BLEACH_AVAILABLE:
            # Fallback: escape all HTML entities
            logger.warning("bleach not installed, using HTML escape fallback for sanitization")
            return html.escape(str(content))
        
        # Use bleach to sanitize
        cleaned = bleach.clean(
            str(content),
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True,
            strip_comments=True,
        )
        
        return cleaned
    
    @staticmethod
    def sanitize_text(content: Optional[str]) -> str:
        """
        Remove all HTML tags from text, leaving only plain text.
        
        Args:
            content: Text potentially containing HTML
        
        Returns:
            Plain text without HTML tags
        
        Example:
            >>> content = '<p>Hello <b>World</b></p>'
            >>> sanitized = InputSanitizer.sanitize_text(content)
            >>> sanitized
            'Hello World'
        """
        if not content:
            return ''
        
        if not BLEACH_AVAILABLE:
            # Fallback: use regex to remove HTML tags
            content = str(content)
            content = re.sub(r'<[^>]+>', '', content)
            return html.unescape(content).strip()
        
        # Use bleach with no tags allowed
        cleaned = bleach.clean(
            str(content),
            tags=[],
            strip=True,
            strip_comments=True,
        )
        
        return html.unescape(cleaned).strip()
    
    @staticmethod
    def sanitize_url(url: Optional[str], allowed_schemes: list = None) -> Optional[str]:
        """
        Validate and sanitize URLs to prevent javascript: and data: URIs.
        
        Args:
            url: URL string from user
            allowed_schemes: List of allowed URL schemes (default: SAFE_URL_SCHEMES)
        
        Returns:
            Valid URL or None if URL is invalid
        
        Example:
            >>> url = 'javascript:alert("XSS")'
            >>> sanitized = InputSanitizer.sanitize_url(url)
            >>> sanitized is None
            True
            
            >>> url = 'https://example.com'
            >>> sanitized = InputSanitizer.sanitize_url(url)
            >>> sanitized
            'https://example.com'
        """
        if not url:
            return None
        
        if allowed_schemes is None:
            allowed_schemes = InputSanitizer.SAFE_URL_SCHEMES
        
        url = str(url).strip()
        
        # Block common XSS URL patterns
        dangerous_patterns = [
            r'^javascript:',
            r'^data:',
            r'^vbscript:',
            r'on\w+\s*=',  # Event handlers
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(f"Blocked dangerous URL pattern: {url[:50]}")
                return None
        
        # If URL is relative, allow it
        if url.startswith('/') or url.startswith('.'):
            return url
        
        # Parse and validate absolute URLs
        try:
            parsed = urlparse(url)
            if parsed.scheme and parsed.scheme not in allowed_schemes:
                logger.warning(f"Blocked URL with disallowed scheme: {parsed.scheme}")
                return None
            return url
        except Exception as e:
            logger.warning(f"Invalid URL detected: {str(e)}")
            return None
    
    @staticmethod
    def sanitize_filename(filename: Optional[str], max_length: int = 200) -> str:
        """
        Sanitize file names to prevent directory traversal and injection attacks.
        
        Args:
            filename: Original filename
            max_length: Maximum filename length (default: 200)
        
        Returns:
            Safe filename
        
        Example:
            >>> filename = '../../../etc/passwd'
            >>> sanitized = InputSanitizer.sanitize_filename(filename)
            >>> sanitized
            'etcpasswd'
        """
        if not filename:
            return 'file'
        
        filename = str(filename)
        
        # Remove directory traversal attempts
        filename = filename.replace('..', '')
        filename = filename.replace('/', '')
        filename = filename.replace('\\', '')
        filename = filename.replace('\x00', '')
        
        # Remove potentially dangerous characters
        filename = re.sub(r'[^\w\s.-]', '', filename)
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > max_length:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            name = name[:max_length - len(ext) - 1]
            filename = f"{name}.{ext}" if ext else name
        
        # Ensure it's not empty
        if not filename:
            filename = 'file'
        
        return filename
    
    @staticmethod
    def sanitize_email(email: Optional[str]) -> Optional[str]:
        """
        Validate and sanitize email addresses.
        
        Args:
            email: Email address to validate
        
        Returns:
            Lowercase email or None if invalid
        """
        if not email:
            return None
        
        email = str(email).strip().lower()
        
        # Basic email validation (more thorough validation should use django validators)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, email):
            return email
        
        return None
    
    @staticmethod
    def sanitize_phone(phone: Optional[str]) -> Optional[str]:
        """
        Sanitize phone numbers by removing all non-numeric characters.
        
        Args:
            phone: Phone number string
        
        Returns:
            Numeric phone number or empty string
        """
        if not phone:
            return ''
        
        # Keep only digits and leading +
        phone = str(phone).strip()
        if phone.startswith('+'):
            phone = '+' + re.sub(r'\D', '', phone)
        else:
            phone = re.sub(r'\D', '', phone)
        
        return phone


def sanitize_html(content: Optional[str]) -> str:
    """Shortcut function to sanitize HTML content."""
    return InputSanitizer.sanitize_html(content)


def sanitize_text(content: Optional[str]) -> str:
    """Shortcut function to sanitize text (remove all HTML)."""
    return InputSanitizer.sanitize_text(content)


def sanitize_url(url: Optional[str]) -> Optional[str]:
    """Shortcut function to sanitize URLs."""
    return InputSanitizer.sanitize_url(url)


def sanitize_filename(filename: Optional[str]) -> str:
    """Shortcut function to sanitize filenames."""
    return InputSanitizer.sanitize_filename(filename)


def sanitize_email(email: Optional[str]) -> Optional[str]:
    """Shortcut function to sanitize email addresses."""
    return InputSanitizer.sanitize_email(email)


def sanitize_phone(phone: Optional[str]) -> Optional[str]:
    """Shortcut function to sanitize phone numbers."""
    return InputSanitizer.sanitize_phone(phone)
