from datetime import datetime

from backend.app import app
from backend.notification_service import (
    get_notifications_for_user,
    notify_assessment_checked,
)


def _student_session(client):
    with client.session_transaction() as session:
        session.update({'role': 'student', 'user_id': 17})


def test_student_notifications_page_and_list_endpoint_are_connected(monkeypatch):
    monkeypatch.setattr(
        'backend.app.get_notifications_for_user',
        lambda user_id, role: [
            {'id': 3, 'is_read': 0, 'type': 'assessment_result', 'title': 'Assessment', 'message': 'Score: 8/10'}
        ],
    )

    with app.test_client() as client:
        _student_session(client)
        page = client.get('/notifications')
        response = client.get('/get_notifications')

    assert page.status_code == 200
    assert b'Student Notifications' in page.data
    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'notifications': [
            {'id': 3, 'is_read': 0, 'type': 'assessment_result', 'title': 'Assessment', 'message': 'Score: 8/10'}
        ],
        'unread_count': 1,
    }


def test_unread_count_endpoint_returns_count_for_authenticated_user(monkeypatch):
    captured = {}

    def fake_count(user_id, role):
        captured.update(user_id=user_id, role=role)
        return 4

    monkeypatch.setattr('backend.app.get_unread_notification_count', fake_count)

    with app.test_client() as client:
        _student_session(client)
        response = client.get('/get_unread_count')

    assert response.status_code == 200
    assert response.get_json() == {'success': True, 'count': 4, 'unread_count': 4}
    assert captured == {'user_id': 17, 'role': 'student'}


def test_notification_read_endpoints_are_connected(monkeypatch):
    marked_one = []
    marked_all = []

    monkeypatch.setattr(
        'backend.app.mark_notification_read',
        lambda notification_id, user_id, role: marked_one.append((notification_id, user_id, role)) or True,
    )
    monkeypatch.setattr(
        'backend.app.mark_all_notifications_read',
        lambda user_id, role: marked_all.append((user_id, role)) or True,
    )

    with app.test_client() as client:
        _student_session(client)
        one_response = client.post('/mark_notification_read', json={'notification_id': 3})
        page_response = client.post('/mark_notifications_read')
        dashboard_response = client.post('/mark_all_notifications_read')

    assert one_response.status_code == 200
    assert one_response.get_json() == {'success': True}
    assert page_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert marked_one == [(3, 17, 'student')]
    assert marked_all == [(17, 'student'), (17, 'student')]


def test_notification_read_endpoint_rejects_invalid_id():
    with app.test_client() as client:
        _student_session(client)
        response = client.post('/mark_notification_read', json={'notification_id': 'invalid'})

    assert response.status_code == 400
    assert response.get_json()['success'] is False


def test_notification_list_reports_database_errors(monkeypatch):
    def fail_to_load(user_id, role):
        raise RuntimeError('database unavailable')

    monkeypatch.setattr('backend.app.get_notifications_for_user', fail_to_load)

    with app.test_client() as client:
        _student_session(client)
        response = client.get('/get_notifications')

    assert response.status_code == 500
    assert response.get_json() == {
        'success': False,
        'message': 'Unable to load notifications',
    }


def test_score_update_notification_identifies_activity_and_shows_new_score(monkeypatch):
    captured = {}

    def fake_insert(notification_type, title, message, **kwargs):
        captured.update(
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs,
        )
        return True

    monkeypatch.setattr('backend.notification_service._insert_notification', fake_insert)

    assert notify_assessment_checked(
        17, 'Variables Activity', 8, 'Great work', 42, 10, 'Activity'
    )
    assert captured == {
        'notification_type': 'activity_checked',
        'title': 'Activity Score Updated',
        'message': 'Your teacher updated your activity score for Variables Activity: '
        '8/10 points. Feedback: Great work',
        'user_id': 17,
        'target_role': 'student',
        'related_id': 42,
    }


def test_failing_score_notifications_include_the_exact_retry_destination(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            self.query = query

        def fetchall(self):
            return [
                {
                    'id': 42,
                    'type': 'activity_checked',
                    'title': 'Activity Score Updated',
                    'message': 'Your teacher updated your score.',
                    'related_id': 12,
                    'is_read': 0,
                    'created_at': datetime.now(),
                    'max_points': 10,
                    'item_language': 'php',
                    'item_number': 3,
                    'teacher_score': 6,
                    'module_language': None,
                    'module_number': None,
                    'module_points_earned': None,
                    'module_max_points': None,
                },
                {
                    'id': 43,
                    'type': 'assessment_checked',
                    'title': 'Assessment Score Updated',
                    'message': 'Your teacher updated your assessment score.',
                    'related_id': 13,
                    'is_read': 0,
                    'created_at': datetime.now(),
                    'max_points': 10,
                    'item_language': 'python',
                    'item_number': 4,
                    'teacher_score': 78,
                    'module_language': None,
                    'module_number': None,
                    'module_points_earned': None,
                    'module_max_points': None,
                },
                {
                    'id': 44,
                    'type': 'module_score_updated',
                    'title': 'Module Score Updated',
                    'message': 'Your teacher updated your module score.',
                    'related_id': 15,
                    'is_read': 0,
                    'created_at': datetime.now(),
                    'max_points': None,
                    'item_language': None,
                    'item_number': None,
                    'teacher_score': None,
                    'module_language': 'java',
                    'module_number': 2,
                    'module_points_earned': 7,
                    'module_max_points': 10,
                },
            ]

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(
        'backend.notification_service.get_db_connection',
        FakeConnection,
    )

    notifications = get_notifications_for_user(17, 'student')

    assert notifications[0]['retry_url'] == '/playground_php?activity=3'
    assert notifications[1]['retry_url'] == '/assessment_python_activity?id=4'
    assert notifications[2]['retry_url'] == '/student_modules/java/2'
