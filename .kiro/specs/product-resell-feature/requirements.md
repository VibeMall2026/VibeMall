# Requirements Document: Product Resell Feature

## Introduction

The Product Resell Feature transforms the e-commerce platform into a marketplace where users can become micro-entrepreneurs by reselling products with their own markup. This feature enables resellers to share products with customers at marked-up prices, with delivery going directly to the end customer. The platform handles payment distribution, earning tracking, payout processing, and provides comprehensive admin tools for monitoring resell activities. This system is inspired by Meesho's resell functionality and creates opportunities for users to earn income through product reselling.

## Glossary

- **Reseller**: A user who creates resell links and shares products with customers at marked-up prices
- **End_Customer**: The final buyer who purchases products through a reseller's link
- **Resell_Link**: A unique URL containing a resell code that tracks the reseller and their margin
- **Margin**: The markup amount added by the reseller to the base product price
- **Base_Price**: The original product price before reseller markup
- **Reseller_Earning**: The margin amount earned by a reseller from an order
- **Payout**: Transfer of confirmed earnings from the platform to the reseller's account
- **Resell_Order**: An order placed through a resell link
- **Admin_Panel**: Administrative interface for managing resell operations
- **Payment_Gateway**: External service for processing payments and payouts
- **Reseller_Profile**: Extended user profile containing reseller-specific information and payment details

## Requirements

### Requirement 1: Resell Link Creation

**User Story:** As a reseller, I want to create unique resell links for products with my own margin, so that I can share them with customers and earn from sales.

#### Acceptance Criteria

1. WHEN a reseller selects a product and specifies a margin amount, THE System SHALL generate a unique resell code
2. WHEN generating a resell code, THE System SHALL ensure the code is unique across all existing resell links
3. WHEN a margin amount is provided, THE System SHALL validate that it is greater than zero and does not exceed 50% of the base product price
4. WHEN a resell link is created, THE System SHALL calculate and store the margin percentage
5. WHEN a resell link is created, THE System SHALL generate a shareable URL containing the resell code
6. WHEN a resell link is created, THE System SHALL set its status to active by default

### Requirement 2: Resell Link Validation

**User Story:** As an end customer, I want to access products through valid resell links, so that I can purchase from resellers.

#### Acceptance Criteria

1. WHEN an end customer clicks a resell link, THE System SHALL validate the resell code exists
2. WHEN validating a resell link, THE System SHALL verify the link is active
3. WHEN validating a resell link, THE System SHALL verify the associated product is available
4. IF a resell link is inactive or invalid, THEN THE System SHALL display an error message to the customer
5. WHEN a valid resell link is accessed, THE System SHALL increment the views count for that link
6. WHEN a valid resell link is accessed, THE System SHALL store the resell link reference in the customer's session

### Requirement 3: Resell Order Processing

**User Story:** As an end customer, I want to place orders through resell links, so that I can purchase products from resellers.

#### Acceptance Criteria

1. WHEN a customer adds products to cart via a resell link, THE System SHALL calculate the total price as base price plus margin
2. WHEN processing a resell order, THE System SHALL validate the resell link is still active
3. WHEN creating a resell order, THE System SHALL set the is_resell flag to true
4. WHEN creating a resell order, THE System SHALL associate the order with the reseller user
5. WHEN creating a resell order, THE System SHALL calculate and store the base amount separately from the total margin
6. WHEN creating a resell order, THE System SHALL create order items with both base price and margin amount tracked separately
7. WHEN a resell order is created, THE System SHALL create a ResellerEarning record with status PENDING
8. WHEN a resell order is created, THE System SHALL increment the orders count on the resell link
9. WHEN a resell order is created, THE System SHALL add the margin amount to the resell link's total earnings

### Requirement 4: Payment Processing for Resell Orders

**User Story:** As the platform, I want to process payments for resell orders correctly, so that customers pay the full amount and earnings are tracked for resellers.

#### Acceptance Criteria

1. WHEN processing payment for a resell order, THE System SHALL charge the customer the total amount including base price, margin, tax, and shipping
2. WHEN payment is successful, THE System SHALL set the order payment status to PAID
3. WHEN payment is successful, THE System SHALL clear the customer's cart
4. IF payment fails, THEN THE System SHALL not create the order and SHALL display an error message
5. WHEN payment is processed, THE System SHALL not transfer margin amount to reseller immediately

### Requirement 5: Reseller Earnings Confirmation

**User Story:** As the platform, I want to confirm reseller earnings after order delivery, so that resellers receive payment only for completed orders.

#### Acceptance Criteria

1. WHEN an order status changes to DELIVERED, THE System SHALL allow earnings confirmation for that order
2. WHEN confirming earnings, THE System SHALL verify the ResellerEarning status is PENDING
3. WHEN confirming earnings, THE System SHALL update the ResellerEarning status to CONFIRMED
4. WHEN confirming earnings, THE System SHALL set the confirmed_at timestamp
5. WHEN earnings are confirmed, THE System SHALL add the margin amount to the reseller's available balance
6. WHEN earnings are confirmed, THE System SHALL add the margin amount to the reseller's total earnings
7. WHEN earnings are confirmed, THE System SHALL increment the reseller's total orders count
8. WHEN earnings are confirmed, THE System SHALL send a notification to the reseller

### Requirement 6: Reseller Payout Processing

**User Story:** As a reseller, I want to withdraw my confirmed earnings, so that I can receive payment for my sales.

#### Acceptance Criteria

1. WHEN a reseller requests a payout, THE System SHALL validate the amount does not exceed available balance
2. WHEN a reseller requests a payout, THE System SHALL validate the amount is greater than zero
3. WHEN processing a payout via bank transfer, THE System SHALL require bank account number and IFSC code
4. WHEN processing a payout via UPI, THE System SHALL require UPI ID
5. WHEN a payout is initiated, THE System SHALL create a PayoutTransaction with status INITIATED
6. WHEN a payout is initiated, THE System SHALL deduct the amount from the reseller's available balance
7. WHEN payment gateway confirms successful transfer, THE System SHALL update payout status to COMPLETED
8. WHEN payment gateway confirms successful transfer, THE System SHALL set the completed_at timestamp
9. WHEN payment gateway confirms successful transfer, THE System SHALL update associated ResellerEarning records to PAID status
10. IF payout fails, THEN THE System SHALL update payout status to FAILED and refund the amount to available balance
11. WHEN a payout is completed, THE System SHALL send a success notification to the reseller
12. IF a payout fails, THEN THE System SHALL send a failure notification to the reseller

### Requirement 7: Invoice Generation

**User Story:** As an end customer, I want to receive an invoice for my resell order, so that I have a record of my purchase.

#### Acceptance Criteria

1. WHEN an order payment is successful, THE System SHALL generate an invoice for the order
2. WHEN generating an invoice, THE System SHALL include order number, invoice number, and order date
3. WHEN generating an invoice, THE System SHALL include customer name and shipping address
4. WHEN generating an invoice, THE System SHALL list all order items with product name, quantity, and unit price
5. WHEN displaying unit prices on invoice, THE System SHALL show the total price including margin
6. WHEN generating an invoice, THE System SHALL include subtotal, tax, shipping cost, and total amount
7. WHEN generating an invoice, THE System SHALL not separately display the margin amount to the customer
8. IF a coupon discount is applied, THEN THE System SHALL include discount amount and coupon code on the invoice

### Requirement 8: Reseller Dashboard

**User Story:** As a reseller, I want to view my earnings and performance metrics, so that I can track my reselling business.

#### Acceptance Criteria

1. WHEN a reseller accesses their dashboard, THE System SHALL display total earnings
2. WHEN a reseller accesses their dashboard, THE System SHALL display available balance
3. WHEN a reseller accesses their dashboard, THE System SHALL display total number of orders
4. WHEN a reseller accesses their dashboard, THE System SHALL display pending earnings amount
5. WHEN a reseller accesses their dashboard, THE System SHALL display list of recent orders
6. WHEN a reseller accesses their dashboard, THE System SHALL display list of active resell links
7. WHEN a reseller views a resell link, THE System SHALL show views count, orders count, and total earnings for that link

### Requirement 9: Admin Resell Management

**User Story:** As an administrator, I want to monitor and manage resell operations, so that I can ensure platform integrity and support resellers.

#### Acceptance Criteria

1. WHEN an admin accesses the resell dashboard, THE System SHALL display all resell orders with filtering options
2. WHEN an admin filters resell orders, THE System SHALL support filtering by reseller, date range, and order status
3. WHEN an admin views a reseller's analytics, THE System SHALL display total earnings, orders count, and performance metrics
4. WHEN an admin generates a resell report, THE System SHALL include data for the specified date range
5. WHEN an admin manages a reseller account, THE System SHALL allow enabling or disabling reseller status
6. WHEN an admin views payout transactions, THE System SHALL display all payouts with status and transaction details
7. WHEN an admin views a resell order, THE System SHALL display base amount and margin amount separately

### Requirement 10: Reseller Profile Management

**User Story:** As a reseller, I want to manage my profile and payment details, so that I can receive payouts.

#### Acceptance Criteria

1. WHEN a user enables reseller functionality, THE System SHALL create a ResellerProfile for that user
2. WHEN a reseller updates their profile, THE System SHALL allow setting business name
3. WHEN a reseller updates payment details, THE System SHALL allow setting bank account information
4. WHEN a reseller updates payment details, THE System SHALL allow setting UPI ID
5. WHEN a reseller updates payment details, THE System SHALL allow setting PAN number
6. WHEN a reseller requests a payout above tax threshold, THE System SHALL require PAN number to be set
7. THE System SHALL ensure a user can have only one reseller profile

### Requirement 11: Resell Link Management

**User Story:** As a reseller, I want to manage my resell links, so that I can control which products I'm actively promoting.

#### Acceptance Criteria

1. WHEN a reseller views their resell links, THE System SHALL display all links created by that reseller
2. WHEN a reseller deactivates a resell link, THE System SHALL set the is_active flag to false
3. WHEN a reseller deactivates a resell link, THE System SHALL prevent new orders through that link
4. WHEN a reseller reactivates a resell link, THE System SHALL set the is_active flag to true
5. WHEN a reseller views a resell link, THE System SHALL display the shareable URL
6. WHERE a resell link has an expiration date, THE System SHALL automatically deactivate the link after expiration

### Requirement 12: Order Cancellation Handling

**User Story:** As the platform, I want to handle order cancellations correctly, so that reseller earnings are adjusted appropriately.

#### Acceptance Criteria

1. WHEN a resell order is cancelled, THE System SHALL update the associated ResellerEarning status to CANCELLED
2. WHEN a resell order is cancelled with PENDING earnings, THE System SHALL not add the margin to reseller's balance
3. WHEN a resell order is cancelled with CONFIRMED earnings, THE System SHALL deduct the margin from reseller's available balance
4. WHEN a resell order is cancelled, THE System SHALL decrement the orders count on the resell link
5. WHEN a resell order is cancelled, THE System SHALL deduct the margin from the resell link's total earnings
6. WHEN a resell order is cancelled, THE System SHALL send a notification to the reseller

### Requirement 13: Data Integrity and Validation

**User Story:** As the platform, I want to maintain data integrity for resell operations, so that financial calculations are always accurate.

#### Acceptance Criteria

1. THE System SHALL ensure reseller available balance never becomes negative
2. WHEN calculating order totals, THE System SHALL ensure total_amount equals base_amount plus total_margin plus tax plus shipping_cost minus coupon_discount
3. WHEN calculating order margins, THE System SHALL ensure total_margin equals the sum of all order item margins
4. WHEN creating order items, THE System SHALL ensure product_price equals base_price plus margin_amount
5. WHEN creating order items, THE System SHALL ensure subtotal equals product_price multiplied by quantity
6. IF is_resell is true, THEN THE System SHALL ensure reseller and resell_link are set on the order
7. WHEN confirming earnings, THE System SHALL ensure the earning amount matches the order's total margin

### Requirement 14: Notification System

**User Story:** As a reseller, I want to receive notifications about my earnings and payouts, so that I stay informed about my business.

#### Acceptance Criteria

1. WHEN earnings are confirmed, THE System SHALL send a notification to the reseller with the earning amount and order number
2. WHEN a payout is completed, THE System SHALL send a notification to the reseller with the payout amount
3. WHEN a payout fails, THE System SHALL send a notification to the reseller with failure details
4. WHEN an order is cancelled, THE System SHALL send a notification to the reseller about the cancellation
5. WHEN a resell link receives an order, THE System SHALL send a notification to the reseller

### Requirement 15: Security and Access Control

**User Story:** As the platform, I want to ensure secure access to resell features, so that only authorized users can perform resell operations.

#### Acceptance Criteria

1. WHEN a user attempts to create a resell link, THE System SHALL verify the user has reseller permissions enabled
2. WHEN a user attempts to access reseller dashboard, THE System SHALL verify the user has a reseller profile
3. WHEN a user attempts to request a payout, THE System SHALL verify the user is the owner of the reseller profile
4. WHEN an admin performs resell management operations, THE System SHALL verify the user has admin permissions
5. THE System SHALL prevent users from modifying other resellers' data

### Requirement 16: Analytics and Reporting

**User Story:** As an administrator, I want to generate analytics and reports for resell operations, so that I can understand platform performance.

#### Acceptance Criteria

1. WHEN an admin generates a resell report, THE System SHALL include total number of resellers
2. WHEN an admin generates a resell report, THE System SHALL include total resell orders
3. WHEN an admin generates a resell report, THE System SHALL include total margins earned by all resellers
4. WHEN an admin generates a resell report, THE System SHALL include total payouts processed
5. WHEN an admin generates a resell report, THE System SHALL include top performing resellers
6. WHEN an admin views reseller analytics, THE System SHALL display conversion rate for each reseller
7. WHEN an admin views reseller analytics, THE System SHALL calculate conversion rate as orders count divided by views count
