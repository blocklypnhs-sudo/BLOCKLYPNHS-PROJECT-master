import pytest

from backend.app import app


@pytest.mark.parametrize(
    ('language', 'expected_heading'),
    [('python', 'Python Playground'), ('java', 'Java Playground')],
)
def test_assessment_activity_opens_playground(monkeypatch, language, expected_heading):
    class FakeCursor:
        def execute(self, query, params=()):
            self.result = {'title': f'{language.title()} Fundamentals'}

        def fetchone(self):
            return self.result

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    monkeypatch.setattr(
        'backend.app.get_db_connection',
        lambda: FakeConnection(),
    )

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 1

        response = client.get(f'/assessment_{language}_activity?id=1')

    assert response.status_code == 200
    assert expected_heading.encode() in response.data
    assert b'id="blocklyDiv"' in response.data
