from backend import app as app_module


class FakeCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append((query, params))

    def fetchone(self):
        return {
            'id': 7,
            'email': 'student@example.com',
            'full_name': 'Test Student',
            'username': 'test-student',
        }

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.db_cursor = FakeCursor()
        self.commits = 0

    def cursor(self, dictionary=False):
        assert dictionary is True
        return self.db_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def test_forgot_password_sends_link_with_reset_template(monkeypatch):
    connection = FakeConnection()
    sent = {}
    monkeypatch.setattr(app_module, 'get_db_connection', lambda: connection)
    monkeypatch.setattr(
        app_module,
        'send_password_reset_email',
        lambda email, name, url: sent.update(email=email, name=name, url=url) or (True, ''),
    )
    monkeypatch.setenv('APP_BASE_URL', 'https://blocklearn.example')

    with app_module.app.test_client() as client:
        response = client.post('/forgot-password', json={'identifier': '123456789012'})

    assert response.status_code == 200
    result = response.get_json()
    assert result['success'] is True
    assert 'reset_url' not in result
    assert sent['email'] == 'student@example.com'
    assert sent['name'] == 'Test Student'
    assert sent['url'].startswith('https://blocklearn.example/reset-password?token=')
    assert connection.commits == 1
    update = next(query for query in connection.db_cursor.queries if query[0].lstrip().startswith('UPDATE'))
    assert update[1][2] == 7


def test_forgot_password_requires_email_on_student_account(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(app_module, 'get_db_connection', lambda: connection)
    monkeypatch.setattr(
        app_module,
        'send_password_reset_email',
        lambda *_args: (_ for _ in ()).throw(AssertionError('must not send')),
    )
    connection.db_cursor.fetchone = lambda: {
        'id': 7,
        'email': None,
        'full_name': 'Test Student',
        'username': 'test-student',
    }

    with app_module.app.test_client() as client:
        response = client.post('/forgot-password', json={'identifier': '123456789012'})

    assert response.status_code == 400
    assert 'no usable email' in response.get_json()['message'].lower()
