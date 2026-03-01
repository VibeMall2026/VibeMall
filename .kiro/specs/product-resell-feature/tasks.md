# Implementation Plan: Product Resell Feature

## Overview

This implementation plan breaks down the Product Resell Feature into discrete coding tasks. The feature enables users to become resellers by creating unique links with their own margin, sharing products with customers, and earning from sales. The implementation follows a phased approach: database setup, backend models and APIs, frontend interfaces, payment integration, and testing.

## Tasks

- [x] 1. Set up database models and migrations
  - [x] 1.1 Create ResellLink model with validation
    - Create Django model with fields: reseller, product, resell_code, margin_amount, margin_percentage, is_active, views_count, orders_count, total_earnings, created_at, expires_at
    - Add unique constraint on resell_code
    - Implement model validation for margin_amount (positive, max 50% of product price)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_
  
  - [x] 1.2 Create ResellerEarning model
    - Create Django model with fields: reseller, order, resell_link, margin_amount, status, confirmed_at, paid_at, payout_transaction, created_at
    - Add status choices: PENDING, CONFIRMED, PAID, CANCELLED
    - Add OneToOneField relationship with Order
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 1.3 Create PayoutTransaction model
    - Create Django model with fields: reseller, amount, payout_method, status, transaction_id, bank_account, upi_id, admin_notes, initiated_at, completed_at
    - Add status choices: INITIATED, PROCESSING, COMPLETED, FAILED
    - Add payout method choices: BANK_TRANSFER, UPI, WALLET
    - _Requirements: 6.1, 6.3, 6.4, 6.5_
  
  - [x] 1.4 Create ResellerProfile model
    - Create Django model with fields: user, is_reseller_enabled, business_name, total_earnings, available_balance, total_orders, bank_account_name, bank_account_number, bank_ifsc_code, upi_id, pan_number, created_at, updated_at
    - Add OneToOneField relationship with User
    - Add validation for available_balance (cannot be negative)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [x] 1.5 Enhance Order model with resell fields
    - Add fields: is_resell (BooleanField), reseller (ForeignKey to User), resell_link (ForeignKey to ResellLink), total_margin (DecimalField), base_amount (DecimalField)
    - Add validation: if is_resell=True, reseller and resell_link must be set
    - _Requirements: 3.3, 3.4, 3.5, 13.6_
  
  - [x] 1.6 Enhance OrderItem model with margin tracking
    - Add fields: base_price (DecimalField), margin_amount (DecimalField)
    - Add validation: product_price = base_price + margin_amount
    - _Requirements: 3.6, 13.4, 13.5_
  
  - [x] 1.7 Create database migration files
    - Generate migrations for all new models
    - Generate migration for Order and OrderItem enhancements
    - Add database indexes: ResellLink.resell_code, Order(is_resell, reseller_id), ResellerEarning(reseller_id, status), PayoutTransaction(reseller_id, status)
    - _Requirements: All above_


- [ ] 2. Implement resell link creation and management
  - [x] 2.1 Create ResellLinkGenerator service class
    - Implement create_resell_link() method with unique code generation
    - Implement validate_resell_link() method for checkout validation
    - Implement get_reseller_links() method for listing user's links
    - Add margin validation logic (0 < margin <= base_price * 0.5)
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [ ]* 2.2 Write property test for resell link creation
    - **Property 5: Resell Link Uniqueness**
    - **Property 10: Resell Link Default Status**
    - **Property 14: Margin Validation Bounds**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.6**
  
  - [x] 2.3 Create resell link creation view and API endpoint
    - Create POST endpoint /api/resell/create-link/
    - Validate user has reseller permissions
    - Accept product_id and margin_amount in request
    - Return resell_code and shareable URL
    - _Requirements: 1.1, 1.5, 15.1_
  
  - [x] 2.4 Create resell link management views
    - Create GET endpoint /api/resell/my-links/ for listing reseller's links
    - Create POST endpoint /api/resell/deactivate-link/ for deactivating links
    - Create POST endpoint /api/resell/reactivate-link/ for reactivating links
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [ ]* 2.5 Write unit tests for resell link management
    - Test link creation with valid and invalid margins
    - Test link deactivation and reactivation
    - Test link listing and filtering
    - _Requirements: 1.1, 1.3, 11.1, 11.2, 11.3_

- [ ] 3. Implement resell order processing
  - [x] 3.1 Create MarginCalculator service class
    - Implement calculate_total_price() method
    - Implement calculate_reseller_earnings() method
    - Implement validate_margin() method
    - _Requirements: 3.1, 3.5_
  
  - [ ]* 3.2 Write property test for margin calculations
    - **Property 1: Margin Calculation Consistency**
    - **Property 6: Order Item Price Composition**
    - **Property 9: Margin Percentage Calculation**
    - **Property 12: Order Item Subtotal Calculation**
    - **Validates: Requirements 3.1, 3.5, 13.3, 13.4, 13.5**
  
  - [x] 3.3 Create ResellOrderProcessor service class
    - Implement create_resell_order() method
    - Calculate base_amount and total_margin
    - Create Order with is_resell=True, reseller, and resell_link
    - Create OrderItems with base_price and margin_amount
    - Create ResellerEarning record with status=PENDING
    - Update resell_link statistics (orders_count, total_earnings)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_
  
  - [x] 3.4 Modify checkout view to handle resell links
    - Check session for resell_link_id
    - Validate resell link is active
    - Use ResellOrderProcessor for resell orders
    - Calculate total with margin included
    - _Requirements: 2.6, 3.1, 3.2_
  
  - [x] 3.5 Create resell link validation middleware
    - Capture resell code from URL query parameter
    - Validate resell link exists and is active
    - Store resell_link_id in session
    - Increment views_count on resell link
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6_
  
  - [ ]* 3.6 Write property test for order processing
    - **Property 2: Payment Distribution Integrity**
    - **Property 11: Resell Order Association**
    - **Property 16: Link Statistics Update on Order**
    - **Validates: Requirements 3.3, 3.4, 3.8, 3.9, 4.1, 13.2, 13.6**
  
  - [ ]* 3.7 Write unit tests for resell order processing
    - Test order creation with resell link
    - Test order amount calculations
    - Test order item creation with margins
    - Test reseller earning record creation
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6, 3.7_


- [ ] 4. Implement payment processing for resell orders
  - [x] 4.1 Enhance payment processing to handle resell orders
    - Modify payment view to charge total amount (base + margin + tax + shipping)
    - Set order payment_status to PAID on success
    - Clear customer cart after successful payment
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [ ]* 4.2 Write property test for payment processing
    - **Property 2: Payment Distribution Integrity**
    - **Validates: Requirements 4.1, 13.2**
  
  - [ ]* 4.3 Write unit tests for payment processing
    - Test payment amount calculation for resell orders
    - Test payment success flow
    - Test payment failure handling
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement reseller earnings confirmation
  - [x] 6.1 Create earnings confirmation service
    - Implement confirm_reseller_earnings() function
    - Validate order status is DELIVERED
    - Update ResellerEarning status from PENDING to CONFIRMED
    - Set confirmed_at timestamp
    - Update reseller's available_balance, total_earnings, and total_orders
    - Send notification to reseller
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  
  - [ ]* 6.2 Write property test for earnings confirmation
    - **Property 4: Earning Status Progression**
    - **Property 17: Earnings Confirmation Balance Update**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.5, 5.6, 5.7**
  
  - [x] 6.3 Create admin action for bulk earnings confirmation
    - Add admin action to confirm multiple earnings at once
    - Filter orders by DELIVERED status
    - Call confirm_reseller_earnings() for each order
    - _Requirements: 5.1, 5.2_
  
  - [ ] 6.4 Create automatic earnings confirmation task
    - Create Celery task to auto-confirm earnings for DELIVERED orders
    - Schedule task to run every 15 minutes
    - _Requirements: 5.1, 5.2_
  
  - [ ]* 6.5 Write unit tests for earnings confirmation
    - Test earnings confirmation for delivered orders
    - Test balance updates
    - Test notification sending
    - Test status transition validation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 7. Implement reseller payout processing
  - [x] 7.1 Create ResellerPaymentManager service class
    - Implement get_reseller_balance() method
    - Implement process_payout() method
    - Implement get_earnings_history() method
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 7.2 Implement payout processing logic
    - Validate payout amount does not exceed available balance
    - Validate payment details based on payout method
    - Create PayoutTransaction with status=INITIATED
    - Deduct amount from available_balance
    - Process payment through gateway
    - Update payout status to COMPLETED or FAILED
    - Update associated ResellerEarning records to PAID
    - Refund balance on failure
    - Send notifications
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12_
  
  - [ ]* 7.3 Write property test for payout processing
    - **Property 3: Reseller Balance Consistency**
    - **Property 8: Payout Amount Validation**
    - **Property 13: Payout Failure Balance Restoration**
    - **Validates: Requirements 6.1, 6.2, 6.6, 6.10, 13.1**
  
  - [x] 7.4 Create payout request API endpoint
    - Create POST endpoint /api/resell/request-payout/
    - Accept amount, payout_method, and payment details
    - Validate user is reseller and has sufficient balance
    - Call ResellerPaymentManager.process_payout()
    - Return payout transaction details
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 15.3_
  
  - [x] 7.5 Integrate with payment gateway for payouts
    - Implement Razorpay transfer API integration
    - Handle webhook for payout status updates
    - Implement retry logic for failed payouts
    - _Requirements: 6.7, 6.8, 6.9, 6.10_
  
  - [ ]* 7.6 Write unit tests for payout processing
    - Test payout validation
    - Test balance deduction and restoration
    - Test payment gateway integration
    - Test earning status updates
    - Test notification sending
    - _Requirements: 6.1, 6.2, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12_


- [ ] 8. Implement invoice generation with margin
  - [x] 8.1 Enhance invoice generation to handle resell orders
    - Modify invoice template to show product_price (includes margin)
    - Ensure margin is not separately displayed to customer
    - Include order_number, invoice_number, customer details
    - Include all order items with quantities and prices
    - Include subtotal, tax, shipping, and total
    - Include coupon discount if applicable
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_
  
  - [ ]* 8.2 Write property test for invoice generation
    - **Property 7: Invoice Amount Accuracy**
    - **Property 18: Invoice Margin Privacy**
    - **Validates: Requirements 7.2, 7.4, 7.6, 7.7**
  
  - [ ]* 8.3 Write unit tests for invoice generation
    - Test invoice generation for resell orders
    - Test margin is not displayed separately
    - Test invoice amount calculations
    - Test PDF generation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

- [x] 9. Implement reseller dashboard frontend
  - [x] 9.1 Create reseller dashboard page
    - Display total_earnings, available_balance, total_orders, pending_earnings
    - Display list of recent orders with order details
    - Display list of active resell links with statistics
    - Add navigation to create new resell link
    - Add navigation to request payout
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  
  - [x] 9.2 Create resell link creation form
    - Product selection dropdown
    - Margin amount input with validation
    - Display calculated margin percentage
    - Display shareable URL after creation
    - Add copy-to-clipboard button for URL
    - _Requirements: 1.1, 1.3, 1.4, 1.5_
  
  - [x] 9.3 Create resell link management interface
    - Display all reseller's links in a table
    - Show views_count, orders_count, total_earnings for each link
    - Add activate/deactivate toggle buttons
    - Add shareable URL with copy button
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 9.4 Create payout request form
    - Display current available balance
    - Payout amount input with validation
    - Payout method selection (Bank Transfer, UPI, Wallet)
    - Payment details fields based on selected method
    - Submit button to request payout
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 9.5 Create earnings history page
    - Display list of all earnings with order details
    - Show status (PENDING, CONFIRMED, PAID, CANCELLED)
    - Filter by status and date range
    - Display associated payout transaction if paid
    - _Requirements: 8.4, 8.5_
  
  - [x] 9.6 Add reseller profile management page
    - Form to update business_name
    - Form to update bank account details
    - Form to update UPI ID
    - Form to update PAN number
    - _Requirements: 10.2, 10.3, 10.4, 10.5_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 11. Implement admin panel for resell management
  - [x] 11.1 Create AdminResellDashboard service class
    - Implement get_resell_orders() with filtering
    - Implement get_reseller_analytics() for performance metrics
    - Implement generate_resell_report() for date range reports
    - Implement manage_reseller_status() to enable/disable resellers
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 11.2 Create admin resell orders view
    - Display all resell orders in a table
    - Add filters: reseller, date range, order status
    - Show base_amount and total_margin separately
    - Add link to reseller profile
    - Add link to order details
    - _Requirements: 9.1, 9.2, 9.7_
  
  - [x] 11.3 Create admin reseller analytics view
    - Display reseller performance metrics
    - Show total_earnings, total_orders, conversion_rate
    - Display chart of earnings over time
    - Show top performing resellers
    - _Requirements: 9.3, 16.6, 16.7_
  
  - [x] 11.4 Create admin resell reports view
    - Date range selector
    - Generate report with total resellers, orders, margins, payouts
    - Display top performing resellers
    - Export to CSV/PDF
    - _Requirements: 9.4, 16.1, 16.2, 16.3, 16.4, 16.5_
  
  - [x] 11.5 Create admin reseller management view
    - List all resellers with status
    - Enable/disable reseller functionality
    - View reseller profile details
    - View reseller earnings and payouts
    - Manual balance adjustment (with audit log)
    - _Requirements: 9.5, 15.4_
  
  - [x] 11.6 Create admin payout management view
    - Display all payout transactions
    - Filter by status, reseller, date range
    - View payout details and payment information
    - Manual payout approval/rejection
    - _Requirements: 9.6_
  
  - [ ]* 11.7 Write unit tests for admin functionality
    - Test resell order filtering
    - Test reseller analytics calculations
    - Test report generation
    - Test reseller status management
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 12. Implement order cancellation handling
  - [x] 12.1 Create order cancellation handler for resell orders
    - Update ResellerEarning status to CANCELLED
    - If status was CONFIRMED, deduct margin from available_balance
    - Decrement orders_count on resell_link
    - Deduct margin from resell_link total_earnings
    - Send notification to reseller
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_
  
  - [ ]* 12.2 Write property test for order cancellation
    - **Property 20: Order Cancellation Earning Adjustment**
    - **Validates: Requirements 12.1, 12.3**
  
  - [ ]* 12.3 Write unit tests for order cancellation
    - Test cancellation with PENDING earnings
    - Test cancellation with CONFIRMED earnings
    - Test balance adjustments
    - Test notification sending
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [ ] 13. Implement notification system
  - [x] 13.1 Create notification templates for resell events
    - Earnings confirmed notification
    - Payout completed notification
    - Payout failed notification
    - Order cancelled notification
    - New order notification
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 13.2 Integrate notifications with resell workflows
    - Send notification on earnings confirmation
    - Send notification on payout completion/failure
    - Send notification on order cancellation
    - Send notification on new resell order
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [ ]* 13.3 Write unit tests for notifications
    - Test notification sending for each event
    - Test notification content
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_


- [ ] 14. Implement security and access control
  - [ ] 14.1 Add reseller permission checks
    - Create decorator to verify user has is_reseller_enabled
    - Apply to all resell link creation endpoints
    - Apply to reseller dashboard views
    - _Requirements: 15.1, 15.2_
  
  - [ ] 14.2 Implement access control for reseller data
    - Ensure resellers can only view their own earnings
    - Ensure resellers can only view their own payouts
    - Ensure resellers cannot modify confirmed earnings
    - Verify user ownership before allowing payout requests
    - _Requirements: 15.2, 15.3, 15.4_
  
  - [ ] 14.3 Add admin permission checks
    - Verify admin permissions for resell management operations
    - Verify admin permissions for manual balance adjustments
    - _Requirements: 15.4, 15.5_
  
  - [ ] 14.4 Implement rate limiting
    - Add rate limit to resell link creation (10 per hour)
    - Add rate limit to payout requests (5 per day)
    - _Requirements: 15.1_
  
  - [ ]* 14.5 Write unit tests for security
    - Test permission checks
    - Test access control
    - Test rate limiting
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [ ] 15. Implement data validation and integrity checks
  - [ ] 15.1 Add model-level validation
    - Validate available_balance cannot be negative
    - Validate total_amount calculation for orders
    - Validate total_margin calculation for orders
    - Validate product_price calculation for order items
    - Validate subtotal calculation for order items
    - Validate is_resell requires reseller and resell_link
    - Validate earning amount matches order margin
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_
  
  - [ ]* 15.2 Write property test for data integrity
    - **Property 3: Reseller Balance Consistency**
    - **Property 15: Reseller Profile Uniqueness**
    - **Validates: Requirements 10.7, 13.1**
  
  - [ ]* 15.3 Write unit tests for validation
    - Test all model validations
    - Test constraint violations
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [ ] 16. Implement caching and performance optimizations
  - [ ] 16.1 Add database indexes
    - Create index on ResellLink.resell_code
    - Create composite index on Order(is_resell, reseller_id)
    - Create composite index on ResellerEarning(reseller_id, status)
    - Create composite index on PayoutTransaction(reseller_id, status)
    - _Requirements: Performance optimization_
  
  - [ ] 16.2 Implement caching for reseller dashboard
    - Cache dashboard statistics with 5-minute TTL
    - Cache resell link lookups with 1-hour TTL
    - Invalidate cache on relevant updates
    - _Requirements: Performance optimization_
  
  - [ ] 16.3 Optimize database queries
    - Use select_related() for reseller and resell_link in order queries
    - Use prefetch_related() for order items
    - Use aggregation for balance calculations
    - Implement pagination for order lists (50 per page)
    - _Requirements: Performance optimization_

- [ ] 17. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 18. Integration and wiring
  - [x] 18.1 Wire resell link creation to product pages
    - Add "Become a Reseller" button on product detail pages
    - Show button only to users with is_reseller_enabled
    - Open modal/form for margin input
    - Display generated resell link with copy button
    - _Requirements: 1.1, 1.5_
  
  - [x] 18.2 Wire resell link handling to checkout flow
    - Detect resell code in URL query parameter
    - Store resell_link_id in session
    - Display reseller information during checkout (optional)
    - Use ResellOrderProcessor for order creation
    - _Requirements: 2.1, 2.6, 3.2_
  
  - [x] 18.3 Wire earnings confirmation to order delivery
    - Add signal handler for order status change to DELIVERED
    - Automatically call confirm_reseller_earnings()
    - _Requirements: 5.1, 5.2_
  
  - [x] 18.4 Wire payout processing to admin panel
    - Add admin action for manual payout approval
    - Add admin view for payout transaction details
    - _Requirements: 9.6_
  
  - [x] 18.5 Wire notifications to all resell events
    - Connect notification sending to earnings confirmation
    - Connect notification sending to payout completion
    - Connect notification sending to order cancellation
    - Connect notification sending to new resell order
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 18.6 Add reseller menu items to navigation
    - Add "Reseller Dashboard" link to user menu
    - Add "My Resell Links" link to user menu
    - Add "Earnings & Payouts" link to user menu
    - Show menu items only to users with is_reseller_enabled
    - _Requirements: 8.1, 8.6, 11.1_
  
  - [x] 18.7 Add admin menu items for resell management
    - Add "Resell Orders" to admin menu
    - Add "Resellers" to admin menu
    - Add "Payouts" to admin menu
    - Add "Resell Reports" to admin menu
    - _Requirements: 9.1, 9.5, 9.6, 9.4_

- [ ] 19. Create documentation
  - [ ] 19.1 Create API documentation
    - Document all resell-related API endpoints
    - Include request/response examples
    - Document authentication requirements
    - Document rate limits
    - _Requirements: All API endpoints_
  
  - [ ] 19.2 Create user guide for resellers
    - How to become a reseller
    - How to create resell links
    - How to share links with customers
    - How to track earnings
    - How to request payouts
    - _Requirements: User documentation_
  
  - [ ] 19.3 Create admin guide
    - How to manage resellers
    - How to confirm earnings
    - How to process payouts
    - How to generate reports
    - _Requirements: Admin documentation_

- [ ]* 20. Integration testing
  - [ ]* 20.1 Write end-to-end test for complete resell flow
    - Test: Reseller creates link → Customer uses link → Order placed → Payment processed → Earning confirmed → Payout requested → Payout completed
    - Verify data consistency across all models
    - Verify notifications sent at each step
    - _Requirements: All requirements_
  
  - [ ]* 20.2 Write integration tests for admin panel
    - Test resell order filtering and display
    - Test reseller analytics calculations
    - Test bulk operations
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ]* 20.3 Write integration tests for payment gateway
    - Test payment processing for resell orders
    - Test payout transfers
    - Test webhook handling
    - _Requirements: 4.1, 6.7, 6.8, 6.9_

- [ ] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- Checkpoints ensure incremental validation
- The implementation uses Django for backend and Bootstrap for frontend
- Payment gateway integration uses Razorpay
- Celery is used for asynchronous task processing
