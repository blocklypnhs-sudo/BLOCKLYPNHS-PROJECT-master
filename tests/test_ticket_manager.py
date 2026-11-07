from backend.tickets import get_all_tickets


def test_get_all_tickets_uses_student_columns_available_in_project_schema(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.query = ''
            self.params = ()

        def execute(self, query, params=()):
            self.query = query
            self.params = params

        def fetchall(self):
            if self.query == 'SHOW COLUMNS FROM students':
                return [
                    {'Field': 'id'},
                    {'Field': 'username'},
                    {'Field': 'full_name'},
                    {'Field': 'lrn'},
                    {'Field': 'grade_level'},
                ]
            return []

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.tickets.get_db_connection', lambda: connection)

    result = get_all_tickets()

    assert result == {'success': True, 'tickets': []}
    query = connection.cursor_instance.query
    assert 's.full_name' in query
    assert 's.first_name' not in query
    assert 's.middle_initial' not in query
    assert 's.last_name' not in query
    assert 'FROM ict_tickets t' in query


def test_get_all_tickets_applies_status_filter(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.query = ''
            self.params = ()

        def execute(self, query, params=()):
            self.query = query
            self.params = params

        def fetchall(self):
            if self.query == 'SHOW COLUMNS FROM students':
                return [{'Field': 'username'}, {'Field': 'full_name'}, {'Field': 'lrn'}]
            return []

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.tickets.get_db_connection', lambda: connection)

    result = get_all_tickets('pending')

    assert result == {'success': True, 'tickets': []}
    assert 'WHERE t.status = %s' in connection.cursor_instance.query
    assert connection.cursor_instance.params == ('pending',)
