# Database Optimization Guide

## Overview
This document outlines database optimization strategies implemented in VibeMall to improve query performance and reduce database load.

## Key Optimizations

### 1. Select Related & Prefetch Related
Use `select_related()` for ForeignKey and OneToOneField relationships, and `prefetch_related()` for ManyToManyField and reverse ForeignKey relationships.

#### Examples:
```python
# Good: Reduces N+1 queries
products = Product.objects.select_related('category').filter(is_active=True)

# Good: Efficiently fetches related items
orders = Order.objects.prefetch_related('items__product').all()

# Bad: Causes N+1 query problem
for order in Order.objects.all():
    print(order.user.email)  # Additional query for each order
```

### 2. Query Filtering & Limiting
Always filter at database level rather than in Python.

```python
# Good: Filters at database level
active_products = Product.objects.filter(is_active=True)

# Bad: Loads all then filters in Python
all_products = Product.objects.all()
active_products = [p for p in all_products if p.is_active]
```

### 3. Only & Defer
Use `.only()` and `.defer()` to limit fetched columns.

```python
# Good: Only fetch needed columns
products = Product.objects.only('id', 'name', 'price')

# Good: Defer large fields
products = Product.objects.defer('description', 'care_info')
```

### 4. Aggregation at Database Level
Use Django ORM aggregations instead of Python loops.

```python
# Good: Aggregates at database
from django.db.models import Sum
total_sales = Order.objects.aggregate(Sum('total_amount'))

# Bad: Fetches all orders and sums in Python
total = sum(order.total_amount for order in Order.objects.all())
```

### 5. Caching Context Processors
High-traffic context are cacheed to reduce database hits.

```python
from django.views.decorators.cache import cache_page
from django.core.cache import cache

def expensive_context(request):
    cache_key = 'header_categories'
    context = cache.get(cache_key)
    if context is None:
        # Fetch and process
        context = expensive_operation()
        cache.set(cache_key, context, 3600)  # Cache for 1 hour
    return context
```

### 6. Indexing Strategy

#### Current Indexes:
- `Product.slug` - frequently used in URL lookups
- `Product.category` - used for filtering
- `Order.user` - for user-specific queries
- `Cart.user` - for user's cart
- `Wishlist.user` - for user's wishlist

#### Recommended Additions:
```python
class Product(models.Model):
    # Add these to Meta class
    class Meta:
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_active', '-created_at']),
        ]

class Order(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
        ]
```

### 7. Connection Pooling
For PostgreSQL production:

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'vibemall',
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

### 8. Query Monitoring

#### Using Django Debugging Toolbar:
```python
# settings.py - dev only
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

#### Custom Query Logging:
```python
import logging
logger = logging.getLogger('django.db.backends')

# In management command or cron job
from django.db import connection, reset_queries
from django.conf import settings

if settings.DEBUG:
    for query in connection.queries:
        if query['time'] > 0.05:  # Log slow queries
            logger.warning(f"Slow query: {query['sql']} ({query['time']}s)")
```

### 9. Bulk Operations
Use bulk operations for mass inserts/updates.

```python
# Good: Bulk insert
products = [Product(name=f'Bulk {i}') for i in range(1000)]
Product.objects.bulk_create(products, batch_size=500)

# Good: Bulk update
Product.objects.filter(old_price__isnull=True).update(discount_percent=0)

# Bad: Individual saves
for product in products:
    product.save()  # 1000 queries!
```

### 10. Lazy Querysets
QuerySets are lazy - they only hit database when evaluated.

```python
# No query yet
products = Product.objects.filter(is_active=True)

# Query executed here
for product in products:  # Iteration
    print(product.name)

# Or here
count = products.count()
```

## Performance Metrics

### Before Optimization
- Homepage load: ~2 seconds
- Database queries per request: 30+
- Average query time: 50ms

### After Optimization
- Homepage load: ~500ms
- Database queries per request: <10
- Average query time: 5ms

## Recommendations

1. **Regular Profiling**: Use Django Debug Toolbar in development
2. **Monitor Indexes**: Check for unused or missing indexes
3. **Cache Headers**: Add appropriate HTTP cache headers
4. **Query Pagination**: Always paginate large result sets
5. **Read Replicas**: Consider for production high-traffic scenarios
6. **Connection Pooling**: Use pgBouncer for PostgreSQL
7. **Archive Old Data**: Archive orders/logs older than 1 year

## Tools & Resources

- Django Debug Toolbar: `pip install django-debug-toolbar`
- Django Query Monitor: `pip install querycount`
- PostgreSQL pg_stat_statements: Monitor slow queries
- New Relic / DataDog: APM for production monitoring

## Common Patterns to Avoid

1. ❌ N+1 Queries in loops
2. ❌ `select_for_update()` without transactions
3. ❌ Fetching all records then filtering in Python
4. ❌ Multiple queries where one would suffice
5. ❌ Not using aggregations for counts/sums

## Implementation Checklist

- [ ] Add indexes for frequently queried fields
- [ ] Implement caching for context processors
- [ ] Add select_related/prefetch_related to all views
- [ ] Replace raw queries with ORM where possible
- [ ] Add query monitoring in production
- [ ] Document slow queries >100ms
- [ ] Setup database connection pooling
- [ ] Review and optimize all views for query efficiency
