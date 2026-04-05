document.addEventListener('DOMContentLoaded', function () {
    // Mobile Side Menu Toggle Functionality
    const sideMenu = document.querySelector('[data-vm-mobile-menu]');
    const menuOverlay = document.querySelector('[data-vm-mobile-menu-overlay]');
    const menuToggleBtns = document.querySelectorAll('.offcanvas-toggle-btn');
    const menuCloseBtn = document.querySelector('[data-vm-mobile-menu-close]');
    const submenuToggles = document.querySelectorAll('[data-vm-mobile-submenu-toggle]');

    if (sideMenu && menuOverlay && (menuToggleBtns.length > 0 || menuCloseBtn)) {
        const pageRoot = document.documentElement;

        function lockPageScroll() {
            if (document.body.dataset.vmMenuScrollLocked === 'true') {
                return;
            }

            const scrollY = window.scrollY || window.pageYOffset || 0;

            document.body.dataset.vmMenuScrollLocked = 'true';
            document.body.dataset.vmMenuScrollY = String(scrollY);
            document.body.dataset.vmMenuBodyOverflow = document.body.style.overflow || '';
            document.body.dataset.vmMenuBodyPosition = document.body.style.position || '';
            document.body.dataset.vmMenuBodyTop = document.body.style.top || '';
            document.body.dataset.vmMenuBodyWidth = document.body.style.width || '';
            document.body.dataset.vmMenuBodyTouchAction = document.body.style.touchAction || '';
            document.body.dataset.vmMenuHtmlOverflow = pageRoot.style.overflow || '';
            document.body.dataset.vmMenuHtmlTouchAction = pageRoot.style.touchAction || '';

            pageRoot.style.overflow = 'hidden';
            pageRoot.style.touchAction = 'none';
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.top = '-' + scrollY + 'px';
            document.body.style.width = '100%';
            document.body.style.touchAction = 'none';
        }

        function unlockPageScroll() {
            const lockedScrollY = Number(document.body.dataset.vmMenuScrollY || '0');

            pageRoot.style.overflow = document.body.dataset.vmMenuHtmlOverflow || '';
            pageRoot.style.touchAction = document.body.dataset.vmMenuHtmlTouchAction || '';
            document.body.style.overflow = document.body.dataset.vmMenuBodyOverflow || '';
            document.body.style.position = document.body.dataset.vmMenuBodyPosition || '';
            document.body.style.top = document.body.dataset.vmMenuBodyTop || '';
            document.body.style.width = document.body.dataset.vmMenuBodyWidth || '';
            document.body.style.touchAction = document.body.dataset.vmMenuBodyTouchAction || '';

            delete document.body.dataset.vmMenuScrollLocked;
            delete document.body.dataset.vmMenuScrollY;
            delete document.body.dataset.vmMenuBodyOverflow;
            delete document.body.dataset.vmMenuBodyPosition;
            delete document.body.dataset.vmMenuBodyTop;
            delete document.body.dataset.vmMenuBodyWidth;
            delete document.body.dataset.vmMenuBodyTouchAction;
            delete document.body.dataset.vmMenuHtmlOverflow;
            delete document.body.dataset.vmMenuHtmlTouchAction;

            window.scrollTo(0, lockedScrollY);
        }

        function recoverMenuState() {
            const menuIsOpen = sideMenu.classList.contains('is-open') || menuOverlay.classList.contains('is-open');
            const hasScrollLock = document.body.dataset.vmMenuScrollLocked === 'true';

            if (!menuIsOpen && hasScrollLock) {
                unlockPageScroll();
            }
        }

        // Close menu function
        function closeMenu() {
            sideMenu.classList.remove('is-open');
            menuOverlay.classList.remove('is-open');
            unlockPageScroll();
            // Close all open submenus
            submenuToggles.forEach(function (toggle) {
                toggle.setAttribute('aria-expanded', 'false');
                const submenu = toggle.closest('.vm-mobile-side-menu__item--submenu')?.querySelector('[data-vm-mobile-submenu]');
                if (submenu) {
                    submenu.classList.remove('is-open');
                }
            });
        }

        // Open menu function
        function openMenu() {
            sideMenu.classList.add('is-open');
            menuOverlay.classList.add('is-open');
            lockPageScroll();
        }

        // Toggle menu (open/close)
        function toggleMenu(e) {
            e.stopPropagation();
            const isOpen = sideMenu.classList.contains('is-open');
            if (isOpen) {
                closeMenu();
            } else {
                openMenu();
            }
        }

        // Attach toggle to all menu buttons
        menuToggleBtns.forEach(function (btn) {
            btn.addEventListener('click', toggleMenu);
        });

        if (menuCloseBtn) {
            menuCloseBtn.addEventListener('click', closeMenu);
        }

        menuOverlay.addEventListener('click', closeMenu);

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && sideMenu.classList.contains('is-open')) {
                closeMenu();
            }
        });

        window.addEventListener('resize', function () {
            if (window.innerWidth >= 992 && sideMenu.classList.contains('is-open')) {
                closeMenu();
            }
        });

        // Ensure stale scroll locks never survive browser navigation restore.
        window.addEventListener('pagehide', function () {
            closeMenu();
        });

        window.addEventListener('pageshow', function () {
            recoverMenuState();
        });

        window.addEventListener('popstate', function () {
            closeMenu();
            recoverMenuState();
        });

        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'hidden') {
                closeMenu();
                return;
            }

            recoverMenuState();
        });

        // Submenu toggle
        submenuToggles.forEach(function (toggle) {
            toggle.addEventListener('click', function (e) {
                e.preventDefault();
                const submenu = toggle.closest('.vm-mobile-side-menu__item--submenu')?.querySelector('[data-vm-mobile-submenu]');
                if (submenu) {
                    const isOpen = toggle.getAttribute('aria-expanded') === 'true';
                    toggle.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
                    submenu.classList.toggle('is-open');
                }
            });
        });

        // Close menu when a link is clicked
        const menuLinks = document.querySelectorAll('.vm-mobile-side-menu__link:not([data-vm-mobile-submenu-toggle]), .vm-mobile-side-menu__sublink');
        menuLinks.forEach(function (link) {
            link.addEventListener('click', function () {
                // Don't close on submit/button type links
                if (link.tagName !== 'BUTTON') {
                    closeMenu();
                }
            });

            link.addEventListener('touchstart', function () {
                if (link.tagName !== 'BUTTON') {
                    closeMenu();
                }
            }, { passive: true });
        });
    }

    const searchRoots = document.querySelectorAll('[data-vm-mobile-search-root]');

    searchRoots.forEach(function (root) {
        const toggle = root.querySelector('[data-vm-mobile-search-toggle]');
        const form = root.querySelector('[data-vm-mobile-search-form]');
        const input = root.querySelector('input[name="q"]');
        if (!toggle || !form) {
            return;
        }

        toggle.addEventListener('click', function () {
            const isOpen = form.classList.toggle('is-open');
            toggle.classList.toggle('is-open', isOpen);
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            if (isOpen && input) {
                window.setTimeout(function () { input.focus(); }, 120);
            }
        });

        document.addEventListener('click', function (event) {
            if (!root.contains(event.target)) {
                form.classList.remove('is-open');
                toggle.classList.remove('is-open');
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
    });

    const slider = document.querySelector('[data-vm-mobile-slider]');
    if (slider) {
        const slides = Array.from(slider.querySelectorAll('[data-vm-mobile-slide]'));
        const dots = Array.from(document.querySelectorAll('[data-vm-mobile-dot]'));
        let activeIndex = slides.findIndex(function (slide) {
            return slide.classList.contains('is-active');
        });

        if (activeIndex < 0) {
            activeIndex = 0;
        }

        const render = function (index) {
            slides.forEach(function (slide, slideIndex) {
                slide.classList.toggle('is-active', slideIndex === index);
            });
            dots.forEach(function (dot, dotIndex) {
                dot.classList.toggle('is-active', dotIndex === index);
            });
            activeIndex = index;
        };

        dots.forEach(function (dot, index) {
            dot.addEventListener('click', function () {
                render(index);
            });
        });

        render(activeIndex);
        window.setInterval(function () {
            render((activeIndex + 1) % slides.length);
        }, 4200);
    }
});