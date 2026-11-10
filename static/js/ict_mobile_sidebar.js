(() => {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar || document.querySelector('.portal-mobile-menu')) return;

    const menuButton = document.createElement('button');
    menuButton.className = 'portal-mobile-menu';
    menuButton.type = 'button';
    menuButton.setAttribute('aria-controls', sidebar.id || 'sidebar');
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.setAttribute('aria-label', 'Open navigation menu');
    menuButton.innerHTML = '<iconify-icon icon="lucide:menu" aria-hidden="true"></iconify-icon><span>Menu</span>';
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
            ? '<iconify-icon icon="lucide:x" aria-hidden="true"></iconify-icon><span>Close</span>'
            : '<iconify-icon icon="lucide:menu" aria-hidden="true"></iconify-icon><span>Menu</span>';
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
        if (window.matchMedia('(max-width: 768px)').matches) return;
        setMenuOpen(false);
        if (!sidebar.classList.contains('ict-notifications-sidebar')) {
            const collapsed = localStorage.getItem('bl-ict-sidebar') === '1';
            sidebar.classList.toggle('collapsed', collapsed);
            document.querySelector('.main-content')?.classList.toggle('shifted', collapsed);
        }
    });
})();
