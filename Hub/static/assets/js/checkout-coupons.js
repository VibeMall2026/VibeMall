(function () {
    function parseAmount(value) {
        const cleaned = String(value || '').replace(/[^\d.-]/g, '');
        const amount = Number.parseFloat(cleaned);
        return Number.isFinite(amount) ? amount : 0;
    }

    function getCsrfToken() {
        const tokenField = document.querySelector('[name=csrfmiddlewaretoken]');
        return (tokenField && tokenField.value) ? tokenField.value : '';
    }

    function getCartTotal() {
        const subtotalText = document.getElementById('cart_subtotal_amount')?.textContent;
        const finalText = document.getElementById('final_total_display')?.textContent;
        return parseAmount(subtotalText || finalText || '0');
    }

    function showCouponMessage(message, type) {
        const messageBox = document.getElementById('couponMessage');
        if (!messageBox) {
            return;
        }

        messageBox.innerHTML = `<div class="alert vm-inline-alert alert-${type} alert-dismissible fade show"><small>${message}</small><button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
        window.setTimeout(function () {
            messageBox.innerHTML = '';
        }, 5000);
    }

    function setCouponPanelVisible(visible) {
        const couponsPanel = document.getElementById('availableCouponsPanel');
        const viewButton = document.getElementById('viewAvailableCoupons');
        if (couponsPanel) {
            couponsPanel.style.display = visible ? 'block' : 'none';
            couponsPanel.dataset.loaded = visible ? 'true' : 'false';
        }
        if (viewButton) {
            viewButton.textContent = visible ? 'Hide Coupons' : 'Available Coupons';
        }
    }

    function syncCouponSummary(discountAmount, couponCode, couponId) {
        const couponDisplay = document.getElementById('appliedCouponDisplay');
        const couponCodeDisplay = document.getElementById('appliedCouponCode');
        const couponAmountDisplay = document.getElementById('appliedCouponAmount');
        const couponIdInput = document.getElementById('appliedCouponId');
        const couponDiscountRow = document.getElementById('coupon_discount_row');
        const couponDiscountAmount = document.getElementById('coupon_discount_amount');

        if (couponDisplay) {
            couponDisplay.style.display = 'block';
        }
        if (couponAmountDisplay) {
            couponAmountDisplay.textContent = Number(discountAmount || 0).toFixed(2);
        }
        if (couponCodeDisplay && couponCode) {
            couponCodeDisplay.textContent = couponCode;
        }
        if (couponIdInput) {
            couponIdInput.value = couponId || '';
        }
        if (couponDiscountRow && couponDiscountAmount) {
            couponDiscountRow.style.display = 'table-row';
            couponDiscountAmount.textContent = `-₹${Number(discountAmount || 0).toFixed(2)}`;
        }
    }

    function clearCouponSummary() {
        const couponInput = document.getElementById('couponCode');
        const couponDisplay = document.getElementById('appliedCouponDisplay');
        const couponCodeDisplay = document.getElementById('appliedCouponCode');
        const couponAmountDisplay = document.getElementById('appliedCouponAmount');
        const couponIdInput = document.getElementById('appliedCouponId');
        const couponDiscountRow = document.getElementById('coupon_discount_row');
        const couponDiscountAmount = document.getElementById('coupon_discount_amount');

        if (couponInput) {
            couponInput.value = '';
        }
        if (couponDisplay) {
            couponDisplay.style.display = 'none';
        }
        if (couponCodeDisplay) {
            couponCodeDisplay.textContent = '';
        }
        if (couponAmountDisplay) {
            couponAmountDisplay.textContent = '0.00';
        }
        if (couponIdInput) {
            couponIdInput.value = '';
        }
        if (couponDiscountRow) {
            couponDiscountRow.style.display = 'none';
        }
        if (couponDiscountAmount) {
            couponDiscountAmount.textContent = '-₹0.00';
        }
    }

    function renderCoupons(coupons) {
        const couponsList = document.getElementById('availableCouponsList');
        const couponsStatus = document.getElementById('availableCouponsStatus');
        if (!couponsList) {
            return;
        }

        if (couponsStatus) {
            couponsStatus.textContent = `${coupons.length} coupon${coupons.length === 1 ? '' : 's'} found`;
        }

        couponsList.innerHTML = coupons.map(function (coupon) {
            const usedClass = coupon.used ? ' is-used' : '';
            const buttonHtml = coupon.used
                ? '<button type="button" disabled>Used</button>'
                : `<button type="button" class="vm-checkout-coupon-apply" data-code="${coupon.code}">Apply</button>`;
            const description = coupon.description || coupon.title || 'Offer available on eligible orders.';
            const discount = coupon.discount || 'Offer';
            return `
                <div class="vm-checkout-d-coupon-card${usedClass}" data-code="${coupon.code}" data-used="${coupon.used ? '1' : '0'}" role="button" tabindex="0">
                    <div>
                        <h5>${coupon.code}</h5>
                        <p>${description}</p>
                        <div class="vm-checkout-d-coupon-meta">
                            <span>${discount}</span>
                            ${coupon.title ? `<span>${coupon.title}</span>` : ''}
                        </div>
                    </div>
                    <div>${buttonHtml}</div>
                </div>
            `;
        }).join('');

        couponsList.querySelectorAll('.vm-checkout-coupon-apply').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                applyCouponCode(this.getAttribute('data-code'));
            });
        });

        couponsList.querySelectorAll('.vm-checkout-d-coupon-card[data-code]').forEach(function (card) {
            card.addEventListener('click', function (event) {
                if (event.target.closest('button') || card.dataset.used === '1') {
                    return;
                }
                applyCouponCode(card.dataset.code);
            });
        });
    }

    function applyCouponCode(code) {
        if (!code) {
            showCouponMessage('Please enter a coupon code', 'warning');
            return;
        }

        fetch('/api/validate-coupon/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                code: String(code).trim().toUpperCase(),
                cart_total: getCartTotal()
            })
        })
        .then(function (response) {
            return response.json().then(function (data) {
                return { response: response, data: data };
            });
        })
        .then(function (payload) {
            if (!payload.response.ok || !payload.data.valid) {
                throw new Error(payload.data.message || 'Unable to apply coupon.');
            }

            const couponInput = document.getElementById('couponCode');
            const couponCodeDisplay = document.getElementById('appliedCouponCode');

            if (couponInput) {
                couponInput.value = payload.data.code;
            }
            if (couponCodeDisplay) {
                couponCodeDisplay.textContent = payload.data.code;
            }

            syncCouponSummary(payload.data.discount_amount, payload.data.code, payload.data.coupon_id);
            setCouponPanelVisible(false);
            showCouponMessage(payload.data.message, 'success');
        })
        .catch(function (error) {
            showCouponMessage((error && error.message) || 'Error applying coupon', 'danger');
        });
    }

    function loadCoupons() {
        const couponsPanel = document.getElementById('availableCouponsPanel');
        const couponsStatus = document.getElementById('availableCouponsStatus');
        const couponsList = document.getElementById('availableCouponsList');

        if (!couponsPanel || !couponsList) {
            return;
        }

        couponsPanel.style.display = 'block';
        couponsPanel.dataset.loaded = 'false';
        if (couponsStatus) {
            couponsStatus.textContent = 'Loading coupons...';
        }
        couponsList.innerHTML = '';
        setCouponPanelVisible(true);

        fetch(`/api/available-coupons/?cart_total=${encodeURIComponent(getCartTotal())}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(function (response) {
            return response.json();
        })
        .then(function (data) {
            if (data.success && Array.isArray(data.coupons) && data.coupons.length > 0) {
                couponsPanel.dataset.loaded = 'true';
                renderCoupons(data.coupons);
                return;
            }

            couponsPanel.dataset.loaded = 'true';
            if (couponsStatus) {
                couponsStatus.textContent = 'No coupons available right now';
            }
            couponsList.innerHTML = '<div class="vm-checkout-d-coupon-card"><div><h5>No coupons available</h5><p>Please try again later.</p></div></div>';
        })
        .catch(function () {
            couponsPanel.dataset.loaded = 'true';
            if (couponsStatus) {
                couponsStatus.textContent = 'Unable to load coupons';
            }
            couponsList.innerHTML = '<div class="vm-checkout-d-coupon-card"><div><h5>Could not load coupons</h5><p>Please try again in a moment.</p></div></div>';
            showCouponMessage('Error loading coupons', 'danger');
        });
    }

    function removeCoupon() {
        clearCouponSummary();
        setCouponPanelVisible(false);
        showCouponMessage('Coupon removed', 'info');
    }

    function interceptCouponButtonClicks() {
        const viewButton = document.getElementById('viewAvailableCoupons');
        const applyButton = document.getElementById('applyCoupon');
        const removeButton = document.getElementById('removeCoupon');
        const couponInput = document.getElementById('couponCode');

        if (viewButton) {
            viewButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                loadCoupons();
            }, true);
        }

        if (applyButton) {
            applyButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                const code = (couponInput && couponInput.value || '').trim().toUpperCase();
                if (!code) {
                    showCouponMessage('Please enter a coupon code', 'warning');
                    return;
                }
                applyCouponCode(code);
            }, true);
        }

        if (removeButton) {
            removeButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                removeCoupon();
            }, true);
        }

        if (couponInput) {
            couponInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    applyCouponCode(couponInput.value);
                }
            });
        }

        window.VMCheckoutShowAvailableCoupons = loadCoupons;
        window.VMCheckoutApplyCouponCode = function () {
            applyCouponCode(couponInput ? couponInput.value : '');
        };
        window.VMCheckoutRemoveCoupon = removeCoupon;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', interceptCouponButtonClicks);
    } else {
        interceptCouponButtonClicks();
    }
})();
