import json

from backend import emailjs_service


def test_emailjs_requires_service_template_and_public_key(monkeypatch):
    for key in (
        'EMAILJS_SERVICE_ID',
        'EMAILJS_TEMPLATE_ID',
        'EMAILJS_PUBLIC_KEY',
    ):
        monkeypatch.delenv(key, raising=False)

    sent, error = emailjs_service.send_student_otp('student@example.com', '012345')

    assert sent is False
    assert 'not configured' in error


def test_emailjs_sends_template_values_using_server_credentials(monkeypatch):
    monkeypatch.setenv('EMAILJS_SERVICE_ID', 'service_test')
    monkeypatch.setenv('EMAILJS_TEMPLATE_ID', 'template_test')
    monkeypatch.setenv('EMAILJS_PUBLIC_KEY', 'public_test')
    monkeypatch.setenv('EMAILJS_PRIVATE_KEY', 'private_test')
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'ok'

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['timeout'] = timeout
        captured['user_agent'] = request.get_header('User-agent')
        captured['payload'] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(emailjs_service.urllib.request, 'urlopen', fake_urlopen)

    sent, error = emailjs_service.send_student_otp(
        'student@example.com', '012345', 'Student One',
    )

    assert sent is True
    assert error == ''
    assert captured['url'] == emailjs_service.EMAILJS_URL
    assert captured['timeout'] == 15
    assert captured['user_agent'] == 'BlockLearn/1.0'
    assert captured['payload'] == {
        'service_id': 'service_test',
        'template_id': 'template_test',
        'user_id': 'public_test',
        'accessToken': 'private_test',
        'template_params': {
            'email': 'student@example.com',
            'name': 'Student One',
            'passcode': '012345',
            'time': captured['payload']['template_params']['time'],
        },
    }
    assert len(captured['payload']['template_params']['time']) == 8


def test_password_reset_uses_separate_template_and_link_variable(monkeypatch):
    monkeypatch.setenv('EMAILJS_SERVICE_ID', 'service_test')
    monkeypatch.setenv('EMAILJS_TEMPLATE_ID', 'template_otp')
    monkeypatch.setenv('EMAILJS_PASSWORD_RESET_TEMPLATE_ID', 'template_reset')
    monkeypatch.setenv('EMAILJS_PUBLIC_KEY', 'public_test')
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'ok'

    def fake_urlopen(request, timeout):
        captured['payload'] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(emailjs_service.urllib.request, 'urlopen', fake_urlopen)

    sent, error = emailjs_service.send_password_reset_email(
        'student@example.com',
        'Student One',
        'https://blocklearn.example/reset-password?token=one-time-token',
    )

    assert sent is True
    assert error == ''
    assert captured['payload']['template_id'] == 'template_reset'
    assert captured['payload']['template_params'] == {
        'email': 'student@example.com',
        'name': 'Student One',
        'link': 'https://blocklearn.example/reset-password?token=one-time-token',
    }


def test_password_reset_requires_its_template_id(monkeypatch):
    monkeypatch.setenv('EMAILJS_SERVICE_ID', 'service_test')
    monkeypatch.setenv('EMAILJS_PUBLIC_KEY', 'public_test')
    monkeypatch.delenv('EMAILJS_PASSWORD_RESET_TEMPLATE_ID', raising=False)

    sent, error = emailjs_service.send_password_reset_email(
        'student@example.com', 'Student One', 'https://example.com/reset',
    )

    assert sent is False
    assert 'EMAILJS_PASSWORD_RESET_TEMPLATE_ID' in error
