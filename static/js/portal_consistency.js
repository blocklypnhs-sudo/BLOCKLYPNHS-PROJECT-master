(() => {
    const sproutDecoration = `
        <div class="sidebar-deco" aria-hidden="true">
            <svg viewBox="0 0 232 46" preserveAspectRatio="none" focusable="false">
                <path d="M0,20 C62,38 130,8 232,24 L232,46 L0,46 Z" fill="rgba(255,255,255,0.05)"></path>
                <path d="M0,32 C76,44 148,20 232,34 L232,46 L0,46 Z" fill="rgba(255,255,255,0.045)"></path>
            </svg>
            <svg class="deco-sprout-svg" viewBox="0 0 48 48" focusable="false">
                <path d="M24 44 V26" stroke="rgba(190,235,205,0.55)" stroke-width="2.4" stroke-linecap="round" fill="none"></path>
                <path d="M24 30 C14 30 8 24 8 14 C18 14 24 20 24 30 Z" fill="rgba(190,235,205,0.38)"></path>
                <path d="M24 26 C24 16 30 10 40 10 C40 20 34 26 24 26 Z" fill="rgba(190,235,205,0.52)"></path>
            </svg>
        </div>`;

    function initializeMobileDropdownPositioning() {
        const dropdownSelector = '.notif-dropdown, .profile-dropdown, .module-profile-dropdown';
        const positionedStyles = new WeakMap();
        const styleProperties = [
            'position',
            'top',
            'left',
            'right',
            'transform',
            'max-width',
            'max-height',
            'overflow-y'
        ];

        const restoreDropdownPosition = (dropdown) => {
            const originalStyles = positionedStyles.get(dropdown);
            if (!originalStyles) return;
            originalStyles.forEach(([property, value, priority]) => {
                if (value) {
                    dropdown.style.setProperty(property, value, priority);
                } else {
                    dropdown.style.removeProperty(property);
                }
            });
            positionedStyles.delete(dropdown);
        };

        const positionDropdown = (dropdown) => {
            if (!dropdown.classList.contains('open')) {
                restoreDropdownPosition(dropdown);
                return;
            }
            if (!window.matchMedia('(max-width: 768px)').matches) {
                restoreDropdownPosition(dropdown);
                return;
            }

            let trigger;
            if (dropdown.classList.contains('notif-dropdown')) {
                trigger = dropdown.closest('.notification-wrap')
                    ?.querySelector('#notifBtn, .notification-btn, .notif-btn');
            } else if (dropdown.classList.contains('module-profile-dropdown')) {
                trigger = dropdown.closest('.module-profile-wrap')
                    ?.querySelector('#moduleProfileTrigger, .module-profile');
            } else {
                trigger = dropdown.closest('.profile-trigger')
                    || document.querySelector('#profileTrigger');
            }
            if (!trigger) return;

            if (!positionedStyles.has(dropdown)) {
                positionedStyles.set(dropdown, styleProperties.map((property) => [
                    property,
                    dropdown.style.getPropertyValue(property),
                    dropdown.style.getPropertyPriority(property)
                ]));
            }

            const setImportant = (property, value) => {
                dropdown.style.setProperty(property, value, 'important');
            };
            setImportant('position', 'fixed');
            setImportant('top', '12px');
            setImportant('left', '12px');
            setImportant('right', 'auto');
            setImportant('transform', 'none');
            setImportant('max-width', 'calc(100vw - 24px)');
            setImportant('max-height', 'calc(100dvh - 24px)');
            setImportant('overflow-y', 'auto');

            const triggerRect = trigger.getBoundingClientRect();
            const dropdownRect = dropdown.getBoundingClientRect();
            const viewportWidth = document.documentElement.clientWidth;
            const viewportHeight = window.innerHeight;
            const margin = 12;
            const left = Math.max(
                margin,
                Math.min(triggerRect.right - dropdownRect.width, viewportWidth - dropdownRect.width - margin)
            );
            const belowTop = triggerRect.bottom + 8;
            const availableBelow = viewportHeight - belowTop - margin;
            const availableAbove = triggerRect.top - margin;
            const openAbove = dropdownRect.height > availableBelow && availableAbove > availableBelow;
            const top = openAbove
                ? Math.max(margin, triggerRect.top - Math.min(dropdownRect.height, availableAbove) - 8)
                : belowTop;
            const availableHeight = Math.max(
                80,
                viewportHeight - top - margin
            );

            setImportant('left', left + 'px');
            setImportant('top', top + 'px');
            setImportant('max-height', availableHeight + 'px');
        };

        const repositionOpenDropdowns = () => {
            document.querySelectorAll(dropdownSelector).forEach(positionDropdown);
        };
        const scheduleReposition = (dropdown) => {
            window.requestAnimationFrame(() => positionDropdown(dropdown));
        };

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target.matches(dropdownSelector)) {
                    scheduleReposition(mutation.target);
                }
            });
        });
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class'],
            subtree: true
        });
        window.addEventListener('resize', repositionOpenDropdowns);
        repositionOpenDropdowns();
    }

    function initializePortalSidebar() {
        initializeMobileDropdownPositioning();

        try {
            if (localStorage.getItem('blocklearn-theme') === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
        } catch (error) {
            console.warn('Unable to load saved theme preference.', error);
        }

        const sidebar = document.querySelector('.sidebar, .student-sidebar');
        if (!sidebar) return;

        if (sidebar.classList.contains('teacher-sidebar') &&
            window.matchMedia('(min-width: 769px)').matches) {
            try {
                const collapsed = localStorage.getItem('teacher-sidebar-collapsed');
                if (collapsed === '1' || collapsed === '0') {
                    window.portalSetSidebarCollapsed(collapsed === '1');
                }
            } catch (error) {
                console.warn('Unable to load saved sidebar preference.', error);
            }
        }

        if (!sidebar.querySelector('.sidebar-deco')) {
            const decoration = document.createElement('template');
            decoration.innerHTML = sproutDecoration.trim();
            const footer = sidebar.querySelector('.sidebar-footer');
            sidebar.insertBefore(decoration.content.firstElementChild, footer || null);
        }

        if (document.querySelector('.portal-mobile-menu')) return;

        const menuButton = document.createElement('button');
        menuButton.className = 'portal-mobile-menu';
        menuButton.type = 'button';
        menuButton.setAttribute('aria-controls', sidebar.id || 'sidebar');
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.innerHTML = '<i class="fas fa-bars" aria-hidden="true"></i><span>Menu</span>';
        document.body.appendChild(menuButton);

        const overlay = document.createElement('div');
        overlay.className = 'portal-mobile-overlay';
        overlay.setAttribute('aria-hidden', 'true');
        sidebar.insertAdjacentElement('afterend', overlay);

        const setMenuOpen = (open) => {
            sidebar.classList.toggle('mobile-open', open);
            overlay.classList.toggle('visible', open);
            overlay.setAttribute('aria-hidden', String(!open));
            document.body.classList.toggle('portal-menu-open', open);
            menuButton.setAttribute('aria-expanded', String(open));
            menuButton.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
            menuButton.innerHTML = open
                ? '<i class="fas fa-times" aria-hidden="true"></i><span>Close</span>'
                : '<i class="fas fa-bars" aria-hidden="true"></i><span>Menu</span>';
            if (open) sidebar.classList.remove('collapsed');
        };

        menuButton.addEventListener('click', () => {
            setMenuOpen(!sidebar.classList.contains('mobile-open'));
        });
        overlay.addEventListener('click', () => setMenuOpen(false));
        sidebar.addEventListener('click', (event) => {
            if (event.target.closest('a[href]') && window.matchMedia('(max-width: 768px)').matches) {
                setMenuOpen(false);
            }
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && sidebar.classList.contains('mobile-open')) {
                setMenuOpen(false);
                menuButton.focus();
            }
        });
        window.addEventListener('resize', () => {
            if (!window.matchMedia('(max-width: 768px)').matches) setMenuOpen(false);
        });
    }

    window.portalSetSidebarCollapsed = function (collapsed) {
        const sidebar = document.querySelector('.sidebar, .student-sidebar');
        const mainContent = document.querySelector('.main-content');
        if (!sidebar) return;

        sidebar.classList.toggle('collapsed', collapsed);
        if (mainContent) mainContent.classList.toggle('shifted', collapsed);
        try {
            localStorage.setItem('teacher-sidebar-collapsed', collapsed ? '1' : '0');
        } catch (error) {
            console.warn('Unable to save sidebar preference.', error);
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializePortalSidebar, { once: true });
    } else {
        initializePortalSidebar();
    }
})();