(function () {
    const script = document.currentScript;
    const role = script ? script.dataset.role : '';
    const userName = script ? script.dataset.userName : '';

    const style = document.createElement('style');
    style.textContent = `
        .portal-global-account { position: relative; z-index: 1100; }
        .portal-global-account-trigger {
            display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px;
            border: 1px solid rgba(120, 140, 130, .25); border-radius: 12px;
            background: var(--card-white, #fff); color: var(--text-primary, #10382c);
            font: inherit; font-size: .82rem; font-weight: 700; cursor: pointer;
        }
        .portal-global-account-trigger:hover { border-color: var(--green-accent, #147a54); }
        .portal-global-account-menu {
            display: none; position: absolute; top: calc(100% + 8px); right: 0;
            min-width: 190px; padding: 8px; border: 1px solid var(--border-fresh, #e0ebe4);
            border-radius: 12px; background: var(--card-white, #fff); color: var(--text-primary, #10382c);
            box-shadow: 0 12px 30px rgba(0,0,0,.16);
        }
        .portal-global-account-menu.open { display: block; }
        .portal-global-account-menu a {
            display: block; padding: 9px 10px; border-radius: 8px; color: inherit;
            font-size: .82rem; font-weight: 650; text-decoration: none;
        }
        .portal-global-account-menu a:hover { background: var(--green-soft, #e3f4ec); }
        .portal-global-account-menu a.logout { color: #b42318; }
        .portal-global-account-name { padding: 8px 10px; font-size: .78rem; font-weight: 800; }
        .portal-sidebar {
            box-sizing: border-box; position: fixed; inset: 0 auto 0 0; z-index: 1000;
            width: 232px; height: 100vh; display: flex; flex-direction: column;
            overflow-y: auto; overflow-x: hidden;
            background: linear-gradient(178deg,#0a382a 0%,#0e4a37 55%,#0c4332 100%);
            color: #a9d3c0; box-shadow: 5px 0 26px rgba(8,40,30,.22);
            font-family: inherit;
            transition: width .35s cubic-bezier(.4,0,.2,1);
        }
        .portal-sidebar .sidebar-logo {
            min-height: 88px; padding: 6px 2px; display: flex; flex: 0 0 auto;
            align-items: center; justify-content: center; overflow: hidden;
            position: relative; border-bottom: 1px solid rgba(255,255,255,.06);
        }
        .portal-sidebar .logo-image { width: 76px; height: 76px; object-fit: contain; flex: 0 0 auto; }
        .portal-sidebar .logo-full { min-width: 0; flex: 1; margin-left: -8px; }
        .portal-sidebar .logo-full h2 { margin: 0; color: #fff; font-size: 1.3rem; font-weight: 800; white-space: nowrap; }
        .portal-sidebar .logo-full h2 em { color: #b8e34e; font-style: normal; }
        .portal-sidebar .logo-full p { margin: 1px 0 0; color: #d6f0e4; font-size: .53rem; font-weight: 600; letter-spacing: 1.4px; white-space: nowrap; text-transform: uppercase; }
        .portal-sidebar .logo-mono, .portal-sidebar .hamburger-wrap { display: none; }
        .portal-sidebar .toggle-btn, .portal-sidebar .hamburger-btn {
            width: 34px; height: 34px; display: flex; flex: 0 0 auto;
            align-items: center; justify-content: center; border-radius: 9px;
            border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.08);
            color: #d8efe5; cursor: pointer;
        }
        .portal-sidebar .toggle-btn { position: absolute; top: 50%; right: 8px; transform: translateY(-50%); }
        .portal-sidebar .hamburger-wrap { padding: 8px 0 4px; justify-content: center; }
        .portal-sidebar .sidebar-nav { min-height: 0; flex: 1; padding: 4px 0; }
        .portal-sidebar .nav-section-label {
            padding: 14px 18px 5px; color: rgba(190,225,208,.45);
            font-size: .56rem; font-weight: 700; letter-spacing: 1.4px; text-transform: uppercase;
        }
        .portal-sidebar .nav-item { position: relative; margin: 0 0 3px; }
        .portal-sidebar .nav-link-custom {
            width: calc(100% - 16px); min-height: 38px; margin: 0 8px; padding: 8px 12px;
            display: flex; align-items: center; gap: 11px; border: 0; border-radius: 999px;
            background: transparent; color: #a9d3c0; font: inherit; font-size: .82rem;
            font-weight: 600; text-align: left; text-decoration: none; white-space: nowrap;
        }
        .portal-sidebar .nav-link-custom:hover { background: rgba(255,255,255,.08); color: #fff; }
        .portal-sidebar .nav-link-custom.active {
            background: #fff; color: #12604a; font-weight: 650;
            box-shadow: 0 4px 16px rgba(0,0,0,.1);
        }
        .portal-sidebar .nav-link-custom > i { width: 20px; flex: 0 0 20px; font-size: 1rem; text-align: center; }
        body.portal-teacher-sidebar > .app {
            width: calc(100% - 232px); max-width: none; margin: 0 0 0 232px;
        }
        body.portal-teacher-sidebar > main {
            width: calc(100% - 232px); max-width: none; margin: 0 0 0 232px;
        }
        body.portal-sidebar-collapsed > .app,
        body.portal-sidebar-collapsed > main {
            width: calc(100% - 70px); margin-left: 70px;
        }
        .portal-sidebar.collapsed { width: 70px; }
        .portal-sidebar.collapsed .logo-image,
        .portal-sidebar.collapsed .logo-full,
        .portal-sidebar.collapsed .toggle-btn { display: none; }
        .portal-sidebar.collapsed .logo-mono { display: flex; width: 40px; height: 40px; }
        .portal-sidebar.collapsed .logo-mono img { width: 40px; height: 40px; object-fit: contain; }
        .portal-sidebar.collapsed .hamburger-wrap { display: flex; }
        .portal-sidebar.collapsed .nav-text,
        .portal-sidebar.collapsed .nav-section-label { display: none; }
        .portal-sidebar.collapsed .nav-link-custom { width: 54px; justify-content: center; padding: 8px 0; }
        @media (max-width: 768px) {
            .portal-sidebar { width: 70px; }
            .portal-sidebar:not(.collapsed) { width: min(232px, 85vw); }
            .portal-sidebar:not(.collapsed) .logo-image,
            .portal-sidebar:not(.collapsed) .logo-full,
            .portal-sidebar:not(.collapsed) .toggle-btn { display: flex; }
            .portal-sidebar:not(.collapsed) .logo-image { display: block; }
            .portal-sidebar:not(.collapsed) .logo-mono,
            .portal-sidebar:not(.collapsed) .hamburger-wrap { display: none; }
            .portal-sidebar:not(.collapsed) .nav-text { display: inline !important; }
            .portal-sidebar:not(.collapsed) .nav-section-label { display: block; }
            .portal-sidebar:not(.collapsed) .nav-link-custom { width: calc(100% - 16px); justify-content: flex-start; padding: 8px 12px; }
            body.portal-teacher-sidebar > .app,
            body.portal-teacher-sidebar > main,
            body.portal-sidebar-collapsed > .app,
            body.portal-sidebar-collapsed > main { width: calc(100% - 70px); margin-left: 70px; }
        }
    `;
    document.head.appendChild(style);

    function teacherNavigation() {
        function link(path, icon, label) {
            return `<div class="nav-item"><a href="${path}" class="nav-link-custom" data-nav-path="${path}"><i class="fa-solid ${icon}" aria-hidden="true"></i><span class="nav-text">${label}</span></a></div>`;
        }
        return `
            <div class="nav-section-label">Overview</div>
            ${link('/teacher_dashboard', 'fa-table-cells-large', 'Dashboard')}
            ${link('/teacher_leaderboard', 'fa-trophy', 'Leaderboard')}
            ${link('/teacher_students', 'fa-users', 'Students')}
            ${link('/teacher_score_results', 'fa-clipboard-check', 'Student Scores')}
            ${link('/assessments_result', 'fa-file-circle-check', 'Assessment Results')}
            <div class="nav-section-label">Insights</div>
            ${link('/teacher_reports_analytics', 'fa-chart-line', 'Reports & Analytics')}
            ${link('/teacher_feedback_analytics', 'fa-message', 'Feedback Analytics')}
            <div class="nav-section-label">Account</div>
            ${link('/teacher_profile', 'fa-circle-user', 'Profile')}
            ${link('/teacher_settings', 'fa-sliders', 'Settings')}`;
    }

    function installNavigation() {
        const path = window.location.pathname;
        if (role === 'teacher' && !document.querySelector('aside.sidebar')) {
            const sidebar = document.createElement('aside');
            const startCollapsed = window.innerWidth <= 768;
            sidebar.className = `portal-sidebar${startCollapsed ? ' collapsed' : ''}`;
            sidebar.setAttribute('aria-label', 'Teacher navigation');
            sidebar.innerHTML = `
                <div class="sidebar-logo">
                    <img src="/static/BL-LOGO.png" alt="BlockLearn Logo" class="logo-image">
                    <div class="logo-full"><h2>Block<em>Learn</em></h2><p>PNHS · ICT Studio</p></div>
                    <div class="logo-mono"><img src="/static/BL-LOGO.png" alt="BlockLearn Logo"></div>
                    <button class="toggle-btn" type="button" aria-label="Collapse sidebar"><i class="fa-solid fa-angles-left" aria-hidden="true"></i></button>
                </div>
                <div class="hamburger-wrap">
                    <button class="hamburger-btn" type="button" aria-label="Expand sidebar"><i class="fa-solid fa-bars" aria-hidden="true"></i></button>
                </div>
                <nav class="sidebar-nav" aria-label="Teacher navigation"></nav>`;
            document.body.insertBefore(sidebar, document.body.firstChild);
            document.body.classList.add('portal-teacher-sidebar');
            if (startCollapsed) document.body.classList.add('portal-sidebar-collapsed');
            let nav = sidebar.querySelector('.sidebar-nav');
            nav.innerHTML = teacherNavigation();
            nav.querySelectorAll('[data-nav-path]').forEach(link => {
                if (link.dataset.navPath === path) {
                    link.classList.add('active');
                    link.setAttribute('aria-current', 'page');
                }
            });
            sidebar.querySelector('.toggle-btn').addEventListener('click', () => {
                sidebar.classList.add('collapsed');
                document.body.classList.add('portal-sidebar-collapsed');
            });
            sidebar.querySelector('.hamburger-btn').addEventListener('click', () => {
                sidebar.classList.remove('collapsed');
                document.body.classList.remove('portal-sidebar-collapsed');
            });
            window.addEventListener('resize', () => {
                if (window.innerWidth <= 768) {
                    sidebar.classList.add('collapsed');
                    document.body.classList.add('portal-sidebar-collapsed');
                }
            });
        }
    }

    function appendSignOut(menu) {
        if (!menu || menu.querySelector('a[href="/logout"]')) return;
        const link = document.createElement('a');
        link.href = '/logout';
        link.className = menu.querySelector('.pd-links') ? 'pd-link logout'
            : menu.querySelector('.ud-body') ? 'ud-item logout'
                : menu.classList.contains('account-dropdown') ? 'account-menu-link logout'
                    : 'logout';
        link.textContent = 'Sign Out';
        const group = menu.querySelector('.pd-links, .ud-body') || menu;
        const separator = document.createElement('div');
        separator.className = menu.querySelector('.pd-links') ? 'pd-sep' : 'portal-account-separator';
        group.append(separator, link);
    }

    function installAccountMenu() {
        const roleLabel = role === 'ict' ? 'ICT Support' : role === 'teacher' ? 'Teacher' : 'Student';
        const name = userName || roleLabel;
        const menus = document.querySelectorAll('.profile-dropdown, .account-dropdown, .user-dropdown');
        menus.forEach(appendSignOut);
        if (menus.length || document.querySelector('.module-profile')) return;

        const topbar = document.querySelector('.top-bar-right, .topbar-actions, .top-bar, .topbar');
        if (!topbar) return;
        const wrap = document.createElement('div');
        wrap.className = 'portal-global-account';
        wrap.innerHTML = `
            <button type="button" class="portal-global-account-trigger" aria-expanded="false">
                <i class="fas fa-user-circle" aria-hidden="true"></i>
                <span class="portal-global-account-name"></span>
                <i class="fas fa-chevron-down" aria-hidden="true"></i>
            </button>
            <div class="portal-global-account-menu" role="menu">
                <div class="portal-global-account-name"></div>
                <a class="logout" href="/logout" role="menuitem">Sign Out</a>
            </div>`;
        wrap.querySelectorAll('.portal-global-account-name').forEach(element => {
            element.textContent = name;
        });
        const button = wrap.querySelector('button');
        const menu = wrap.querySelector('.portal-global-account-menu');
        button.addEventListener('click', () => {
            const open = menu.classList.toggle('open');
            button.setAttribute('aria-expanded', String(open));
        });
        document.addEventListener('click', event => {
            if (!wrap.contains(event.target)) {
                menu.classList.remove('open');
                button.setAttribute('aria-expanded', 'false');
            }
        });
        topbar.appendChild(wrap);
    }

    function describeTarget(element) {
        const ariaLabel = element.getAttribute('aria-label');
        const title = element.getAttribute('title');
        const label = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`) : null;
        return (ariaLabel || title || (label && label.textContent) || element.innerText || element.name || '')
            .replace(/\s+/g, ' ')
            .trim()
            .slice(0, 120);
    }

    function auditEvent(eventType, element) {
        const label = describeTarget(element);
        fetch('/audit/ui-event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            keepalive: true,
            body: JSON.stringify({
                event: eventType,
                element: element.tagName.toLowerCase() === 'a' ? 'a'
                    : element.tagName.toLowerCase() === 'button' ? 'button'
                        : element.tagName.toLowerCase() === 'input' ? 'input'
                            : element.tagName.toLowerCase() === 'select' ? 'select'
                                : element.tagName.toLowerCase() === 'textarea' ? 'textarea'
                                    : element.tagName.toLowerCase() === 'summary' ? 'summary' : 'interactive',
                label,
                page: window.location.pathname
            })
        }).then(response => {
            if (!response.ok) console.warn('UI audit event was not recorded:', response.status);
        }).catch(error => console.warn('UI audit request failed:', error));
    }

    function installAuditListeners() {
        document.addEventListener('click', event => {
            const target = event.target.closest('a, button, summary, [role="button"], [onclick]');
            if (target) auditEvent('click', target);
        }, true);
        document.addEventListener('change', event => {
            const target = event.target.closest('input, select, textarea');
            if (target) auditEvent('change', target);
        }, true);
    }

    installNavigation();
    installAccountMenu();
    installAuditListeners();
})();
