(function () {
  const language = MODULE.language;
  const banks = {
    python: {
      output: 'print("Hello")', assignment: 'score = 10', comment: '#',
      truth: 'True', condition: 'if score >= 10:', loop: 'for i in range(3):',
      function: 'def greet():', stringType: 'str', array: 'scores = [1, 2, 3]'
    },
    java: {
      output: 'System.out.println("Hello");', assignment: 'int score = 10;',
      comment: '//', truth: 'true', condition: 'if (score >= 10) {',
      loop: 'for (int i = 0; i < 3; i++) {', function: 'void greet() {',
      stringType: 'String', array: 'int[] scores = {1, 2, 3};'
    },
    php: {
      output: 'echo "Hello";', assignment: '$score = 10;', comment: '//',
      truth: 'true', condition: 'if ($score >= 10) {',
      loop: 'for ($i = 0; $i < 3; $i++) {', function: 'function greet() {',
      stringType: 'string', array: '$scores = [1, 2, 3];'
    },
    javascript: {
      output: 'console.log("Hello");', assignment: 'let score = 10;',
      comment: '//', truth: 'true', condition: 'if (score >= 10) {',
      loop: 'for (let i = 0; i < 3; i++) {', function: 'function greet() {',
      stringType: 'string', array: 'const scores = [1, 2, 3];'
    },
    cpp: {
      output: 'std::cout << "Hello";', assignment: 'int score = 10;',
      comment: '//', truth: 'true', condition: 'if (score >= 10) {',
      loop: 'for (int i = 0; i < 3; i++) {', function: 'void greet() {',
      stringType: 'std::string', array: 'int scores[] = {1, 2, 3};'
    }
  };
  const config = banks[language];
  if (!config || !Array.isArray(MODULE.quiz)) return;

  const makeQuestion = (id, q, options, correct, explain) =>
    ({ id: `${language}-${id}`, q, options, correct, explain });
  const extraQuestions = [
    makeQuestion('print', 'Which statement displays the text Hello?', [
      config.output, 'echo("Hello")', 'show("Hello")', 'display "Hello"'
    ], 0, `Use ${config.output} to display text in ${language}.`),
    makeQuestion('assign', 'Which line assigns 10 to the variable score?', [
      config.assignment, 'score == 10', 'score :=: 10', 'set score equals 10'
    ], 0, `Use ${config.assignment} to assign a value.`),
    makeQuestion('comment', 'Which symbol starts a single-line comment in this language?', [
      config.comment, '<!--', '**', ';;'
    ], 0, `A single-line comment starts with ${config.comment}.`),
    makeQuestion('boolean', 'Which value represents true in this language?', [
      config.truth, '"true"', 'YES', '1 == 0'
    ], 0, `The boolean true value is ${config.truth}.`),
    makeQuestion('equals', 'Which operator checks whether two values are equal?', [
      '==', '=', '=>', '<>'
    ], 0, 'Use == for an equality comparison; = is commonly used for assignment.'),
    makeQuestion('condition', 'Which line begins a condition that checks whether score is at least 10?', [
      config.condition, 'when score >= 10 then', 'score >= 10 if', 'check(score, 10)'
    ], 0, `Use ${config.condition} to begin the condition.`),
    makeQuestion('loop', 'Which line begins a loop that repeats three times?', [
      config.loop, 'repeat = 3 forever', 'loop(i, 3, 0)', 'while i == 3'
    ], 0, `Use ${config.loop} to begin a three-iteration loop.`),
    makeQuestion('function', 'Which line begins a function named greet?', [
      config.function, 'make greet:', 'function = greet()', 'start greet'
    ], 0, `Use ${config.function} to define the function.`),
    makeQuestion('string', 'Which type is used for text values in this language?', [
      config.stringType, 'boolean', 'integer', 'decimal'
    ], 0, `Text values use the ${config.stringType} type.`),
    makeQuestion('remainder', 'Which operator gives the remainder after division?', [
      '%', '/', '*', '**'
    ], 0, 'The % operator returns the remainder after division.'),
    makeQuestion('array', 'Which line creates a list or array containing 1, 2, and 3?', [
      config.array, 'scores = (1; 2; 3)', 'scores = 1 | 2 | 3', 'array scores: 1, 2, 3'
    ], 0, `Use ${config.array} to create the collection.`),
    makeQuestion('addition', 'What is the result of 8 + 4?', [
      '12', '2', '32', '84'
    ], 0, 'Addition combines the values: 8 + 4 = 12.')
  ];

  const pool = MODULE.quiz.concat(extraQuestions);
  const storageKey = `blocklearn_quiz_set_${MODULE.id}`;
  let previous = null;
  try { previous = sessionStorage.getItem(storageKey); } catch (error) {}
  let selected = [];
  for (let attempt = 0; attempt < 6; attempt += 1) {
    selected = pool.slice().sort(() => Math.random() - 0.5).slice(0, 10);
    const key = selected.map(question => question.id || question.q).sort().join('|');
    if (key !== previous || pool.length <= 10) break;
  }
  try {
    sessionStorage.setItem(storageKey, selected.map(question => question.id || question.q).sort().join('|'));
  } catch (error) {}
  MODULE.quiz = selected;
  quizAnswers = [];

  const originalLoadProgress = window.loadProgress;
  if (typeof originalLoadProgress === 'function') {
    window.loadProgress = function () {
      originalLoadProgress();
      quizAnswers = [];
    };
  }

  window.renderQuiz = function () {
    const container = document.getElementById('quizContainer');
    if (!container) return;
    container.innerHTML = MODULE.quiz.map((question, index) => `
      <div class="quiz-q">
        <div class="q-text">${index + 1}. ${question.q}</div>
        <div class="quiz-opts">
          ${question.options.map((option, optionIndex) =>
            `<button class="quiz-opt" onclick="answerQuiz(${index}, ${optionIndex})">${option}</button>`
          ).join('')}
        </div>
        <div class="quiz-feedback" id="fb-${index}"></div>
      </div>
    `).join('');
    const subtitle = container.parentElement.querySelector('.subtitle');
    if (subtitle) subtitle.textContent = 'Answer all 10 questions. Each correct answer is worth 1 point; earn at least 7/10 to continue.';
    const next = document.getElementById('quizNextBtn');
    if (next) next.disabled = true;
  };

  window.answerQuiz = function (questionIndex, optionIndex) {
    if (quizAnswers[questionIndex] !== undefined) return;
    const question = MODULE.quiz[questionIndex];
    if (!question) return;
    const buttons = document.querySelectorAll(`.quiz-q:nth-child(${questionIndex + 1}) .quiz-opt`);
    buttons.forEach(button => { button.disabled = true; });
    const feedback = document.getElementById(`fb-${questionIndex}`);
    const correct = optionIndex === question.correct;
    buttons[optionIndex].classList.add(correct ? 'correct' : 'incorrect');
    if (!correct) buttons[question.correct].classList.add('correct');
    feedback.className = `quiz-feedback show ${correct ? 'ok' : 'no'}`;
    feedback.textContent = `${correct ? 'Correct. ' : 'Not quite. '}${question.explain}`;
    quizAnswers[questionIndex] = correct;
    if (quizAnswers.filter(answer => answer !== undefined).length === MODULE.quiz.length) {
      document.getElementById('quizNextBtn').disabled = false;
    }
  };

  window.finishQuiz = function () {
    if (quizAnswers.filter(answer => answer !== undefined).length !== MODULE.quiz.length) {
      showToast('Answer all 10 questions before continuing.', 'error');
      return;
    }
    const points = quizAnswers.filter(Boolean).length;
    if (points < 7) {
      showToast(`You got ${points}/10. Review the lesson and try a new question set.`, 'error');
      quizAnswers = [];
      renderQuiz();
      return;
    }
    showToast(`Quiz passed: ${points}/10 points. Proceed to the assessment.`, 'success');
    goStep(6);
  };

  const originalGoStep = window.goStep;
  if (typeof originalGoStep === 'function') {
    window.goStep = function (step, fromStepper) {
      if (step === 6 && quizAnswers.filter(answer => answer !== undefined).length !== MODULE.quiz.length) {
        showToast('Complete all 10 quiz questions first.', 'error');
        return;
      }
      return originalGoStep(step, fromStepper);
    };
  }
})();
