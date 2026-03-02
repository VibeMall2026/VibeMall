# VibeMall Admin Panel - Resell Management Implementation & Corrections

**Focus:** Admin Panel Only (Staff/Superuser Views)  
**Document Version:** 1.0  
**Last Updated:** March 1, 2026

---

## TABLE OF CONTENTS
1. [Issues to Correct](#issues-to-correct)
2. [Admin Views to Modify](#admin-views-to-modify)
3. [Admin Templates to Update](#admin-templates-to-update)
4. [Admin Features to Implement](#admin-features-to-implement)
5. [Admin-Only Security](#admin-only-security)
6. [Implementation Checklist](#implementation-checklist)

---

## ISSUES TO CORRECT

### ❌ Issue 1: Input Validation Missing in Date Filters

**Location:** `views_admin_resell.py`, Lines 55-70

**Current Code:**
```python
date_from = request.GET.get('date_from', '')
date_to = request.GET.get('date_to', '')

try:
    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
except ValueError:
    pass  # Silently ignores!
```

**Problems:**
- Invalid dates silently ignored
- No bounds checking
- No error message shown to admin
- Can cause confusing blank results

**Correction:**
```python
def validate_admin_date_range(date_from_str: str, date_to_str: str) -> Tuple[Optional[date], Optional[date], List[str]]:
    """Validate date range from admin filters"""
    errors = []
    date_from = None
    date_to = None
    
    # Validate date_from
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            if date_from > timezone.now().date():
                errors.append("From date cannot be in the future")
            if date_from < (timezone.now() - timedelta(days=365*10)).date():
                errors.append("From date cannot be more than 10 years back")
        except ValueError:
            errors.append(f"Invalid From date format: {date_from_str}")
    
    # Validate date_to
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            if date_to > timezone.now().date():
                errors.append("To date cannot be in the future")
        except ValueError:
            errors.append(f"Invalid To date format: {date_to_str}")
    
    # Validate range
    if date_from and date_to and date_from > date_to:
        errors.append("From date cannot be after To date")
    
    return date_from, date_to, errors

# IN VIEW FUNCTION
def admin_resell_orders(request):
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    
    date_from, date_to, errors = validate_admin_date_range(date_from_str, date_to_str)
    
    if errors:
        messages.error(request, ' | '.join(errors))
        return render(request, 'admin_panel/resell/orders.html', {
            'error_messages': errors,
            'date_from': date_from_str,
            'date_to': date_to_str,
        })
    
    # Proceed with safely validated dates
    if date_from and date_to:
        queryset = queryset.filter(created_at__range=[date_from, date_to])
```

**Files to Update:**
- `views_admin_resell.py` (lines 55-80)
- Create new `admin_validators.py` utility file
- All admin list views

**Effort:** 1.5 hours

---

### ❌ Issue 2: N+1 Query Problem in Admin Analytics

**Location:** `views_admin_resell.py`, Lines 100-150 (`admin_reseller_analytics`)

**Current Code:**
```python
resellers = ResellerProfile.objects.filter(is_reseller_enabled=True)

for reseller in resellers:  # First query: X resellers
    earnings = ResellerEarning.objects.filter(reseller=reseller.user).aggregate(...)  # X more queries!
    orders = Order.objects.filter(reseller_id=reseller.user.id).count()  # X more queries!
    
# With 1000 resellers = 3000+ database hits
```

**Impact:** 
- Admin analytics page takes 10+ seconds to load
- Database CPU spikes

**Correction:**
```python
from django.db.models import Sum, Count, Avg, Q, F, DecimalField
from django.db.models.functions import Coalesce

def admin_reseller_analytics(request):
    """Admin analytics with optimized queries"""
    
    # Single optimized query with annotations
    resellers = ResellerProfile.objects.filter(
        is_reseller_enabled=True
    ).select_related('user').annotate(
        # Earnings calculations
        total_earnings=Coalesce(Sum('user__reseller_earnings__margin_amount'), 0),
        confirmed_earnings=Coalesce(
            Sum(
                'user__reseller_earnings__margin_amount',
                filter=Q(user__reseller_earnings__status='CONFIRMED')
            ),
            0
        ),
        pending_earnings=Coalesce(
            Sum(
                'user__reseller_earnings__margin_amount',
                filter=Q(user__reseller_earnings__status='PENDING')
            ),
            0
        ),
        paid_earnings=Coalesce(
            Sum(
                'user__reseller_earnings__margin_amount',
                filter=Q(user__reseller_earnings__status='PAID')
            ),
            0
        ),
        
        # Order calculations
        total_orders=Count('user__reseller_earnings', distinct=True),
        this_month_orders=Count(
            'user__reseller_earnings',
            filter=Q(
                user__reseller_earnings__created_at__month=timezone.now().month,
                user__reseller_earnings__created_at__year=timezone.now().year
            ),
            distinct=True
        ),
        
        # Payout calculations
        total_payouts=Count('user__payout_transactions', distinct=True),
        pending_payouts=Count(
            'user__payout_transactions',
            filter=Q(user__payout_transactions__status='PENDING'),
            distinct=True
        ),
        
        # Average calculations
        avg_margin=Coalesce(Avg('user__reseller_earnings__margin_amount'), 0),
    ).order_by('-total_earnings')
    
    # NOW aggregate for platform metrics
    platform_stats = ResellerEarning.objects.aggregate(
        platform_total_earnings=Coalesce(Sum('margin_amount'), 0),
        platform_confirmed=Coalesce(
            Sum('margin_amount', filter=Q(status='CONFIRMED')),
            0
        ),
        platform_pending=Coalesce(
            Sum('margin_amount', filter=Q(status='PENDING')),
            0
        ),
    )
    
    context = {
        'resellers': resellers[:50],  # Top 50
        'total_resellers': resellers.count(),
        'platform_stats': platform_stats,
        'resellers_paginated': resellers,
    }
    
    return render(request, 'admin_panel/resell/analytics.html', context)
```

**Files to Update:**
- `views_admin_resell.py` (lines 100-150)

**Effort:** 1 hour

---

### ❌ Issue 3: No Error Handling in Payout Approval

**Location:** `views_admin_resell.py`, Lines 280-320 (`admin_approve_payout`)

**Current Code:**
```python
def admin_approve_payout(request, payout_id):
    payout = get_object_or_404(PayoutTransaction, id=payout_id)
    
    # Missing checks:
    # - Is reseller still enabled?
    # - Is payout already approved?
    # - Are bank details valid?
    # - Is amount reasonable?
    
    payout.status = 'APPROVED'
    payout.save()  # Could fail silently
    
    return JsonResponse({'success': True})
```

**Problems:**
- Can approve disabled reseller payout
- No validation that earnings exist
- No audit trail
- No error messages for admin

**Correction:**
```python
from django.db import transaction
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger('resell_admin')

@staff_member_required
@require_POST
@transaction.atomic
def admin_approve_payout(request, payout_id):
    """Approve payout with comprehensive validation"""
    
    try:
        # Lock for update to prevent race conditions
        payout = PayoutTransaction.objects.select_for_update().get(
            id=payout_id
        )
    except PayoutTransaction.DoesNotExist:
        logger.warning(f"Payout {payout_id} not found - attempted by {request.user}")
        return JsonResponse(
            {'success': False, 'error': 'Payout not found'},
            status=404
        )
    
    # VALIDATION 1: Payout Status
    if payout.status != 'PENDING':
        return JsonResponse({
            'success': False,
            'error': f'Payout already {payout.status.lower()}. Cannot approve.'
        }, status=400)
    
    # VALIDATION 2: Reseller Active Check
    try:
        reseller_profile = payout.reseller.reseller_profile
    except AttributeError:
        logger.error(f"Reseller profile missing for payout {payout_id}")
        return JsonResponse({
            'success': False,
            'error': 'Reseller profile not found'
        }, status=400)
    
    if not reseller_profile.is_reseller_enabled:
        logger.warning(
            f"Admin {request.user} attempted to approve payout "
            f"for disabled reseller {payout.reseller}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Cannot approve payout for disabled reseller'
        }, status=403)
    
    # VALIDATION 3: Bank Details Present
    if not all([
        reseller_profile.bank_account_number,
        reseller_profile.bank_ifsc_code,
        reseller_profile.bank_account_name
    ]):
        return JsonResponse({
            'success': False,
            'error': 'Reseller bank details incomplete. Please contact reseller.'
        }, status=400)
    
    # VALIDATION 4: Amount Sanity Check
    if payout.amount <= 0:
        logger.error(f"Invalid payout amount: {payout.amount} for {payout_id}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid payout amount'
        }, status=400)
    
    if payout.amount > Decimal('1000000'):  # Max ₹10 lakh
        logger.error(f"Suspiciously large payout: ₹{payout.amount} for {payout_id}")
        return JsonResponse({
            'success': False,
            'error': 'Payout amount exceeds maximum limit'
        }, status=400)
    
    # VALIDATION 5: OTP for Large Payouts (>₹100K)
    if payout.amount > Decimal('100000'):
        otp_token = request.POST.get('otp_token', '')
        if not otp_token:
            return JsonResponse({
                'success': False,
                'error': 'OTP verification required for payouts >₹100,000',
                'requires_otp': True
            }, status=403)
        
        if not verify_otp_for_user(request.user, otp_token):
            logger.warning(
                f"Failed OTP verification for admin {request.user} "
                f"approving payout {payout_id}"
            )
            return JsonResponse({
                'success': False,
                'error': 'Invalid OTP'
            }, status=403)
    
    # All validations passed - Approve
    try:
        payout.status = 'APPROVED'
        payout.approved_by = request.user
        payout.approved_at = timezone.now()
        payout.save()
        
        # Create audit log
        ResellAuditLog.objects.create(
            action_type='PAYOUT_APPROVED',
            reseller=payout.reseller,
            performed_by=request.user,
            details={
                'payout_id': str(payout_id),
                'amount': str(payout.amount),
                'payout_method': payout.payout_method,
                'reseller_name': payout.reseller.get_full_name() or payout.reseller.username,
            },
            ip_address=get_client_ip(request),
        )
        
        logger.info(
            f"✓ APPROVED: Payout ID {payout_id} for "
            f"₹{payout.amount} to {payout.reseller.username} "
            f"by {request.user.username}"
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Payout ₹{payout.amount:,.0f} approved successfully',
            'payout_id': payout_id,
        })
        
    except Exception as e:
        logger.exception(f"Error approving payout {payout_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to approve payout. Please try again or contact support.'
        }, status=500)

def verify_otp_for_user(user: User, otp_token: str) -> bool:
    """Verify OTP for admin"""
    # Implementation depends on your OTP system
    # This is placeholder
    return True
```

**Files to Update:**
- `views_admin_resell.py` (lines 280-320)
- Create `admin_utils.py` with `get_client_ip()` and OTP verification

**Effort:** 2 hours

---

### ❌ Issue 4: No Sorting/Pagination in Admin Lists

**Location:** All admin list views in `views_admin_resell.py`

**Current Code:**
```python
# admin_reseller_management()
resellers = ResellerProfile.objects.filter(is_reseller_enabled=True)

context = {'resellers': resellers}  # All resellers, no pagination
# With 5000+ resellers = 10+ second page load!
```

**Correction:**
```python
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@staff_member_required
def admin_reseller_management(request):
    """Admin: Manage resellers with filters, sorting, pagination"""
    
    # BASE QUERYSET
    queryset = ResellerProfile.objects.select_related('user').all()
    
    # FILTER 1: Status
    status = request.GET.get('status', 'enabled')
    if status == 'enabled':
        queryset = queryset.filter(is_reseller_enabled=True)
    elif status == 'disabled':
        queryset = queryset.filter(is_reseller_enabled=False)
    
    # FILTER 2: Search
    search = request.GET.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    # FILTER 3: Date Range
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    
    date_from, date_to, date_errors = validate_admin_date_range(date_from_str, date_to_str)
    if date_errors:
        messages.warning(request, 'Date filter error: ' + ' | '.join(date_errors))
    if date_from:
        queryset = queryset.filter(user__date_joined__gte=date_from)
    if date_to:
        queryset = queryset.filter(user__date_joined__lte=date_to)
    
    # SORTING
    sort_by = request.GET.get('sort_by', '-user__date_joined')
    valid_sorts = {
        'username': 'user__username',
        '-username': '-user__username',
        'earnings': '-total_earnings',  # Descending by default
        'balance': '-available_balance',
        'joined': '-user__date_joined',
    }
    
    if sort_by in valid_sorts:
        queryset = queryset.annotate(
            total_earnings=Coalesce(Sum('user__reseller_earnings__margin_amount'), 0)
        ).order_by(valid_sorts[sort_by])
    else:
        queryset = queryset.order_by('-user__date_joined')
    
    # PAGINATION
    page_size = request.GET.get('page_size', '25')
    try:
        page_size = int(page_size)
        if page_size not in [10, 25, 50, 100]:
            page_size = 25
    except (ValueError, TypeError):
        page_size = 25
    
    paginator = Paginator(queryset, page_size)
    page_num = request.GET.get('page', 1)
    
    try:
        resellers = paginator.page(page_num)
    except PageNotAnInteger:
        resellers = paginator.page(1)
    except EmptyPage:
        resellers = paginator.page(paginator.num_pages)
    
    # CONTEXT
    context = {
        'resellers': resellers,
        'paginator': paginator,
        'total_count': paginator.count,
        'current_page': resellers.number,
        'total_pages': paginator.num_pages,
        'page_range': paginator.page_range,
        
        # Filter values (for template)
        'filter_status': status,
        'filter_search': search,
        'filter_date_from': date_from_str,
        'filter_date_to': date_to_str,
        'filter_sort': sort_by,
        'filter_page_size': page_size,
    }
    
    return render(request, 'admin_panel/resell/resellers.html', context)
```

**Files to Update:**
- `views_admin_resell.py` (all list views)

**Effort:** 2.5 hours

---

### ❌ Issue 5: Empty Error Handling in Admin Actions

**Location:** All POST views in `views_admin_resell.py`

**Current Code:**
```python
def admin_toggle_reseller_status(request, reseller_id):
    reseller = get_object_or_404(User, id=reseller_id)
    
    # No try/except
    profile = reseller.reseller_profile
    profile.is_reseller_enabled = not profile.is_reseller_enabled
    profile.save()
    
    return redirect('admin:resell_resellers')
```

**Problems:**
- Exception if reseller_profile doesn't exist
- No feedback to admin
- No logging
- No audit trail

**Correction:**
```python
@staff_member_required
@require_POST
def admin_toggle_reseller_status(request, reseller_id):
    """Toggle reseller enable/disable status"""
    
    try:
        reseller = User.objects.get(id=reseller_id)
    except User.DoesNotExist:
        messages.error(request, f'Reseller with ID {reseller_id} not found')
        return redirect('admin:resell_resellers')
    
    try:
        profile = reseller.reseller_profile
    except ResellerProfile.DoesNotExist:
        messages.error(request, f'{reseller.username} is not a reseller')
        return redirect('admin:resell_resellers')
    
    # Get current status
    old_status = profile.is_reseller_enabled
    new_status = not old_status
    
    # Get disable reason if disabling
    disable_reason = ''
    if old_status and not new_status:
        disable_reason = request.POST.get('disable_reason', '').strip()
        if not disable_reason:
            messages.warning(request, 'Please provide a reason for disabling')
            return redirect('admin:resell_resellers')
    
    try:
        profile.is_reseller_enabled = new_status
        profile.save()
        
        # Create audit log
        ResellAuditLog.objects.create(
            action_type='RESELLER_DISABLED' if not new_status else 'RESELLER_ENABLED',
            reseller=reseller,
            performed_by=request.user,
            details={
                'old_status': old_status,
                'new_status': new_status,
                'reason': disable_reason,
            },
            ip_address=get_client_ip(request),
        )
        
        status_text = 'Enabled' if new_status else 'Disabled'
        messages.success(request, f'Reseller {reseller.username} {status_text}')
        
        logger.info(
            f"✓ Reseller {reseller.username} "
            f"{'ENABLED' if new_status else 'DISABLED'} by {request.user}"
        )
        
    except Exception as e:
        logger.exception(f"Error toggling reseller {reseller_id} status: {str(e)}")
        messages.error(request, 'Failed to update reseller status. Try again.')
    
    return redirect('admin:resell_resellers')
```

**Files to Update:**
- `views_admin_resell.py` (all POST views)

**Effort:** 2 hours

---

## ADMIN VIEWS TO MODIFY

### View 1: `admin_resell_orders()` - Line 32

**Current Status:** ⚠️ Basic filtering only

**Modifications Required:**

| Item | Current | Required |
|------|---------|----------|
| Pagination | None | Add (25 per page) |
| Sorting | None | By date, amount, status |
| Filters | Status | + Payment status, reseller, amount range |
| Query | 20+ queries | Optimize to <5 |
| Search | None | By order ID, customer name |

**Code Update:**
```python
@staff_member_required
def admin_resell_orders(request):
    """Admin: View all resell orders with filters, sorting, pagination"""
    
    # BASE QUERY - OPTIMIZED
    queryset = Order.objects.filter(
        is_resell=True
    ).select_related(
        'user',           # Customer
        'reseller',       # Reseller
        'resell_link'     # Resell link
    ).prefetch_related(
        'items'           # Order items
    )
    
    # FILTERS
    status = request.GET.get('status', '')
    if status and status in ['PENDING', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED']:
        queryset = queryset.filter(order_status=status)
    
    payment_status = request.GET.get('payment_status', '')
    if payment_status and payment_status in ['PENDING', 'COMPLETED', 'FAILED', 'REFUNDED']:
        queryset = queryset.filter(payment_status=payment_status)
    
    reseller_id = request.GET.get('reseller', '')
    if reseller_id:
        try:
            queryset = queryset.filter(reseller_id=int(reseller_id))
        except (ValueError, TypeError):
            pass
    
    # SEARCH
    search = request.GET.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(order_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # DATE RANGE
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    date_from, date_to, date_errors = validate_admin_date_range(date_from_str, date_to_str)
    
    if date_from:
        queryset = queryset.filter(created_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__lte=date_to)
    
    # SORTING
    sort_by = request.GET.get('sort_by', '-created_at')
    valid_sorts = ['-created_at', 'created_at', '-total_amount', 'total_amount', 'order_status']
    if sort_by in valid_sorts:
        queryset = queryset.order_by(sort_by)
    
    # PAGINATION
    paginator = Paginator(queryset, 25)
    page = request.GET.get('page', 1)
    try:
        orders = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        orders = paginator.page(1)
    
    # SUMMARY STATS (CACHED)
    cache_key = "admin_resell_orders_stats"
    stats = cache.get(cache_key)
    if not stats:
        stats = {
            'total_orders': queryset.count(),
            'total_amount': queryset.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'total_margin': queryset.aggregate(Sum('total_margin'))['total_margin__sum'] or 0,
        }
        cache.set(cache_key, stats, 300)  # Cache 5 minutes
    
    context = {
        'orders': orders,
        'stats': stats,
        'filter_status': status,
        'filter_payment_status': payment_status,
        'filter_search': search,
    }
    
    return render(request, 'admin_panel/resell/orders.html', context)
```

**Files to Update:**
- `views_admin_resell.py` (lines 32-95)

**Effort:** 1.5 hours

---

### View 2: `admin_reseller_analytics()` - Line 100

**Current Status:** ⚠️ Incomplete

**Modifications Required:**
- Optimize N+1 queries (from 20+ to 2-3)
- Add platform average metrics
- Add top 10% reseller metrics
- Add monthly trends
- Add risk flagging

**Code Update:** (See Issue 2 - N+1 Query Problem above)

**Files to Update:**
- `views_admin_resell.py` (lines 100-150)

**Effort:** 1 hour

---

### View 3: `admin_payout_management()` - Line 320

**Current Status:** ⚠️ Missing filters

**Modifications Required:**

```python
@staff_member_required
def admin_payout_management(request):
    """Admin: Manage payouts with filters and actions"""
    
    queryset = PayoutTransaction.objects.select_related(
        'reseller'
    ).all()
    
    # FILTERS
    status = request.GET.get('status', '')  # PENDING, APPROVED, PROCESSING, COMPLETED, FAILED
    if status:
        queryset = queryset.filter(status=status)
    
    payout_method = request.GET.get('method', '')  # BANK, UPI
    if payout_method:
        queryset = queryset.filter(payout_method=payout_method)
    
    # AMOUNT RANGE
    min_amount = request.GET.get('min_amount', '')
    max_amount = request.GET.get('max_amount', '')
    try:
        if min_amount:
            queryset = queryset.filter(amount__gte=Decimal(min_amount))
        if max_amount:
            queryset = queryset.filter(amount__lte=Decimal(max_amount))
    except (ValueError, TypeError):
        pass
    
    # DATE RANGE
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    date_from, date_to, _ = validate_admin_date_range(date_from_str, date_to_str)
    
    if date_from:
        queryset = queryset.filter(initiated_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(initiated_at__lte=date_to)
    
    # SORTING
    sort_by = request.GET.get('sort_by', '-initiated_at')
    valid_sorts = ['-initiated_at', 'initiated_at', '-amount', 'amount', 'status']
    if sort_by in valid_sorts:
        queryset = queryset.order_by(sort_by)
    
    # PAGINATION
    paginator = Paginator(queryset, 25)
    page = request.GET.get('page', 1)
    payouts = paginator.page(page) if page else paginator.page(1)
    
    context = {
        'payouts': payouts,
        'filter_status': status,
        'filter_method': payout_method,
    }
    
    return render(request, 'admin_panel/resell/payouts.html', context)
```

**Files to Update:**
- `views_admin_resell.py` (lines 320-370)

**Effort:** 1.5 hours

---

## ADMIN TEMPLATES TO UPDATE

### Template 1: `resellers.html`

**Current State:** ⚠️ Basic list only

**Required Updates:**

```django
<!-- FILTER SECTION (ADD) -->
<div class="card mb-4">
    <div class="card-header bg-primary text-white">
        <h5 class="mb-0">Filter Resellers</h5>
    </div>
    <div class="card-body">
        <form method="get" class="row g-3">
            <!-- Search -->
            <div class="col-md-3">
                <label class="form-label">Search</label>
                <input type="text" name="search" class="form-control" 
                       placeholder="Username, email..." value="{{ filter_search }}">
            </div>
            
            <!-- Status -->
            <div class="col-md-2">
                <label class="form-label">Status</label>
                <select name="status" class="form-select">
                    <option value="">All</option>
                    <option value="enabled" {% if filter_status == 'enabled' %}selected{% endif %}>Active</option>
                    <option value="disabled" {% if filter_status == 'disabled' %}selected{% endif %}>Disabled</option>
                </select>
            </div>
            
            <!-- Date Range -->
            <div class="col-md-2">
                <label class="form-label">From Date</label>
                <input type="date" name="date_from" class="form-control" value="{{ filter_date_from }}">
            </div>
            
            <div class="col-md-2">
                <label class="form-label">To Date</label>
                <input type="date" name="date_to" class="form-control" value="{{ filter_date_to }}">
            </div>
            
            <!-- Sort -->
            <div class="col-md-2">
                <label class="form-label">Sort By</label>
                <select name="sort_by" class="form-select">
                    <option value="-user__date_joined">Newest First</option>
                    <option value="user__username">Username (A-Z)</option>
                    <option value="-total_earnings">Highest Earnings</option>
                </select>
            </div>
            
            <!-- Buttons -->
            <div class="col-md-2">
                <label class="form-label">&nbsp;</label>
                <button type="submit" class="btn btn-primary w-100">Apply</button>
            </div>
        </form>
    </div>
</div>

<!-- RESULTS TABLE (UPDATE) -->
<div class="table-responsive">
    <table class="table table-hover">
        <thead class="table-dark">
            <tr>
                <th>
                    <input type="checkbox" id="selectAll" class="form-check-input">
                </th>
                <th>Username</th>
                <th>Email</th>
                <th>Total Earnings</th>
                <th>Available Balance</th>
                <th>Orders</th>
                <th>Status</th>
                <th>Joined</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for reseller in resellers %}
            <tr>
                <td>
                    <input type="checkbox" class="form-check-input reseller-checkbox" 
                           value="{{ reseller.user.id }}">
                </td>
                <td>
                    <a href="{% url 'admin:resell_reseller_detail' reseller.user.id %}">
                        {{ reseller.user.username }}
                    </a>
                </td>
                <td>{{ reseller.user.email }}</td>
                <td><strong>₹{{ reseller.total_earnings|floatformat:0|default:"0" }}</strong></td>
                <td>₹{{ reseller.available_balance|floatformat:0|default:"0" }}</td>
                <td>{{ reseller.total_orders|default:"0" }}</td>
                <td>
                    {% if reseller.is_reseller_enabled %}
                        <span class="badge bg-success">Active</span>
                    {% else %}
                        <span class="badge bg-danger">Disabled</span>
                    {% endif %}
                </td>
                <td>{{ reseller.user.date_joined|date:"M d, Y" }}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <a href="{% url 'admin:resell_reseller_detail' reseller.user.id %}" 
                           class="btn btn-info" title="View">
                            <i class="fas fa-eye"></i>
                        </a>
                        {% if reseller.is_reseller_enabled %}
                        <button class="btn btn-warning toggle-reseller" 
                                data-id="{{ reseller.user.id }}" title="Disable">
                            <i class="fas fa-ban"></i>
                        </button>
                        {% else %}
                        <button class="btn btn-success toggle-reseller" 
                                data-id="{{ reseller.user.id }}" title="Enable">
                            <i class="fas fa-check"></i>
                        </button>
                        {% endif %}
                    </div>
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="9" class="text-center text-muted">No resellers found</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- PAGINATION (ADD) -->
{% if paginator.num_pages > 1 %}
<nav>
    <ul class="pagination justify-content-center">
        {% if resellers.has_previous %}
        <li class="page-item">
            <a class="page-link" href="?page=1">First</a>
        </li>
        <li class="page-item">
            <a class="page-link" href="?page={{ resellers.previous_page_number }}">Previous</a>
        </li>
        {% endif %}
        
        <li class="page-item active">
            <span class="page-link">Page {{ resellers.number }} of {{ paginator.num_pages }}</span>
        </li>
        
        {% if resellers.has_next %}
        <li class="page-item">
            <a class="page-link" href="?page={{ resellers.next_page_number }}">Next</a>
        </li>
        <li class="page-item">
            <a class="page-link" href="?page={{ paginator.num_pages }}">Last</a>
        </li>
        {% endif %}
    </ul>
</nav>
{% endif %}
```

**Files to Update:**
- `templates/admin_panel/resell/resellers.html`

**Effort:** 1.5 hours

---

### Template 2: `orders.html`

**Current State:** ⚠️ Minimal

**Required Updates:**

```django
<!-- FILTER SECTION -->
<div class="card mb-4">
    <div class="card-header bg-primary text-white">
        <h5 class="mb-0">Filter Orders</h5>
    </div>
    <div class="card-body">
        <form method="get" class="row g-3">
            <div class="col-md-2">
                <label class="form-label">Order Status</label>
                <select name="status" class="form-select">
                    <option value="">All</option>
                    <option value="PENDING">Pending</option>
                    <option value="CONFIRMED">Confirmed</option>
                    <option value="SHIPPED">Shipped</option>
                    <option value="DELIVERED">Delivered</option>
                    <option value="CANCELLED">Cancelled</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <label class="form-label">Payment Status</label>
                <select name="payment_status" class="form-select">
                    <option value="">All</option>
                    <option value="PENDING">Pending</option>
                    <option value="COMPLETED">Completed</option>
                    <option value="FAILED">Failed</option>
                    <option value="REFUNDED">Refunded</option>
                </select>
            </div>
            
            <div class="col-md-2">
                <label class="form-label">From Date</label>
                <input type="date" name="date_from" class="form-control">
            </div>
            
            <div class="col-md-2">
                <label class="form-label">To Date</label>
                <input type="date" name="date_to" class="form-control">
            </div>
            
            <div class="col-md-2">
                <label class="form-label">Search</label>
                <input type="text" name="search" class="form-control" placeholder="Order ID">
            </div>
            
            <div class="col-md-2">
                <label class="form-label">&nbsp;</label>
                <button type="submit" class="btn btn-primary w-100">Filter</button>
            </div>
        </form>
    </div>
</div>

<!-- SUMMARY STATS (ADD) -->
<div class="row mb-4">
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h6 class="card-title text-muted">Total Orders</h6>
                <h3>{{ stats.total_orders }}</h3>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h6 class="card-title text-muted">Total Amount</h6>
                <h3>₹{{ stats.total_amount|floatformat:0 }}</h3>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h6 class="card-title text-muted">Total Margin</h6>
                <h3>₹{{ stats.total_margin|floatformat:0 }}</h3>
            </div>
        </div>
    </div>
</div>

<!-- ORDERS TABLE -->
<table class="table table-hover">
    <thead>
        <tr>
            <th>Order ID</th>
            <th>Customer</th>
            <th>Reseller</th>
            <th>Amount</th>
            <th>Margin</th>
            <th>Status</th>
            <th>Payment</th>
            <th>Date</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {% for order in orders %}
        <tr>
            <td><a href="#">{{ order.order_id }}</a></td>
            <td>{{ order.user.username }}</td>
            <td>
                <a href="{% url 'admin:resell_reseller_detail' order.reseller.id %}">
                    {{ order.reseller.username }}
                </a>
            </td>
            <td>₹{{ order.total_amount|floatformat:0 }}</td>
            <td>₹{{ order.total_margin|floatformat:0 }}</td>
            <td>
                <span class="badge bg-primary">{{ order.order_status }}</span>
            </td>
            <td>
                <span class="badge bg-info">{{ order.payment_status }}</span>
            </td>
            <td>{{ order.created_at|date:"M d, Y" }}</td>
            <td>
                <a href="#" class="btn btn-sm btn-info">View</a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

**Files to Update:**
- `templates/admin_panel/resell/orders.html`

**Effort:** 1.5 hours

---

### Template 3: `payouts.html`

**Current State:** ❌ Missing

**To Create:** New template with payout management UI

```django
<!-- Similar structure to orders.html but for payouts -->
<!-- Filters: Status, Method, Amount Range, Date Range -->
<!-- Table: Payout ID, Reseller, Amount, Method, Status, Actions -->
<!-- Per-row actions: Approve, Reject, Retry (for failed) -->
```

**Files to Create:**
- `templates/admin_panel/resell/payouts.html`

**Effort:** 1.5 hours

---

### Template 4: `analytics.html` - ENHANCEMENT

**Current State:** ⚠️ Incomplete

**Add Charts:**
- Earnings trend (line chart)
- Top resellers (bar chart)
- Orders distribution (pie chart)

**Use:** ChartJS or Plotly

**Effort:** 2 hours

---

## ADMIN FEATURES TO IMPLEMENT

### Feature 1: KYC Verification Admin View

**Location:** New view function `admin_kyc_verification()`

**Features:**
- [ ] View pending KYC submissions
- [ ] Filter by status (Pending, Approved, Rejected)
- [ ] View uploaded documents
- [ ] Approve/reject with notes
- [ ] Auto-disable reseller on rejection
- [ ] Resend request button

**Implementation Effort:** 3 hours (view + template)

---

### Feature 2: Audit Log Viewer

**Location:** New view function `admin_audit_logs()`

**Features:**
- [ ] Filter by action type
- [ ] Filter by date range
- [ ] Filter by admin user
- [ ] Filter by affected reseller
- [ ] Show action details (old/new values)
- [ ] Export to CSV

**Implementation Effort:** 2 hours (view + template)

---

### Feature 3: Payout Reconciliation

**Location:** New view function `admin_payout_reconciliation()`

**Features:**
- [ ] View payouts by date range
- [ ] Compare approved vs completed vs failed
- [ ] Reconcile with bank statement
- [ ] Retry failed payouts
- [ ] Generate reconciliation report

**Implementation Effort:** 2.5 hours

---

### Feature 4: Reseller Bulk Actions

**Location:** Update `admin_reseller_management()`

**Features:**
- [ ] Bulk enable/disable
- [ ] Bulk export (CSV)
- [ ] Bulk message send
- [ ] Bulk tier upgrade

**Implementation Effort:** 1.5 hours

---

## ADMIN-ONLY SECURITY

### 1. **Rate Limiting on Admin Actions**

```python
from django_ratelimit.decorators import ratelimit

@staff_member_required
@require_POST
@ratelimit(key='user', rate='10/m')  # 10 approvals per minute max
def admin_approve_payout(request, payout_id):
    # ...
```

**Apply to:**
- `admin_approve_payout()` - 5/min
- `admin_reject_payout()` - 5/min
- `admin_toggle_reseller_status()` - 10/min
- `admin_kyc_verification()` (approve only) - 5/min

**Effort:** 30 minutes

---

### 2. **Admin Action Audit Logging**

**Create Model:**
```python
class AdminActionLog(models.Model):
    ACTION_CHOICES = [
        ('APPROVE_PAYOUT', 'Approve Payout'),
        ('REJECT_PAYOUT', 'Reject Payout'),
        ('ENABLE_RESELLER', 'Enable Reseller'),
        ('DISABLE_RESELLER', 'Disable Reseller'),
        ('VERIFY_KYC', 'Verify KYC'),
        ('REJECT_KYC', 'Reject KYC'),
    ]
    
    admin = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    affected_reseller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_actions')
    details =models.JSONField()
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['admin', '-timestamp']),
            models.Index(fields=['affected_reseller', '-timestamp']),
        ]
```

**Effort:** 1 hour

---

### 3. **Two-Factor Authentication for High-Risk Actions**

```python
def admin_requires_otp(amount_threshold=Decimal('100000')):
    """Decorator requiring OTP for high-value operations"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.method != 'POST':
                return view_func(request, *args, **kwargs)
            
            # Get amount from kwargs or POST
            amount = kwargs.get('amount') or Decimal(request.POST.get('amount', 0))
            
            if amount > amount_threshold:
                otp_token = request.POST.get('otp_token', '')
                if not otp_token or not verify_otp(request.user, otp_token):
                    return JsonResponse({'error': 'OTP required'}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

@admin_requires_otp(Decimal('100000'))  # Require OTP for >₹100K
def admin_approve_payout(request, payout_id):
    # ...
```

**Effort:** 1.5 hours

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Critical Issues (Week 1)

- [ ] **Issue 1**: Add input validation to date filters
  - [ ] Create `admin_validators.py`
  - [ ] Update all admin views using dates
  - [ ] Test with invalid inputs
  - **Effort:** 1.5 hours

- [ ] **Issue 2**: Optimize N+1 queries in analytics
  - [ ] Update `admin_reseller_analytics()` view
  - [ ] Test query count (<5)
  - [ ] Verify page load time (<1s)
  - **Effort:** 1 hour

- [ ] **Issue 3**: Add error handling to payout approval
  - [ ] Update `admin_approve_payout()` view
  - [ ] Add validation checks
  - [ ] Create audit logging
  - [ ] Test all error paths
  - **Effort:** 2 hours

- [ ] **Issue 4**: Add sorting/pagination
  - [ ] Update all list views
  - [ ] Create pagination templates
  - [ ] Test with large datasets
  - **Effort:** 2.5 hours

- [ ] **Issue 5**: Add error handling to admin actions
  - [ ] Update all POST views
  - [ ] Add try/except blocks
  - [ ] Create audit logs
  - [ ] Test with invalid data
  - **Effort:** 2 hours

**Subtotal Phase 1: ~9 hours**

---

### Phase 2: Templates (Week 2)

- [ ] **Template 1**: Update `resellers.html`
  - [ ] Add filter section
  - [ ] Update table with new columns
  - [ ] Add pagination
  - [ ] Add bulk action checkboxes
  - **Effort:** 1.5 hours

- [ ] **Template 2**: Update `orders.html`
  - [ ] Add filter section
  - [ ] Add summary stats cards
  - [ ] Update table
  - [ ] Add pagination
  - **Effort:** 1.5 hours

- [ ] **Template 3**: Create `payouts.html`
  - [ ] Design from scratch
  - [ ] Add filters
  - [ ] Add payout table
  - [ ] Add action buttons (Approve, Reject, Retry)
  - **Effort:** 1.5 hours

- [ ] **Template 4**: Enhance `analytics.html`
  - [ ] Integrate ChartJS
  - [ ] Add earnings trend chart
  - [ ] Add top resellers chart
  - [ ] Add orders distribution
  - **Effort:** 2 hours

**Subtotal Phase 2: ~6.5 hours**

---

### Phase 3: New Admin Features (Week 2-3)

- [ ] **Feature 1**: KYC Verification View
  - [ ] Create `admin_kyc_verification()` view
  - [ ] Create template
  - [ ] Add document viewer
  - [ ] Add approve/reject form
  - **Effort:** 3 hours

- [ ] **Feature 2**: Audit Log Viewer
  - [ ] Create `admin_audit_logs()` view
  - [ ] Create model indices
  - [ ] Create template
  - [ ] Add filters
  - **Effort:** 2 hours

- [ ] **Feature 3**: Payout Reconciliation
  - [ ] Create `admin_payout_reconciliation()` view
  - [ ] Create reconciliation logic
  - [ ] Create template
  - [ ] Add export functionality
  - **Effort:** 2.5 hours

- [ ] **Feature 4**: Bulk Actions
  - [ ] Implement in reseller management
  - [ ] Add select all checkbox
  - [ ] Add bulk enable/disable
  - [ ] Add bulk export
  - **Effort:** 1.5 hours

**Subtotal Phase 3: ~9 hours**

---

### Phase 4: Security Hardening (Week 3)

- [ ] **Security 1**: Rate Limiting
  - [ ] Apply to high-risk views
  - [ ] Add to requirements.txt (`django-ratelimit`)
  - [ ] Configure limits
  - [ ] Test rate limiting
  - **Effort:** 1 hour

- [ ] **Security 2**: Audit Logging Model
  - [ ] Create `AdminActionLog` model
  - [ ] Create migration
  - [ ] Log all admin actions
  - [ ] Create admin interface
  - **Effort:** 1.5 hours

- [ ] **Security 3**: OTP for High-Value Actions
  - [ ] Create `admin_requires_otp()` decorator
  - [ ] Integrate with existing OTP system
  - [ ] Update high-risk views
  - [ ] Test OTP flow
  - **Effort:** 1.5 hours

**Subtotal Phase 4: ~4 hours**

---

### Phase 5: Testing & Deployment (Week 4)

- [ ] **Testing**
  - [ ] Unit tests for views
  - [ ] Integration tests for admin panel
  - [ ] Load testing (1000+ resellers)
  - [ ] Security testing
  - **Effort:** 4 hours

- [ ] **Deployment**
  - [ ] Database migrations
  - [ ] Static files collection
  - [ ] Cache warming
  - [ ] Monitoring setup
  - **Effort:** 2 hours

**Subtotal Phase 5: ~6 hours**

---

## TOTAL ESTIMATE: ~34.5 hours (~1 week intensive or 2 weeks normal pace)

---

## FILES TO CREATE/UPDATE

### Files to Create

1. `Hub/admin_validators.py` - Input validation utilities
2. `Hub/admin_utils.py` - Helper functions (IP, OTP, etc.)
3. `templates/admin_panel/resell/payouts.html` - New template
4. `templates/admin_panel/resell/kyc_verification.html` - New template
5. `templates/admin_panel/resell/audit_logs.html` - New template
6. Migration for `AdminActionLog` model

### Files to Modify

1. `Hub/views_admin_resell.py` - All admin views (~200 lines changed)
2. `Hub/models.py` - Add `AdminActionLog` model (~30 lines)
3. `templates/admin_panel/resell/resellers.html` - Update (~100 lines)
4. `templates/admin_panel/resell/orders.html` - Update (~80 lines)
5. `templates/admin_panel/resell/analytics.html` - Enhance (~100 lines)

---

## SUCCESS CRITERIA

After completing all items:

✅ All admin pages load in <500ms  
✅ Max 5 database queries per page  
✅ Comprehensive error handling on all admin actions  
✅ All admin actions logged with attribution  
✅ Advanced filters on all list views (sort, search, date range)  
✅ Pagination on all admin lists  
✅ Payout approval requires validation + OTP for >₹100K  
✅ Admin audit trail complete & searchable  
✅ No N+1 queries (verified)  
✅ Security hardening complete (rate limits, logging, OTP)

