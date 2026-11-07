/* BlockLearn mobile navigation (phones <= 768px). Pairs with /static/mobile.css */
(function () {
  'use strict';
  var mq = window.matchMedia('(max-width: 768px)');
  var ICONS = {"house": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><path d=\"M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8\"/><path d=\"M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z\"/></g>", "clipboard-list": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><rect width=\"8\" height=\"4\" x=\"8\" y=\"2\" rx=\"1\" ry=\"1\"/><path d=\"M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2m4 7h4m-4 5h4m-8-5h.01M8 16h.01\"/></g>", "puzzle": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M15.39 4.39a1 1 0 0 0 1.68-.474a2.5 2.5 0 1 1 3.014 3.015a1 1 0 0 0-.474 1.68l1.683 1.682a2.414 2.414 0 0 1 0 3.414L19.61 15.39a1 1 0 0 1-1.68-.474a2.5 2.5 0 1 0-3.014 3.015a1 1 0 0 1 .474 1.68l-1.683 1.682a2.414 2.414 0 0 1-3.414 0L8.61 19.61a1 1 0 0 0-1.68.474a2.5 2.5 0 1 1-3.014-3.015a1 1 0 0 0 .474-1.68l-1.683-1.682a2.414 2.414 0 0 1 0-3.414L4.39 8.61a1 1 0 0 1 1.68.474a2.5 2.5 0 1 0 3.014-3.015a1 1 0 0 1-.474-1.68l1.683-1.682a2.414 2.414 0 0 1 3.414 0z\"/>", "chart-no-axes-combined": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M12 16v5m4-6.361V21m4-10.344V21m2-18l-8.646 8.646a.5.5 0 0 1-.708 0L9.354 8.354a.5.5 0 0 0-.707 0L2 15m2 3.463V21m4-6.344V21\"/>", "ellipsis": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><circle cx=\"12\" cy=\"12\" r=\"1\"/><circle cx=\"19\" cy=\"12\" r=\"1\"/><circle cx=\"5\" cy=\"12\" r=\"1\"/></g>", "circle-user-round": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><path d=\"M17.925 20.056a6 6 0 0 0-11.851.001\"/><circle cx=\"12\" cy=\"11\" r=\"4\"/><circle cx=\"12\" cy=\"12\" r=\"10\"/></g>", "sliders-horizontal": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M10 5H3m9 14H3M14 3v4m2 10v4m5-9h-9m9 7h-5m5-14h-7m-6 5v4m0-2H3\"/>", "trophy": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><path d=\"M10 14.66V17a1 1 0 0 1-1 1a2 2 0 0 0-2 2v2m7-7.34V17a1 1 0 0 0 1 1a2 2 0 0 1 2 2v2m.916-12H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3M4 22h16\"/><path d=\"M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z\"/><path d=\"M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3\"/></g>", "circle-help": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3m.08 4h.01\"/></g>", "ticket": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Zm11-4v2m0 10v2m0-8v2\"/>", "bell": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M10.268 21a2 2 0 0 0 3.464 0m-10.47-5.674A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326\"/>", "moon": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401\"/>", "sun": "<g fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\"><circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41\"/></g>", "log-out": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"m16 17l5-5l-5-5m5 5H9m0 9H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4\"/>", "x": "<path fill=\"none\" stroke=\"currentColor\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M18 6L6 18M6 6l12 12\"/>"};

  function svg(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || '') + '</svg>';
  }

  var TABS = [
    { href: '/student_dashboard',  label: 'Home',       icon: 'house',                  match: ['/student_dashboard'] },
    { href: '/module_assessments', label: 'Learn',      icon: 'clipboard-list',         match: ['/module_assessments', '/student_modules', '/student_assessments', '/python_assessments', '/java_assessments'] },
    { href: '/student_activities', label: 'Activities', icon: 'puzzle',                 match: ['/student_activities'] },
    { href: '/student_progress',   label: 'Progress',   icon: 'chart-no-axes-combined', match: ['/student_progress'] }
  ];
  var MORE = [
    { href: '/student_profile',     label: 'Profile',        icon: 'circle-user-round' },
    { href: '/student_settings',    label: 'Settings',       icon: 'sliders-horizontal' },
    { href: '/student_leaderboard', label: 'Leaderboard',    icon: 'trophy' },
    { href: '/student_help',        label: 'Help & FAQ',     icon: 'circle-help' },
    { href: '/student_tickets',     label: 'Support Tickets', icon: 'ticket' },
    { href: '/notifications',       label: 'Notifications',  icon: 'bell' }
  ];

  function onPath(item) {
    var p = location.pathname.replace(/\/+$/, '') || '/';
    return (item.match || [item.href]).some(function (m) { return p === m || p.indexOf(m + '/') === 0 || p.indexOf(m + '_') === 0; });
  }

  function studentName() {
    var el = document.querySelector('.profile-trigger-info strong, .profile-trigger-info .name, .profile-trigger-info span, .sidebar-user-info h4, .sidebar-user-info strong');
    var name = el && el.textContent.trim();
    return name || 'Student';
  }
  function studentMeta() {
    var el = document.querySelector('.profile-trigger-info small, .profile-trigger-info p, .sidebar-user-info p');
    return (el && el.textContent.trim()) || 'BlockLearn student';
  }

  function build() {
    if (document.querySelector('.bl-bottom-nav')) return;
    var moreActive = MORE.some(onPath);

    var nav = document.createElement('nav');
    nav.className = 'bl-bottom-nav';
    nav.setAttribute('aria-label', 'Main navigation');
    nav.innerHTML = TABS.map(function (t) {
      return '<a class="bl-tab' + (onPath(t) ? ' active' : '') + '" href="' + t.href + '"' + (onPath(t) ? ' aria-current="page"' : '') + '>' +
        '<div class="bl-pill">' + svg(t.icon) + '</div><span>' + t.label + '</span></a>';
    }).join('') +
      '<button type="button" class="bl-tab' + (moreActive ? ' active' : '') + '" id="blMoreBtn" aria-haspopup="dialog" aria-expanded="false">' +
      '<div class="bl-pill">' + svg('ellipsis') + '</div><span>More</span></button>';

    var backdrop = document.createElement('div');
    backdrop.className = 'bl-sheet-backdrop';

    var sheet = document.createElement('div');
    sheet.className = 'bl-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-label', 'More');
    var name = studentName();
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    sheet.innerHTML =
      '<div class="bl-sheet-grab"></div>' +
      '<div class="bl-sheet-user"><div class="bl-avatar">' + (name.charAt(0).toUpperCase() || 'S') + '</div>' +
      '<div><strong></strong><small></small></div></div>' +
      '<div class="bl-sheet-list">' +
      MORE.map(function (m) {
        return '<a class="bl-sheet-link' + (onPath(m) ? ' active' : '') + '" href="' + m.href + '">' + svg(m.icon) + '<span>' + m.label.replace('&', '&amp;') + '</span></a>';
      }).join('') +
      '<button type="button" class="bl-sheet-link" id="blThemeBtn">' + svg(dark ? 'sun' : 'moon') + '<span>' + (dark ? 'Light mode' : 'Dark mode') + '</span></button>' +
      '<a class="bl-sheet-link danger" href="/logout">' + svg('log-out') + '<span>Sign out</span></a>' +
      '</div>';
    sheet.querySelector('strong').textContent = name;
    sheet.querySelector('small').textContent = studentMeta();

    document.body.appendChild(nav);
    document.body.appendChild(backdrop);
    document.body.appendChild(sheet);
    document.body.classList.add('bl-has-nav');

    var btn = nav.querySelector('#blMoreBtn');
    function refreshThemeLabel() {
      var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      var tb = sheet.querySelector('#blThemeBtn');
      tb.innerHTML = svg(isDark ? 'sun' : 'moon') + '<span>' + (isDark ? 'Light mode' : 'Dark mode') + '</span>';
    }
    function setOpen(open) {
      if (open) refreshThemeLabel();
      document.body.classList.toggle('bl-sheet-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    btn.addEventListener('click', function () { setOpen(!document.body.classList.contains('bl-sheet-open')); });
    backdrop.addEventListener('click', function () { setOpen(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });

    // Dark mode: reuse the page's own theme button so preference handling stays in one place
    sheet.querySelector('#blThemeBtn').addEventListener('click', function () {
      var pageBtn = document.querySelector('.theme-btn');
      if (pageBtn) { pageBtn.click(); }
      else {
        var html = document.documentElement;
        if (html.getAttribute('data-theme') === 'dark') html.removeAttribute('data-theme');
        else html.setAttribute('data-theme', 'dark');
      }
      setOpen(false);
    });
  }

  // Wide tables scroll inside their own box instead of stretching the page
  function wrapTables() {
    document.querySelectorAll('.main-content table, main table').forEach(function (t) {
      var p = t.parentElement;
      if (!p || p.classList.contains('bl-scroll-x')) return;
      var cs = getComputedStyle(p);
      if (/(auto|scroll)/.test(cs.overflowX)) return;
      var wrap = document.createElement('div');
      wrap.className = 'bl-scroll-x';
      p.insertBefore(wrap, t);
      wrap.appendChild(t);
    });
  }

  function init() {
    if (!mq.matches) return;
    build();
    wrapTables();
    // Tables are often drawn after data loads
    var tries = 0, timer = setInterval(function () { wrapTables(); if (++tries > 8) clearInterval(timer); }, 800);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  // Rotating a tablet or resizing across the breakpoint builds the bar when needed
  if (mq.addEventListener) mq.addEventListener('change', init);
})();
