(function () {
    'use strict';

    // Keep one extra history entry so Back returns to this dashboard URL.
    history.replaceState({ dashboard: true }, document.title, window.location.href);
    history.pushState({ dashboard: true }, document.title, window.location.href);

    window.addEventListener('popstate', function () {
        history.go(1);
    });
})();