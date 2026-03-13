# Implementation Plan

- [-] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Password Visibility Toggle Functionality
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases - clicking toggle buttons on login and registration forms
  - Test that clicking the toggle button on login password field toggles input type between "password" and "text"
  - Test that clicking the toggle button on registration password field toggles input type between "password" and "text"
  - Test that clicking the toggle button on registration confirm password field toggles input type between "password" and "text"
  - Test that the icon toggles between `fa-eye` and `fa-eye-slash` for all toggle buttons
  - Test that multiple clicks produce correct state (even clicks = masked, odd clicks = revealed)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: toggle buttons do not respond to clicks, onclick attributes contain escaped quotes
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [~] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Toggle Functionality
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-toggle interactions
  - Test that password fields are masked by default on page load
  - Test that form submission works correctly (login and registration)
  - Test that password validation (strength indicator, match checking) works correctly
  - Test that email validation works correctly
  - Test that hover effects on toggle button display correctly (background changes to #f4a800)
  - Test that remember me checkbox on login form works correctly
  - Test that terms acceptance checkbox on registration form works correctly
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 3. Fix for password visibility toggle non-functional due to Django template escaping

  - [~] 3.1 Update login.html template
    - Remove inline `onclick="togglePassword('password')"` attribute from toggle button
    - Add `data-target="password"` attribute to toggle button
    - Add event listener in JavaScript section to attach click handler
    - Use `document.querySelector('.toggle-password-btn')` to select the button
    - Read `data-target` attribute and call `togglePassword()` with that value
    - _Bug_Condition: isBugCondition(input) where input.target.hasClass('toggle-password-btn') AND onclick is malformed_
    - _Expected_Behavior: Toggle input type between "password" and "text", toggle icon between fa-eye and fa-eye-slash_
    - _Preservation: All non-toggle interactions (form submission, validation, hover effects, remember me) must remain unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [~] 3.2 Update register.html template
    - Remove inline `onclick="togglePassword('password')"` from password field toggle button
    - Remove inline `onclick="togglePassword('confirm_password')"` from confirm password field toggle button
    - Add `data-target="password"` attribute to password field toggle button
    - Add `data-target="confirm_password"` attribute to confirm password field toggle button
    - Add event listeners in JavaScript section to attach click handlers to both buttons
    - Use `document.querySelectorAll('.toggle-password-btn')` to select all toggle buttons
    - Attach click event listener to each button that reads `data-target` and calls `togglePassword()`
    - _Bug_Condition: isBugCondition(input) where input.target.hasClass('toggle-password-btn') AND onclick is malformed_
    - _Expected_Behavior: Toggle input type between "password" and "text", toggle icon between fa-eye and fa-eye-slash for both password fields_
    - _Preservation: All non-toggle interactions (form submission, validation, hover effects, terms checkbox) must remain unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [~] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Password Visibility Toggle Functionality
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [~] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Toggle Functionality
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [~] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
