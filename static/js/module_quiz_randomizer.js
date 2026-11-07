(function () {
  if (typeof MODULE === 'undefined' || !Array.isArray(MODULE.quiz)) return;

  const extraByModule = {
    'python:1': [
      {
        q: 'What does age = 16 do in Python?',
        options: ['Assigns 16 to age', 'Checks whether age is 16', 'Prints 16', 'Creates a loop'],
        correct: 0,
        explain: 'A single equals sign assigns a value to a variable.'
      },
      {
        q: 'Which value is a string in Python?',
        options: ['"Hello"', '16', 'True', '3.14'],
        correct: 0,
        explain: 'Text enclosed in quotation marks is a string.'
      }
    ],
    'python:2': [
      {
        q: 'What values does range(1, 4) produce?',
        options: ['1, 2, 3', '1, 2, 3, 4', '0, 1, 2, 3', '4, 3, 2, 1'],
        correct: 0,
        explain: 'The stop value 4 is not included in range(1, 4).'
      },
      {
        q: 'Why must a variable in a while loop usually be updated?',
        options: ['So the condition can eventually become false', 'To define a function', 'To print the variable automatically', 'To create a list'],
        correct: 0,
        explain: 'Updating the loop variable lets the loop condition eventually become false.'
      }
    ],
    'java:1': [
      {
        q: 'Which Java type stores a whole number?',
        options: ['int', 'String', 'boolean', 'double only'],
        correct: 0,
        explain: 'The int type stores whole-number values.'
      },
      {
        q: 'What does System.out.println(age); display?',
        options: ['The value stored in age', 'The word age', 'A new variable', 'Nothing'],
        correct: 0,
        explain: 'Without quotation marks, age refers to the variable value.'
      }
    ],
    'java:2': [
      {
        q: 'What does i++ do in a Java for loop?',
        options: ['Increases i by 1', 'Sets i to zero', 'Decreases i by 1', 'Ends the program'],
        correct: 0,
        explain: 'The increment expression increases i after each loop iteration.'
      },
      {
        q: 'When is a Java while loop body repeated?',
        options: ['While its condition is true', 'Only when its condition is false', 'Once for each method', 'Only after the program ends'],
        correct: 0,
        explain: 'A while loop keeps running while its boolean condition is true.'
      }
    ],
    'php:1': [
      {
        q: 'Which symbol begins a PHP variable name?',
        options: ['$', '#', '@', '&'],
        correct: 0,
        explain: 'PHP variable names begin with a dollar sign.'
      },
      {
        q: 'Which PHP statement displays the value of $name?',
        options: ['echo $name;', 'print($name) in every case', 'System.out.println($name);', 'console.log($name);'],
        correct: 0,
        explain: 'PHP uses echo to display text or a variable value.'
      }
    ],
    'php:2': [
      {
        q: 'Which PHP keyword checks a condition?',
        options: ['if', 'repeat', 'define', 'echo'],
        correct: 0,
        explain: 'Use if to run code when a condition is true.'
      },
      {
        q: 'What does else do in an if/else statement?',
        options: ['Runs when the if condition is false', 'Repeats the if block', 'Declares a variable', 'Ends the program'],
        correct: 0,
        explain: 'else provides an alternative branch when the if condition is false.'
      }
    ],
    'javascript:1': [
      {
        q: 'Which keyword can declare a reassignable JavaScript variable?',
        options: ['let', 'def', 'int', 'echo'],
        correct: 0,
        explain: 'Use let to declare a variable that can be reassigned.'
      },
      {
        q: 'What does console.log(score) display?',
        options: ['The value stored in score', 'The word score only', 'A new variable', 'Nothing'],
        correct: 0,
        explain: 'Without quotes, score refers to the variable value.'
      }
    ],
    'javascript:2': [
      {
        q: 'Which keyword defines a JavaScript function?',
        options: ['function', 'method', 'def', 'create'],
        correct: 0,
        explain: 'A standard JavaScript function declaration begins with function.'
      },
      {
        q: 'What does return do inside a function?',
        options: ['Sends a value back to the caller', 'Repeats the function forever', 'Prints a value automatically', 'Declares a variable'],
        correct: 0,
        explain: 'return sends a result back to the code that called the function.'
      }
    ],
    'cpp:1': [
      {
        q: 'Which C++ type stores a whole number?',
        options: ['int', 'string only', 'boolean', 'float only'],
        correct: 0,
        explain: 'The int type stores whole-number values.'
      },
      {
        q: 'What does std::cout << age display?',
        options: ['The value stored in age', 'The word age only', 'A new variable', 'Nothing'],
        correct: 0,
        explain: 'The stream operator sends the variable value to the output stream.'
      }
    ],
    'cpp:2': [
      {
        q: 'What does i++ do in a C++ for loop?',
        options: ['Increases i by 1', 'Sets i to zero', 'Decreases i by 1', 'Ends the program'],
        correct: 0,
        explain: 'The increment expression increases i after each loop iteration.'
      },
      {
        q: 'What is the purpose of the condition in a for loop?',
        options: ['Decides whether another iteration runs', 'Prints the counter', 'Declares a function', 'Clears the loop body'],
        correct: 0,
        explain: 'The loop continues while its condition is true.'
      }
    ]
  };

  const moduleKey = `${MODULE.language}:${MODULE.number}`;
  const extras = extraByModule[moduleKey];
  if (!extras || MODULE.quiz.length !== 3) {
    console.error(`Expected three base quiz questions for ${moduleKey}.`);
    return;
  }

  function shuffle(items) {
    for (let index = items.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(Math.random() * (index + 1));
      [items[index], items[swapIndex]] = [items[swapIndex], items[index]];
    }
    return items;
  }

  const questions = MODULE.quiz.concat(extras).map(question => {
    const options = shuffle(question.options.slice());
    const correctAnswer = question.options[question.correct];
    return {
      ...question,
      options,
      correct: options.indexOf(correctAnswer)
    };
  });

  MODULE.quiz = shuffle(questions);

  document.addEventListener('DOMContentLoaded', function () {
    const subtitle = document.querySelector('[data-step="5"] .subtitle');
    if (subtitle) {
      subtitle.textContent = 'Answer all 5 questions. You need at least 4/5 correct to continue.';
    }
    quizAnswers = [];
    renderQuiz();
    const nextButton = document.getElementById('quizNextBtn');
    if (nextButton) nextButton.disabled = true;
  });

  window.finishQuiz = function () {
    const correct = quizAnswers.filter(Boolean).length;
    if (correct < 4) {
      showToast(`You got ${correct}/5. Review the lesson and retry the quiz.`, 'error');
      quizAnswers = [];
      renderQuiz();
      document.getElementById('quizNextBtn').disabled = true;
      return;
    }
    showToast(`Quiz passed: ${correct}/5. Proceed to the assessment.`, 'success');
    goStep(6);
  };
})();
