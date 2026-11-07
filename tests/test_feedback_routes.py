from backend.feedback import FeedbackManager
from backend.app import app


def test_general_student_feedback_appends_for_analytics(monkeypatch):
    executed = []

    class FakeCursor:
        def execute(self, query, params=()):
            executed.append((query, params))
            assert query.lstrip().startswith('INSERT INTO feedback')

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

    monkeypatch.setattr('backend.feedback.get_db_connection', FakeConnection)

    for comment in ('First thought', 'Second thought'):
        result = FeedbackManager.submit_feedback(
            student_id=7,
            student_name='Student Name',
            student_lrn='123456789012',
            rating=5,
            category='Learning Experience',
            comment=comment,
            feedback_type='learning',
            language='php',
        )
        assert result['success'] is True

    assert len(executed) == 2
    assert [params[9] for _, params in executed] == ['First thought', 'Second thought']


def test_student_feedback_route_uses_session_identity(monkeypatch):
    captured = {}

    def capture_feedback(**kwargs):
        captured.update(kwargs)
        return {'success': True, 'message': 'Feedback created successfully'}

    class FakeCursor:
        def execute(self, query, params=()):
            pass

        def fetchone(self):
            return None

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

    monkeypatch.setattr('backend.app.submit_feedback', capture_feedback)
    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'student',
                'user_id': 7,
                'full_name': 'Student Name',
                'lrn': '123456789012',
            })
        response = client.post('/submit_feedback', json={
            'rating': 5,
            'category': 'Learning Experience',
            'comment': 'Clear instructions',
            'feedback_type': 'learning',
            'language': 'php',
        })

    assert response.status_code == 200
    assert captured['student_id'] == 7
    assert captured['student_name'] == 'Student Name'
    assert captured['student_lrn'] == '123456789012'
    assert captured['feedback_type'] == 'learning'
    assert captured['language'] == 'php'
    assert captured['assessment_id'] is None


def test_teacher_feedback_summary_route_returns_learning_analytics(monkeypatch):
    captured_filters = {}

    def fake_summary(filters):
        captured_filters.update(filters)
        return {'success': True, 'total': 2, 'avg_rating': 4.5}

    monkeypatch.setattr('backend.app.get_learning_summary', fake_summary)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'teacher', 'user_id': 9})
        response = client.get('/api/teacher/feedback/summary?language=php&category=Content')

    assert response.status_code == 200
    assert response.get_json()['total'] == 2
    assert captured_filters['language'] == 'php'
    assert captured_filters['category'] == 'Content'