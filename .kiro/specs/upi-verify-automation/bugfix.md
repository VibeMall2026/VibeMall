# Bugfix Requirements Document

## Introduction

On the return request page, UPI ID verification is incomplete. When a user enters a UPI ID and clicks "Verify", the system should automatically attempt to collect ₹1 to that UPI ID to confirm it is valid. Currently, clicking "Verify" does not trigger this payment collection flow — the automation is missing, leaving UPI IDs unverified and the verification status never updated.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a user enters a UPI ID and clicks the "Verify" button THEN the system does not trigger any payment collection attempt
1.2 WHEN the "Verify" button is clicked THEN the system does not update the UPI ID verification status to "Verified" or show any error

### Expected Behavior (Correct)

2.1 WHEN a user enters a UPI ID and clicks the "Verify" button THEN the system SHALL automatically attempt to collect ₹1 to that UPI ID
2.2 WHEN the ₹1 collection to the UPI ID succeeds THEN the system SHALL mark the UPI ID as "Verified" and display the verified status
2.3 WHEN the ₹1 collection to the UPI ID fails THEN the system SHALL display an inline error message "Invalid UPI ID"

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a user has not yet clicked "Verify" THEN the system SHALL CONTINUE TO display the UPI ID input field and "Verify" button in their default unverified state
3.2 WHEN a UPI ID has already been verified THEN the system SHALL CONTINUE TO display the verified status without requiring re-verification
3.3 WHEN a user submits the return request form THEN the system SHALL CONTINUE TO require a verified UPI ID before allowing submission
