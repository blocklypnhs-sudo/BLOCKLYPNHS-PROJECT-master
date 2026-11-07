from backend.app import _activity_is_unlocked, app


def test_playground_pages_include_sequence_controls_without_timer():
    playgrounds = (
        ('/playground_php', b'phpActivities'),
        ('/playground_javascript', b'jsActivities'),
        ('/playground_cpp', b'cppActivities'),
    )
    for path, activity_config in playgrounds:
        with app.test_client() as client:
            with client.session_transaction() as student_session:
                student_session.update({
                    'role': 'student',
                    'user_id': 41,
                    'student_name_loaded': True,
                })
            response = client.get(path)

        assert response.status_code == 200
        assert b'/static/js/activity_session.js' in response.data
        assert b'id="activityTimeLimit"' not in response.data
        assert activity_config in response.data


def test_activity_sequence_requires_previous_activity_to_pass(monkeypatch):
    class FakeCursor:
        def __init__(self, previous_attempt):
            self.previous_attempt = previous_attempt

        def execute(self, query, params=()):
            self.params = params

        def fetchone(self):
            return self.previous_attempt

    monkeypatch.setattr('backend.app.are_activities_unlocked', lambda *args: True)

    assert _activity_is_unlocked(
        FakeCursor({'status': 'submitted', 'score': 80, 'auto_score': 8}),
        41, 'php', 2,
    )
    assert not _activity_is_unlocked(
        FakeCursor({'status': 'submitted', 'score': 40, 'auto_score': 4}),
        41, 'php', 2,
    )
    assert not _activity_is_unlocked(
        FakeCursor(None),
        41, 'php', 3,
    )


def test_start_activity_records_activity_without_timer(monkeypatch):
    executed = []

    class FakeCursor:
        def execute(self, query, params=()):
            executed.append((query, params))
            if 'FROM learning_items' in query:
                self.result = {'id': 12}
            elif 'FROM assessment_attempts' in query:
                self.result = None
            else:
                self.result = None

        def fetchone(self):
            result = getattr(self, 'result', None)
            self.result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)
    monkeypatch.setattr('backend.app._activity_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.log_audit', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as student_session:
            student_session.update({
                'role': 'student',
                'user_id': 41,
                'student_name_loaded': True,
            })
        response = client.post('/start_activity', json={
            'language': 'php',
            'assessment_number': 1,
        })

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert 'time_limit_seconds' not in result
    timer_insert = next(query for query, _ in executed if 'INSERT INTO activity_attempt_sessions' in query)
    assert 'INTERVAL 10 YEAR' in timer_insert


def test_start_activity_rejects_later_activity_until_previous_passes(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            self.result = {'id': 13} if 'FROM learning_items' in query else None

        def fetchone(self):
            result = getattr(self, 'result', None)
            self.result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)
    monkeypatch.setattr('backend.app._activity_is_unlocked', lambda *args: False)
    monkeypatch.setattr('backend.app.log_audit', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as student_session:
            student_session.update({
                'role': 'student',
                'user_id': 41,
                'student_name_loaded': True,
            })
        response = client.post('/start_activity', json={
            'language': 'php',
            'assessment_number': 2,
        })

    assert response.status_code == 403
    assert response.get_json()['message'] == 'Complete and pass the previous activity first'


def test_submit_activity_allows_submission_without_timer(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            if 'SELECT id, title, description, hint, required_blocks' in query:
                self.result = {
                    'id': 12,
                    'title': 'Hello PHP',
                    'expected_output': 'Hello, PHP!',
                    'points': 10,
                    'description': 'Print Hello, PHP!',
                    'hint': '',
                    'required_blocks': 'echo,TEXT',
                }
            else:
                self.result = None

        def fetchone(self):
            result = getattr(self, 'result', None)
            self.result = None
            return result

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)
    monkeypatch.setattr('backend.app._activity_is_unlocked', lambda *args: True)
    monkeypatch.setattr('backend.app.log_audit', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as student_session:
            student_session.update({
                'role': 'student',
                'user_id': 41,
                'student_name_loaded': True,
            })
        response = client.post('/submit_activity', json={
            'language': 'php',
            'assessment_number': 1,
            'code_blocks': '<xml><block type="php_echo"></block></xml>',
        })

    assert response.status_code == 200
    assert response.get_json()['success'] is True
