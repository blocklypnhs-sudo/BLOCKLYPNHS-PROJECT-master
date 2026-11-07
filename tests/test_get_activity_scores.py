from backend.app import app


def test_get_activity_scores_uses_assessment_attempts_fallback(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._result = []
            self._execute_calls = []

        def execute(self, query, params=()):
            self._execute_calls.append((query, params))
            if 'FROM activities' in query and 'student_id = %s' in query:
                self._result = []
            elif 'FROM assessment_attempts aa' in query:
                self._result = [{
                    'lrn': '123456789012',
                    'activity_name': 'Hello C++',
                    'language': 'cpp',
                    'score': 9.0,
                    'max_score': 10,
                    'completed_at': '2026-09-10 09:00'
                }]
            else:
                self._result = []

        def fetchall(self):
            return list(self._result)

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'

        response = client.get('/get_activity_scores')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['scores'][0]['lrn'] == '123456789012'
    assert data['scores'][0]['activity_name'] == 'Hello C++'
    assert data['scores'][0]['score'] == 9.0
    assert data['scores'][0]['max_score'] == 10


def test_leaderboard_uses_activity_and_assessment_scores(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.result = []
            self.query = ''
            self.queries = []

        def execute(self, query, params=()):
            self.query = query
            self.queries.append(query)
            if 'SHOW COLUMNS FROM students' in query:
                self.result = [
                    {'Field': 'full_name'},
                    {'Field': 'username'},
                    {'Field': 'lrn'},
                ]
            elif 'SUM(duration_seconds)' in query:
                self.result = [{'student_id': 7, 'learning_time_seconds': 3661}]
            else:
                self.result = [{
                    'id': 7,
                    'name': 'Student One',
                    'grade': 'Grade 11',
                    'completed': 2,
                    'points': 19,
                    'progress': 13,
                    'avg_score': 9.5,
                    'activity_percentage': 12.7,
                    'attempts': 4,
                }]

        def fetchall(self):
            return self.result

        def fetchone(self):
            return {}

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    conn = FakeConn()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: conn)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'

        response = client.get('/leaderboard')

    assert response.status_code == 200
    data = response.get_json()
    assert data['leaderboard'][0]['average_score'] == 9.5
    assert data['leaderboard'][0]['activity_percentage'] == 12.7
    assert data['leaderboard'][0]['activities_attempted'] == 2
    assert data['leaderboard'][0]['attempts'] == 4
    assert data['leaderboard'][0]['learning_time_seconds'] == 3661
    assert data['leaderboard'][0]['student_name'] == 'Student One'
    assert 'lrn' not in data['leaderboard'][0]
    leaderboard_query = next(query for query in conn.cursor_obj.queries if 'FROM students s' in query)
    assert "d.language IN ('php', 'javascript', 'cpp')" in leaderboard_query
    assert 'd.assessment_number BETWEEN 1 AND 5' in leaderboard_query
    assert 'CROSS JOIN activities d' in leaderboard_query
    assert '/ 150 * 100' in leaderboard_query
    assert 'LEAST(10' in leaderboard_query
    assert 'aa.auto_score > 0 OR aa.score = 0' in leaderboard_query
    assert 'FROM learning_item_submission_history' in leaderboard_query
    assert 'COUNT(*) AS attempt_count' in leaderboard_query
    assert 'HAVING SUM(scored.is_completed) > 0' in leaderboard_query
    assert 'ORDER BY activity_percentage DESC' in leaderboard_query

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'

        response = client.get('/teacher/leaderboard_data')

    assert response.status_code == 200
    teacher_row = response.get_json()['leaderboard'][0]
    assert teacher_row['rank'] == 1
    assert teacher_row['name'] == 'Student One'
    assert teacher_row['grade'] == 'Grade 11'
    assert teacher_row['avg_score'] == 9.5
    assert teacher_row['points'] == 19
    assert teacher_row['activity_percentage'] == 12.7
    assert teacher_row['attempts'] == 4
    assert teacher_row['learning_time_seconds'] == 3661


def test_assessment_results_returns_scores_out_of_ten(monkeypatch):
    class FakeCursor:
        query = ''

        def execute(self, query):
            self.query = query

        def fetchall(self):
            if self.query == 'SHOW COLUMNS FROM students':
                return [
                    {'Field': 'full_name'},
                    {'Field': 'username'},
                    {'Field': 'lrn'},
                ]
            return [{
                'score': 9.0,
                'max_score': 10,
                'result': 'Passed',
            }]

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

        response = client.get('/get_assessment_results')

    assert response.status_code == 200
    result = response.get_json()['results'][0]
    assert result['score'] == 9.0
    assert result['max_score'] == 10
    assert 'ROUND(a.score / 10, 1)' in connection.cursor_instance.query
    assert "CASE WHEN a.score >= 75 THEN 'Passed'" in connection.cursor_instance.query


def test_activity_score_leaderboard_returns_per_item_rankings(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.result = []
            self.query = ''

        def execute(self, query, params=()):
            self.query = query
            if query == 'SHOW COLUMNS FROM students':
                self.result = [
                    {'Field': 'full_name'},
                    {'Field': 'username'},
                    {'Field': 'lrn'},
                ]
            else:
                self.result = [
                    {
                        'student_id': 1,
                        'student_name': 'Student One',
                        'item_id': 3,
                        'item_name': 'Loops',
                        'language': 'php',
                        'item_type': 'Activity',
                        'score': 9,
                        'submitted_at': None,
                    },
                    {
                        'student_id': 2,
                        'student_name': 'Student Two',
                        'item_id': 3,
                        'item_name': 'Loops',
                        'language': 'php',
                        'item_type': 'Activity',
                        'score': 9,
                        'submitted_at': None,
                    },
                    {
                        'student_id': 3,
                        'student_name': 'Student Three',
                        'item_id': 3,
                        'item_name': 'Loops',
                        'language': 'php',
                        'item_type': 'Activity',
                        'score': 8,
                        'submitted_at': None,
                    },
                    {
                        'student_id': 1,
                        'student_name': 'Student One',
                        'item_id': 4,
                        'item_name': 'Functions',
                        'language': 'php',
                        'item_type': 'Activity',
                        'score': 10,
                        'submitted_at': None,
                    },
                ]

        def fetchall(self):
            return list(self.result)

        def fetchone(self):
            return None

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
            session['role'] = 'student'
        response = client.get('/leaderboard/activity-scores')

    assert response.status_code == 200
    scores = response.get_json()['scores']
    assert [row['rank'] for row in scores] == [1, 1, 3, 1]
    assert [row['score'] for row in scores] == [9.0, 9.0, 8.0, 10.0]
    assert 'JOIN learning_items item' in connection.cursor_instance.query


def test_grading_exports_fetch_all_rows_without_regular_page_limits(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.result = []
            self.query = ''

        def execute(self, query, params=()):
            self.query = query
            if query == 'SHOW COLUMNS FROM students':
                self.result = [
                    {'Field': 'full_name'},
                    {'Field': 'username'},
                    {'Field': 'lrn'},
                ]

        def fetchall(self):
            return list(self.result)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    for path in ('/get_scores?export=1', '/get_assessment_results?export=1'):
        connection = FakeConnection()
        monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
        with app.test_client() as client:
            with client.session_transaction() as session:
                session['role'] = 'teacher'
            response = client.get(path)

        assert response.status_code == 200
        assert 'LIMIT' not in connection.cursor_instance.query


def test_leaderboard_pages_are_available_to_their_roles():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
        student_page = client.get('/student_leaderboard')
        assert student_page.status_code == 200

        with client.session_transaction() as session:
            session['role'] = 'teacher'
        teacher_page = client.get('/teacher_leaderboard')
        assert teacher_page.status_code == 200


def test_teacher_score_submissions_route_uses_assessment_attempts(monkeypatch):
    expected = [{
        'submission_id': 42,
        'student_name': 'Student One',
        'student_lrn': '123456789012',
        'activity_title': 'Hello Python',
        'question': 'Print Hello to the console.',
        'guide': 'Use print() to display the message.',
        'expected_output': 'Hello',
        'language': 'python',
        'item_type': 'assessment',
        'max_score': 10,
        'raw_score': 70,
        'auto_score': 7,
        'teacher_score': None,
        'teacher_feedback': None,
        'code': 'print("Hello")',
        'output': 'Hello',
        'status': 'passed',
    }]

    class FakeCursor:
        def execute(self, query):
            assert 'FROM assessment_attempts a' in query
            assert 'd.description AS question' in query
            assert 'd.hint AS guide' in query
            assert 'a.code_blocks AS code_blocks' in query
            assert 'a.generated_code AS code' in query
            assert 'a.score AS raw_score' in query
            assert 'a.submitted_at' in query
            assert 'd.expected_output AS expected_output' in query
            assert "d.language = 'python'" in query
            assert "ELSE 'pending'" in query
            assert "WHERE a.status = 'submitted'" in query
            assert "THEN 'activity'" in query
            assert "ELSE 'assessment' END AS item_type" in query

        def fetchall(self):
            return expected

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'

        response = client.get('/teacher/get_submissions')

    assert response.status_code == 200
    assert response.get_json() == {'success': True, 'submissions': expected}


    def test_php_teacher_submission_generates_code_from_saved_workspace(monkeypatch):
        workspace_xml = (
            '<xml><block type="php_echo"><value name="TEXT">'
            '<block type="php_text"><field name="TEXT">Hello, PHP!</field></block>'
            '</value></block></xml>'
        )

        class FakeCursor:
            def execute(self, query):
                assert 'a.code_blocks AS code_blocks' in query

            def fetchall(self):
                return [{
                    'submission_id': 303,
                    'language': 'php',
                    'code': '',
                    'code_blocks': workspace_xml,
                }]

            def close(self):
                pass

        class FakeConnection:
            def cursor(self, dictionary=True):
                return FakeCursor()

            def close(self):
                pass

        monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)

        with app.test_client() as client:
            with client.session_transaction() as session:
                session['role'] = 'teacher'
            response = client.get('/teacher/get_submissions')

        assert response.status_code == 200
        submission = response.get_json()['submissions'][0]
        assert submission['code'] == 'echo "Hello, PHP!";'
        assert 'code_blocks' not in submission


def test_teacher_review_route_saves_teacher_score_to_attempt(monkeypatch):
    executed = []

    class FakeCursor:
        def execute(self, query, params=()):
            executed.append((query, params))

        def fetchone(self):
            return {
                'points': 10,
                'title': 'Hello Python',
                'language': 'python',
                'assessment_number': 3,
                'student_id': 99,
            }

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())
    monkeypatch.setattr('backend.app.notify_assessment_checked', lambda *args: None)
    awarded = []
    monkeypatch.setattr(
        'backend.app.try_award_after_submission',
        lambda cursor, student_id, language, assessment_number: (
            awarded.append((student_id, language, assessment_number)) or {
                'new_badges': ['python_a3'],
                'certificate_issued': True,
                'module_complete': True,
            }
        ),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'teacher'
            session['user_id'] = 7

        response = client.post('/teacher/review_submission', json={
            'submission_id': 42,
            'score': 8,
            'feedback': 'Good work',
        })

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert result['new_badges'] == ['python_a3']
    assert result['certificate_issued'] is True
    assert result['module_complete'] is True
    update_query, update_params = executed[1]
    assert 'UPDATE assessment_attempts' in update_query
    assert update_params[:4] == (80, 8, 'Good work', 7)
    assert update_params[-1] == 42
    assert awarded == [(99, 'python', 3)]
