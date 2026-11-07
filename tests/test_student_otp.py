from backend import app as app_module


class FakeConnection:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class FakeCursor:
    def __init__(self, challenge):
        self.challenge = challenge
        self.statements = []

    def execute(self, query, params=()):
        self.statements.append((query, params))
        if query.lstrip().startswith('DELETE'):
            self.challenge = None

    def fetchone(self):
        return self.challenge


def test_student_otp_is_consumed_once(monkeypatch):
    monkeypatch.setattr(app_module.app, 'secret_key', 'test-secret')
    code = '123456'
    challenge_token = 'opaque-challenge-token'
    challenge = {
        'id': 42,
        'otp_hash': app_module._otp_code_hash(challenge_token, code),
        'purpose': 'login',
        'student_id': 3,
        'email': 'student@example.com',
        'attempts': 0,
    }
    cursor = FakeCursor(challenge)

    result, error = app_module._get_valid_student_otp(
        cursor, FakeConnection(), challenge_token, code, 'login',
    )

    assert error is None
    assert result['id'] == 42
    assert cursor.challenge is None
    assert any(query.lstrip().startswith('DELETE') for query, _ in cursor.statements)


def test_student_otp_wrong_code_increments_attempt_count(monkeypatch):
    monkeypatch.setattr(app_module.app, 'secret_key', 'test-secret')
    challenge_token = 'opaque-challenge-token'
    challenge = {
        'id': 42,
        'otp_hash': app_module._otp_code_hash(challenge_token, '123456'),
        'purpose': 'login',
        'student_id': 3,
        'email': 'student@example.com',
        'attempts': 0,
    }
    cursor = FakeCursor(challenge)
    connection = FakeConnection()

    result, error = app_module._get_valid_student_otp(
        cursor, connection, challenge_token, '654321', 'login',
    )

    assert result is None
    assert 'incorrect' in error.lower()
    assert connection.commits == 1
    assert any(query.lstrip().startswith('UPDATE') for query, _ in cursor.statements)
