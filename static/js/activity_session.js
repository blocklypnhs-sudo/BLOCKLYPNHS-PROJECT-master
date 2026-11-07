(function () {
  let language;
  let activityNumbers = {};

  function updateActivityButtons(activities) {
    const statuses = new Map(
      activities
        .filter((activity) => activity.language === language)
        .map((activity) => [Number(activity.activity_number), activity.status])
    );

    document.querySelectorAll('.activity-btn[data-activity]').forEach((button) => {
      const number = activityNumbers[button.dataset.activity];
      if (!number) {
        button.disabled = false;
        button.classList.remove('activity-locked');
        return;
      }

      const status = statuses.get(number) || 'LOCKED';
      const locked = status === 'LOCKED';
      button.disabled = locked;
      button.classList.toggle('activity-locked', locked);
      button.title = locked ? 'Pass the previous activity to unlock this one.' : '';
      const badge = button.querySelector('.activity-lock-label');
      if (locked && !badge) {
        const label = document.createElement('span');
        label.className = 'activity-lock-label';
        label.textContent = 'Locked';
        button.appendChild(label);
      } else if (!locked && badge) {
        badge.remove();
      }
    });
  }

  async function refreshStatuses() {
    const response = await fetch('/get_activities');
    const result = await response.json();
    if (!response.ok || !result.success || !Array.isArray(result.activities)) {
      throw new Error(result.message || 'Unable to load activity status.');
    }
    updateActivityButtons(result.activities);
    return result.activities;
  }

  async function start(activityId, restart) {
    const number = activityNumbers[activityId];
    if (!number) {
      const submit = document.querySelector('.btn-submit');
      if (submit) submit.disabled = false;
      return { success: true, completed: false };
    }

    const response = await fetch('/start_activity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language,
        assessment_number: number,
        restart: restart === true
      })
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.message || 'Unable to start this activity.');
    }

    const submit = document.querySelector('.btn-submit');
    if (submit) submit.disabled = !!result.completed;
    refreshStatuses().catch((error) => {
      console.error('Unable to refresh activity sequence:', error);
    });
    return result;
  }

  async function submitted() {
    const submit = document.querySelector('.btn-submit');
    if (submit) submit.disabled = true;
    refreshStatuses().catch((error) => {
      console.error('Unable to refresh activity sequence:', error);
    });
  }

  window.ActivitySession = {
    initialize: async function (activityLanguage, activities) {
      language = activityLanguage;
      activityNumbers = Object.fromEntries(
        Object.entries(activities).map(([id, activity]) => [id, Number(activity.step) || 0])
      );
      document.querySelectorAll('.activity-btn[data-activity]').forEach((button) => {
        if (activityNumbers[button.dataset.activity]) {
          button.disabled = true;
          button.classList.add('activity-locked');
        }
      });
      try {
        await refreshStatuses();
      } catch (error) {
        console.error('Unable to load activity sequence:', error);
      }
    },
    start,
    submitted,
  };
})();
