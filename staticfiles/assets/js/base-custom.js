/* Base Template Custom JavaScript - Extracted from base.html */

// Cart functionality
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

// Toggle Wishlist for Product Cards
async function toggleWishlistCard(productId, button) {
    // Check if user is logged in
    if (!userAuthenticated) {
        window.location.href = "/login/?next=" + window.location.pathname;
        return;
    }

    const url = `/ajax-add-to-wishlist/${productId}/`;
    const csrftoken = getCsrfToken();
    const icon = button.querySelector('i');
    const isWishlisted = icon.classList.contains('fas');

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Toggle icon
            if (data.in_wishlist) {
                icon.classList.remove('fal');
                icon.classList.add('fas');
                button.style.color = '#ff4757';
            } else {
                icon.classList.remove('fas');
                icon.classList.add('fal');
                button.style.color = '';
            }
        } else {
            alert(data.message || 'Failed to update wishlist');
        }
    } catch (error) {
        console.error('Wishlist toggle error:', error);
        alert('An error occurred. Please try again.');
    }
}

// Check wishlist status on page load
document.addEventListener('DOMContentLoaded', function() {
    if (typeof userAuthenticated !== 'undefined' && userAuthenticated) {
        const wishlistButtons = document.querySelectorAll('.wishlist-btn-card');
        wishlistButtons.forEach(button => {
            const onclickAttr = button.getAttribute('onclick');
            if (onclickAttr) {
                const match = onclickAttr.match(/\d+/);
                if (match) {
                    const productId = match[0];
                    checkWishlistStatus(productId, button);
                }
            }
        });
    }
});

async function checkWishlistStatus(productId, button) {
    try {
        const response = await fetch(`/check-wishlist/${productId}/`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const data = await response.json();
        
        if (data.in_wishlist) {
            const icon = button.querySelector('i');
            icon.classList.remove('fal');
            icon.classList.add('fas');
            button.style.color = '#ff4757';
        }
    } catch (error) {
        console.error('Check wishlist error:', error);
    }
}

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
