(function () {
    if (window.__vmCheckoutCouponsInitialized) {
        return;
    }
    window.__vmCheckoutCouponsInitialized = true;

    function parseAmount(value) {
        const cleaned = String(value || '').replace(/[^\d.-]/g, '');
        const amount = Number.parseFloat(cleaned);
        return Number.isFinite(amount) ? amount : 0;
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function getCsrfToken() {
        const tokenField = document.querySelector('[name=csrfmiddlewaretoken]');
        return tokenField && tokenField.value ? tokenField.value : '';
    }

    function getEls() {
        return {
            couponInput: document.getElementById('couponCode'),
            applyButton: document.getElementById('applyCoupon'),
            viewButton: document.getElementById('viewAvailableCoupons'),
            removeButton: document.getElementById('removeCoupon'),
            messageBox: document.getElementById('couponMessage'),
            panel: document.getElementById('availableCouponsPanel'),
            list: document.getElementById('availableCouponsList'),
            status: document.getElementById('availableCouponsStatus'),
            discountRow: document.getElementById('coupon_discount_row'),
            discountAmount: document.getElementById('coupon_discount_amount'),
            appliedDisplay: document.getElementById('appliedCouponDisplay'),
            appliedCode: document.getElementById('appliedCouponCode'),
            appliedAmount: document.getElementById('appliedCouponAmount'),
            appliedId: document.getElementById('appliedCouponId'),
            subtotalAmount: document.getElementById('cart_subtotal_amount'),
            finalTotalAmount: document.getElementById('final_total_display')
        };
    }

    function getCartTotal() {
        const els = getEls();
        const subtotalText = els.subtotalAmount && els.subtotalAmount.textContent;
        const finalText = els.finalTotalAmount && els.finalTotalAmount.textContent;
        return parseAmount(subtotalText || finalText || '0');
    }

    function showMessage(message, type) {
        const els = getEls();
        if (!els.messageBox) {
            return;
        }

        const alertType = ['success', 'danger', 'warning', 'info'].includes(type) ? type : 'info';
        els.messageBox.innerHTML = `
            <div class="alert vm-inline-alert alert-${alertType} alert-dismissible fade show" role="alert">
                <small>${escapeHtml(message)}</small>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;

        window.clearTimeout(window.__vmCheckoutCouponMessageTimer);
        window.__vmCheckoutCouponMessageTimer = window.setTimeout(function () {
            if (els.messageBox) {
                els.messageBox.innerHTML = '';
            }
        }, 5000);
    }

    function setPanelVisible(visible) {
        const els = getEls();
        if (els.panel) {
            els.panel.style.display = visible ? 'block' : 'none';
        }
        if (els.viewButton) {
            els.viewButton.textContent = visible ? 'Hide Coupons' : 'Available Coupons';
        }
    }

    function syncAppliedState(discountAmount, couponCode, couponId) {
        const els = getEls();

        if (els.appliedDisplay) {
            els.appliedDisplay.style.display = 'block';
        }
        if (els.appliedCode) {
            els.appliedCode.textContent = couponCode || '';
        }
        if (els.appliedAmount) {
            els.appliedAmount.textContent = Number(discountAmount || 0).toFixed(2);
        }
        if (els.appliedId) {
            els.appliedId.value = couponId || '';
        }
        if (els.discountRow) {
            els.discountRow.style.display = 'table-row';
        }
        if (els.discountAmount) {
            els.discountAmount.textContent = `-₹${Number(discountAmount || 0).toFixed(2)}`;
        }
    }

    function clearAppliedState() {
        const els = getEls();

        if (els.couponInput) {
            els.couponInput.value = '';
        }
        if (els.appliedDisplay) {
            els.appliedDisplay.style.display = 'none';
        }
        if (els.appliedCode) {
            els.appliedCode.textContent = '';
        }
        if (els.appliedAmount) {
            els.appliedAmount.textContent = '0.00';
        }
        if (els.appliedId) {
            els.appliedId.value = '';
        }
        if (els.discountRow) {
            els.discountRow.style.display = 'none';
        }
        if (els.discountAmount) {
            els.discountAmount.textContent = '-₹0.00';
        }
    }

    function buildCouponCard(coupon) {
        const used = !!coupon.used;
        const title = coupon.title || coupon.description || 'Offer available on eligible orders.';
        const description = coupon.description || coupon.title || 'Offer available on eligible orders.';
        const discount = coupon.discount || 'Offer';
        const code = coupon.code || '';

        return `
            <div class="vm-checkout-d-coupon-card${used ? ' is-used' : ''}" data-code="${escapeHtml(code)}" data-used="${used ? '1' : '0'}" role="button" tabindex="0">
                <div>
                    <h5>${escapeHtml(code)}</h5>
                    <p>${escapeHtml(description)}</p>
                    <div class="vm-checkout-d-coupon-meta">
                        <span>${escapeHtml(discount)}</span>
                        ${title ? `<span>${escapeHtml(title)}</span>` : ''}
                    </div>
                </div>
                <div>
                    ${
                        used
                            ? '<button type="button" disabled>Used</button>'
                            : `<button type="button" class="vm-checkout-coupon-apply" data-code="${escapeHtml(code)}">Apply</button>`
                    }
                </div>
            </div>
        `;
    }

    function renderCoupons(coupons) {
        const els = getEls();
        if (!els.list) {
            return;
        }

        const normalizedCoupons = Array.isArray(coupons) ? coupons : [];
        if (els.status) {
            els.status.textContent = `${normalizedCoupons.length} coupon${normalizedCoupons.length === 1 ? '' : 's'} found`;
        }

        els.list.innerHTML = normalizedCoupons.length
            ? normalizedCoupons.map(buildCouponCard).join('')
            : '<div class="vm-checkout-d-coupon-card"><div><h5>No coupons available</h5><p>Please try again later.</p></div></div>';

        els.list.querySelectorAll('.vm-checkout-coupon-apply').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                applyCouponCode(this.getAttribute('data-code'));
            });
        });

        els.list.querySelectorAll('.vm-checkout-d-coupon-card[data-code]').forEach(function (card) {
            card.addEventListener('click', function (event) {
                if (event.target.closest('button') || card.dataset.used === '1') {
                    return;
                }
                applyCouponCode(card.dataset.code);
            });
            card.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    if (card.dataset.used !== '1') {
                        applyCouponCode(card.dataset.code);
                    }
                }
            });
        });
    }

    function normalizeCouponValidationResponse(payload) {
        if (!payload) {
            return { valid: false, message: 'Unable to validate coupon.' };
        }

        if (payload.data && typeof payload.data === 'object') {
            return payload.data;
        }

        return payload;
    }

    function applyCouponCode(rawCode) {
        const code = String(rawCode || '').trim().toUpperCase();
        if (!code) {
            showMessage('Please enter a coupon code.', 'warning');
            return;
        }

        fetch('/api/validate-coupon/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                code: code,
                cart_total: getCartTotal()
            })
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { response: response, data: data };
                });
            })
            .then(function (payload) {
                const result = normalizeCouponValidationResponse(payload);
                if (!payload.response.ok || !result.valid) {
                    throw new Error(result.message || 'Unable to apply coupon.');
                }

                const els = getEls();
                if (els.couponInput) {
                    els.couponInput.value = result.code || code;
                }

                syncAppliedState(result.discount_amount, result.code || code, result.coupon_id);
                setPanelVisible(false);
                showMessage(result.message || 'Coupon applied.', 'success');
            })
            .catch(function (error) {
                showMessage((error && error.message) || 'Error applying coupon.', 'danger');
            });
    }

    function loadCoupons() {
        const els = getEls();
        if (!els.panel || !els.list) {
            return;
        }

        setPanelVisible(true);
        els.panel.dataset.loaded = 'false';
        els.list.innerHTML = '';
        if (els.status) {
            els.status.textContent = 'Loading coupons...';
        }

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
                const coupons = Array.isArray(data && data.coupons) ? data.coupons : [];
                els.panel.dataset.loaded = 'true';
                renderCoupons(coupons);

                if (!coupons.length) {
                    if (els.status) {
                        els.status.textContent = data && data.message ? data.message : 'No coupons available right now';
                    }
                    showMessage(data && data.message ? data.message : 'No coupons available right now.', 'info');
                }
            })
            .catch(function (error) {
                els.panel.dataset.loaded = 'true';
                if (els.status) {
                    els.status.textContent = 'Unable to load coupons';
                }
                els.list.innerHTML = '<div class="vm-checkout-d-coupon-card"><div><h5>Could not load coupons</h5><p>Please try again in a moment.</p></div></div>';
                showMessage((error && error.message) || 'Error loading coupons.', 'danger');
            });
    }

    function removeCoupon() {
        clearAppliedState();
        setPanelVisible(false);
        showMessage('Coupon removed.', 'info');
    }

    function bindEvents() {
        const els = getEls();

        if (els.viewButton) {
            els.viewButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();

                const panelVisible = els.panel && els.panel.style.display !== 'none';
                if (panelVisible && els.panel.dataset.loaded === 'true') {
                    setPanelVisible(false);
                    return;
                }

                loadCoupons();
            }, true);
        }

        if (els.applyButton) {
            els.applyButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                applyCouponCode(els.couponInput ? els.couponInput.value : '');
            }, true);
        }

        if (els.removeButton) {
            els.removeButton.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                removeCoupon();
            }, true);
        }

        if (els.couponInput) {
            els.couponInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    applyCouponCode(els.couponInput.value);
                }
            });
        }

        window.VMCheckoutShowAvailableCoupons = loadCoupons;
        window.VMCheckoutApplyCouponCode = function () {
            applyCouponCode(els.couponInput ? els.couponInput.value : '');
        };
        window.VMCheckoutRemoveCoupon = removeCoupon;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindEvents);
    } else {
        bindEvents();
    }
})();
