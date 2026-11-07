from backend import app as app_module


class FakeLoginCursor:
    def __init__(self, user):
        self.user = user

    def execute(self, query, params=()):
        pass

    def fetchone(self):
        return self.user

    def close(self):
        pass


class FakeLoginConnection:
    def __init__(self, user):
        self.login_cursor = FakeLoginCursor(user)
        self.commits = 0

    def cursor(self, dictionary=False):
        return self.login_cursor

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_login_get_renders_login_page():
    with app_module.app.test_client() as client:
        response = client.get('/login')

    assert response.status_code == 200
    assert b'<title>BlockLearn' in response.data
    assert b'verify-student-login-otp' not in response.data
    assert b'studentOtpGroup' not in response.data
    assert b'emailSetupGroup' not in response.data
    assert b'/static/mobile_responsive.css' in response.data


def test_registration_page_requires_email_verification():
    with app_module.app.test_client() as client:
        response = client.get('/registeracc')

    assert response.status_code == 200
    assert b'/send-registration-otp' in response.data
    assert b'id="regOtp"' in response.data
    assert b'/static/mobile_responsive.css' in response.data


def test_student_login_completes_without_email_otp(monkeypatch):
    user = {
        'id': 42,
        'username': '123456789012',
        'full_name': 'Test Student',
        'lrn': '123456789012',
        'grade_level': '10',
        'password': 'stored-password',
        'email': None,
    }
    connection = FakeLoginConnection(user)
    monkeypatch.setattr(app_module, 'get_db_connection', lambda: connection)
    monkeypatch.setattr(app_module, 'lockout_seconds_remaining', lambda *_: 0)
    monkeypatch.setattr(app_module, 'verify_password', lambda *_: (True, False))
    monkeypatch.setattr(app_module, '_complete_login', lambda *_: None)
    monkeypatch.setattr(app_module, 'clear_failed_attempts', lambda *_: None)
    monkeypatch.setattr(app_module, 'log_audit', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        app_module,
        '_issue_student_otp',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('OTP must not be issued')),
    )

    with app_module.app.test_client() as client:
        response = client.post('/login', json={
            'role': 'student',
            'lrn': '123456789012',
            'password': 'student-password',
        })

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'role': 'student',
        'redirect': '/student_dashboard',
    }
    assert connection.commits == 1
