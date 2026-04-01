/* Base Template Custom JavaScript - Extracted from base.html */

// Cart functionality
(function () {
    const navRoot = document.getElementById('mobileBottomNav');
    if (!navRoot) return;

    const path = (window.location.pathname || '/').toLowerCase();
    let activeKey = 'home';

    if (path.startsWith('/wishlist')) {
        activeKey = 'wishlist';
    } else if (
        path.startsWith('/cart') ||
        path.startsWith('/checkout') ||
        path.startsWith('/order-confirmation') ||
        path.startsWith('/razorpay-payment')
    ) {
        activeKey = 'cart';
    } else if (
        path.startsWith('/profile') ||
        path.startsWith('/login') ||
        path.startsWith('/register') ||
        path.startsWith('/orders') ||
        path.startsWith('/password_reset') ||
        path.startsWith('/verify-email')
    ) {
        activeKey = 'account';
    } else if (
        path.startsWith('/shop') ||
        path.startsWith('/product') ||
        path.startsWith('/blog') ||
        path.startsWith('/about') ||
        path.startsWith('/faq') ||
        path.startsWith('/contact') ||
        path.startsWith('/track-order')
    ) {
        activeKey = 'shop';
    }

    navRoot.querySelectorAll('.mobile-bottom-nav__item').forEach((item) => {
        const key = item.getAttribute('data-nav-key');
        item.classList.toggle('is-active', key === activeKey);
    });
})();

(function () {
    const isAuthed = typeof userAuthenticated !== 'undefined' ? userAuthenticated : false;
    if (!isAuthed) return;

    const updateCartDom = (data) => {
        const countNodes = document.querySelectorAll('.cart-count');
        const totalNodes = document.querySelectorAll('.cart-total');
        const miniCountNodes = document.querySelectorAll('.cart-mini-count');
        const miniCart = document.getElementById('miniCartContent');

        if (countNodes.length) {
            countNodes.forEach((node) => {
                node.textContent = data.cart_count ?? node.textContent;
            });
        }
        if (totalNodes.length) {
            totalNodes.forEach((node) => {
                node.textContent = data.cart_total ?? node.textContent;
            });
        }
        if (miniCountNodes.length) {
            miniCountNodes.forEach((node) => {
                node.textContent = data.cart_count ?? node.textContent;
            });
        }
        if (miniCart && data.mini_cart_html) {
            miniCart.innerHTML = data.mini_cart_html;
        }
    };

    window.refreshMiniCart = function () {
        fetch('/cart/summary/', { credentials: 'same-origin' })
            .then((res) => res.json())
            .then(updateCartDom)
            .catch(() => {});
    };

    let cartHoverTimer;
    const cartBlock = document.querySelector('.block-cart');
    const triggerCartRefresh = () => {
        clearTimeout(cartHoverTimer);
        cartHoverTimer = setTimeout(() => {
            if (typeof window.refreshMiniCart === 'function') {
                window.refreshMiniCart();
            }
        }, 150);
    };
    if (cartBlock) {
        cartBlock.addEventListener('mouseenter', triggerCartRefresh);
        cartBlock.addEventListener('focusin', triggerCartRefresh);
        cartBlock.addEventListener('click', triggerCartRefresh);
    }

    document.addEventListener('cart:updated', () => {
        window.refreshMiniCart();
    });
})();

// Support Chat Widget
(function() {
    const toggleBtn = document.getElementById('supportChatToggle');
    const closeBtn = document.getElementById('supportChatClose');
    const panel = document.getElementById('supportChatPanel');
    const messagesEl = document.getElementById('supportChatMessages');
    const inputEl = document.getElementById('supportChatInput');
    const sendBtn = document.getElementById('supportChatSend');
    const fileInput = document.getElementById('supportChatFiles');
    const guestBox = document.getElementById('supportChatGuest');
    const guestName = document.getElementById('supportGuestName');
    const guestEmail = document.getElementById('supportGuestEmail');
    let threadId = null;

    function getCsrfToken() {
        const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
    }

    function renderMessages(messages) {
        messagesEl.innerHTML = '';
        messages.forEach((msg) => {
            const bubble = document.createElement('div');
            bubble.className = 'chat-bubble ' + (msg.sender === 'ADMIN' ? 'admin' : 'user');
            if (msg.message) {
                const textEl = document.createElement('div');
                textEl.textContent = msg.message;
                bubble.appendChild(textEl);
            }

            if (msg.attachments && msg.attachments.length) {
                const list = document.createElement('div');
                list.className = 'chat-attachment-list';
                msg.attachments.forEach((att) => {
                    const link = document.createElement('a');
                    link.className = 'chat-attachment-item';
                    link.href = att.url;
                    link.target = '_blank';
                    if (att.is_image) {
                        const img = document.createElement('img');
                        img.src = att.url;
                        img.alt = att.name;
                        link.appendChild(img);
                    } else {
                        link.textContent = att.name;
                    }
                    list.appendChild(link);
                });
                bubble.appendChild(list);
            }
            messagesEl.appendChild(bubble);
        });
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function loadThread() {
        fetch('/chat/thread/')
            .then(res => res.json())
            .then((data) => {
                threadId = data.thread_id;
                renderMessages(data.messages || []);
                if (guestBox) {
                    if (!userAuthenticated && data.requires_profile) {
                        guestBox.classList.remove('chat-hidden');
                    } else {
                        guestBox.classList.add('chat-hidden');
                    }
                }
                if (guestName && data.guest_name) guestName.value = data.guest_name;
                if (guestEmail && data.guest_email) guestEmail.value = data.guest_email;
            });
    }

    function sendMessage(text) {
        const formData = new FormData();
        formData.append('message', text || '');
        if (threadId) formData.append('thread_id', threadId);
        if (!userAuthenticated && guestName && guestEmail) {
            formData.append('guest_name', guestName.value.trim());
            formData.append('guest_email', guestEmail.value.trim());
        }
        if (fileInput && fileInput.files.length) {
            Array.from(fileInput.files).forEach((file) => {
                formData.append('attachments', file);
            });
        }

        fetch('/chat/message/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            body: formData
        })
        .then(res => res.json())
        .then((data) => {
            if (data.error) {
                alert(data.error);
                return;
            }
            inputEl.value = '';
            if (fileInput) fileInput.value = '';
            loadThread();
        });
    }

    function setPanelOpen(open) {
        panel.classList.toggle('chat-hidden', !open);
        toggleBtn.classList.toggle('chat-hidden', open);
        toggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    toggleBtn.addEventListener('click', () => {
        const shouldOpen = panel.classList.contains('chat-hidden');
        setPanelOpen(shouldOpen);
        if (shouldOpen) {
            loadThread();
        }
    });

    closeBtn.addEventListener('click', () => {
        setPanelOpen(false);
    });

    sendBtn.addEventListener('click', () => {
        const text = inputEl.value.trim();
        if (text || (fileInput && fileInput.files.length)) sendMessage(text);
    });

    inputEl.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            const text = inputEl.value.trim();
            if (text || (fileInput && fileInput.files.length)) sendMessage(text);
        }
    });

    document.querySelectorAll('.chat-quick').forEach((btn) => {
        btn.addEventListener('click', () => {
            sendMessage(btn.dataset.text);
        });
    });
})();

// Buy Now for Product Cards
function getCsrfToken() {
    const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
}

async function buyNowCard(productId) {
    // Check if user is logged in
    if (!userAuthenticated) {
        window.location.href = "/login/?next=" + window.location.pathname;
        return;
    }

    const url = `/buy-now/${productId}/`;
    const csrftoken = getCsrfToken();

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: 'quantity=1'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Redirect to cart
            window.location.href = data.redirect_url || '/cart/';
        } else {
            alert(data.message || 'Failed to process order');
        }
    } catch (error) {
        console.error('Buy Now error:', error);
        alert('An error occurred. Please try again.');
    }
}

(function () {
    const isAuthenticated = typeof userAuthenticated !== 'undefined' && userAuthenticated;
    const getLoginUrl = () => `/login/?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;

    const showStorefrontNotification = (message, type) => {
        if (!message) return;

        if (typeof bootstrap === 'undefined' || !bootstrap.Alert) {
            alert(message);
            return;
        }

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type || 'success'} alert-dismissible fade show vm-floating-alert`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.appendChild(alertDiv);

        window.setTimeout(() => {
            const alert = bootstrap.Alert.getOrCreateInstance(alertDiv);
            alert.close();
        }, 2600);
    };

    const showStorefrontConfirm = (message) => {
        const promptMessage = message || 'Are you sure?';

        // Remove any existing confirm overlay
        const existingOverlay = document.getElementById('vmConfirmOverlay');
        if (existingOverlay) existingOverlay.remove();

        // Build a pure CSS/JS dialog - no Bootstrap dependency
        const overlay = document.createElement('div');
        overlay.id = 'vmConfirmOverlay';
        overlay.style.cssText = [
            'position:fixed', 'inset:0', 'z-index:99999',
            'display:flex', 'align-items:center', 'justify-content:center',
            'background:rgba(0,0,0,0.45)', 'backdrop-filter:blur(4px)',
            '-webkit-backdrop-filter:blur(4px)', 'padding:20px',
        ].join(';');

        overlay.innerHTML = `
            <div style="
                background:#fff;
                border-radius:16px;
                padding:28px 24px 22px;
                max-width:360px;
                width:100%;
                box-shadow:0 20px 50px rgba(0,0,0,0.22);
                text-align:center;
                animation:vmConfirmIn .18s ease;
            ">
                <div style="width:48px;height:48px;border-radius:50%;background:#fff3f3;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#e03636" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                </div>
                <h5 style="margin:0 0 8px;font-size:17px;font-weight:700;color:#111827;font-family:inherit;">Remove Item</h5>
                <p style="margin:0 0 24px;font-size:14px;color:#6b7280;line-height:1.5;" id="vmConfirmMsg"></p>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    <button id="vmConfirmCancel" style="
                        height:44px;border-radius:999px;border:1.5px solid #e5e7eb;
                        background:#f9fafb;color:#374151;font-size:14px;font-weight:600;
                        cursor:pointer;transition:background .2s;
                    ">Cancel</button>
                    <button id="vmConfirmOk" style="
                        height:44px;border-radius:999px;border:0;
                        background:#111827;color:#fff;font-size:14px;font-weight:600;
                        cursor:pointer;transition:background .2s;
                    ">Remove</button>
                </div>
            </div>
            <style>
                @keyframes vmConfirmIn {
                    from { opacity:0; transform:scale(.92) translateY(10px); }
                    to   { opacity:1; transform:scale(1) translateY(0); }
                }
            </style>
        `;

        document.body.appendChild(overlay);

        const msgEl = overlay.querySelector('#vmConfirmMsg');
        const okBtn = overlay.querySelector('#vmConfirmOk');
        const cancelBtn = overlay.querySelector('#vmConfirmCancel');
        if (msgEl) msgEl.textContent = promptMessage;

        return new Promise((resolve) => {
            const cleanup = (result) => {
                overlay.remove();
                resolve(result);
            };

            okBtn.addEventListener('click', () => cleanup(true));
            cancelBtn.addEventListener('click', () => cleanup(false));

            // Close on backdrop click
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) cleanup(false);
            });

            // Close on Escape key
            const handleKey = (e) => {
                if (e.key === 'Escape') {
                    document.removeEventListener('keydown', handleKey);
                    cleanup(false);
                }
            };
            document.addEventListener('keydown', handleKey);

            // Focus cancel button for accessibility
            cancelBtn.focus();
        });
    };

    const setCount = (selector, value) => {
        if (typeof value !== 'number' || Number.isNaN(value)) return;
        document.querySelectorAll(selector).forEach((node) => {
            node.textContent = value;
        });
    };

    const getCount = (selector) => {
        const node = document.querySelector(selector);
        if (!node) return 0;
        return parseInt(node.textContent, 10) || 0;
    };

    const setButtonIconState = (button, active, fallbackRegularClass) => {
        const icon = button?.querySelector('i');
        if (!icon) return;

        const regularClass = icon.dataset.regularClass
            || (icon.classList.contains('far') ? 'far' : icon.classList.contains('fal') ? 'fal' : fallbackRegularClass);

        icon.dataset.regularClass = regularClass;
        icon.classList.remove('fas', 'far', 'fal');
        icon.classList.add(active ? 'fas' : regularClass);
    };

    const setButtonLabel = (button, active) => {
        const label = active ? button.dataset.labelActive : button.dataset.labelInactive;
        if (!label) return;

        const labelNode = button.querySelector('[data-button-label]') || button.querySelector('span:last-child');
        if (labelNode) {
            labelNode.textContent = label;
        }
    };

    const applyWishlistState = (button, inWishlist) => {
        if (!button) return;

        button.dataset.inWishlist = inWishlist ? '1' : '0';
        button.classList.toggle('wishlisted', inWishlist);
        button.classList.toggle('wishlist-filled', inWishlist);
        button.classList.toggle('is-active', inWishlist);
        button.setAttribute('aria-pressed', inWishlist ? 'true' : 'false');
        button.title = inWishlist ? 'Remove from wishlist' : 'Add to wishlist';
        setButtonIconState(button, inWishlist, 'fal');
        setButtonLabel(button, inWishlist);
    };

    const applyCartState = (button, inCart) => {
        if (!button) return;

        button.dataset.inCart = inCart ? '1' : '0';
        button.classList.toggle('in-cart', inCart);
        button.setAttribute('aria-pressed', inCart ? 'true' : 'false');
        button.title = inCart ? 'Remove from cart' : 'Add to cart';
        setButtonIconState(button, inCart, 'fal');
        setButtonLabel(button, inCart);
    };

    const syncWishlistButtons = (productId, inWishlist) => {
        document.querySelectorAll(`[data-product-id="${productId}"]`).forEach((button) => {
            if (button.matches('.wishlist-btn, .wishlist-chip, .vm-pd-m-wishlist, .qv-wishlist')) {
                applyWishlistState(button, inWishlist);
            }
        });
    };

    const syncCartButtons = (productId, inCart) => {
        document.querySelectorAll(`[data-product-id="${productId}"]`).forEach((button) => {
            if (button.matches('.cart-btn')) {
                applyCartState(button, inCart);
            }
        });
    };

    const resolveButton = (firstArg, secondArg) => {
        if (firstArg instanceof Element) {
            return firstArg;
        }
        if (secondArg instanceof Element) {
            if (!secondArg.dataset.productId && firstArg) {
                secondArg.dataset.productId = String(firstArg);
            }
            return secondArg;
        }
        return null;
    };

    async function toggleWishlist(firstArg, secondArg) {
        const button = resolveButton(firstArg, secondArg);
        if (!button) return;

        const productId = button.dataset.productId;
        const loggedIn = button.dataset.loggedIn ? button.dataset.loggedIn === '1' : isAuthenticated;

        if (!loggedIn) {
            window.location.href = getLoginUrl();
            return;
        }

        if (!productId) return;

        button.disabled = true;
        try {
            const response = await fetch(`/wishlist/add/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                showStorefrontNotification(data.message || 'Failed to update wishlist.', 'danger');
                return data;
            }

            syncWishlistButtons(productId, !!data.in_wishlist);
            if (typeof data.wishlist_count === 'number') {
                setCount('.wishlist-count', data.wishlist_count);
            } else {
                const delta = data.in_wishlist ? 1 : -1;
                setCount('.wishlist-count', Math.max(0, getCount('.wishlist-count') + delta));
            }

            showStorefrontNotification(
                data.message || (data.in_wishlist ? 'Product added to wishlist!' : 'Product removed from wishlist.'),
                data.in_wishlist ? 'success' : 'secondary'
            );
            return data;
        } catch (error) {
            console.error('Wishlist toggle error:', error);
            showStorefrontNotification('An error occurred while updating wishlist.', 'danger');
        } finally {
            button.disabled = false;
        }
    }

    async function toggleCart(button) {
        if (!(button instanceof Element)) return;

        const productId = button.dataset.productId;
        const loggedIn = button.dataset.loggedIn ? button.dataset.loggedIn === '1' : isAuthenticated;

        if (!loggedIn) {
            window.location.href = getLoginUrl();
            return;
        }

        if (!productId) return;

        button.disabled = true;
        try {
            const response = await fetch(`/cart/toggle/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                showStorefrontNotification(data.message || 'Failed to update cart.', 'danger');
                return data;
            }

            syncCartButtons(productId, !!data.in_cart);
            if (typeof data.cart_count === 'number') {
                setCount('.cart-count', data.cart_count);
            }

            if (typeof window.refreshMiniCart === 'function') {
                window.refreshMiniCart();
            }
            document.dispatchEvent(new CustomEvent('cart:updated', { detail: data }));

            showStorefrontNotification(
                data.message || (data.in_cart ? 'Product added to cart!' : 'Product removed from cart.'),
                data.in_cart ? 'success' : 'secondary'
            );
            return data;
        } catch (error) {
            console.error('Cart toggle error:', error);
            showStorefrontNotification('An error occurred while updating cart.', 'danger');
        } finally {
            button.disabled = false;
        }
    }

    const WISHLIST_BUTTON_SELECTOR = '.wishlist-btn, .wishlist-chip, .vm-pd-m-wishlist, .qv-wishlist';
    const CART_BUTTON_SELECTOR = '.cart-btn[data-product-id]';

    document.addEventListener('click', (event) => {
        const wishlistButton = event.target.closest(WISHLIST_BUTTON_SELECTOR);
        if (wishlistButton) {
            event.preventDefault();
            event.stopPropagation();
            toggleWishlist(wishlistButton);
            return;
        }

        const cartButton = event.target.closest(CART_BUTTON_SELECTOR);
        if (cartButton) {
            event.preventDefault();
            event.stopPropagation();
            toggleCart(cartButton);
        }
    }, true);

    document.addEventListener('click', async (event) => {
        const eventTarget = event.target;
        if (!(eventTarget instanceof Element)) {
            return;
        }

        const confirmTrigger = eventTarget.closest('.js-confirm-remove[href]');
        if (!confirmTrigger) {
            return;
        }

        event.preventDefault();
        event.stopImmediatePropagation();

        const href = confirmTrigger.getAttribute('href') || confirmTrigger.href;
        if (!href) {
            return;
        }

        const message = confirmTrigger.getAttribute('data-confirm-message') || 'Are you sure?';
        let shouldProceed = false;

        shouldProceed = await showStorefrontConfirm(message);

        if (shouldProceed) {
            window.location.assign(href);
        }
    }, true);

    window.vmStorefrontActions = {
        toggleWishlist,
        toggleCart,
        confirm: showStorefrontConfirm,
        syncWishlistButtons,
        syncCartButtons,
        applyWishlistState,
        applyCartState,
    };

    window.toggleWishlistCard = toggleWishlist;
    window.handleWishlistClick = toggleWishlist;
    window.handleCartClick = toggleCart;
})();

// Newsletter subscription forms (About/404 CTA blocks)
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('.js-newsletter-form');
    if (!forms.length) return;

    const setFeedback = (el, message, type) => {
        if (!el) return;
        el.textContent = message || '';
        el.classList.remove('text-success', 'text-danger', 'text-warning');
        if (type === 'success') el.classList.add('text-success');
        if (type === 'error') el.classList.add('text-danger');
        if (type === 'info') el.classList.add('text-warning');
    };

    forms.forEach((form) => {
        const emailInput = form.querySelector('input[name=\"email\"]');
        const submitBtn = form.querySelector('button[type=\"submit\"]');
        const feedbackEl = form.parentElement.querySelector('.newsletter-feedback');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            if (!emailInput || !submitBtn) return;

            const email = emailInput.value.trim();
            if (!email) {
                setFeedback(feedbackEl, 'Please enter your email address.', 'error');
                return;
            }

            setFeedback(feedbackEl, '', '');
            const originalButtonText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = 'Please wait...';

            try {
                const formData = new FormData(form);
                const csrfInput = form.querySelector('input[name=\"csrfmiddlewaretoken\"]');
                const csrfToken = csrfInput ? csrfInput.value : getCsrfToken();

                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    },
                    credentials: 'same-origin',
                    body: formData
                });

                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.message || 'Unable to subscribe right now.');
                }

                const feedbackType = data.status === 'already_subscribed' ? 'info' : 'success';
                setFeedback(feedbackEl, data.message || 'Subscribed successfully.', feedbackType);
                form.reset();
            } catch (error) {
                setFeedback(feedbackEl, error.message || 'Something went wrong. Please try again.', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalButtonText;
            }
        });
    });
});
