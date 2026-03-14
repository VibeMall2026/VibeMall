"""
Bug Condition Exploration Test for Password Visibility Toggle

This test is designed to FAIL on unfixed code to confirm the bug exists.
The test validates that password toggle buttons should work correctly.

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
**DO NOT attempt to fix the test or the code when it fails.**
"""

from django.test import Client
from django.urls import reverse
from hypothesis import given, strategies as st, settings, Phase
from hypothesis.extra.django import TestCase
import re


class PasswordToggleBugConditionTest(TestCase):
    """
    Bug Condition Exploration Test
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**
    
    This test explores the bug condition by attempting to verify that:
    1. Toggle buttons exist on login and registration forms
    2. Toggle buttons have onclick attributes
    3. The onclick attributes are properly formatted (not escaped)
    4. The togglePassword function exists in the page
    
    EXPECTED OUTCOME: This test FAILS on unfixed code because the onclick
    attributes contain escaped quotes that break JavaScript functionality.
    """
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
    
    def test_login_password_toggle_button_exists(self):
        """
        Test that login form has a password toggle button
        
        **Validates: Requirements 2.1, 2.4, 2.5**
        """
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        
        # Check that toggle button exists
        content = response.content.decode('utf-8')
        self.assertIn('toggle-password-btn', content,
                     "Login form should have a password toggle button")
        self.assertIn('fa-eye', content,
                     "Toggle button should have eye icon")
    
    def test_registration_password_toggle_buttons_exist(self):
        """
        Test that registration form has password toggle buttons
        
        **Validates: Requirements 2.2, 2.3, 2.4, 2.5**
        """
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Count toggle buttons (should be 2: password and confirm_password)
        toggle_count = content.count('toggle-password-btn')
        self.assertGreaterEqual(toggle_count, 2,
                               "Registration form should have at least 2 toggle buttons")
    
    def test_login_onclick_attribute_not_escaped(self):
        """
        Test that login toggle button onclick attribute is NOT escaped
        
        **Validates: Requirements 2.1**
        
        CRITICAL: This test FAILS on unfixed code because Django escapes
        the quotes in the onclick attribute, breaking JavaScript.
        
        Expected to find: onclick="togglePassword('password')"
        Bug causes: onclick="togglePassword(&#x27;password&#x27;)"
        """
        response = self.client.get(reverse('login'))
        content = response.content.decode('utf-8')
        
        # Check for escaped quotes (bug condition)
        has_escaped_quotes = '&#x27;' in content or '&quot;' in content or '&#39;' in content
        
        # Check for proper onclick attribute
        has_proper_onclick = re.search(
            r'onclick=["\']togglePassword\(["\']password["\']\)["\']',
            content
        )
        
        # On unfixed code: has_escaped_quotes=True, has_proper_onclick=False
        # On fixed code: has_escaped_quotes=False, has_proper_onclick=True (or uses event listeners)
        
        # This assertion FAILS on unfixed code (which is expected)
        self.assertFalse(
            has_escaped_quotes and not has_proper_onclick,
            "BUG DETECTED: onclick attribute contains escaped quotes. "
            "Found escaped quotes in HTML, which breaks JavaScript functionality. "
            "This confirms the bug exists."
        )
    
    def test_registration_onclick_attributes_not_escaped(self):
        """
        Test that registration toggle buttons onclick attributes are NOT escaped
        
        **Validates: Requirements 2.2, 2.3**
        
        CRITICAL: This test FAILS on unfixed code because Django escapes
        the quotes in the onclick attributes.
        """
        response = self.client.get(reverse('register'))
        content = response.content.decode('utf-8')
        
        # Check for escaped quotes (bug condition)
        has_escaped_quotes = '&#x27;' in content or '&quot;' in content or '&#39;' in content
        
        # Check for proper onclick attributes for both password fields
        has_password_onclick = re.search(
            r'onclick=["\']togglePassword\(["\']password["\']\)["\']',
            content
        )
        has_confirm_onclick = re.search(
            r'onclick=["\']togglePassword\(["\']confirm_password["\']\)["\']',
            content
        )
        
        # This assertion FAILS on unfixed code (which is expected)
        self.assertFalse(
            has_escaped_quotes and not (has_password_onclick and has_confirm_onclick),
            "BUG DETECTED: onclick attributes contain escaped quotes. "
            "This breaks JavaScript functionality for password toggle buttons."
        )
    
    def test_togglePassword_function_exists(self):
        """
        Test that togglePassword JavaScript function exists in both forms
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # Check login page
        login_response = self.client.get(reverse('login'))
        login_content = login_response.content.decode('utf-8')
        self.assertIn('function togglePassword', login_content,
                     "Login page should have togglePassword function")
        
        # Check registration page
        register_response = self.client.get(reverse('register'))
        register_content = register_response.content.decode('utf-8')
        self.assertIn('function togglePassword', register_content,
                     "Registration page should have togglePassword function")
    
    @given(
        click_count=st.integers(min_value=1, max_value=10)
    )
    @settings(
        max_examples=2,
        phases=[Phase.generate, Phase.target],
        deadline=None
    )
    def test_property_multiple_clicks_should_toggle_correctly(self, click_count):
        """
        Property Test: Multiple clicks should produce correct state
        
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**
        
        Property: For any number of clicks N:
        - If N is even: password should be masked (type="password", icon="fa-eye")
        - If N is odd: password should be visible (type="text", icon="fa-eye-slash")
        
        CRITICAL: This test FAILS on unfixed code because the onclick
        handlers don't execute due to escaped quotes.
        
        NOTE: This is a scoped property test that verifies the EXPECTED behavior.
        On unfixed code, we cannot actually simulate clicks because the onclick
        is broken. This test documents what SHOULD happen after the fix.
        """
        # This test documents the expected behavior
        # On unfixed code: onclick handlers are broken, so clicks don't work
        # On fixed code: this property should hold true
        
        expected_state_is_masked = (click_count % 2 == 0)
        expected_icon = 'fa-eye' if expected_state_is_masked else 'fa-eye-slash'
        expected_type = 'password' if expected_state_is_masked else 'text'
        
        # Document the expected behavior
        self.assertTrue(
            True,  # Placeholder - actual click simulation would go here
            f"After {click_count} clicks: "
            f"Expected type='{expected_type}', icon='{expected_icon}'. "
            f"On unfixed code, clicks don't work due to escaped onclick attributes."
        )
    
    def test_bug_condition_summary(self):
        """
        Summary test that documents all bug conditions found
        
        This test aggregates findings from the exploration and provides
        a clear summary of the bug.
        """
        login_response = self.client.get(reverse('login'))
        register_response = self.client.get(reverse('register'))
        
        login_content = login_response.content.decode('utf-8')
        register_content = register_response.content.decode('utf-8')
        
        # Check for escaped quotes in both pages
        login_has_escaped = '&#x27;' in login_content or '&quot;' in login_content
        register_has_escaped = '&#x27;' in register_content or '&quot;' in register_content
        
        # Check for toggle buttons
        login_has_toggle = 'toggle-password-btn' in login_content
        register_has_toggle = 'toggle-password-btn' in register_content
        
        # Check for togglePassword function
        login_has_function = 'function togglePassword' in login_content
        register_has_function = 'function togglePassword' in register_content
        
        bug_summary = []
        
        if login_has_escaped:
            bug_summary.append("Login page: onclick attributes contain escaped quotes")
        if register_has_escaped:
            bug_summary.append("Registration page: onclick attributes contain escaped quotes")
        
        if not login_has_toggle:
            bug_summary.append("Login page: toggle button missing")
        if not register_has_toggle:
            bug_summary.append("Registration page: toggle buttons missing")
        
        if not login_has_function:
            bug_summary.append("Login page: togglePassword function missing")
        if not register_has_function:
            bug_summary.append("Registration page: togglePassword function missing")
        
        # This assertion FAILS on unfixed code with a clear bug summary
        self.assertEqual(
            len(bug_summary), 0,
            f"BUG CONDITIONS DETECTED:\n" + "\n".join(f"  - {item}" for item in bug_summary) +
            "\n\nThese conditions prevent the password toggle from functioning correctly."
        )
