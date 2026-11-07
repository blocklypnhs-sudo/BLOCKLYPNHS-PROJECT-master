from backend.app import app


def test_student_profile_renders_database_record_over_stale_session(monkeypatch):
    student = {
        'id': 7,
        'username': '123456789012',
        'full_name': 'Franceska F Felonia',
        'display_name': 'Franceska F Felonia',
        'lrn': '123456789012',
        'grade_level': 'Grade 11 - ICT',
        'email': 'franceska@example.com',
        'created_at': 'September 30, 2026',
    }

    class FakeCursor:
        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchone(self):
            return student

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
            session.update({
                'role': 'student',
                'user_id': 7,
                'username': '123456789012',
                'full_name': '123456789012',
                'lrn': '123456789012',
            })

        response = client.get('/student_profile')

    assert response.status_code == 200
    assert b'Franceska F Felonia' in response.data
    assert b'Grade 11 - ICT' in response.data
    assert b'franceska@example.com' in response.data
    assert b'id="profileName">Franceska F Felonia</span>' in response.data
    assert b'id="pdName">Franceska F Felonia</div>' in response.data
    assert b'Edit Profile' not in response.data
    assert b'id="editProfileModal"' not in response.data
    assert b'function saveProfile(' not in response.data
    assert b'Activities Done' not in response.data
    assert b'statActivities' not in response.data
    assert b'Average Score' not in response.data
    assert b'statAvgScore' not in response.data


def test_student_dashboard_uses_database_name_in_greeting_and_account_menu(monkeypatch):
    student = {
        'username': '136761100534',
        'full_name': 'Maria Santos',
        'lrn': '136761100534',
        'grade_level': 'Grade 11',
    }

    class FakeCursor:
        def execute(self, query, params):
            assert 'FROM students WHERE id = %s' in query
            assert params == (7,)

        def fetchone(self):
            return student

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'student',
                'user_id': 7,
                'username': '136761100534',
                'full_name': '136761100534',
                'lrn': '136761100534',
            })

        response = client.get('/student_dashboard')

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<em id="greetingName">Maria Santos!</em>' in page
    assert 'id="profileName">Maria Santos</span>' in page
    assert 'id="pdName">Maria Santos</div>' in page
    assert 'data-student-lrn="136761100534"' in page


def test_student_settings_uses_database_name_in_account_menu(monkeypatch):
    class FakeCursor:
        def execute(self, query, params):
            assert 'FROM students WHERE id = %s' in query
            assert params == (7,)

        def fetchone(self):
            return {
                'username': '136761100534',
                'full_name': 'Maria Santos',
                'lrn': '136761100534',
                'grade_level': 'Grade 11',
                'email': 'maria@example.com',
            }

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'student',
                'user_id': 7,
                'username': '136761100534',
                'full_name': '136761100534',
                'lrn': '136761100534',
            })

        response = client.get('/student_settings')

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="profileName">Maria Santos</span>' in page
    assert 'id="pdName">Maria Santos</div>' in page
    assert 'id="settingsLrn">136761100534</span>' in page
    assert 'id="settingsEmailDisplay">maria@example.com</span>' in page
    assert 'id="editFullName"' in page and 'value="Maria Santos"' in page
    assert 'id="editGradeLevel"' in page and 'value="Grade 11"' in page
    assert 'onsubmit="saveProfileSettings(event)"' in page
    assert "var PROFILE_API  = '/update_profile';" in page


def test_student_dashboard_does_not_use_lrn_as_name_when_full_name_is_missing(monkeypatch):
    class FakeCursor:
        def execute(self, query, params):
            pass

        def fetchone(self):
            return {
                'username': '136761100534',
                'full_name': None,
                'lrn': '136761100534',
                'grade_level': 'Grade 11',
            }

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'student',
                'user_id': 7,
                'username': '136761100534',
                'full_name': '136761100534',
                'lrn': '136761100534',
            })

        response = client.get('/student_dashboard')

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<em id="greetingName">Student!</em>' in page
    assert 'id="profileName">Student</span>' in page
    assert 'data-student-lrn="136761100534"' in page


def test_update_profile_persists_account_fields(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params):
            self.calls.append((query, params))

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()
            self.committed = False

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            self.committed = True

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'student',
                'user_id': 7,
                'student_name_loaded': True,
            })

        response = client.post('/update_profile', json={
            'full_name': 'Franceska Felonia',
            'grade_level': 'Grade 11 - ICT',
            'email': 'franceska@example.com',
        })

    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert connection.committed is True
    assert connection.cursor_instance.calls == [(
        'UPDATE students SET full_name = %s, grade_level = %s, email = %s WHERE id = %s',
        ('Franceska Felonia', 'Grade 11 - ICT', 'franceska@example.com', 7),
    )]