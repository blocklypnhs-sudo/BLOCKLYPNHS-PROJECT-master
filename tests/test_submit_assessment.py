import json

import pytest

from backend.app import (
    _load_or_create_secret_key,
    _normalize_duration_seconds,
    app,
)


def test_student_session_survives_app_key_reload(tmp_path, monkeypatch):
    original_key = _load_or_create_secret_key(str(tmp_path))
    reloaded_key = _load_or_create_secret_key(str(tmp_path))
    assert reloaded_key == original_key

    monkeypatch.setattr(app, 'secret_key', original_key)
    with app.test_client() as client:
        with client.session_transaction() as student_session:
            student_session.update({
                'role': 'student',
                'user_id': 41,
                'student_name_loaded': True,
            })

        monkeypatch.setattr(app, 'secret_key', reloaded_key)
        response = client.get('/student_modules')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/module_assessments')


def test_submit_assessment_does_not_trust_client_output_for_non_python(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._assessment = {
                'id': 1, 'title': 'C++ Activity',
                'expected_output': 'Hello, C++!', 'points': 10,
            }
            self._executed = []
            self.insert_params = None
            self.insert_query = None
            self.history_insert_params = None

        def execute(self, query, params):
            self._executed.append((query, params))
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self._fetchone_result = self._assessment
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.insert_query = query
                self._fetchone_result = None
            elif 'INSERT INTO learning_item_submission_history' in query:
                self.history_insert_params = params
                self._fetchone_result = None
            else:
                self._fetchone_result = None

        def fetchone(self):
            result = getattr(self, '_fetchone_result', None)
            self._fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConn()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app.run_cpp_blocks', lambda code_blocks: '__PENDING_REVIEW__')
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)
    monkeypatch.setattr('backend.app.notify_student_assessment_result', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 1
            session['full_name'] = 'Student Name'

        response = client.post(
            '/submit_assessment',
            json={
                'language': 'cpp',
                'assessment_number': 1,
                'code_blocks': '<xml></xml>',
                'generated_code': 'std::cout << "Hello, C++!";',
                'output': 'Hello, C++!',
                'duration_seconds': 123
            }
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['points'] == 0
    assert data['max_points'] == 10
    assert data['status'] == 'pending_review'
    assert connection.cursor_obj.insert_params[3] == 'std::cout << "Hello, C++!";'
    assert connection.cursor_obj.insert_params[4] == 'Hello, C++!'
    assert connection.cursor_obj.insert_params[5:8] == (0, 0, 'submitted')
    assert "generated_code IS NULL OR generated_code = ''" in connection.cursor_obj.insert_query
    assert connection.cursor_obj.history_insert_params[10] == 'pending_review'
    saved_breakdown = json.loads(connection.cursor_obj.history_insert_params[11])
    assert connection.cursor_obj.history_insert_params[12] == 123
    assert len({row['criterion'] for row in saved_breakdown}) == len(saved_breakdown)
    assert sum(row['max_points'] for row in saved_breakdown) == 10
    assert all(
        isinstance(row['points_earned'], int) and isinstance(row['max_points'], int)
        for row in saved_breakdown
    )
    output_criterion = next(
        row for row in saved_breakdown
        if row['criterion'] == 'Expected program output'
    )
    assert 'may need teacher review' in output_criterion['feedback']


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (42, 42),
        (-5, 0),
        (90000, 86400),
        ('invalid', 0),
        (None, 0),
        (True, 0),
    ],
)
def test_normalize_duration_seconds(value, expected):
    assert _normalize_duration_seconds(value) == expected


@pytest.mark.parametrize(
    ('path', 'language', 'expected_output', 'server_output', 'expected_score', 'expected_status'),
    [
        (
            '/submit_assessment', 'python', 'one\ntwo\nthree',
            'one\nwrong\nthree', 90, 'completed',
        ),
        (
            '/submit_activity', 'cpp', 'one\ntwo\nthree',
            'one\ntwo\nthree\nextra', 90, 'completed',
        ),
    ],
)
def test_submission_scores_each_output_line_and_awards_partial_points(
    monkeypatch, path, language, expected_output, server_output,
    expected_score, expected_status,
):
    class FakeCursor:
        def __init__(self):
            self.fetchone_result = None
            self.history_params = None

        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self.fetchone_result = {
                    'id': 5,
                    'title': 'Line scoring test',
                    'expected_output': expected_output,
                    'points': 15,
                }
            elif 'SELECT COUNT(*) AS attempt_count' in query:
                self.fetchone_result = {'attempt_count': 0}
            elif 'SELECT teacher_score, auto_score, score' in query:
                self.fetchone_result = {
                    'teacher_score': None,
                    'auto_score': round(expected_score / 10),
                    'score': expected_score,
                }
            elif 'INSERT INTO learning_item_submission_history' in query:
                self.history_params = params
                self.fetchone_result = None
            elif 'expires_at > NOW() AS active' in query:
                self.fetchone_result = {'active': 1}
            else:
                self.fetchone_result = None

        def fetchone(self):
            result = self.fetchone_result
            self.fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app._activity_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.run_python', lambda source: server_output)
    monkeypatch.setattr('backend.app.run_cpp_blocks', lambda blocks: server_output)
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)
    monkeypatch.setattr('backend.app.notify_student_assessment_result', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        'backend.app.try_award_after_submission',
        lambda *args: {
            'new_badges': [],
            'certificate_issued': False,
            'module_complete': False,
        },
    )

    workspace_block = (
        '<block type="text_print"></block>' if language == 'python'
        else '<block type="cpp_cout"></block>'
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 15})

        response = client.post(path, json={
            'language': language,
            'assessment_number': 1,
            'code_blocks': f'<xml>{workspace_block}</xml>',
            'generated_code': 'print("output")',
            'output': 'untrusted browser output',
        })

    data = response.get_json()
    assert response.status_code == 200
    assert data['score'] == expected_score
    assert data['points'] == round(expected_score / 10)
    assert data['max_points'] == 10
    assert data['status'] == expected_status
    assert len({row['criterion'] for row in data['answer_breakdown']}) == len(data['answer_breakdown'])
    assert sum(row['max_points'] for row in data['answer_breakdown']) == 10
    assert all(
        isinstance(row['points_earned'], int) and isinstance(row['max_points'], int)
        for row in data['answer_breakdown']
    )
    assert sum(
        row['points_earned'] for row in data['answer_breakdown']
    ) == data['points']
    output_criterion = next(
        row for row in data['answer_breakdown']
        if row['criterion'] == 'Expected program output'
    )
    assert output_criterion['expected_answer'] == expected_output
    assert output_criterion['student_answer'] == server_output
    assert output_criterion['feedback'] == (
        '2 of 3 output lines match.'
        if server_output == 'one\nwrong\nthree'
        else '3 of 4 output lines match.'
    )
    assert connection.cursor_instance.history_params[7] == expected_score
    assert connection.cursor_instance.history_params[9] == 10
    assert connection.cursor_instance.history_params[10] == expected_status


def test_submit_java_assessment_uses_block_workspace_for_score(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None

        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self.fetchone_result = {
                    'id': 3,
                    'title': 'Java Assessment',
                    'expected_output': 'Hello, World!',
                    'points': 10,
                }
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.fetchone_result = None
            else:
                self.fetchone_result = None

        def fetchone(self):
            result = getattr(self, 'fetchone_result', None)
            self.fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)
    monkeypatch.setattr('backend.app.notify_student_assessment_result', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 12})

        response = client.post('/submit_assessment', json={
            'language': 'java',
            'assessment_number': 1,
            'code_blocks': (
                '<xml xmlns="https://developers.google.com/blockly/xml">'
                '<block type="java_print"><value name="TEXT">'
                '<block type="text"><field name="TEXT">Hello, World!</field></block>'
                '</value></block></xml>'
            ),
            'generated_code': 'this code is not executed',
            'output': 'untrusted browser output',
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['score'] == 100
    assert result['points'] == 10
    assert result['status'] == 'completed'
    assert connection.cursor_instance.insert_params[5:8] == (100, 10, 'submitted')


def test_submit_assessment_uses_verified_python_output_and_awards(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None
            self.fetchone_result = None

        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self.fetchone_result = {
                    'id': 2,
                    'title': 'Python Assessment',
                    'expected_output': 'Hello, World!',
                    'points': 10,
                }
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.fetchone_result = None
            elif 'SELECT teacher_score, auto_score, score' in query:
                self.fetchone_result = {
                    'teacher_score': None,
                    'auto_score': 10,
                    'score': 100,
                }
            else:
                self.fetchone_result = None

        def fetchone(self):
            result = self.fetchone_result
            self.fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app.run_python', lambda source: 'Hello, World!')
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)
    monkeypatch.setattr('backend.app.notify_student_assessment_result', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        'backend.app.try_award_after_submission',
        lambda *args: {
            'new_badges': ['python_a1'],
            'certificate_issued': False,
            'module_complete': False,
        },
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 7})

        response = client.post('/submit_assessment', json={
            'language': 'python',
            'assessment_number': 1,
            'code_blocks': '<xml><block type="text_print"></block></xml>',
            'generated_code': 'print("Hello, World!")',
            'output': 'tampered browser output',
        })

    data = response.get_json()
    assert response.status_code == 200
    assert data['score'] == 100
    assert data['status'] == 'completed'
    assert data['new_badges'] == ['python_a1']
    assert connection.cursor_instance.insert_params[4] == 'Hello, World!'
    assert connection.cursor_instance.insert_params[5:8] == (100, 10, 'submitted')


def test_submit_assessment_verified_wrong_python_output_is_failed(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None

        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self.fetchone_result = {
                    'id': 1, 'title': 'Python Assessment',
                    'expected_output': 'Hello, World!', 'points': 10,
                }
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.fetchone_result = None

        def fetchone(self):
            return getattr(self, 'fetchone_result', None)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app.run_python', lambda source: '16')
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 1})

        response = client.post('/submit_assessment', json={
            'language': 'python',
            'assessment_number': 1,
            'code_blocks': '<xml><block type="text_print"></block></xml>',
            'generated_code': 'print("16")',
            'output': '16',
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['success'] is True
    assert result['score'] == 70
    assert result['points'] == 7


def test_submit_assessment_normalizes_output_whitespace_before_scoring(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None

        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self.fetchone_result = {
                    'id': 2, 'title': 'Python Assessment',
                    'expected_output': 'Hello, World!', 'points': 10,
                }
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.fetchone_result = None

        def fetchone(self):
            result = getattr(self, 'fetchone_result', None)
            self.fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app.run_python', lambda source: 'Hello, World!\n\n')
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)
    monkeypatch.setattr('backend.app.notify_student_assessment_result', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 9})

        response = client.post('/submit_assessment', json={
            'language': 'python',
            'assessment_number': 1,
            'code_blocks': '<xml><block type="text_print"></block></xml>',
            'generated_code': 'print("Hello, World!")',
            'output': 'Hello, World!\n\n',
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['score'] == 100
    assert result['status'] == 'completed'


def test_passing_module_assessment_records_lesson_completion(monkeypatch):
    award_calls = []

    class FakeCursor:
        def __init__(self):
            self.insert_params = None
            self.history_insert_params = None

        def execute(self, query, params=()):
            if 'INSERT INTO module_assessment_attempts' in query:
                self.insert_params = params
            elif 'INSERT INTO module_assessment_submission_history' in query:
                self.history_insert_params = params

        def fetchone(self):
            return None

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app._module_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.notify_module_assessment_result', lambda *args: None)
    monkeypatch.setattr('backend.app.run_python', lambda source: '16')
    monkeypatch.setattr(
        'backend.app.mark_lesson_complete',
        lambda cursor, student_id, language, lesson_number: award_calls.append(
            ('lesson', student_id, language, lesson_number)
        ),
    )
    monkeypatch.setattr(
        'backend.app.try_award_after_lesson',
            lambda cursor, student_id, language: (
                award_calls.append(('award', student_id, language)) or {
                    'new_badges': [],
                    'certificate_issued': False,
                    'module_complete': False,
                }
            ),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 41})

        response = client.post('/submit_module_assessment', json={
            'module_id': 'python-01-basics',
            'language': 'python',
            'code_blocks': (
                '<xml><block type="variables_set"><field name="VAR">age</field>'
                '<value name="VALUE"><block type="math_number"><field name="NUM">16</field>'
                '</block></value><next><block type="text_print"><value name="TEXT">'
                '<block type="variables_get"><field name="VAR">age</field></block>'
                '</value></block></next></block></xml>'
            ),
            'generated_code': 'age = 16\nprint(age)',
            'output': 'tampered browser output',
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['passed'] is True
    assert len({row['criterion'] for row in result['answer_breakdown']}) == len(result['answer_breakdown'])
    assert sum(row['max_points'] for row in result['answer_breakdown']) == 10
    assert all(
        isinstance(row['points_earned'], int) and isinstance(row['max_points'], int)
        for row in result['answer_breakdown']
    )
    assert sum(
        row['points_earned'] for row in result['answer_breakdown']
    ) == result['points']
    assert result['lesson_completion_recorded'] is True
    assert connection.cursor_instance.insert_params[8] == '16'
    assert connection.cursor_instance.history_insert_params[12] == 'passed'
    assert 'matches' in connection.cursor_instance.history_insert_params[13]
    assert award_calls == [
        ('lesson', 41, 'python', 1),
        ('award', 41, 'python'),
    ]


@pytest.mark.parametrize(
    ('module_id', 'module_number', 'expected_output'),
    [
        ('cpp-01-basics', 1, '1\n2\n3\n4\n5'),
        ('cpp-02-loops', 2, '1\n2\n3\n4\n5\n6\n7\n8\n9\n10'),
    ],
)
def test_cpp_module_assessment_accepts_valid_submission(
    monkeypatch, module_id, module_number, expected_output
):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None

        def execute(self, query, params=()):
            if 'INSERT INTO module_assessment_attempts' in query:
                self.insert_params = params

        def fetchone(self):
            return None

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app._module_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.notify_module_assessment_result', lambda *args: None)
    monkeypatch.setattr('backend.app.mark_lesson_complete', lambda *args: None)
    monkeypatch.setattr('backend.app.try_award_after_lesson', lambda *args: {
        'new_badges': [],
        'certificate_issued': False,
        'module_complete': False,
    })

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 42})

        response = client.post('/submit_module_assessment', json={
            'module_id': module_id,
            'language': 'cpp',
            'code_blocks': (
                '<xml><block type="cpp_for"><field name="VAR">i</field>'
                '<value name="FROM"><block type="cpp_number"><field name="NUM">1</field></block></value>'
                f'<value name="TO"><block type="cpp_number"><field name="NUM">{module_number * 5}</field></block></value>'
                '<statement name="DO"><block type="cpp_cout"><value name="TEXT">'
                '<block type="cpp_variable_get"><field name="NAME">i</field></block>'
                '</value></block></statement></block></xml>'
            ),
            'generated_code': f'for (int i = 1; i <= {module_number * 5}; i++) {{ cout << i; }}',
            'output': expected_output,
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['success'] is True
    assert result['passed'] is True
    assert connection.cursor_instance.insert_params[1:4] == (
        module_id, 'cpp', module_number,
    )
    assert connection.cursor_instance.insert_params[7:9] == (
        expected_output, expected_output,
    )


def test_php_module_assessments_accept_valid_submissions(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None

        def execute(self, query, params=()):
            if 'INSERT INTO module_assessment_attempts' in query:
                self.insert_params = params

        def fetchone(self):
            return None

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app._module_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.notify_module_assessment_result', lambda *args: None)
    monkeypatch.setattr('backend.app.mark_lesson_complete', lambda *args: None)
    monkeypatch.setattr('backend.app.try_award_after_lesson', lambda *args: {
        'new_badges': [],
        'certificate_issued': False,
        'module_complete': False,
    })

    module_submissions = [
        (
            'php-01-variables', 1, '16',
            '<xml><block type="php_variable"><field name="NAME">age</field>'
            '<value name="VALUE"><block type="php_number"><field name="NUM">16</field></block></value>'
            '<next><block type="php_echo"><value name="TEXT">'
            '<block type="php_variable_get"><field name="NAME">age</field></block>'
            '</value></block></next></block></xml>',
        ),
        (
            'php-02-conditionals', 2, 'Passed',
            '<xml><block type="php_variable"><field name="NAME">grade</field>'
            '<value name="VALUE"><block type="php_number"><field name="NUM">88</field></block></value>'
            '<next><block type="php_if_elseif">'
            '<value name="IF0"><block type="php_compare"><field name="OP">GTE</field>'
            '<value name="A"><block type="php_variable_get"><field name="NAME">grade</field></block></value>'
            '<value name="B"><block type="php_number"><field name="NUM">90</field></block></value>'
            '</block></value><statement name="DO0"><block type="php_echo">'
            '<value name="TEXT"><block type="php_text"><field name="TEXT">Excellent</field></block></value>'
            '</block></statement><value name="IF1"><block type="php_compare"><field name="OP">GTE</field>'
            '<value name="A"><block type="php_variable_get"><field name="NAME">grade</field></block></value>'
            '<value name="B"><block type="php_number"><field name="NUM">75</field></block></value>'
            '</block></value><statement name="DO1"><block type="php_echo">'
            '<value name="TEXT"><block type="php_text"><field name="TEXT">Passed</field></block></value>'
            '</block></statement><statement name="ELSE"><block type="php_echo">'
            '<value name="TEXT"><block type="php_text"><field name="TEXT">Failed</field></block></value>'
            '</block></statement></block></next></block></xml>',
        ),
    ]
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 42})

        for module_id, module_number, expected_output, code_blocks in module_submissions:
            response = client.post('/submit_module_assessment', json={
                'module_id': module_id,
                'language': 'php',
            'code_blocks': code_blocks,
                'generated_code': 'PHP module code',
            'output': 'tampered browser output',
            })
            result = response.get_json()
            assert response.status_code == 200
            assert result['passed'] is True
            assert result['score'] == 100
            assert len({row['criterion'] for row in result['answer_breakdown']}) == len(result['answer_breakdown'])
            assert sum(row['max_points'] for row in result['answer_breakdown']) == 10
            assert all(
                isinstance(row['points_earned'], int) and isinstance(row['max_points'], int)
                for row in result['answer_breakdown']
            )
            assert sum(
                row['points_earned'] for row in result['answer_breakdown']
            ) == result['points']
            assert connection.cursor_instance.insert_params[3] == module_number
            assert connection.cursor_instance.insert_params[8] == expected_output


def test_php_assessment_scores_from_server_interpreted_blocks(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None
            self.fetchone_result = None

        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks, expected_output, points' in query:
                self.fetchone_result = {
                    'id': 8,
                    'title': 'PHP Assessment',
                    'expected_output': 'Hello, PHP!',
                    'points': 10,
                }
            elif 'expires_at > NOW() AS active' in query:
                self.fetchone_result = {'active': 1}
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.fetchone_result = None
            else:
                self.fetchone_result = None

        def fetchone(self):
            result = self.fetchone_result
            self.fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app._activity_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)
    monkeypatch.setattr('backend.app.notify_student_assessment_result', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 23})

        response = client.post('/submit_activity', json={
            'language': 'php',
            'assessment_number': 1,
            'code_blocks': (
                '<xml><block type="php_echo"><value name="TEXT">'
                '<block type="php_text"><field name="TEXT">Hello, PHP!</field></block>'
                '</value></block></xml>'
            ),
            'generated_code': 'untrusted browser-generated source',
            'output': 'untrusted browser output',
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['score'] == 100
    assert result['points'] == 10
    assert result['status'] == 'completed'
    assert connection.cursor_instance.insert_params[4] == 'Hello, PHP!'
    assert connection.cursor_instance.insert_params[5:8] == (100, 10, 'submitted')
