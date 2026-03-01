"""
Resell Feature Views

This module contains views for resell functionality:
- Resell link creation and management
- Reseller dashboard
- Payout requests
- Earnings history
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.utils import timezone

from .models import (
    ResellLink,
    ResellerProfile,
    ResellerEarning,
    PayoutTransaction,
    Product,
    Order
)
from .resell_services import (
    ResellLinkGenerator,
    MarginCalculator,
    ResellerPaymentManager,
    ResellOrderProcessor
)


# ============================================
# RESELL LINK MANAGEMENT
# ============================================

@login_required
@require_POST
def create_resell_link(request):
    """
    Create a new resell link
    POST /api/resell/create-link/
    
    Required POST parameters:
    - product_id: ID of the product
    - margin_amount: Margin amount to add
    
    Returns JSON response with resell link details
    """
    try:
        product_id = request.POST.get('product_id')
        margin_amount = request.POST.get('margin_amount')
        
        if not product_id or not margin_amount:
            return JsonResponse({
                'success': False,
                'error': 'Product ID and margin amount are required.'
            }, status=400)
        
        try:
            margin_amount = Decimal(margin_amount)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid margin amount.'
            }, status=400)
        
        # Create resell link using service
        resell_link = ResellLinkGenerator.create_resell_link(
            user_id=request.user.id,
            product_id=int(product_id),
            margin_amount=margin_amount
        )
        
        # Generate shareable URL
        shareable_url = request.build_absolute_uri(
            f'/product/{resell_link.product.slug}/?resell={resell_link.resell_code}'
        )
        
        return JsonResponse({
            'success': True,
            'resell_link': {
                'id': resell_link.id,
                'resell_code': resell_link.resell_code,
                'shareable_url': shareable_url,
                'margin_amount': str(resell_link.margin_amount),
                'margin_percentage': str(resell_link.margin_percentage),
                'product_name': resell_link.product.name,
                'product_price': str(resell_link.product.price),
                'customer_price': str(resell_link.product.price + resell_link.margin_amount),
            }
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while creating the resell link.'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def my_resell_links(request):
    """
    Get all resell links for the current user
    GET /api/resell/my-links/
    
    Optional query parameters:
    - active_only: 'true' to get only active links
    
    Returns JSON response with list of resell links
    """
    try:
        active_only = request.GET.get('active_only', 'false').lower() == 'true'
        
        links = ResellLinkGenerator.get_reseller_links(
            user_id=request.user.id,
            active_only=active_only
        )
        
        links_data = []
        for link in links:
            shareable_url = request.build_absolute_uri(
                f'/product/{link.product.slug}/?resell={link.resell_code}'
            )
            
            links_data.append({
                'id': link.id,
                'resell_code': link.resell_code,
                'shareable_url': shareable_url,
                'product_id': link.product.id,
                'product_name': link.product.name,
                'product_price': str(link.product.price),
                'margin_amount': str(link.margin_amount),
                'margin_percentage': str(link.margin_percentage),
                'customer_price': str(link.product.price + link.margin_amount),
                'is_active': link.is_active,
                'views_count': link.views_count,
                'orders_count': link.orders_count,
                'total_earnings': str(link.total_earnings),
                'created_at': link.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'links': links_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while fetching resell links.'
        }, status=500)


@login_required
@require_POST
def deactivate_resell_link(request):
    """
    Deactivate a resell link
    POST /api/resell/deactivate-link/
    
    Required POST parameters:
    - link_id: ID of the resell link
    
    Returns JSON response
    """
    try:
        link_id = request.POST.get('link_id')
        
        if not link_id:
            return JsonResponse({
                'success': False,
                'error': 'Link ID is required.'
            }, status=400)
        
        resell_link = ResellLinkGenerator.deactivate_link(
            resell_link_id=int(link_id),
            user_id=request.user.id
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Resell link deactivated successfully.',
            'link_id': resell_link.id,
            'is_active': resell_link.is_active
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while deactivating the link.'
        }, status=500)


@login_required
@require_POST
def reactivate_resell_link(request):
    """
    Reactivate a resell link
    POST /api/resell/reactivate-link/
    
    Required POST parameters:
    - link_id: ID of the resell link
    
    Returns JSON response
    """
    try:
        link_id = request.POST.get('link_id')
        
        if not link_id:
            return JsonResponse({
                'success': False,
                'error': 'Link ID is required.'
            }, status=400)
        
        resell_link = ResellLinkGenerator.reactivate_link(
            resell_link_id=int(link_id),
            user_id=request.user.id
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Resell link reactivated successfully.',
            'link_id': resell_link.id,
            'is_active': resell_link.is_active
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while reactivating the link.'
        }, status=500)


# ============================================
# RESELLER DASHBOARD
# ============================================

@login_required
def reseller_dashboard(request):
    """
    Reseller dashboard view
    GET /reseller/dashboard/
    
    Displays earnings, balance, and performance metrics
    """
    try:
        profile = request.user.reseller_profile
        
        if not profile.is_reseller_enabled:
            messages.warning(request, 'You do not have reseller permissions.')
            return redirect('home')
        
    except ResellerProfile.DoesNotExist:
        messages.warning(request, 'You do not have a reseller profile.')
        return redirect('home')
    
    # Get dashboard data
    recent_orders = Order.objects.filter(
        reseller=request.user,
        is_resell=True
    ).select_related('user').order_by('-created_at')[:10]
    
    active_links = ResellLink.objects.filter(
        reseller=request.user,
        is_active=True
    ).select_related('product').order_by('-created_at')[:10]
    
    # Calculate pending earnings
    pending_earnings = ResellerEarning.objects.filter(
        reseller=request.user,
        status='PENDING'
    ).aggregate(total=Sum('margin_amount'))['total'] or Decimal('0.00')
    
    context = {
        'profile': profile,
        'recent_orders': recent_orders,
        'active_links': active_links,
        'pending_earnings': pending_earnings,
    }
    
    return render(request, 'reseller/dashboard.html', context)


@login_required
def reseller_links_page(request):
    """
    Reseller links management page
    GET /reseller/links/
    
    Displays all resell links with management options
    """
    try:
        profile = request.user.reseller_profile
        
        if not profile.is_reseller_enabled:
            messages.warning(request, 'You do not have reseller permissions.')
            return redirect('home')
        
    except ResellerProfile.DoesNotExist:
        messages.warning(request, 'You do not have a reseller profile.')
        return redirect('home')
    
    # Get all links
    links = ResellLink.objects.filter(
        reseller=request.user
    ).select_related('product').order_by('-created_at')
    
    # Get products for creating new links
    products = Product.objects.filter(is_active=True).order_by('name')
    
    context = {
        'links': links,
        'products': products,
    }
    
    return render(request, 'reseller/links.html', context)


@login_required
def earnings_history(request):
    """
    Earnings history page
    GET /reseller/earnings/
    
    Displays all earnings with status and payout information
    """
    try:
        profile = request.user.reseller_profile
        
        if not profile.is_reseller_enabled:
            messages.warning(request, 'You do not have reseller permissions.')
            return redirect('home')
        
    except ResellerProfile.DoesNotExist:
        messages.warning(request, 'You do not have a reseller profile.')
        return redirect('home')
    
    # Get earnings with filters
    status_filter = request.GET.get('status', '')
    
    earnings = ResellerEarning.objects.filter(
        reseller=request.user
    ).select_related('order', 'resell_link', 'payout_transaction')
    
    if status_filter:
        earnings = earnings.filter(status=status_filter)
    
    earnings = earnings.order_by('-created_at')
    
    context = {
        'earnings': earnings,
        'status_filter': status_filter,
    }
    
    return render(request, 'reseller/earnings.html', context)


# ============================================
# PAYOUT MANAGEMENT
# ============================================

@login_required
def payout_request_page(request):
    """
    Payout request page
    GET /reseller/payout/
    
    Displays payout request form and history
    """
    try:
        profile = request.user.reseller_profile
        
        if not profile.is_reseller_enabled:
            messages.warning(request, 'You do not have reseller permissions.')
            return redirect('home')
        
    except ResellerProfile.DoesNotExist:
        messages.warning(request, 'You do not have a reseller profile.')
        return redirect('home')
    
    # Get payout history
    payouts = PayoutTransaction.objects.filter(
        reseller=request.user
    ).order_by('-initiated_at')[:20]
    
    context = {
        'profile': profile,
        'payouts': payouts,
    }
    
    return render(request, 'reseller/payout.html', context)


@login_required
@require_POST
def request_payout(request):
    """
    Request a payout
    POST /api/resell/request-payout/
    
    Required POST parameters:
    - amount: Payout amount
    - payout_method: Payment method (BANK_TRANSFER, UPI, WALLET)
    - bank_account_number: (if BANK_TRANSFER)
    - bank_ifsc_code: (if BANK_TRANSFER)
    - upi_id: (if UPI)
    
    Returns JSON response
    """
    try:
        amount = request.POST.get('amount')
        payout_method = request.POST.get('payout_method')
        
        if not amount or not payout_method:
            return JsonResponse({
                'success': False,
                'error': 'Amount and payout method are required.'
            }, status=400)
        
        try:
            amount = Decimal(amount)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid amount.'
            }, status=400)
        
        # Prepare payment details
        payment_details = {}
        if payout_method == 'BANK_TRANSFER':
            payment_details['bank_account_number'] = request.POST.get('bank_account_number', '')
            payment_details['bank_ifsc_code'] = request.POST.get('bank_ifsc_code', '')
        elif payout_method == 'UPI':
            payment_details['upi_id'] = request.POST.get('upi_id', '')
        
        # Process payout
        payout = ResellerPaymentManager.process_payout(
            user_id=request.user.id,
            amount=amount,
            payout_method=payout_method,
            payment_details=payment_details
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Payout request submitted successfully.',
            'payout': {
                'id': payout.id,
                'amount': str(payout.amount),
                'status': payout.status,
                'payout_method': payout.payout_method,
                'initiated_at': payout.initiated_at.isoformat(),
            }
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while processing the payout request.'
        }, status=500)


@login_required
def reseller_profile_page(request):
    """
    Reseller profile management page
    GET /reseller/profile/
    
    Displays and allows editing of reseller profile
    """
    try:
        profile = request.user.reseller_profile
    except ResellerProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = ResellerProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Update profile
        profile.business_name = request.POST.get('business_name', '')
        profile.bank_account_name = request.POST.get('bank_account_name', '')
        profile.bank_account_number = request.POST.get('bank_account_number', '')
        profile.bank_ifsc_code = request.POST.get('bank_ifsc_code', '')
        profile.upi_id = request.POST.get('upi_id', '')
        profile.pan_number = request.POST.get('pan_number', '')
        
        try:
            profile.save()
            messages.success(request, 'Profile updated successfully.')
        except ValidationError as e:
            messages.error(request, str(e))
        
        return redirect('reseller_profile')
    
    context = {
        'profile': profile,
    }
    
    return render(request, 'reseller/profile.html', context)
