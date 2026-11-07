from backend.app import app


def test_homepage_redirects_authenticated_users_to_their_dashboard():
    dashboard_by_role = {
        'student': '/student_dashboard',
        'teacher': '/teacher_dashboard',
        'ict': '/ict_support_dashboard',
    }

    with app.test_client() as client:
        for role, dashboard_path in dashboard_by_role.items():
            with client.session_transaction() as session:
                session.clear()
                session.update({'role': role, 'user_id': 1})

            response = client.get('/')

            assert response.status_code == 302
            assert response.location.endswith(dashboard_path)
            assert response.headers['Cache-Control'] == (
                'no-store, no-cache, must-revalidate, private'
            )


def test_teacher_cannot_reopen_dashboard_after_logout():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'teacher',
                'user_id': 1,
                'username': 'teacher1',
            })

        authenticated_dashboard = client.get('/teacher_dashboard')
        assert authenticated_dashboard.status_code == 200
        assert authenticated_dashboard.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )

        logout_response = client.get('/logout')
        assert logout_response.status_code == 302
        assert logout_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )

        with client.session_transaction() as session:
            assert not session

        dashboard_response = client.get('/teacher_dashboard')
        assert dashboard_response.status_code == 302
        assert dashboard_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )
        assert dashboard_response.location.endswith('/')

        homepage_response = client.get('/')
        assert homepage_response.status_code == 200
        assert b'Login' in homepage_response.data
        assert homepage_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )


def test_student_cannot_reopen_dashboard_after_logout(monkeypatch):
    student = {
        'username': '123456789012',
        'full_name': 'Student User',
        'lrn': '123456789012',
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
                'username': student['username'],
                'lrn': student['lrn'],
            })

        dashboard_response = client.get('/student_dashboard')
        assert dashboard_response.status_code == 200
        assert dashboard_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )

        logout_response = client.get('/logout')
        assert logout_response.status_code == 302

        with client.session_transaction() as session:
            assert not session

        back_navigation_response = client.get('/student_dashboard')
        assert back_navigation_response.status_code == 302
        assert back_navigation_response.location.endswith('/')
        assert back_navigation_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )


def test_ict_cannot_reopen_dashboard_after_logout():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'role': 'ict',
                'user_id': 1,
                'username': 'ict-tech',
            })

        authenticated_dashboard = client.get('/ict_support_dashboard')
        assert authenticated_dashboard.status_code == 200
        assert authenticated_dashboard.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )

        logout_response = client.get('/logout')
        assert logout_response.status_code == 302
        assert logout_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )

        with client.session_transaction() as session:
            assert not session

        back_navigation_response = client.get('/ict_support_dashboard')
        assert back_navigation_response.status_code == 302
        assert back_navigation_response.location.endswith('/')
        assert back_navigation_response.headers['Cache-Control'] == (
            'no-store, no-cache, must-revalidate, private'
        )
