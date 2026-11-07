from backend.app import app


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
