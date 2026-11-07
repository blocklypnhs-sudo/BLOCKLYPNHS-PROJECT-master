(function () {
  'use strict';

  var page = document.body;
  var language = page.dataset.moduleLanguage;
  var lessonNumber = Number(page.dataset.lessonNumber);

  if (!language || !Number.isInteger(lessonNumber)) return;

  function saveCompletion(button, restoreExistingState) {
    return fetch('/mark_lesson_complete', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: language, lesson_number: lessonNumber }),
    }).then(function (response) {
      return response.json().then(function (payload) {
        if (!response.ok || !payload.success) {
          throw new Error(payload.message || 'Could not save lesson completion.');
        }
        return payload;
      });
    }).then(function (payload) {
      if (!restoreExistingState && typeof window.markSectionComplete === 'function') {
        window.markSectionComplete('lesson');
      }
      try {
        if (payload.new_badges && payload.new_badges.length) {
          sessionStorage.setItem('new_badges', JSON.stringify(payload.new_badges));
        }
        localStorage.setItem('progress_updated', Date.now().toString());
      } catch (error) {}
      button.classList.add('done');
      button.disabled = true;
      button.innerHTML = '<i class="fas fa-check-circle"></i> Lesson Completed';

      var nextStep = Number(button.dataset.nextStep);
      if (nextStep && typeof window.goStep === 'function') window.goStep(nextStep);
    }).catch(function (error) {
      console.error('[lesson_completion]', error);
      if (!restoreExistingState) {
        button.disabled = false;
        button.removeAttribute('aria-busy');
        button.innerHTML = '<i class="fas fa-rotate-right"></i> Could not save. Retry';
      }
    });
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-mark-lesson-complete]');
    if (!button || button.disabled) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveCompletion(button, false);
  }, true);

  document.addEventListener('DOMContentLoaded', function () {
    var existingButton = document.querySelector(
      '.btn-mark-complete[data-section="lesson"].done[data-mark-lesson-complete]'
    );
    if (existingButton) saveCompletion(existingButton, true);
  });
})();