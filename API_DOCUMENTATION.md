# VibeMall API Documentation

## Overview

VibeMall provides a comprehensive set of REST API endpoints for product management, shopping cart operations, user accounts, payments, and administrative functions. All API endpoints follow RESTful conventions and return JSON responses.

**API Base URL**: `https://vibemall.com/`  
**Authentication**: Session-based for logged-in users, token-based for API clients  
**Response Format**: JSON

---

## Table of Contents

1. [Product & Search APIs](#product--search-apis)
2. [Cart Management APIs](#cart-management-apis)
3. [Wishlist APIs](#wishlist-apis)
4. [Review & Question APIs](#review--question-apis)
5. [User Account APIs](#user-account-apis)
6. [Chat APIs](#chat-apis)
7. [Payment APIs](#payment-apis)
8. [Admin APIs](#admin-apis)
9. [Reel APIs](#reel-apis)
10. [Status Codes & Error Handling](#status-codes--error-handling)

---

## Product & Search APIs

### Search Products

**Endpoint**: `GET /api/products/search/`

**Description**: Search for products by query string

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (product name, category, brand) |
| `page` | integer | No | Page number for pagination (default: 1) |

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 1,
      "name": "Product Name",
      "price": 1299.00,
      "image": "/media/products/image.jpg",
      "rating": 4.5,
      "reviews_count": 125,
      "in_stock": true,
      "category": "Fashion",
      "url": "/product/product-slug/"
    }
  ],
  "total_count": 45,
  "page": 1,
  "per_page": 20,
  "total_pages": 3
}
```

**Error Response** (400 Bad Request):
```json
{
  "results": []
}
```

**Example Usage**:
```bash
curl "https://vibemall.com/api/products/search/?q=shirt&page=1"
```

**Status Codes**:
- `200` - Search completed successfully
- `400` - Invalid parameters

---

### Get Product Details

**Endpoint**: `GET /product/<slug:slug>/`

**Description**: Get detailed information about a product

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `slug` | string | Product slug (URL-friendly name) |

**Response** (200 OK):
```json
{
  "id": 1,
  "name": "Premium Cotton T-Shirt",
  "slug": "premium-cotton-t-shirt",
  "price": 599.00,
  "discount_percentage": 20,
  "original_price": 749.00,
  "description": "High-quality cotton t-shirt",
  "category": "Clothing",
  "subcategory": "T-Shirts",
  "brand": "Fashion Hub",
  "stock": 150,
  "rating": 4.5,
  "reviews_count": 125,
  "images": [
    "/media/products/image1.jpg",
    "/media/products/image2.jpg"
  ],
  "specifications": {
    "material": "100% Cotton",
    "care": "Machine wash 30°C"
  },
  "return_policy": "30 days return policy",
  "reviews": [
    {
      "id": 1,
      "author": "John Doe",
      "rating": 5,
      "comment": "Great quality!",
      "helpful": 45,
      "not_helpful": 2,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Status Codes**:
- `200` - Product found
- `404` - Product not found

---

## Cart Management APIs

### Add To Cart

**Endpoint**: `POST /add-to-cart/`

**Description**: Add a product to shopping cart

**Request Header**:
```
Content-Type: application/x-www-form-urlencoded
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | integer | Yes | ID of product to add |
| `quantity` | integer | No | Quantity to add (default: 1) |
| `variant` | string | No | Product variant (size, color, etc.) |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Product added to cart",
  "cart_count": 3,
  "cart_total": 2597.00,
  "item": {
    "cart_id": 42,
    "product_id": 1,
    "product_name": "Premium Cotton T-Shirt",
    "quantity": 2,
    "price": 599.00,
    "total": 1198.00
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Product out of stock",
  "available_quantity": 0
}
```

**Status Codes**:
- `200` - Product added successfully
- `400` - Invalid request or out of stock
- `401` - User not authenticated

**Example Usage**:
```bash
curl -X POST "https://vibemall.com/add-to-cart/" \
  -d "product_id=1&quantity=2"
```

---

### Get Cart Summary

**Endpoint**: `GET /api/cart/summary/`

**Description**: Get current shopping cart contents and totals

**Response** (200 OK):
```json
{
  "success": true,
  "cart": [
    {
      "cart_id": 42,
      "product_id": 1,
      "product_name": "Premium Cotton T-Shirt",
      "price": 599.00,
      "quantity": 2,
      "total": 1198.00,
      "image": "/media/products/image.jpg",
      "in_stock": true
    },
    {
      "cart_id": 43,
      "product_id": 2,
      "product_name": "Denim Jeans",
      "price": 1299.00,
      "quantity": 1,
      "total": 1299.00,
      "image": "/media/products/jeans.jpg",
      "in_stock": false
    }
  ],
  "summary": {
    "subtotal": 2497.00,
    "shipping": 100.00,
    "tax": 449.46,
    "discount": 0.00,
    "total": 3046.46,
    "item_count": 3
  }
}
```

**Status Codes**:
- `200` - Cart retrieved successfully
- `401` - User not authenticated

---

### Update Cart Quantity

**Endpoint**: `POST /update-cart-quantity/<int:cart_id>/`

**Description**: Update quantity of an item in cart

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `cart_id` | integer | Cart item ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `quantity` | integer | Yes | New quantity (minimum: 1) |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Cart updated",
  "cart_item": {
    "cart_id": 42,
    "product_id": 1,
    "quantity": 5,
    "total": 2995.00
  },
  "cart_total": 4294.00,
  "cart_count": 6
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Only 50 items available in stock"
}
```

**Status Codes**:
- `200` - Quantity updated
- `400` - Invalid quantity or out of stock
- `404` - Cart item not found

---

### Remove From Cart

**Endpoint**: `DELETE /remove-from-cart/<int:cart_id>/`

**Description**: Remove an item from shopping cart

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `cart_id` | integer | Cart item ID to remove |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Item removed from cart",
  "cart_count": 2,
  "cart_total": 1897.00
}
```

**Status Codes**:
- `200` - Item removed successfully
- `404` - Cart item not found

**Example Usage**:
```bash
curl -X DELETE "https://vibemall.com/remove-from-cart/42/"
```

---

### Toggle Cart Item

**Endpoint**: `POST /cart/toggle/<int:product_id>/`

**Description**: Quick add/remove product from cart (AJAX endpoint)

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `product_id` | integer | Product ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | No | 'add' or 'remove' (auto-detect if omitted) |

**Response** (200 OK - Add Product):
```json
{
  "success": true,
  "action": "added",
  "message": "Product added to cart",
  "cart_count": 3
}
```

**Response** (200 OK - Remove Product):
```json
{
  "success": true,
  "action": "removed",
  "message": "Product removed from cart",
  "cart_count": 2
}
```

---

## Wishlist APIs

### Add To Wishlist

**Endpoint**: `POST /add-to-wishlist/`

**Description**: Add product to wishlist

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | integer | Yes | Product ID to add |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Added to wishlist",
  "wishlist_id": 156,
  "product_id": 1,
  "action": "added"
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Product already in wishlist"
}
```

**Status Codes**:
- `200` - Added to wishlist
- `400` - Invalid request or already in wishlist
- `401` - User not authenticated

---

### Check Wishlist Status

**Endpoint**: `GET /check-wishlist/<int:product_id>/`

**Description**: Check if product is in user's wishlist

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `product_id` | integer | Product ID |

**Response** (200 OK - In Wishlist):
```json
{
  "in_wishlist": true,
  "wishlist_id": 156,
  "product_id": 1
}
```

**Response** (200 OK - Not In Wishlist):
```json
{
  "in_wishlist": false,
  "product_id": 1
}
```

---

### Remove From Wishlist

**Endpoint**: `DELETE /remove-from-wishlist/<int:wishlist_id>/`

**Description**: Remove product from wishlist

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `wishlist_id` | integer | Wishlist item ID |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Removed from wishlist",
  "wishlist_id": 156
}
```

---

### Move Wishlist Item To Cart

**Endpoint**: `POST /move-wishlist-to-cart/<int:wishlist_id>/`

**Description**: Move product from wishlist to cart

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `wishlist_id` | integer | Wishlist item ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `quantity` | integer | No | Quantity to add (default: 1) |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Item moved to cart",
  "cart_count": 4,
  "wishlist_id": 156
}
```

---

## Review & Question APIs

### Submit Product Review

**Endpoint**: `POST /product/<int:product_id>/submit-review/`

**Description**: Submit a review for a product

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `product_id` | integer | Product ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rating` | integer | Yes | Rating from 1 to 5 |
| `comment` | string | Yes | Review comment (max 500 chars) |
| `title` | string | No | Review title |
| `purchase_verified` | boolean | No | Is this verified purchase |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Review submitted. Awaiting approval.",
  "review": {
    "id": 523,
    "rating": 4,
    "comment": "Great product, good quality",
    "created_at": "2024-01-20T15:30:00Z",
    "status": "pending_approval"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Rating must be between 1 and 5"
}
```

**Status Codes**:
- `200` - Review submitted
- `400` - Invalid data
- `401` - User not authenticated

---

### Vote on Review

**Endpoint**: `POST /review/<int:review_id>/vote/`

**Description**: Mark review as helpful or not helpful

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `review_id` | integer | Review ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vote_type` | string | Yes | 'helpful' or 'not_helpful' |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Vote recorded",
  "review_id": 523,
  "helpful_count": 48,
  "not_helpful_count": 2,
  "user_vote": "helpful"
}
```

**Status Codes**:
- `200` - Vote recorded
- `400` - Invalid vote type
- `401` - User not authenticated

---

### Submit Product Question

**Endpoint**: `POST /product/<int:product_id>/submit-question/`

**Description**: Ask a question about a product

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `product_id` | integer | Product ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question` | string | Yes | Question text (max 300 chars) |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Question submitted",
  "question": {
    "id": 87,
    "question": "What is the material composition?",
    "product": 1,
    "created_at": "2024-01-20T15:35:00Z",
    "status": "pending"
  }
}
```

**Status Codes**:
- `200` - Question submitted
- `400` - Invalid data
- `401` - User not authenticated

---

## User Account APIs

### Get User Profile Stats

**Endpoint**: `GET /api/profile/stats/`

**Description**: Get user profile statistics and activity

**Response** (200 OK):
```json
{
  "user": {
    "id": 5,
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+91-9876543210",
    "profile_image": "/media/profile_images/john.jpg"
  },
  "stats": {
    "total_orders": 8,
    "total_spent": 12599.00,
    "cancelled_orders": 1,
    "average_order_value": 1574.88,
    "wishlisted_products": 5,
    "active_returns": 1,
    "loyalty_points": 1260
  },
  "recent_orders": [
    {
      "order_number": "ORD-202401-001",
      "date": "2024-01-20",
      "total": 2599.00,
      "status": "delivered",
      "items_count": 3
    }
  ],
  "member_since": "2023-06-15"
}
```

**Status Codes**:
- `200` - Stats retrieved
- `401` - User not authenticated

---

### Request Stock Notification

**Endpoint**: `POST /product/<int:product_id>/notify/`

**Description**: Request notification when out-of-stock product becomes available

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `product_id` | integer | Product ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | Yes | Email for notification |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "You'll be notified when item is back in stock",
  "product_name": "Premium Cotton T-Shirt"
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Product is currently in stock"
}
```

---

## Chat APIs

### Get or Create Chat Thread

**Endpoint**: `GET/POST /chat/thread/`

**Description**: Create new chat thread or retrieve existing conversation

**Request** (GET):
```json
{}
```

**Response** (200 OK):
```json
{
  "thread_id": 42,
  "user_id": 5,
  "created_at": "2024-01-15T10:00:00Z",
  "messages": [
    {
      "id": 201,
      "sender": "customer",
      "message": "Hi, I have a question about order",
      "timestamp": "2024-01-15T10:05:00Z"
    }
  ]
}
```

**Status Codes**:
- `200` - Thread retrieved/created
- `401` - User not authenticated

---

### Send Chat Message

**Endpoint**: `POST /chat/message/`

**Description**: Send a message in chat thread

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `thread_id` | integer | Yes | Chat thread ID |
| `message` | string | No | Message text |
| `attachment` | file | No | File attachment |

**Response** (200 OK):
```json
{
  "success": true,
  "message_id": 202,
  "thread_id": 42,
  "sender": "customer",
  "message": "Is there a discount available?",
  "timestamp": "2024-01-15T10:15:00Z",
  "attachment": null
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Message or attachment is required."
}
```

**Status Codes**:
- `200` - Message sent
- `400` - Invalid request
- `401` - User not authenticated

---

## Payment APIs

### Razorpay Webhook

**Endpoint**: `POST /razorpay-webhook/`

**Description**: Webhook endpoint for Razorpay payment notifications (Server-to-Server)

**Headers**:
```
X-Razorpay-Signature: <signature>
Content-Type: application/json
```

**Payload**:
```json
{
  "event": "payment.authorized",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_29QQoUBi66xm2f",
        "order_id": "order_DBJOWzybf0sJbb",
        "amount": 50000,
        "currency": "INR",
        "status": "authorized"
      }
    }
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Webhook processed"
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "message": "Invalid signature"
}
```

**Status Codes**:
- `200` - Webhook processed
- `400` - Invalid signature or data
- `403` - Unauthorized

---

### Payment Success Callback

**Endpoint**: `POST /razorpay-payment-success/`

**Description**: Handle successful payment from Razorpay

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `razorpay_order_id` | string | Yes | Razorpay order ID |
| `razorpay_payment_id` | string | Yes | Razorpay payment ID |
| `razorpay_signature` | string | Yes | Payment signature |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Payment successful",
  "order_id": 123,
  "order_number": "ORD-202401-001",
  "amount": 2599.00,
  "status": "completed"
}
```

**Status Codes**:
- `200` - Payment processed
- `400` - Invalid payment data
- `401` - User not authenticated

---

### Process Refund

**Endpoint**: `POST /admin-panel/orders/<int:order_id>/refund/`

**Description**: Process refund for an order (Admin only)

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `order_id` | integer | Order ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `refund_amount` | float | Yes | Amount to refund |
| `reason` | string | Yes | Refund reason |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Refund processed",
  "refund": {
    "id": "rfnd_1234xyz",
    "order_id": 123,
    "amount": 2599.00,
    "status": "pending",
    "created_at": "2024-01-20T16:00:00Z"
  }
}
```

**Status Codes**:
- `200` - Refund processed
- `400` - Invalid amount or order
- `401` - User not authenticated
- `403` - Admin access required

---

### Validate UPI ID

**Endpoint**: `GET /api/upi/validate/`

**Description**: Validate UPI ID format

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `upi_id` | string | Yes | UPI ID to validate |

**Response** (200 OK - Valid):
```json
{
  "valid": true,
  "upi_id": "john@paytm",
  "message": "Valid UPI ID"
}
```

**Response** (200 OK - Invalid):
```json
{
  "valid": false,
  "upi_id": "invalid-upi",
  "message": "Invalid UPI ID format"
}
```

---

### Lookup IFSC Code

**Endpoint**: `GET /api/ifsc/lookup/`

**Description**: Look up bank details by IFSC code

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ifsc` | string | Yes | IFSC code |

**Response** (200 OK):
```json
{
  "ifsc": "SBIN0001234",
  "bank_name": "State Bank of India",
  "branch_name": "Mumbai Main",
  "branch_code": "1234"
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "IFSC code not found"
}
```

---

## Admin APIs

### Search Orders

**Endpoint**: `GET /admin-panel/api/orders/search/`

**Description**: Search orders in admin panel

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | No | Search query (order number, customer name) |
| `status` | string | No | Filter by order status |
| `date_from` | date | No | Filter from date (YYYY-MM-DD) |
| `date_to` | date | No | Filter to date (YYYY-MM-DD) |
| `page` | integer | No | Page number |

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 123,
      "order_number": "ORD-202401-001",
      "customer": "John Doe",
      "total": 2599.00,
      "status": "completed",
      "created_at": "2024-01-15",
      "items_count": 3
    }
  ],
  "total": 45,
  "page": 1,
  "per_page": 20
}
```

**Requires**: Admin authentication

**Status Codes**:
- `200` - Search performed
- `401` - Admin authentication required
- `403` - Admin access required

---

### Update Inventory

**Endpoint**: `POST /admin-panel/inventory/update-stock/`

**Description**: Update product stock levels (Admin only)

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | integer | Yes | Product ID |
| `quantity` | integer | Yes | New stock quantity |
| `action` | string | No | 'set', 'add', or 'subtract' |

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Stock updated",
  "product": {
    "id": 1,
    "name": "Premium Cotton T-Shirt",
    "stock": 250,
    "previous_stock": 150
  }
}
```

**Status Codes**:
- `200` - Stock updated
- `400` - Invalid data
- `401` - Admin authentication required

---

## Reel APIs

### Track Reel View

**Endpoint**: `POST /reels/<int:reel_id>/track-view/`

**Description**: Record a view for a reel/video

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `reel_id` | integer | Reel ID |

**Response** (200 OK):
```json
{
  "success": true,
  "reel_id": 42,
  "view_count": 1523
}
```

**Status Codes**:
- `200` - View tracked
- `404` - Reel not found

---

### Like/Unlike Reel

**Endpoint**: `POST /reels/<int:reel_id>/like/`

**Description**: Like or unlike a reel

**URL Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `reel_id` | integer | Reel ID |

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | No | 'like' or 'unlike' (auto-detect if omitted) |

**Response** (200 OK - Like):
```json
{
  "success": true,
  "action": "liked",
  "reel_id": 42,
  "likes_count": 234
}
```

**Response** (200 OK - Unlike):
```json
{
  "success": true,
  "action": "unliked",
  "reel_id": 42,
  "likes_count": 233
}
```

**Status Codes**:
- `200` - Action performed
- `404` - Reel not found
- `401` - User not authenticated

---

## Status Codes & Error Handling

### HTTP Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| `200` | OK | Request successful |
| `201` | Created | Resource created |
| `400` | Bad Request | Invalid parameters or data |
| `401` | Unauthorized | Authentication required |
| `403` | Forbidden | Access denied (admin only) |
| `404` | Not Found | Resource not found |
| `409` | Conflict | Resource already exists |
| `422` | Unprocessable Entity | Validation error |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server error |

### Error Response Format

**Standard Error Response**:
```json
{
  "success": false,
  "error": "Error code",
  "message": "Human-readable error message",
  "details": {
    "field": "error description"
  }
}
```

**Example**:
```json
{
  "success": false,
  "error": "INVALID_QUANTITY",
  "message": "Quantity cannot be more than available stock",
  "details": {
    "quantity": "Maximum 50 items available",
    "requested": 100,
    "available": 50
  }
}
```

---

## Authentication

### Session-Based (Web)

For regular web users, authentication is handled via Django sessions:

```bash
# Login
curl -X POST "https://vibemall.com/accounts/login/" \
  -d "username=john&password=secret"

# Make authenticated request
curl "https://vibemall.com/api/profile/stats/" \
  -H "Cookie: sessionid=abc123"
```

### Token-Based (API Clients)

Future implementation for API keys can be added for programmatic access.

---

## Rate Limiting

### Current Limits (To Be Implemented - Task #16)

Planned rate limits per IP:
- Search: 100 requests/hour
- Cart operations: 300 requests/hour
- Payment: 50 requests/hour
- Admin endpoints: 1000 requests/hour

---

## Best Practices

### Request Headers

Always include:
```
Content-Type: application/json
User-Agent: MyApp/1.0
```

### Response Handling

```javascript
fetch('/api/products/search/?q=shirt')
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Not logged in | Login first |
| `403 Forbidden` | Admin access required | Use admin account |
| `404 Not Found` | Resource doesn't exist | Verify ID/slug |
| `422 Validation Error` | Invalid input data | Check required fields |
| `429 Too Many Requests` | Rate limit exceeded | Wait before retrying |

---

## Testing Endpoints

### Using cURL

```bash
# Get search results
curl "https://vibemall.com/api/products/search/?q=shirt"

# Add to cart
curl -X POST "https://vibemall.com/add-to-cart/" \
  -d "product_id=1&quantity=2"

# Get cart summary
curl "https://vibemall.com/api/cart/summary/"
```

### Using JavaScript Fetch

```javascript
// Search products
fetch('/api/products/search/?q=shirt')
  .then(res => res.json())
  .then(data => console.log(data));

// Add to cart
fetch('/add-to-cart/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded'
  },
  body: 'product_id=1&quantity=2'
})
.then(res => res.json())
.then(data => console.log(data));
```

### Using Postman

1. Import endpoints from URLs provided
2. Set authentication method: "Cookies"
3. Login first to get session cookie
4. Make authenticated requests

---

## Versioning

Current API Version: **v1.0**

API endpoints may be versioned in future as `/api/v1/` and `/api/v2/`

---

## Support & Documentation

For additional help:
- **Email**: api-support@vibemall.com
- **Docs**: https://docs.vibemall.com
- **Status**: https://status.vibemall.com

---

## Changelog

### Version 1.0 (Current)
- ✅ Product Search API
- ✅ Cart Management APIs
- ✅ Wishlist APIs
- ✅ Review & Question APIs
- ✅ Payment APIs (Razorpay)
- ✅ Chat APIs
- ✅ Admin APIs
- ✅ Reel APIs

### Planned (v1.1)
- ⏳ API Rate Limiting
- ⏳ Advanced filtering
- ⏳ Bulk operations
- ⏳ Webhook subscriptions

---

**Last Updated**: January 2024  
**Next Review**: April 2024
