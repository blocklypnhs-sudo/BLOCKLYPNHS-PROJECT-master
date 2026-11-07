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

    function initializePortalSidebar() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;

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
        const sidebar = document.querySelector('.sidebar');
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