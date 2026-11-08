import json

from backend.app import app


def test_score_attempt_history_requires_teacher():
    with app.test_client() as client:
        api_response = client.get('/api/teacher/score-attempts')
        page_response = client.get('/teacher/score_history')

    assert api_response.status_code == 401
    assert api_response.get_json()['success'] is False
    assert page_response.status_code == 302


def test_teacher_score_attempt_history_page_renders():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'

        response = client.get('/teacher/score_history')

    assert response.status_code == 200
    assert b'Student Score Attempt History' in response.data


def test_score_attempt_detail_rejects_unknown_attempt_type():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'

        response = client.get('/api/teacher/score-attempts/unknown/1')

    assert response.status_code == 400
    assert response.get_json()['success'] is False


def test_teacher_can_list_saved_score_attempts(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.fetchone_result = None
            self.fetchall_result = []
            self.query = ''
            self.params = ()

        def execute(self, query, params=()):
            self.query = query
            self.params = params
            if 'SHOW COLUMNS FROM students' in query:
                self.fetchall_result = [
                    {'Field': 'first_name'},
                    {'Field': 'last_name'},
                    {'Field': 'lrn'},
                ]
            elif 'SELECT COUNT(*) AS total' in query:
                self.fetchone_result = {'total': 1}
            elif 'FROM (' in query and 'attempts' in query:
                self.fetchall_result = [{
                    'attempt_id': 17,
                    'attempt_type': 'module',
                    'item_type': 'Module Final',
                    'student_name': 'Student One',
                    'title': 'Python Basics',
                    'language': 'python',
                    'score': 67,
                    'points_earned': 7,
                    'max_points': 10,
                    'result_status': 'failed',
                    'submitted_at': '2026-09-10 09:00:00',
                }]

        def fetchone(self):
            result = self.fetchone_result
            self.fetchone_result = None
            return result

        def fetchall(self):
            result = self.fetchall_result
            self.fetchall_result = []
            return result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'

        response = client.get('/api/teacher/score-attempts?page=1&page_size=40')

    data = response.get_json()
    assert response.status_code == 200
    assert data['success'] is True
    assert data['total'] == 1
    assert data['attempts'][0]['attempt_id'] == 17
    assert data['attempts'][0]['result_status'] == 'failed'
    assert connection.cursor_instance.params == (40, 0)
    assert 'learning_item_submission_history' in connection.cursor_instance.query
    assert 'module_assessment_submission_history' in connection.cursor_instance.query
    assert 'CAST(submitted_at AS CHAR) AS submitted_at' in connection.cursor_instance.query


def test_module_score_endpoint_returns_saved_line_breakdown(monkeypatch):
    breakdown = [{
        'criterion': 'Output line 1',
        'correct': True,
        'points_earned': 2,
        'max_points': 2,
    }]

    class FakeCursor:
        def execute(self, query, params=()):
            self.fetchone_result = {
                'score': 100,
                'points_earned': 10,
                'max_points': 10,
                'attempts': 1,
                'status': 'passed',
                'submitted_at': '2026-10-29 04:00:00',
                'answer_breakdown': json.dumps(breakdown),
            }

        def fetchone(self):
            return self.fetchone_result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConnection())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 9})

        response = client.get('/get_module_assessment_score?module_id=python-01-basics')

    data = response.get_json()
    assert response.status_code == 200
    scaled_breakdown = data['attempt']['answer_breakdown']
    assert scaled_breakdown[0]['points_earned'] == 100
    assert scaled_breakdown[0]['max_points'] == 100
