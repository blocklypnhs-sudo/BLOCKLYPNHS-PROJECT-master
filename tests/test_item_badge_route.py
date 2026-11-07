from flask import Flask

from backend.awards_routes import register_awards_routes


def test_earned_item_badge_is_viewable_but_module_badge_is_not():
    class FakeCursor:
        rowcount = 0

        def execute(self, query, params=()):
            pass

        def fetchall(self):
            return [{
                'badge_code': 'python_a1',
                'earned_at': None,
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

    test_app = Flask(__name__, template_folder='../frontend')
    test_app.secret_key = 'test'
    register_awards_routes(test_app, FakeConnection)

    with test_app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 1})

        earned_badge = client.get('/item_badge/python_a1')
        unavailable_module_badge = client.get('/item_badge/python_module')
        unearned_badge = client.get('/item_badge/python_a2')

    assert earned_badge.status_code == 200
    assert b'Python Assessment 1' in earned_badge.data
    assert unavailable_module_badge.status_code == 302
    assert unearned_badge.status_code == 302
