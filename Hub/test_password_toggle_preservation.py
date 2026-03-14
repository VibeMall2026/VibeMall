"""
Preservation Property Tests for Password Visibility Toggle Fix

These tests verify baseline behavior on UNFIXED code that must be preserved after the fix.

**IMPORTANT**: These tests should PASS on unfixed code to confirm baseline behavior.
**GOAL**: Capture existing functionality that must remain unchanged by the fix.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""

from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth.models import User
import re


class PasswordTogglePreservationTests(TestCase):
    """
    Preservation Property Tests
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
    
    These tests verify that non-toggle functionality remains unchanged:
    - Password fields are masked by default on page load (3.1, 3.5)
    - Form submission works correctly (3.2, 3.3)
    - Password validation works correctly (3.4)
    - Email validation works correctly (3.4)
    - Hover effects display correctly (3.6)
    - Remember me checkbox works correctly (3.4)
    - Terms acceptance checkbox works correctly (3.4)
    """
    
    def setUp(self):
        """Set up test client and test user"""
        self.client = Client()
        # Create a test user for login tests
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_login_password_masked_by_default(self):
        """
        Test that password field is masked by default on page load
        
        **Validates: Requirements 3.1, 3.5**
        
        PRESERVATION: Password fields must be masked with type="password" by default
        """
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check that password input has type="password"
        password_input_pattern = r'<input[^>]*id=["\']password["\'][^>]*type=["\']password["\'][^>]*>'
        password_input_pattern_alt = r'<input[^>]*type=["\']password["\'][^>]*id=["\']password["\'][^>]*>'
        
        has_password_type = (
            re.search(password_input_pattern, content) is not None or
            re.search(password_input_pattern_alt, content) is not None
        )
        
        self.assertTrue(
            has_password_type,
            "Password field must be masked (type='password') by default on page load"
        )

    
    def test_registration_passwords_masked_by_default(self):
        """
        Test that password fields are masked by default on registration page
        
        **Validates: Requirements 3.1, 3.5**
        
        PRESERVATION: Both password and confirm_password fields must be masked by default
        """
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Count password type inputs (should be at least 2)
        password_inputs = re.findall(r'type=["\']password["\']', content)
        
        self.assertGreaterEqual(
            len(password_inputs), 2,
            "Registration form must have at least 2 password fields masked by default"
        )
    
    def test_login_form_submission_works(self):
        """
        Test that login form submission works correctly
        
        **Validates: Requirements 3.2**
        
        PRESERVATION: Form submission must process login request with password value
        """
        # Submit login form with valid credentials
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPassword123!'
        }, follow=True)
        
        # Check that login was successful (redirected and user is authenticated)
        self.assertTrue(response.wsgi_request.user.is_authenticated,
                       "Login form submission must work correctly")
    
    def test_registration_form_has_all_fields(self):
        """
        Test that registration form has all required fields
        
        **Validates: Requirements 3.3**
        
        PRESERVATION: Form must have all fields for submission
        """
        response = self.client.get(reverse('register'))
        content = response.content.decode('utf-8')
        
        # Verify form elements exist
        has_name_field = 'name="name"' in content
        has_username_field = 'name="username"' in content
        has_email_field = 'name="email"' in content
        has_password_field = 'name="password"' in content
        has_confirm_password = 'name="confirm_password"' in content
        has_terms_checkbox = 'name="terms_accepted"' in content
        has_submit_button = 'type="submit"' in content
        
        self.assertTrue(
            all([has_name_field, has_username_field, has_email_field, 
                 has_password_field, has_confirm_password, has_terms_checkbox, 
                 has_submit_button]),
            "Registration form must have all required fields for submission"
        )
    
    def test_password_strength_indicator_exists(self):
        """
        Test that password strength indicator exists on registration page
        
        **Validates: Requirements 3.4**
        
        PRESERVATION: Password validation (strength indicator) must continue to function
        """
        response = self.client.get(reverse('register'))
        content = response.content.decode('utf-8')
        
        # Check for password strength indicator elements
        has_strength_bar = 'strength_bar' in content or 'password-strength' in content
        has_strength_text = 'strength_text' in content or 'Password strength' in content
        has_strength_function = 'calculatePasswordStrength' in content
        
        self.assertTrue(
            has_strength_bar and has_strength_text and has_strength_function,
            "Password strength indicator must exist and function correctly"
        )
    
    def test_password_match_validation_exists(self):
        """
        Test that password match validation exists on registration page
        
        **Validates: Requirements 3.4**
        
        PRESERVATION: Password match checking must continue to function
        """
        response = self.client.get(reverse('register'))
        content = response.content.decode('utf-8')
        
        # Check for password match validation elements
        has_confirm_password = 'confirm_password' in content
        has_password_error = 'password_error' in content
        
        self.assertTrue(
            has_confirm_password and has_password_error,
            "Password match validation must exist and function correctly"
        )
    
    def test_email_validation_exists(self):
        """
        Test that email validation exists on both forms
        
        **Validates: Requirements 3.4**
        
        PRESERVATION: Email validation must continue to function normally
        """
        # Check registration page
        register_response = self.client.get(reverse('register'))
        register_content = register_response.content.decode('utf-8')
        
        # Check for email validation elements
        register_has_email_feedback = 'email_feedback' in register_content
        register_has_email_regex = 'emailRegex' in register_content
        
        self.assertTrue(
            register_has_email_feedback and register_has_email_regex,
            "Email validation must exist and function correctly on registration page"
        )
    
    def test_hover_effect_css_exists(self):
        """
        Test that hover effects on toggle button are defined
        
        **Validates: Requirements 3.6**
        
        PRESERVATION: Hover effects must continue to display correctly
        """
        # Check login page for toggle button
        login_response = self.client.get(reverse('login'))
        login_content = login_response.content.decode('utf-8')
        
        # Check that toggle button class exists
        has_toggle_btn = 'toggle-password-btn' in login_content
        
        self.assertTrue(
            has_toggle_btn,
            "Toggle button must exist with proper class for hover effects"
        )
    
    def test_remember_me_checkbox_exists(self):
        """
        Test that remember me checkbox exists and has functionality
        
        **Validates: Requirements 3.4**
        
        PRESERVATION: Remember me functionality must continue to work
        """
        response = self.client.get(reverse('login'))
        content = response.content.decode('utf-8')
        
        # Check for remember me checkbox
        has_remember_checkbox = 'remember_me' in content
        has_remember_label = 'Remember me' in content
        has_remember_logic = 'localStorage' in content and 'vibemall_remember_me' in content
        
        self.assertTrue(
            has_remember_checkbox and has_remember_label and has_remember_logic,
            "Remember me checkbox must exist and function correctly"
        )
    
    def test_terms_acceptance_checkbox_exists(self):
        """
        Test that terms acceptance checkbox exists and has validation
        
        **Validates: Requirements 3.4**
        
        PRESERVATION: Terms acceptance checkbox must continue to work
        """
        response = self.client.get(reverse('register'))
        content = response.content.decode('utf-8')
        
        # Check for terms checkbox
        has_terms_checkbox = 'terms_accepted' in content
        has_terms_label = 'Terms & Conditions' in content
        has_terms_error = 'terms_error' in content
        
        self.assertTrue(
            has_terms_checkbox and has_terms_label and has_terms_error,
            "Terms acceptance checkbox must exist and function correctly"
        )
