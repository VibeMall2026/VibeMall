/**
 * FashioHub Admin Menu Toggle - Complete Sneat Template Implementation
 * Handles sidebar menu collapse/expand and hover state functionality
 */

'use strict';

const AdminMenuHelper = {
  // Breakpoint for large screens
  LAYOUT_BREAKPOINT: 1200,
  
  // Menu states
  menuCollapsed: false,
  menuHovered: false,
  
  // Get layout menu element
  getLayoutMenu() {
    return document.querySelector('#layout-menu');
  },

  // Get root element (html tag)
  getRootEl() {
    return document.documentElement;
  },

  // Check if screen is small (mobile/tablet)
  isSmallScreen() {
    return window.innerWidth < this.LAYOUT_BREAKPOINT;
  },

  // Add class to element
  addClass(el, className) {
    if (el && !el.classList.contains(className)) {
      el.classList.add(className);
    }
  },

  // Remove class from element
  removeClass(el, className) {
    if (el && el.classList.contains(className)) {
      el.classList.remove(className);
    }
  },

  // Toggle class on element
  toggleClass(el, className) {
    if (el) {
      el.classList.toggle(className);
    }
  },

  // Set menu collapsed state
  setCollapsed(collapsed = true) {
    const layoutMenu = this.getLayoutMenu();
    const rootEl = this.getRootEl();
    
    if (!layoutMenu) return;

    this.menuCollapsed = collapsed;

    if (collapsed) {
      // Collapse to icon-only mode (desktop) or hide (mobile)
      this.addClass(rootEl, 'layout-menu-collapsed');
      this.removeClass(rootEl, 'layout-menu-expanded');
      
      if (!this.isSmallScreen()) {
        // On desktop, just collapse to icons
        // Menu will expand on hover
      }
    } else {
      // Expand to full menu
      this.removeClass(rootEl, 'layout-menu-collapsed');
      
      if (this.isSmallScreen()) {
        this.addClass(rootEl, 'layout-menu-expanded');
      }
    }

    // Trigger window resize event
    window.dispatchEvent(new Event('resize'));
  },

  // Toggle menu collapsed state
  toggleCollapsed() {
    this.setCollapsed(!this.menuCollapsed);
  },

  // Handle menu hover on desktop (for collapsed state)
  handleMenuHover() {
    const layoutMenu = this.getLayoutMenu();
    if (!layoutMenu) return;

    // Hover enter - expand on desktop when collapsed
    layoutMenu.addEventListener('mouseenter', () => {
      if (!this.isSmallScreen() && this.menuCollapsed) {
        this.menuHovered = true;
        this.addClass(this.getRootEl(), 'layout-menu-hovered');
      }
    });

    // Hover leave - collapse back on desktop
    layoutMenu.addEventListener('mouseleave', () => {
      if (!this.isSmallScreen() && this.menuCollapsed) {
        this.menuHovered = false;
        this.removeClass(this.getRootEl(), 'layout-menu-hovered');
      }
    });
  },

  // Initialize menu toggle buttons
  initializeMenuToggles() {
    const menuToggles = document.querySelectorAll('.layout-menu-toggle');
    
    menuToggles.forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggleCollapsed();
      });
    });
  },

  // Initialize submenus with proper click handling
  initializeSubmenus() {
    const menuItems = document.querySelectorAll('.menu-item');
    
    menuItems.forEach(item => {
      const menuToggle = item.querySelector('.menu-toggle');
      const menuSub = item.querySelector('.menu-sub');
      
      if (menuToggle && menuSub) {
        menuToggle.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          
          // Toggle current submenu
          const isOpen = item.classList.contains('open');
          
          // Close all other submenus at same level
          const siblings = item.parentElement.querySelectorAll('.menu-item.open');
          siblings.forEach(sibling => {
            if (sibling !== item) {
              sibling.classList.remove('open');
            }
          });
          
          // Toggle current submenu
          if (isOpen) {
            item.classList.remove('open');
            menuSub.style.maxHeight = '0';
            setTimeout(() => {
              menuSub.style.opacity = '0';
              menuSub.style.visibility = 'hidden';
            }, 10);
          } else {
            item.classList.add('open');
            // Use setTimeout to ensure height transition works
            setTimeout(() => {
              menuSub.style.maxHeight = menuSub.scrollHeight + 'px';
              menuSub.style.opacity = '1';
              menuSub.style.visibility = 'visible';
            }, 10);
          }
        });
      }
    });

    // Close submenus when clicking on non-toggle menu items
    const menuLinks = document.querySelectorAll('.menu-link:not(.menu-toggle)');
    menuLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        // Close mobile menu if open
        if (this.isSmallScreen() && this.menuCollapsed === false) {
          this.setCollapsed(true);
        }
      });
    });
  },

  // Close menu on overlay click
  initializeOverlay() {
    const overlay = document.querySelector('.layout-overlay');
    
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        e.preventDefault();
        if (this.isSmallScreen()) {
          this.setCollapsed(true);
        }
      });
    }
  },

  // Handle window resize
  handleWindowResize() {
    let resizeTimeout;
    
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        const rootEl = this.getRootEl();
        
        // On large screens, always expand menu
        if (!this.isSmallScreen()) {
          this.removeClass(rootEl, 'layout-menu-expanded');
          // Don't auto-expand, keep the user's preference
        } else {
          // On small screens, handle mobile view
          if (this.menuCollapsed && rootEl.classList.contains('layout-menu-expanded')) {
            this.removeClass(rootEl, 'layout-menu-expanded');
          }
        }
      }, 200);
    });
  },

  // Initialize all menu functionality
  init() {
    // Wait for DOM to be fully ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        this._initializeComponents();
      });
    } else {
      this._initializeComponents();
    }
  },

  _initializeComponents() {
    this.initializeMenuToggles();
    this.initializeSubmenus();
    this.initializeOverlay();
    this.handleMenuHover();
    this.handleWindowResize();

    // Close submenus when navigating away
    document.addEventListener('click', (e) => {
      // If clicking outside menu
      if (!e.target.closest('#layout-menu') && !e.target.closest('.layout-menu-toggle')) {
        if (this.isSmallScreen() && !this.menuCollapsed) {
          // Keep menu open on mobile, just close submenu
          const openItems = document.querySelectorAll('.menu-item.open');
          openItems.forEach(item => {
            const sub = item.querySelector('.menu-sub');
            item.classList.remove('open');
            if (sub) {
              sub.style.maxHeight = '0';
              sub.style.opacity = '0';
              sub.style.visibility = 'hidden';
            }
          });
        }
      }
    });
  }
};

// Initialize when script loads
AdminMenuHelper.init();
