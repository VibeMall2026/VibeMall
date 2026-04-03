/**
 * Tablet Checkout Form Handler
 * Manages form logic, calculations, validation, and API interactions
 * for tablet view checkout (768px - 1200px)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Exit if not on tablet view
    if (window.matchMedia('(min-width: 1200px) or (max-width: 767.98px)').matches) {
        return;
    }

    // ========================================
    // FORM ELEMENT REFERENCES
    // ========================================
    
    const form = document.getElementById('checkoutTabletForm');
    if (!form) return;

    const fullNameField = document.getElementById('tabletFullNameField');
    const firstNameField = document.getElementById('tabletFirstNameField');
    const lastNameField = document.getElementById('tabletLastNameField');
    const emailField = document.getElementById('tabletEmailField');
    const addressField = document.getElementById('tabletAddressField');
    const cityField = document.getElementById('tabletCityField');
    const postcodeField = document.getElementById('tabletPostcodeField');
    const stateField = document.getElementById('tabletStateField');
    const countryField = document.getElementById('tabletCountryField');
    const phoneField = document.getElementById('tabletPhoneField');
    const customerNotesField = document.getElementById('tabletCustomerNotes');
    const useDefaultCheckbox = document.getElementById('tabletUseDefaultAddress');
    const setDefaultCheckbox = document.getElementById('tabletSetDefaultAddress');

    const paymentMethods = document.querySelectorAll('#tabletPaymentMethods input[type="radio"]');
    const couponCodeInput = document.getElementById('tabletCouponCode');
    const applyCouponBtn = document.getElementById('tabletApplyCoupon');
    const viewCouponsBtn = document.getElementById('tabletViewCoupons');
    const removeCouponBtn = document.getElementById('tabletRemoveCoupon');
    const couponMessage = document.getElementById('tabletCouponMessage');
    const couponActionsDiv = document.getElementById('tabletCouponActions');
    const appliedCouponIdInput = document.getElementById('tabletAppliedCouponId');

    const redeemPointsCheckbox = document.getElementById('tabletRedeemPoints');
    const pointsBox = document.getElementById('tabletPointsBox');
    const pointsToRedeemInput = document.getElementById('tabletPointsToRedeem');

    const submitBtn = document.getElementById('tabletPlaceOrderButton');
    const reviewStep = document.getElementById('tabletReviewStep');

    // Display elements
    const subtotalDisplay = document.getElementById('tabletSubtotalAmount');
    const taxDisplay = document.getElementById('tabletTaxAmount');
    const shippingDisplay = document.getElementById('tabletShippingCost');
    const couponDiscountRow = document.getElementById('tabletCouponDiscountRow');
    const couponDiscountDisplay = document.getElementById('tabletCouponDiscountAmount');
    const pointsDiscountRow = document.getElementById('tabletPointsDiscountRow');
    const pointsDiscountDisplay = document.getElementById('tabletPointsDiscountAmount');
    const finalTotalDisplay = document.getElementById('tabletFinalTotalDisplay');
    const fixedTotalDisplay = document.getElementById('tabletFixedTotalDisplay');

    const couponModal = document.getElementById('tabletCouponModal');
    const closeCouponModalBtn = document.getElementById('tabletCloseCouponModal');
    const cancelCouponBtn = document.getElementById('tabletCancelCoupon');
    const applyCouponFromModalBtn = document.getElementById('tabletApplyCouponFromModal');

    // ========================================
    // STATE MANAGEMENT
    // ========================================

    let appliedCoupon = appliedCouponIdInput.value ? true : false;
    let selectedCouponCode = '';
    let cartSubtotal = parseFloat(subtotalDisplay.textContent.replace(/[₹,]/g, '')) || 0;
    let currentTaxRate = 0.05;
    let baseShippingCost = 50;
    let freeShippingThreshold = 500;

    // ========================================
    // INITIALIZATION
    // ========================================

    function initialize() {
        syncSplitName();
        updateReviewStepVisibility();
        updateTotals();
        attachEventListeners();
    }

    // ========================================
    // NAME FIELD SYNC
    // ========================================

    function syncSplitName() {
        if (!fullNameField) return;

        function splitName() {
            const fullName = fullNameField.value.trim();
            const parts = fullName.split(' ');
            const firstName = parts[0] || '';
            const lastName = parts.slice(1).join(' ') || '';

            firstNameField.value = firstName;
            lastNameField.value = lastName;
        }

        splitName();
        fullNameField.addEventListener('input', splitName);
    }

    // ========================================
    // PINCODE & CITY VALIDATION
    // ========================================

    async function fetchCityFromPincode(pincode) {
        if (!pincode || pincode.length !== 6 || isNaN(pincode)) {
            return null;
        }

        if (countryField.value !== 'India') {
            return null;
        }

        try {
            const response = await fetch(`https://api.postalpincode.in/pincode/${pincode}`);
            const data = await response.json();

            if (data[0].Status === 'Success' && data[0].PostOffice.length > 0) {
                const postOffice = data[0].PostOffice[0];
                return {
                    city: postOffice.District,
                    state: postOffice.State,
                    country: 'India'
                };
            }
        } catch (error) {
            console.error('Pincode lookup error:', error);
        }

        return null;
    }

    function isIndia() {
        return countryField.value === 'India';
    }

    if (postcodeField) {
        postcodeField.addEventListener('blur', async function() {
            if (!isIndia()) {
                document.getElementById('tabletPincodeError').classList.remove('is-visible');
                return;
            }

            const pincode = this.value.trim();
            if (pincode.length !== 6 || isNaN(pincode)) {
                document.getElementById('tabletPincodeError').textContent = 'Please enter a valid 6-digit PIN code';
                document.getElementById('tabletPincodeError').classList.add('is-visible');
                document.getElementById('tabletPincodeValid').value = '0';
                return;
            }

            const cityData = await fetchCityFromPincode(pincode);
            if (cityData) {
                cityField.value = cityData.city;
                stateField.value = cityData.state;
                document.getElementById('tabletPincodeError').classList.remove('is-visible');
                document.getElementById('tabletPincodeValid').value = '1';
            } else {
                document.getElementById('tabletPincodeError').textContent = 'Invalid PIN code for India';
                document.getElementById('tabletPincodeError').classList.add('is-visible');
                document.getElementById('tabletPincodeValid').value = '0';
            }
        });
    }

    // ========================================
    // DEFAULT ADDRESS AUTOFILL
    // ========================================

    if (useDefaultCheckbox) {
        useDefaultCheckbox.addEventListener('change', function() {
            if (this.checked) {
                fullNameField.value = this.dataset.fullName || '';
                phoneField.value = this.dataset.phone || '';
                addressField.value = this.dataset.address1 || '';
                cityField.value = this.dataset.city || '';
                stateField.value = this.dataset.state || '';
                postcodeField.value = this.dataset.pincode || '';
                countryField.value = this.dataset.country || 'India';
                syncSplitName();
            }
        });
    }

    // ========================================
    // PAYMENT METHOD SELECTION
    // ========================================

    function updateReviewStepVisibility() {
        const selectedPayment = form.querySelector('input[name="payment_method"]:checked');
        if (reviewStep) {
            if (selectedPayment && selectedPayment.value === 'RAZORPAY') {
                reviewStep.classList.remove('is-hidden');
            } else {
                reviewStep.classList.add('is-hidden');
            }
        }
    }

    paymentMethods.forEach(method => {
        method.addEventListener('change', function() {
            updatePaymentLabels();
            updateReviewStepVisibility();
        });
    });

    function updatePaymentLabels() {
        document.querySelectorAll('#tabletPaymentMethods .vm-checkout-tablet-radio').forEach(label => {
            label.classList.remove('is-selected');
        });

        document.querySelectorAll('#tabletPaymentMethods input[type="radio"]:checked').forEach(checked => {
            checked.closest('.vm-checkout-tablet-radio').classList.add('is-selected');
        });
    }

    updatePaymentLabels();

    // ========================================
    // TOTALS CALCULATION
    // ========================================

    function getSubtotal() {
        return cartSubtotal;
    }

    function calculateTax(subtotal) {
        return subtotal * currentTaxRate;
    }

    function calculateShippingCost(subtotal) {
        return subtotal > freeShippingThreshold ? 0 : baseShippingCost;
    }

    function calculateCouponDiscount() {
        if (!appliedCoupon) return 0;
        // This will be set when coupon is applied via API
        const couponAmount = parseFloat(couponDiscountDisplay.textContent.replace(/[₹,\-]/g, '')) || 0;
        return couponAmount;
    }

    function calculatePointsDiscount() {
        if (!pointsToRedeemInput || !redeemPointsCheckbox || !redeemPointsCheckbox.checked) return 0;
        const points = parseInt(pointsToRedeemInput.value) || 0;
        return points * 0.03; // 1 point = ₹0.03
    }

    function updateTotals() {
        const subtotal = getSubtotal();
        const tax = calculateTax(subtotal);
        const shipping = calculateShippingCost(subtotal);
        const couponDiscount = calculateCouponDiscount();
        const pointsDiscount = calculatePointsDiscount();

        const finalTotal = subtotal + tax + shipping - couponDiscount - pointsDiscount;

        subtotalDisplay.textContent = '₹' + subtotal.toFixed(2);
        taxDisplay.textContent = '₹' + tax.toFixed(2);
        shippingDisplay.textContent = shipping > 0 ? '₹' + shipping.toFixed(2) : 'FREE';

        if (couponDiscount > 0) {
            couponDiscountRow.classList.remove('is-hidden');
            couponDiscountDisplay.textContent = '-₹' + couponDiscount.toFixed(2);
        } else {
            couponDiscountRow.classList.add('is-hidden');
        }

        finalTotalDisplay.textContent = '₹' + finalTotal.toFixed(2);
        fixedTotalDisplay.textContent = '₹' + finalTotal.toFixed(2);
    }

    // ========================================
    // LOYALTY POINTS
    // ========================================

    if (redeemPointsCheckbox) {
        redeemPointsCheckbox.addEventListener('change', function() {
            if (pointsBox) {
                pointsBox.classList.toggle('is-visible', this.checked);
            }
            if (!this.checked && pointsToRedeemInput) {
                pointsToRedeemInput.value = '0';
            }
            updateTotals();
        });
    }

    if (pointsToRedeemInput) {
        pointsToRedeemInput.addEventListener('input', updateTotals);
    }

    // ========================================
    // COUPON MANAGEMENT
    // ========================================

    if (applyCouponBtn) {
        applyCouponBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const code = couponCodeInput.value.trim().toUpperCase();
            if (code) {
                applyCouponCode(code);
            } else {
                showCouponMessage('Please enter a coupon code', 'error');
            }
        });
    }

    async function applyCouponCode(code) {
        try {
            const response = await fetch('{% url "api_validate_coupon" %}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    code: code,
                    cart_total: cartSubtotal
                })
            });

            const data = await response.json();

            if (data.valid) {
                appliedCoupon = true;
                selectedCouponCode = code;
                appliedCouponIdInput.value = data.code;
                couponDiscountDisplay.textContent = '-₹' + data.discount_amount.toFixed(2);
                showCouponMessage(data.message, 'success');
                couponCodeInput.disabled = true;
                applyCouponBtn.disabled = true;
                removeCouponBtn.style.display = 'inline-block';
                updateTotals();
            } else {
                showCouponMessage(data.message || 'Invalid coupon code', 'error');
            }
        } catch (error) {
            console.error('Coupon validation error:', error);
            showCouponMessage('Error validating coupon. Please try again.', 'error');
        }
    }

    function showCouponMessage(message, type) {
        couponMessage.textContent = message;
        couponMessage.classList.add('is-visible');
        couponMessage.className = 'vm-checkout-tablet-coupon-message is-visible';
        if (type === 'error') {
            couponMessage.style.color = '#ba1a1a';
        } else {
            couponMessage.style.color = '#2d6a4f';
        }
    }

    if (removeCouponBtn) {
        removeCouponBtn.addEventListener('click', function(e) {
            e.preventDefault();
            removeCoupon();
        });
    }

    function removeCoupon() {
        appliedCoupon = false;
        selectedCouponCode = '';
        appliedCouponIdInput.value = '';
        couponCodeInput.value = '';
        couponCodeInput.disabled = false;
        applyCouponBtn.disabled = false;
        removeCouponBtn.style.display = 'none';
        couponMessage.classList.remove('is-visible');
        couponDiscountDisplay.textContent = '-₹0.00';
        couponDiscountRow.classList.add('is-hidden');
        updateTotals();
    }

    if (viewCouponsBtn) {
        viewCouponsBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            await loadAvailableCoupons();
        });
    }

    async function loadAvailableCoupons() {
        try {
            const response = await fetch('{% url "api_available_coupons" %}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    cart_total: cartSubtotal
                })
            });

            const data = await response.json();

            if (data.success && data.coupons.length > 0) {
                showCouponsModal(data.coupons);
            } else {
                showCouponMessage('No available coupons at this time', 'info');
            }
        } catch (error) {
            console.error('Error loading coupons:', error);
            showCouponMessage('Error loading coupons. Please try again.', 'error');
        }
    }

    function showCouponsModal(coupons) {
        const couponList = document.getElementById('tabletCouponList');
        couponList.innerHTML = '';

        coupons.forEach(coupon => {
            const option = document.createElement('label');
            option.className = 'vm-checkout-tablet-coupon-option';
            option.innerHTML = `
                <input type="radio" name="selected_coupon" value="${coupon.code}">
                <div>
                    <div class="vm-checkout-tablet-coupon-option__title">${coupon.code}</div>
                    <div class="vm-checkout-tablet-coupon-option__description">${coupon.description || coupon.title}</div>
                </div>
            `;
            couponList.appendChild(option);
        });

        couponModal.classList.add('is-visible');
    }

    if (closeCouponModalBtn) {
        closeCouponModalBtn.addEventListener('click', function() {
            couponModal.classList.remove('is-visible');
        });
    }

    if (cancelCouponBtn) {
        cancelCouponBtn.addEventListener('click', function() {
            couponModal.classList.remove('is-visible');
        });
    }

    if (applyCouponFromModalBtn) {
        applyCouponFromModalBtn.addEventListener('click', function() {
            const selectedCoupon = document.querySelector('input[name="selected_coupon"]:checked');
            if (selectedCoupon) {
                couponCodeInput.value = selectedCoupon.value;
                applyCouponCode(selectedCoupon.value);
                couponModal.classList.remove('is-visible');
            }
        });
    }

    couponModal.addEventListener('click', function(e) {
        if (e.target === couponModal) {
            couponModal.classList.remove('is-visible');
        }
    });

    // ========================================
    // FORM SUBMISSION
    // ========================================

    if (submitBtn) {
        submitBtn.addEventListener('click', function(e) {
            // Validation happens automatically via form
            // Additional checks can be added here if needed
        });
    }

    // ========================================
    // EVENT LISTENERS
    // ========================================

    function attachEventListeners() {
        // Update totals on relevant field changes
        if (postcodeField) {
            postcodeField.addEventListener('change', updateTotals);
        }

        // Validation feedback
        if (emailField) {
            emailField.addEventListener('blur', function() {
                if (this.value && !this.validity.valid) {
                    this.style.borderColor = '#ba1a1a';
                } else {
                    this.style.borderColor = '';
                }
            });
        }
    }

    // ========================================
    // START
    // ========================================

    initialize();
});
