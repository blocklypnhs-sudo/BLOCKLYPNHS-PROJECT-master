from backend.app import app


def test_ict_dashboard_data_returns_student_counts_and_recent_students(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.query = ''
            self.result = []

        def execute(self, query, params=()):
            self.query = query
            if query.startswith('SHOW COLUMNS FROM students'):
                self.result = [
                    {'Field': 'first_name'},
                    {'Field': 'middle_initial'},
                    {'Field': 'last_name'},
                    {'Field': 'username'},
                    {'Field': 'full_name'},
                ]
            elif 'COUNT(*) AS total_students' in query:
                self.result = [{'total_students': 12}]
            elif 'COUNT(*) AS registered_today' in query:
                self.result = [{'registered_today': 2}]
            elif 'FROM students s' in query:
                self.result = [{
                    'id': 12,
                    'username': 'student12',
                    'full_name': 'Student Twelve',
                    'lrn': '123456789012',
                    'created_at': '2026-10-22 09:00:00',
                }]
            elif 'COUNT(*) AS total_tickets' in query:
                self.result = [{'total_tickets': 4}]
            elif 'COUNT(*) AS pending_tickets' in query:
                self.result = [{'pending_tickets': 1}]
            else:
                self.result = []

        def fetchone(self):
            return self.result[0] if self.result else None

        def fetchall(self):
            return list(self.result)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'ict'

        response = client.get('/get_ict_dashboard_data')

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['total_students'] == 12
    assert payload['registered_today'] == 2
    assert payload['students'][0]['lrn'] == '123456789012'
