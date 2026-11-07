window.getLearningDurationSeconds = function() {
    return Math.max(0, Math.floor((Date.now() - performance.timeOrigin) / 1000));
};
