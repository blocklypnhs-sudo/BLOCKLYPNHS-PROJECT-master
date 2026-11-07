// static/js/module_awards.js
// Renders module progress, item badges, and certificate status on the dashboard.

(function () {
  'use strict';
  const ITEM_BADGE_CODE_PATTERN = /^(python_a|java_a|javascript_act|cpp_act|php_act)[1-5]$/;

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === 'class') node.className = v;
      else if (k === 'style') node.setAttribute('style', v);
      else if (k.startsWith('data-')) node.setAttribute(k, v);
      else node.setAttribute(k, v);
    });
    (children || []).forEach(c => {
      if (typeof c === 'string') node.appendChild(document.createTextNode(c));
      else if (c) node.appendChild(c);
    });
    return node;
  }

  function findCard(language) {
    return document.querySelector(`.dashboard-module-card[data-language="${language}"]`);
  }

  function renderModuleBlock(mod) {
    const itemsBadges = (mod.items.list || []).map(item => {
      const earned = !!mod.badges[item.badge_code];
      const label = item.badge_code
        .replace(mod.language + '_', '')
        .replace('_a', 'A').replace('_act', 'Act');
      const badgeAttributes = {
        class: 'mod-badge ' + (earned ? 'earned' : 'locked'),
        title: earned
          ? `${item.title} — Passed`
          : `${item.title} — ${item.passed ? 'Passed' : 'Not yet passed'}`,
      };
      if (earned) {
        badgeAttributes.href = `/item_badge/${item.badge_code}`;
        badgeAttributes['aria-label'] = `View earned badge: ${item.title}`;
      }
      return el(earned ? 'a' : 'span', badgeAttributes, [earned ? '🏅 ' + label : '🔒 ' + label]);
    });

    const lessonsDone = mod.lessons.done;
    const lessonLine = `Lessons: ${lessonsDone}/${mod.lessons.total}`;
    const itemLine = `Items: ${mod.items.passed}/${mod.items.total}`;

    const children = [
      el('div', { class: 'mod-awards-stats' }, [
        el('span', {
          class: lessonsDone >= mod.lessons.total ? 'done' : '',
          title: 'Lessons marked complete',
        }, [lessonLine]),
        el('span', { class: mod.items.passed >= mod.items.total && mod.items.total > 0 ? 'done' : '' }, [itemLine]),
      ]),
      el('div', { class: 'mod-awards-badges' }, itemsBadges),
    ];

    if (mod.module_assessments && mod.module_assessments.total > 0) {
      const finalsProgress = mod.module_assessments.passed;
      children.splice(1, 0, el('div', { class: 'mod-awards-stats' }, [
        el('span', {
          class: finalsProgress >= mod.module_assessments.total ? 'done' : '',
          title: 'Passed module finals',
        }, [`Module finals: ${finalsProgress}/${mod.module_assessments.total}`]),
      ]));
    }

    if (mod.complete) {
      children.splice(1, 0, el('div', { class: 'mod-awards-stats' }, [
        el('span', { class: 'done' }, ['Module status: Complete']),
      ]));
    }

    if (mod.certificate.available) {
      children.push(el('div', { class: 'mod-awards-cert' }, [
        el('a', {
          class: 'cert-link',
          href: `/module_certificate/${mod.language}`,
        }, ['📜 View Certificate']),
      ]));
    } else if (mod.complete) {
      children.push(el('div', { class: 'mod-awards-cert pending' }, [
        '📜 Certificate pending',
      ]));
    } else {
      children.push(el('div', { class: 'mod-awards-cert locked' }, [
        '📜 Certificate locked — complete both lessons and pass all 5 items to unlock it',
      ]));
    }

    return el('div', { class: 'module-awards', 'data-injected': 'true' }, children);
  }

  function showNewBadgeToast(badgeCode) {
    const toast = el('div', { class: 'awards-toast' }, [
      `🏅 New badge unlocked: ${badgeCode}`,
    ]);
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 50);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function injectStyles() {
    if (document.getElementById('module-awards-styles')) return;
    const style = document.createElement('style');
    style.id = 'module-awards-styles';
    style.textContent = `
      .module-awards {
        margin: 0 10px 10px 54px;
        padding: 0;
        font-size: 13px;
      }
      .mod-awards-stats { display: flex; gap: 12px; color: #666; margin-bottom: 8px; }
      .mod-awards-stats .done { color: #22a06b; font-weight: 600; }
      .mod-awards-badges { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
      .mod-badge { font-size: 11px; padding: 3px 8px; border-radius: 10px; white-space: nowrap; }
      .mod-badge.earned { text-decoration: none; }
      .mod-badge.earned:hover { filter: brightness(0.95); }
      .mod-badge.earned { background: #fff4d6; color: #8a6d0f; border: 1px solid #e5d9a7; }
      .mod-badge.locked { background: #eef2f7; color: #999; border: 1px solid #dde6f3; }
      .mod-awards-cert a {
        display: inline-block; margin-top: 4px; font-size: 12px;
        text-decoration: none; color: #4a90e2;
      }
      .mod-awards-cert a:hover { text-decoration: underline; }
      .mod-awards-cert.locked { color: #999; font-size: 12px; }
      .mod-awards-cert.pending { color: #c9a227; font-size: 12px; }
      .awards-toast {
        position: fixed; bottom: -100px; left: 50%; transform: translateX(-50%);
        background: #1a2740; color: #fff; padding: 12px 22px; border-radius: 8px;
        font-size: 14px; box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        transition: bottom 0.3s ease; z-index: 9999;
      }
      .awards-toast.show { bottom: 30px; }
    `;
    document.head.appendChild(style);
  }

  async function loadAwards() {
    injectStyles();
    let payload;
    try {
      const res = await fetch('/api/module_awards', { credentials: 'same-origin' });
      payload = await res.json();
    } catch (err) {
      console.warn('[module_awards] fetch failed:', err);
      return;
    }
    if (!payload || !payload.success) return;

    // Inject per-module block into each language card
    payload.modules.forEach(mod => {
      const card = findCard(mod.language);
      if (!card) return;
      const existing = card.querySelector('[data-injected="true"]');
      if (existing) existing.remove();
      const block = renderModuleBlock(mod);
      card.appendChild(block);
    });

    // Toast for last submission's new badges
    try {
      const raw = sessionStorage.getItem('new_badges');
      if (raw) {
        const codes = JSON.parse(raw);
        if (Array.isArray(codes)) {
          codes.filter(code => ITEM_BADGE_CODE_PATTERN.test(code))
            .forEach((code, i) => setTimeout(() => showNewBadgeToast(code), i * 700));
        }
        sessionStorage.removeItem('new_badges');
      }
    } catch (e) { /* noop */ }
  }

  window.addEventListener('moduleprogresschange', loadAwards);
  window.addEventListener('storage', function (event) {
    if (event.key === 'progress_updated' || event.key === 'student_dashboard_refresh') loadAwards();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAwards);
  } else {
    loadAwards();
  }
})();