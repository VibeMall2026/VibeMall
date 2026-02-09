/* ===================================
    CUSTOM JAVASCRIPT FOR VIBEMALL
    =================================== */

(function($) {
    'use strict';

    // ===== 1. INITIALIZE SEPARATE SWIPER SLIDERS =====
    function initProductSliders() {
        const sliderConfig = {
            slidesPerView: 1,
            spaceBetween: 20,
            loop: true,
            observer: true,
            observeParents: true,
            autoplay: {
                delay: 6000,
                disableOnInteraction: false,
            },
            navigation: {
                nextEl: '.bs-button-next',
                prevEl: '.bs-button-prev',
            },
            breakpoints: {
                550: {
                    slidesPerView: 2,
                },
                768: {
                    slidesPerView: 3,
                },
                1200: {
                    slidesPerView: 4,
                },
                1400: {
                    slidesPerView: 5,
                }
            }
        };

        // Initialize each slider with its own instance
        if ($('.product-slider-deals').length > 0) {
            new Swiper('.product-slider-deals', {
                ...sliderConfig,
                navigation: {
                    nextEl: '.product-slider-deals').parent().find('.bs-button-next')[0],
                    prevEl: $('.product-slider-deals').parent().find('.bs-button-prev')[0]
                }
            });
        }

        if ($('.product-slider-selling').length > 0) {
            new Swiper('.product-slider-selling', {
                ...sliderConfig,
                navigation: {
                    nextEl: $('.product-slider-selling').parent().find('.bs-button-next')[0],
                    prevEl: $('.product-slider-selling').parent().find('.bs-button-prev')[0],
                }
            });
        }

        if ($('.product-slider-featured').length > 0) {
            new Swiper('.product-slider-featured', {
                ...sliderConfig,
                navigation: {
                    nextEl: $('.product-slider-featured').parent().find('.bs-button-next')[0],
                    prevEl: $('.product-slider-featured').parent().find('.bs-button-prev')[0],
                }
            });
        }

        if ($('.product-slider-recommended').length > 0) {
            new Swiper('.product-slider-recommended', {
                ...sliderConfig,
                navigation: {
                    nextEl: $('.product-slider-recommended').parent().find('.bs-button-next')[0],
                    prevEl: $('.product-slider-recommended').parent().find('.bs-button-prev')[0],
                }
            });
        }
    }

    // ===== 2. DYNAMIC WISHLIST HANDLER =====
    window.handleWishlistClick = function(productId, element) {
        const isAuthenticated = typeof userAuthenticated !== 'undefined' && userAuthenticated;
        
        if (!isAuthenticated) {
            window.location.href = '/login/?next=' + window.location.pathname;
            return;
        }

        const $btn = $(element);
        const $icon = $btn.find('i');
        const isFilled = $btn.hasClass('wishlist-filled');

        if (isFilled) {
            // Remove from wishlist
            removeFromWishlist(productId, $btn, $icon);
        } else {
            // Add to wishlist
            addToWishlist(productId, $btn, $icon);
        }
    };

    function addToWishlist(productId, $btn, $icon) {
        $.ajax({
            url: '/wishlist/add/' + productId + '/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(data) {
                if (data.success) {
                    // Update UI to filled state
                    $btn.addClass('wishlist-filled');
                    $icon.removeClass('fal').addClass('fas');
                    
                    // Show success message
                    showNotification('Product added to wishlist!', 'success');
                } else {
                    showNotification(data.message || 'Already in wishlist', 'warning');
                }
            },
            error: function() {
                showNotification('Error adding to wishlist', 'error');
            }
        });
    }

    function removeFromWishlist(productId, $btn, $icon) {
        // Find wishlist item ID (you may need to store this in data attribute)
        $.ajax({
            url: '/api/wishlist/remove/' + productId + '/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(data) {
                if (data.success) {
                    // Update UI to unfilled state
                    $btn.removeClass('wishlist-filled');
                    $icon.removeClass('fas').addClass('fal');
                    
                    // Show success message
                    showNotification('Removed from wishlist', 'success');
                }
            },
            error: function() {
                showNotification('Error removing from wishlist', 'error');
            }
        });
    }

    // ===== 3. NOTIFICATION HELPER =====
    function showNotification(message, type) {
        const bgColor = type === 'success' ? '#28a745' : type === 'warning' ? '#ffc107' : '#dc3545';
        const notification = $('<div>')
            .css({
                position: 'fixed',
                top: '20px',
                right: '20px',
                backgroundColor: bgColor,
                color: 'white',
                padding: '15px 25px',
                borderRadius: '5px',
                boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                zIndex: 99999,
                fontSize: '14px',
                fontWeight: '500'
            })
            .text(message)
            .appendTo('body');

        setTimeout(function() {
            notification.fadeOut(300, function() {
                $(this).remove();
            });
        }, 3000);
    }

    // ===== 4. CSRF TOKEN HELPER =====
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // ===== 5. INITIALIZE ON DOCUMENT READY =====
    $(document).ready(function() {
        // Initialize sliders after a small delay to ensure DOM is ready
        setTimeout(initProductSliders, 100);

        // Mark wishlist items as filled on page load
        if (typeof wishlistProductIds !== 'undefined') {
            wishlistProductIds.forEach(function(productId) {
                $('.wishlist-btn-' + productId).addClass('wishlist-filled');
                $('.wishlist-btn-' + productId + ' i').removeClass('fal').addClass('fas');
            });
        }
    });

})(jQuery);
