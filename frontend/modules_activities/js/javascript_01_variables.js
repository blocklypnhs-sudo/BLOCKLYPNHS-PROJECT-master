(function(){
'use strict';

var CONFIG = {
    slug: 'js-01-variables',
    passingScore: 75,
    minQuizScore: 67,
    quizQuestions: 3,
    storageKey: 'blocklearn_module_js_01'
};
var studentId = document.body.getAttribute('data-student-id');
if(studentId) CONFIG.storageKey += '_' + studentId;
var SECTION_ORDER = ['intro','objectives','prereq','lesson','worked','guided','independent','quiz','assessment','completion'];
var state = { completed:{}, quizAnswers:{}, quizScore:0, assessmentScore:null, assessmentStatus:null, completedAt:null, attempts:[] };

function saveState(){ try{ localStorage.setItem(CONFIG.storageKey, JSON.stringify(state)); }catch(e){} }
function loadState(){
    try{
        var r = localStorage.getItem(CONFIG.storageKey);
        if(!r) return;
        var saved = JSON.parse(r);
        if(!saved || typeof saved !== 'object') return;
        Object.assign(state, saved);
        var normalized = {};
        for(var i=0; i<SECTION_ORDER.length; i++){
            if(saved.completed && saved.completed[SECTION_ORDER[i]]) normalized[SECTION_ORDER[i]] = true;
            else break;
        }
        state.completed = normalized;
        saveState();
    }catch(e){}
}

function updateProgressTracker(){
    var steps = document.querySelectorAll('.progress-step');
    var nextIndex = SECTION_ORDER.findIndex(function(sid){ return !state.completed[sid]; });
    if(nextIndex < 0) nextIndex = SECTION_ORDER.length;
    steps.forEach(function(s){
        var sid = s.getAttribute('data-step');
        var index = SECTION_ORDER.indexOf(sid);
        s.classList.toggle('done', !!state.completed[sid]);
        s.classList.toggle('current', index === nextIndex);
        s.classList.toggle('locked', index > nextIndex);
        s.setAttribute('aria-disabled', index > nextIndex ? 'true' : 'false');
    });
    updateSectionLocks();
}
function updateSectionLocks(){
    SECTION_ORDER.forEach(function(sid,i){
        var sec = document.getElementById('section-'+sid);
        if(!sec) return;
        if(i === 0){ sec.classList.remove('locked'); return; }
        var prev = SECTION_ORDER[i-1];
        if(state.completed[prev]) sec.classList.remove('locked');
        else sec.classList.add('locked');
    });
}
function getResumeSection(){
    return SECTION_ORDER.find(function(sid){ return !state.completed[sid]; }) || 'completion';
}
window.markSectionComplete = function(sid){
    if(state.completed[sid]) return;
    state.completed[sid] = true; saveState();
    document.querySelectorAll('[data-section="'+sid+'"].btn-mark-complete').forEach(function(b){
        b.classList.add('done'); b.innerHTML = '<i class="fas fa-check-circle"></i> Completed'; b.disabled = true;
    });
    updateProgressTracker();
    showToast('Section marked as complete');
    var idx = SECTION_ORDER.indexOf(sid);
    if(idx >= 0 && idx < SECTION_ORDER.length - 1){
        var nextEl = document.getElementById('section-'+SECTION_ORDER[idx+1]);
        if(nextEl) setTimeout(function(){ nextEl.scrollIntoView({behavior:'smooth',block:'start'}); }, 400);
    }
};
window.scrollToSection = function(sid){
    var el = document.getElementById('section-'+sid);
    if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
};
function bindProgressNavigation(){
    document.querySelectorAll('.progress-step').forEach(function(step){
        step.addEventListener('click', function(){
            var sid = step.getAttribute('data-step');
            var index = SECTION_ORDER.indexOf(sid);
            if(index > 0 && !state.completed[SECTION_ORDER[index - 1]]){
                showToast('Complete the previous section first.');
                return;
            }
            window.scrollToSection(sid);
        });
    });
}
window.toggleGuidedStep = function(id){
    var el = document.querySelector('[data-step="'+id+'"]');
    if(el) el.classList.toggle('done');
};

var sidebar = document.getElementById('sidebar');
var mainContent = document.getElementById('mainContent');
var isExpanded = window.innerWidth > 768;
function applyState(){
    if(isExpanded){ sidebar.classList.remove('collapsed'); mainContent.classList.remove('shifted'); }
    else { sidebar.classList.add('collapsed'); mainContent.classList.add('shifted'); }
}
window.collapseSidebar = function(){ isExpanded = false; applyState(); };
window.expandSidebar = function(){ isExpanded = true; applyState(); };
window.addEventListener('resize', function(){ if(window.innerWidth <= 768 && isExpanded){ isExpanded = false; applyState(); } });
applyState();
window.toggleTheme = function(){
    var h = document.documentElement;
    if(h.getAttribute('data-theme') === 'dark'){ h.removeAttribute('data-theme'); localStorage.setItem('blocklearn-theme','light'); }
    else { h.setAttribute('data-theme','dark'); localStorage.setItem('blocklearn-theme','dark'); }
};
(function(){ var s = localStorage.getItem('blocklearn-theme'); if(s === 'dark') document.documentElement.setAttribute('data-theme','dark'); })();

/* BLOCKS â€” same as JS playground */
Blockly.Blocks['js_print'] = { init: function() {
    this.appendValueInput('TEXT').setCheck(['String','Number']).appendField('console.log');
    this.setInputsInline(true); this.setPreviousStatement(true, null); this.setNextStatement(true, null);
    this.setColour('#f7df1e'); this.setTooltip('Print to console');
}};
Blockly.Blocks['js_set'] = { init: function() {
    this.appendDummyInput().appendField('let').appendField(new Blockly.FieldTextInput('name'),'NAME').appendField('=');
    this.appendValueInput('VALUE');
    this.setInputsInline(true); this.setPreviousStatement(true, null); this.setNextStatement(true, null);
    this.setColour('#8b5cf6');
}};
Blockly.Blocks['js_get'] = { init: function() {
    this.appendDummyInput().appendField(new Blockly.FieldTextInput('name'),'NAME');
    this.setOutput(true, ['String','Number']); this.setColour('#8b5cf6');
}};
Blockly.Blocks['js_math'] = { init: function() {
    this.appendValueInput('A').setCheck('Number').appendField('math');
    this.appendDummyInput().appendField(new Blockly.FieldDropdown([['+','ADD'],['-','SUBTRACT'],['Ã—','MULTIPLY'],['Ã·','DIVIDE']]),'OP');
    this.appendValueInput('B').setCheck('Number').appendField('');
    this.setInputsInline(true); this.setOutput(true,'Number'); this.setColour('#10b981');
}};
Blockly.Blocks['js_number'] = { init: function() {
    this.appendDummyInput().appendField(new Blockly.FieldNumber(0,-Infinity,Infinity,1),'NUM');
    this.setOutput(true,'Number'); this.setColour('#10b981');
}};
Blockly.Blocks['js_text'] = { init: function() {
    this.appendDummyInput().appendField(new Blockly.FieldTextInput(''),'TEXT');
    this.setOutput(true,'String'); this.setColour('#8b5cf6');
}};
Blockly.Blocks['js_if'] = { init: function() {
    this.appendValueInput('IF0').setCheck('Boolean').appendField('if');
    this.appendStatementInput('DO0').appendField('then');
    this.appendStatementInput('ELSE').appendField('else');
    this.setPreviousStatement(true, null); this.setNextStatement(true, null);
    this.setColour('#f0b84d');
}};
Blockly.Blocks['js_compare'] = { init: function() {
    this.appendValueInput('A').setCheck(['Number','String']);
    this.appendDummyInput().appendField(new Blockly.FieldDropdown([['=','EQ'],['â‰ ','NEQ'],['>','GT'],['<','LT'],['â‰¥','GTE'],['â‰¤','LTE']]),'OP');
    this.appendValueInput('B').setCheck(['Number','String']);
    this.setInputsInline(true); this.setOutput(true,'Boolean'); this.setColour('#f0b84d');
}};
Blockly.Blocks['js_for'] = { init: function() {
    this.appendDummyInput().appendField('for (let ').appendField(new Blockly.FieldTextInput('i'),'VAR').appendField(' = ');
    this.appendValueInput('FROM').setCheck('Number');
    this.appendDummyInput().appendField('; ').appendField(new Blockly.FieldTextInput('i'),'VAR2').appendField(' <= ');
    this.appendValueInput('TO').setCheck('Number');
    this.appendDummyInput().appendField('; ').appendField(new Blockly.FieldTextInput('i'),'VAR3').appendField('++) {');
    this.appendStatementInput('DO').appendField('body');
    this.appendDummyInput().appendField('}');
    this.setPreviousStatement(true, null); this.setNextStatement(true, null);
    this.setColour('#d97706');
}};

if(Blockly.JavaScript){
    Blockly.JavaScript['js_print'] = function(b){
        var t = Blockly.JavaScript.valueToCode(b,'TEXT',Blockly.JavaScript.ORDER_ATOMIC) || '""';
        return 'console.log(' + t + ');\n';
    };
    Blockly.JavaScript['js_set'] = function(b){
        var n = b.getFieldValue('NAME');
        var v = Blockly.JavaScript.valueToCode(b,'VALUE',Blockly.JavaScript.ORDER_ATOMIC) || '""';
        return 'let ' + n + ' = ' + v + ';\n';
    };
    Blockly.JavaScript['js_get'] = function(b){ return [b.getFieldValue('NAME'), Blockly.JavaScript.ORDER_ATOMIC]; };
    Blockly.JavaScript['js_math'] = function(b){
        var a = Blockly.JavaScript.valueToCode(b,'A',Blockly.JavaScript.ORDER_ATOMIC) || '0';
        var c = Blockly.JavaScript.valueToCode(b,'B',Blockly.JavaScript.ORDER_ATOMIC) || '0';
        var op = b.getFieldValue('OP');
        var s = op === 'ADD' ? '+' : op === 'SUBTRACT' ? '-' : op === 'MULTIPLY' ? '*' : '/';
        return ['(' + a + ' ' + s + ' ' + c + ')', Blockly.JavaScript.ORDER_ATOMIC];
    };
    Blockly.JavaScript['js_number'] = function(b){ return [b.getFieldValue('NUM'), Blockly.JavaScript.ORDER_ATOMIC]; };
    Blockly.JavaScript['js_text'] = function(b){ return ['"' + (b.getFieldValue('TEXT')||'') + '"', Blockly.JavaScript.ORDER_ATOMIC]; };
    Blockly.JavaScript['js_compare'] = function(b){
        var a = Blockly.JavaScript.valueToCode(b,'A',Blockly.JavaScript.ORDER_ATOMIC) || '0';
        var c = Blockly.JavaScript.valueToCode(b,'B',Blockly.JavaScript.ORDER_ATOMIC) || '0';
        var op = b.getFieldValue('OP');
        var s = op === 'EQ' ? '==' : op === 'NEQ' ? '!=' : op === 'GT' ? '>' : op === 'LT' ? '<' : op === 'GTE' ? '>=' : '<=';
        return ['(' + a + ' ' + s + ' ' + c + ')', Blockly.JavaScript.ORDER_ATOMIC];
    };
    Blockly.JavaScript['js_if'] = function(b){
        var cond = Blockly.JavaScript.valueToCode(b,'IF0',Blockly.JavaScript.ORDER_ATOMIC) || 'false';
        var doC = Blockly.JavaScript.statementToCode(b,'DO0') || '';
        var elC = Blockly.JavaScript.statementToCode(b,'ELSE') || '';
        var code = 'if (' + cond + ') {\n' + doC + '}';
        if(elC) code += ' else {\n' + elC + '}';
        return code + '\n';
    };
    Blockly.JavaScript['js_for'] = function(b){
        var vn = b.getFieldValue('VAR');
        var f = Blockly.JavaScript.valueToCode(b,'FROM',Blockly.JavaScript.ORDER_ATOMIC) || '0';
        var t = Blockly.JavaScript.valueToCode(b,'TO',Blockly.JavaScript.ORDER_ATOMIC) || '0';
        var doC = Blockly.JavaScript.statementToCode(b,'DO') || '';
        return 'for (let ' + vn + ' = ' + f + '; ' + vn + ' <= ' + t + '; ' + vn + '++) {\n' + doC + '}\n';
    };
}

function getToolbox(){
    return '<xml xmlns="https://developers.google.com/blockly/xml" id="toolbox" style="display:none;">' +
        '<category name="BASIC" colour="#f7df1e"><block type="js_print"></block><block type="js_text"></block></category>' +
        '<category name="MATH" colour="#10b981"><block type="js_math"></block><block type="js_number"></block></category>' +
        '<category name="VARIABLES" colour="#8b5cf6"><block type="js_set"></block><block type="js_get"></block></category>' +
        '<category name="LOGIC" colour="#f0b84d"><block type="js_if"></block><block type="js_compare"></block></category>' +
        '<category name="LOOPS" colour="#d97706"><block type="js_for"></block></category>' +
    '</xml>';
}

var ws1, ws2, ws3;
function initWs(elId){
    return Blockly.inject(elId, {
        toolbox: getToolbox(),
        trashcan: true,
        zoom: { controls: false, wheel: true, startScale: 0.9 },
        renderer: 'zelos'
    });
}
function execCode(code, outputEl){
    if(!code || !code.trim()){ outputEl.textContent = 'No code. Build your solution first!'; outputEl.className = 'output-area error'; return ''; }
    var out = []; var orig = console.log;
    try {
        console.log = function(){ out.push(Array.prototype.slice.call(arguments).join(' ')); };
        eval(code);
        console.log = orig;
        if(out.length > 0){ outputEl.textContent = out.join('\n'); outputEl.className = 'output-area success'; }
        else { outputEl.textContent = 'Code ran but no output.'; outputEl.className = 'output-area'; }
        return out.join('\n');
    } catch(e){ console.log = orig; outputEl.textContent = 'Error: ' + e.message; outputEl.className = 'output-area error'; return ''; }
}

window.runWs1 = function(){ if(!ws1) return; var c = Blockly.JavaScript.workspaceToCode(ws1); window.lastCode1 = c; execCode(c, document.getElementById('outputArea')); };
window.runWs2 = function(){ if(!ws2) return; var c = Blockly.JavaScript.workspaceToCode(ws2); execCode(c, document.getElementById('outputArea2')); };
window.runWs3 = function(){ if(!ws3) return; var c = Blockly.JavaScript.workspaceToCode(ws3); window.lastCode3 = c; execCode(c, document.getElementById('outputArea3')); };
window.clearWs1 = function(){ if(ws1 && confirm('Clear?')){ ws1.clear(); document.getElementById('outputArea').textContent = 'Cleared.'; document.getElementById('outputArea').className = 'output-area'; } };
window.clearWs2 = function(){ if(ws2 && confirm('Clear?')){ ws2.clear(); document.getElementById('outputArea2').textContent = 'Cleared.'; document.getElementById('outputArea2').className = 'output-area'; } };
window.clearWs3 = function(){ if(ws3 && confirm('Clear?')){ ws3.clear(); document.getElementById('outputArea3').textContent = 'Cleared.'; document.getElementById('outputArea3').className = 'output-area'; } };
window.zoomWs1 = function(a){ if(!ws1) return; var s = ws1.scale || 1; ws1.setScale(a === 'in' ? Math.min(2, s+0.1) : a === 'out' ? Math.max(0.5, s-0.1) : 1); };
window.zoomWs2 = function(a){ if(!ws2) return; var s = ws2.scale || 1; ws2.setScale(a === 'in' ? Math.min(2, s+0.1) : a === 'out' ? Math.max(0.5, s-0.1) : 1); };
window.zoomWs3 = function(a){ if(!ws3) return; var s = ws3.scale || 1; ws3.setScale(a === 'in' ? Math.min(2, s+0.1) : a === 'out' ? Math.max(0.5, s-0.1) : 1); };

var guidedCurrent = 'hello-js';
var GUIDED = {
    'hello-js': {
        title: 'Activity 1: Hello JS',
        task: 'Print "Hello, JavaScript!" to the console.',
        steps: [
            ['Add console.log', 'Drag <code>console.log</code> from <strong>BASIC</strong>.'],
            ['Add text', 'Attach a <code>TEXT</code> block inside console.log.'],
            ['Type the message', 'Type: <code>Hello, JavaScript!</code>'],
            ['Run and check', 'Click Run. Output: <code>Hello, JavaScript!</code>']
        ],
        check: function(code){ return code.includes('console.log("Hello, JavaScript!")'); }
    },
    'store-score': {
        title: 'Activity 2: Store Score',
        task: 'Create a variable "score" with value 90 and print it.',
        steps: [
            ['Add variable', 'Drag <code>let myVar =</code>. Rename to <code>score</code>.'],
            ['Assign value', 'Attach a NUMBER block with value <code>90</code>.'],
            ['Add console.log', 'Drag <code>console.log</code> from BASIC.'],
            ['Get the variable', 'Attach a <code>myVar</code> get block inside console.log. Set to <code>score</code>.'],
            ['Run and check', 'Output: <code>90</code>']
        ],
        check: function(code){ return code.includes('let score = 90;') && code.includes('console.log(score)'); }
    }
};
window.loadGuided = function(key){
    guidedCurrent = key;
    var g = GUIDED[key]; if(!g) return;
    document.querySelectorAll('.activity-tab[data-guided]').forEach(function(t){
        t.classList.toggle('active', t.getAttribute('data-guided') === key);
    });
    document.getElementById('guidedTitle').textContent = g.title;
    document.getElementById('guidedTask').textContent = g.task;
    var html = g.steps.map(function(s,i){
        return '<div class="guided-step" data-step="g'+(i+1)+'">' +
            '<div class="guided-check" onclick="toggleGuidedStep(\'g'+(i+1)+'\')"><i class="fas fa-check"></i></div>' +
            '<div class="guided-body"><strong>Step '+(i+1)+' â€” '+s[0]+'</strong><p>'+s[1]+'</p></div></div>';
    }).join('');
    document.getElementById('guidedInstructions').innerHTML = '<h3>'+g.title+'</h3><p>'+g.task+'</p>'+html;
    if(ws1) ws1.clear();
    document.getElementById('outputArea').textContent = 'Build your solution. Click RUN!';
    document.getElementById('outputArea').className = 'output-area';
};
window.checkGuided = function(){
    var code = window.lastCode1 || (ws1 ? Blockly.JavaScript.workspaceToCode(ws1) : '');
    var g = GUIDED[guidedCurrent]; if(!g) return;
    showToast(g.check(code) ? 'âœ“ Correct!' : 'Not yet. Check the steps.');
};

var QUIZ = {
    0: { correct: 1, explanation: 'Modern JavaScript uses let (or const) to declare variables.' },
    1: { correct: 2, explanation: 'console.log() prints text to the browser console.' },
    2: { correct: 1, explanation: 'The loop runs i = 0,1,2,3,4 â†’ 5 iterations.' }
};
window.answerQuiz = function(q, chosen){
    if(state.quizAnswers[q] !== undefined) return;
    state.quizAnswers[q] = chosen;
    var qEl = document.querySelector('.quiz-question[data-q="'+q+'"]'); if(!qEl) return;
    var opts = qEl.querySelectorAll('.quiz-option');
    var fb = document.getElementById('feedback-'+q);
    var c = QUIZ[q].correct, ex = QUIZ[q].explanation;
    opts.forEach(function(o,i){
        o.disabled = true;
        if(i === c) o.classList.add('correct');
        if(i === chosen && chosen !== c) o.classList.add('wrong');
    });
    if(fb){
        fb.classList.add('show', chosen === c ? 'correct' : 'wrong');
        fb.innerHTML = (chosen === c ? '<strong>âœ“ Correct!</strong> ' : '<strong>âœ— Not quite.</strong> ') + ex;
    }
    saveState();
    if(Object.keys(state.quizAnswers).length === CONFIG.quizQuestions){
        var correct = 0;
        for(var k in state.quizAnswers){ if(state.quizAnswers[k] === QUIZ[k].correct) correct++; }
        var pct = Math.round((correct / CONFIG.quizQuestions) * 100);
        state.quizScore = pct; saveState();
        showQuizResult(correct, pct);
    }
};
function showQuizResult(correct, pct){
    var r = document.getElementById('quizResult');
    var ic = document.getElementById('quizResultIcon');
    var ti = document.getElementById('quizResultTitle');
    var te = document.getElementById('quizResultText');
    if(!r) return;
    r.style.display = 'block';
    var passed = pct >= CONFIG.minQuizScore;
    ic.className = 'quiz-result-icon ' + (passed ? 'pass' : 'fail');
    ic.innerHTML = passed ? '<i class="fas fa-check"></i>' : '<i class="fas fa-xmark"></i>';
    ti.textContent = passed ? 'Quiz Passed!' : 'Quiz Failed';
    te.textContent = 'You got ' + correct + ' out of ' + CONFIG.quizQuestions + ' (' + pct + '%). ' +
        (passed ? 'Proceed to the Final Assessment.' : 'Review and try again.');
    if(passed){ state.completed.quiz = true; saveState(); updateProgressTracker(); }
}
window.resetQuiz = function(){
    state.quizAnswers = {}; state.quizScore = 0; delete state.completed.quiz; saveState();
    document.querySelectorAll('.quiz-question').forEach(function(q){
        q.querySelectorAll('.quiz-option').forEach(function(o){ o.disabled = false; o.classList.remove('correct','wrong'); });
    });
    document.querySelectorAll('.quiz-feedback').forEach(function(f){ f.classList.remove('show','correct','wrong'); f.innerHTML = ''; });
    document.getElementById('quizResult').style.display = 'none';
    updateProgressTracker();
    scrollToSection('lesson');
};

window.submitAssessment = function(){
    if(!ws3){ showToast('Workspace not ready.'); return; }
    var code = Blockly.JavaScript.workspaceToCode(ws3).trim();
    if(!code){ showToast('Build your solution first!'); return; }
    var output = execCode(code, document.getElementById('outputArea3'));
    var codeBlocks = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(ws3));
    var passed = code.includes('for (let i = 0; i <= 4; i++)') && code.includes('console.log("I love programming!")');
    var score = passed ? 100 : 40;
    recordAttempt(score, code, output);
    fetch('/submit_assessment', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ language:'javascript', assessment_number:5, code_blocks:codeBlocks, generated_code:code, output:output })
    }).catch(function(){});
};
function recordAttempt(score, code, output){
    var status = score >= CONFIG.passingScore ? 'passed' : 'failed';
    state.attempts.push({score:score, status:status, at:new Date().toISOString(), code:code, output:output});
    state.assessmentScore = score;
    state.assessmentStatus = status;
    if(status === 'passed'){
        state.completed.assessment = true;
        state.completedAt = new Date().toISOString();
        state.completed.completion = true;
    }
    saveState();
    updateProgressTracker();
    showFeedback(score, status);
}
function showFeedback(score, status){
    var sec = document.getElementById('section-assessment'); if(!sec) return;
    var old = document.getElementById('feedbackPanel');
    if(old) old.remove();
    var p = document.createElement('div');
    p.id = 'feedbackPanel'; p.className = 'feedback-panel';
    p.innerHTML =
        '<div class="feedback-score">' +
            '<div class="feedback-score-num ' + (status === 'failed' ? 'failed' : '') + '">' + score + '%</div>' +
            '<div class="feedback-score-label">Final Score</div>' +
            '<span class="feedback-status-badge ' + status + '">' + (status === 'passed' ? 'Passed' : 'Failed') + '</span>' +
        '</div>' +
        '<h3>What Happened</h3>' +
        '<p>' + (status === 'passed'
            ? 'Excellent! You correctly used a for loop with console.log in JavaScript.'
            : 'Score is below ' + CONFIG.passingScore + '%. Review and retry.') + '</p>' +
        '<div class="section-actions" style="border-top:none;padding-top:0;">' +
            (status === 'passed'
                ? '<button class="btn-mark-complete" onclick="finishModule()"><i class="fas fa-flag-checkered"></i> Complete Module</button>'
                : '<button class="btn-retry" onclick="retryAssessment()"><i class="fas fa-rotate-right"></i> Retry Assessment</button>' +
                  '<button class="btn-review" onclick="scrollToSection(\'lesson\')"><i class="fas fa-book-open"></i> Review Lesson</button>') +
        '</div>';
    sec.appendChild(p);
    p.scrollIntoView({behavior:'smooth',block:'start'});
}
window.retryAssessment = function(){
    var p = document.getElementById('feedbackPanel'); if(p) p.remove();
    scrollToSection('assessment');
    showToast('Retry. Previous attempt saved.');
};
window.finishModule = function(){
    if(!state.completed.assessment){ showToast('Pass the assessment first.'); return; }
    state.completed.completion = true;
    if(!state.completedAt) state.completedAt = new Date().toISOString();
    saveState();
    updateProgressTracker();
    var sec = document.getElementById('section-completion');
    if(sec) sec.classList.remove('locked');
    var panel = document.getElementById('completionPanel');
    if(panel) panel.innerHTML = buildCompletion();
    scrollToSection('completion');
    showToast('ðŸŽ‰ Module 1 completed!');
};
function buildCompletion(){
    var date = state.completedAt ? new Date(state.completedAt).toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'}) : 'â€”';
    var history = state.attempts.map(function(a,i){
        return '<li style="padding:8px 12px;background:rgba(255,255,255,.4);border-radius:8px;margin-bottom:6px;font-size:.82rem;">' +
            '<strong>Attempt ' + (i+1) + ':</strong> ' + a.score + '% â€” ' +
            '<span style="color:' + (a.status === 'passed' ? 'var(--green-main)' : 'var(--coral)') + ';font-weight:700;">' +
            (a.status === 'passed' ? 'Passed' : 'Failed') + '</span>' +
            '<span style="color:var(--stone-light);font-size:.72rem;display:block;">' + new Date(a.at).toLocaleString() + '</span>' +
        '</li>';
    }).join('');
    return '<div class="feedback-panel">' +
        '<div class="feedback-score">' +
            '<div class="feedback-score-num">' + state.assessmentScore + '%</div>' +
            '<div class="feedback-score-label">Final Assessment Score</div>' +
            '<span class="feedback-status-badge passed">Passed</span>' +
        '</div>' +
        '<h3>Module Completed ðŸŽ‰</h3>' +
        '<p>You completed <strong>JavaScript Variables</strong> on <strong>' + date + '</strong>.</p>' +
        '<h3>Assessment History</h3>' +
        '<ul style="list-style:none;padding:0;margin:0 0 1rem;">' + history + '</ul>' +
    '</div>' +
    '<div class="next-module-card">' +
        '<div class="next-module-content">' +
            '<div class="next-module-label">Next Up</div>' +
            '<h3>Module 2: JavaScript Functions</h3>' +
            '<p>Learn how to group code into reusable functions.</p>' +
        '</div>' +
        '<a href="/student_modules/javascript/2" class="btn-next">Start Module 2 <i class="fas fa-arrow-right"></i></a>' +
    '</div>';
}

function showToast(msg){
    var box = document.getElementById('toastBox');
    if(!box){ box = document.createElement('div'); box.id = 'toastBox'; box.className = 'toast-box'; document.body.appendChild(box); }
    var t = document.createElement('div'); t.className = 'toast-msg';
    t.innerHTML = '<i class="fas fa-circle-info"></i> ' + msg;
    box.appendChild(t);
    setTimeout(function(){ t.classList.add('out'); setTimeout(function(){ t.remove(); }, 300); }, 2800);
}

window.addEventListener('pageshow', function(event){
    if(event.persisted){ setTimeout(function(){ scrollToSection(getResumeSection()); }, 0); }
});

document.addEventListener('DOMContentLoaded', function(){
    loadState();
    bindProgressNavigation();
    updateProgressTracker();
    if(Object.keys(state.completed).length){
        setTimeout(function(){ scrollToSection(getResumeSection()); }, 0);
    }
    Object.keys(state.completed).forEach(function(sid){
        document.querySelectorAll('[data-section="'+sid+'"].btn-mark-complete').forEach(function(b){
            b.classList.add('done'); b.innerHTML = '<i class="fas fa-check-circle"></i> Completed'; b.disabled = true;
        });
    });
    if(Object.keys(state.quizAnswers).length > 0){
        for(var q in state.quizAnswers){
            var chosen = state.quizAnswers[q];
            var qEl = document.querySelector('.quiz-question[data-q="'+q+'"]');
            if(!qEl) continue;
            var opts = qEl.querySelectorAll('.quiz-option');
            var c = QUIZ[q].correct;
            opts.forEach(function(o,i){
                o.disabled = true;
                if(i === c) o.classList.add('correct');
                if(i === chosen && chosen !== c) o.classList.add('wrong');
            });
        }
    }
    if(state.assessmentStatus === 'passed' && state.completed.completion){
        var p = document.getElementById('completionPanel');
        if(p) p.innerHTML = buildCompletion();
    }
    setTimeout(function(){
        try {
            ws1 = initWs('blocklyDiv');
            ws2 = initWs('blocklyDiv2');
            ws3 = initWs('blocklyDiv3');
            window.addEventListener('resize', function(){
                [ws1,ws2,ws3].forEach(function(w){ if(w) Blockly.svgResize(w); });
            });
        } catch(e){ console.error('Blockly init error:', e); }
    }, 300);
});
})();
