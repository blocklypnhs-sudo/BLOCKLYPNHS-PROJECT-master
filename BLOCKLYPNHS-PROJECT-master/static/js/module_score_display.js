(function () {
  const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
  const pointsFor = result => Number.isFinite(Number(result.points))
    ? Number(result.points)
    : Math.max(0, Math.min(10, Math.round(Number(result.score || 0) / 10)));

  window.retryMessage = function (result) {
    if (result.modulePassed) {
      return `This attempt scored below 8/10, but your earlier pass (${pointsFor({score: result.bestScore})}/10) is kept. You can retry to improve.`;
    }
    return 'You need at least 8/10 to pass. Review the lesson, fix your work, and retry.';
  };

  window.renderAssessmentResult = function () {
    const element = document.getElementById('assessmentResult');
    const result = assessmentResultData;
    if (!element || !result) {
      if (element) element.innerHTML = '';
      return;
    }
    const points = pointsFor(result);
    const bestPoints = pointsFor({score: result.bestScore});
    const expected = escapeHtml(result.expected);
    const output = escapeHtml(result.out || '(empty)');
    element.innerHTML = `
      <div class="result-card ${result.passed ? 'pass' : 'fail'}">
        <div class="score">${points}<span style="font-size:1rem">/10</span></div>
        <div class="verdict">${result.passed ? '✓ PASSED' : '✗ BELOW PASS MARK — RETRY REQUIRED'}</div>
        ${result.attempts ? `<div class="detail" style="margin-bottom:6px">Pass mark: 8/10 · Attempt ${Number(result.attempts)}${result.bestScore != null ? ` · Best score: ${bestPoints}/10` : ''}</div>` : ''}
        <div class="detail">
          Your output: <code style="white-space:pre">${output}</code><br>
          Expected: <code style="white-space:pre">${expected}</code><br>
          ${result.passed ? 'Great work! You can view your completion summary.' : retryMessage(result)}
        </div>
        <div style="margin-top:14px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
          <button class="btn-nav secondary" onclick="goStep(1)"><i class="fas fa-book-open"></i> Review Lesson</button>
          <button class="btn-nav${result.passed ? ' secondary' : ''}" onclick="retryAssessment()"><i class="fas fa-redo"></i> Retry Assessment</button>
        </div>
      </div>`;
  };

  window.renderCompletion = function () {
    const result = assessmentResultData;
    const element = document.getElementById('completionContent');
    if (!result || !element) return;
    const date = new Date().toLocaleDateString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric'
    });
    const nextModule = Number(MODULE.number) + 1;
    const nextUrl = nextModule <= 3
      ? `/student_modules/${encodeURIComponent(MODULE.language)}/${nextModule}`
      : '/student_modules';
    const score = result.score == null ? 'Completed' : `${pointsFor(result)}/10`;
    element.innerHTML = `
      <div class="completion-card">
        <div class="trophy">${result.passed ? '🏆' : '📘'}</div>
        <h3>${result.passed ? `Module ${MODULE.number} Complete!` : `Module ${MODULE.number} — Needs Retry`}</h3>
        <div class="stat">Module: <strong>${escapeHtml(MODULE.title)}</strong></div>
        <div class="stat">Final Score: <strong>${score} (${result.passed ? 'Passed' : 'Failed'})</strong></div>
        <div class="stat">Completion Date: <strong>${date}</strong></div>
        <div class="stat">Language: <strong>${escapeHtml(MODULE.language)}</strong></div>
        <div style="margin-top:18px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
          <button class="btn-nav secondary" onclick="window.location.href='/student_progress'">
            <i class="fas fa-chart-line"></i> View Progress
          </button>
          ${result.passed
            ? `<button class="btn-nav" onclick="window.location.href='${nextUrl}'">Next Module <i class="fas fa-arrow-right"></i></button>`
            : `<button class="btn-nav" onclick="goStep(6)"><i class="fas fa-redo"></i> Retry Assessment</button>`}
        </div>
      </div>`;
  };

  const originalToast = window.showToast;
  if (typeof originalToast === 'function') {
    window.showToast = function (message, type) {
      const displayed = String(message).replace(/Score: (\d+)\/100/g, (_, score) =>
        `Score: ${Math.max(0, Math.min(10, Math.round(Number(score) / 10)))}/10`
      ).replace(/pass mark \((\d+)\/100\)/g, 'pass mark (8/10)');
      return originalToast(displayed, type);
    };
  }
})();
