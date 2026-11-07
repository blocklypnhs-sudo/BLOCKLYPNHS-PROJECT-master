(function () {
    const style = document.createElement('style');
    style.textContent = `
        .score-breakdown {
            margin-top: 14px; padding: 12px; border: 1px solid var(--border-fresh, #e0ebe4);
            border-radius: 12px; background: var(--bg-main, #f7fbf9); text-align: left;
        }
        .score-breakdown h4 { margin: 0 0 8px; color: var(--text-primary, #10382c); font-size: .85rem; font-weight: 800; }
        .score-breakdown-details { margin-top: 10px; text-align: left; }
        .score-breakdown-details summary {
            color: var(--text-secondary, #3f5f52); cursor: pointer; font-size: .8rem;
            font-weight: 750; padding: 6px 0;
        }
        .score-breakdown-details .score-breakdown { margin-top: 6px; }
        .score-breakdown-table-wrap { overflow-x: auto; }
        .score-breakdown table { width: 100%; border-collapse: collapse; font-size: .72rem; }
        .score-breakdown th, .score-breakdown td {
            padding: 6px; border-bottom: 1px solid var(--border-fresh, #e0ebe4);
            text-align: left; vertical-align: top;
        }
        .score-breakdown th { color: var(--text-secondary, #3f5f52); font-size: .62rem; text-transform: uppercase; }
        .score-breakdown small {
            display: block; margin-top: 3px; color: var(--text-secondary, #3f5f52);
            white-space: pre-wrap; overflow-wrap: anywhere;
        }
        .score-correct { color: #15803d; font-weight: 800; }
        .score-incorrect { color: #b91c1c; font-weight: 800; }
        .score-attempt-feedback {
            position: fixed; inset: 0; z-index: 10000; display: grid; place-items: center;
            padding: 16px; background: rgba(8, 24, 18, .56);
        }
        .score-attempt-feedback-card {
            position: relative; width: min(680px, 100%); max-height: min(88vh, 760px);
            overflow-y: auto; padding: 22px; border-radius: 16px; background: #fff;
            color: #10382c; box-shadow: 0 20px 60px rgba(0, 0, 0, .28);
        }
        .score-attempt-feedback-card h2 { margin: 0; padding-right: 32px; font-size: 1.2rem; font-weight: 850; }
        .score-attempt-feedback-card > p { margin: 7px 0; color: #52705f; font-size: .86rem; }
        .score-attempt-feedback-card .score-attempt-feedback-status { color: #10382c; }
        .score-attempt-feedback-close {
            position: absolute; top: 12px; right: 12px; width: 34px; height: 34px;
            border: 0; border-radius: 9px; background: #eef6f1; color: #10382c;
            font-size: 1.35rem; cursor: pointer;
        }
        .score-attempt-feedback-return {
            margin-top: 14px; padding: 9px 16px; border: 0; border-radius: 999px;
            background: #12604a; color: #fff; font: inherit; font-size: .82rem;
            font-weight: 750; cursor: pointer;
        }
        @media (max-width: 520px) {
            .score-attempt-feedback-card { padding: 18px 14px; }
            .score-breakdown th, .score-breakdown td { padding: 5px 4px; }
        }
    `;
    document.head.appendChild(style);

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            }[char];
        });
    }

    window.renderScoreBreakdown = function (breakdown) {
        if (!Array.isArray(breakdown) || breakdown.length === 0) return '';
        return `
            <section class="score-breakdown" aria-label="Score breakdown">
                <h4>Task scoring guide · 10 whole-number points</h4>
                <div class="score-breakdown-table-wrap">
                    <table>
                        <thead><tr><th>Question / criterion</th><th>Result</th><th>Points</th></tr></thead>
                        <tbody>${breakdown.map(function (item) {
                            const result = item.correct === true
                                ? '<span class="score-correct">Correct</span>'
                                : item.correct === false
                                    ? '<span class="score-incorrect">Incorrect</span>'
                                    : '<span>Needs review</span>';
                            return `<tr>
                                <td>${item.criterion_number ? `${escapeHtml(item.criterion_number)}. ` : ''}${escapeHtml(item.criterion)}</td>
                                <td>${result}<small>${escapeHtml(item.feedback)}</small>
                                    <small>Expected: ${escapeHtml(item.expected_answer)}</small>
                                    <small>Your answer: ${escapeHtml(item.student_answer)}</small>
                                </td>
                                <td>${escapeHtml(item.points_earned)} / ${escapeHtml(item.max_points)}</td>
                            </tr>`;
                        }).join('')}</tbody>
                    </table>
                </div>
            </section>`;
    };

    window.showScoreAttemptFeedback = function (result, activityTitle, options) {
        const previous = document.getElementById('scoreAttemptFeedback');
        if (previous) previous.remove();

        options = options || {};
        const passed = result.status === 'completed' || result.passed === true;
        const perfectScore = Number(result.score) === 100;
        const needsReview = result.status === 'pending_review';
        const heading = perfectScore ? 'Perfect score!' : passed ? 'Passed!' : needsReview ? 'Submitted for review' : 'Not quite — try again';
        const feedback = document.createElement('div');
        feedback.id = 'scoreAttemptFeedback';
        feedback.className = 'score-attempt-feedback';
        feedback.setAttribute('role', 'dialog');
        feedback.setAttribute('aria-modal', 'true');
        feedback.setAttribute('aria-labelledby', 'scoreAttemptFeedbackTitle');
        feedback.innerHTML = `
            <section class="score-attempt-feedback-card">
                <button class="score-attempt-feedback-close" type="button" aria-label="Close feedback">&times;</button>
                <h2 id="scoreAttemptFeedbackTitle">${escapeHtml(heading)}</h2>
                <p>${escapeHtml(activityTitle || 'Activity')} · ${escapeHtml(result.points)} / ${escapeHtml(result.max_points)} points</p>
                <p class="score-attempt-feedback-status">${needsReview
                    ? 'Your answer needs teacher review. You can continue working in this activity.'
                    : passed
                        ? perfectScore
                            ? 'Every expected output line matched.'
                            : 'You met the pass mark. Review the criterion-by-criterion points below.'
                        : 'Your answer did not meet the expected result. Review the details, then return to the activity and retry.'}</p>
                ${window.renderScoreBreakdown(result.answer_breakdown)}
                <button class="score-attempt-feedback-return" type="button">${passed && options.returnLabel
                    ? escapeHtml(options.returnLabel)
                    : passed ? 'Return to Activity' : 'Return to Activity and Retry'}</button>
            </section>`;
        document.body.appendChild(feedback);

        function closeFeedback() {
            feedback.remove();
            document.removeEventListener('keydown', onKeyDown);
        }
        function onKeyDown(event) {
            if (event.key === 'Escape') closeFeedback();
        }
        feedback.querySelector('.score-attempt-feedback-close').addEventListener('click', closeFeedback);
        feedback.querySelector('.score-attempt-feedback-return').addEventListener('click', function () {
            if (passed && options.returnUrl) {
                window.location.href = options.returnUrl;
                return;
            }
            closeFeedback();
        });
        feedback.addEventListener('click', function (event) {
            if (event.target === feedback) closeFeedback();
        });
        document.addEventListener('keydown', onKeyDown);
        feedback.querySelector('.score-attempt-feedback-return').focus();
    };
})();
