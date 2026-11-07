import pytest

from backend.app import app
from backend.module_awards import are_activities_unlocked


@pytest.mark.parametrize('language', ('php', 'javascript', 'cpp'))
@pytest.mark.parametrize(('completed_lessons', 'expected'), ((1, False), (2, True)))
def test_language_activity_unlock_requires_both_module_lessons(
    language, completed_lessons, expected,
):
    class FakeCursor:
        def execute(self, query, params=()):
            self.language = params[1]

        def fetchone(self):
            return {'total': completed_lessons}

    cursor = FakeCursor()
    assert are_activities_unlocked(cursor, 99, language) is expected
    assert cursor.language == language


@pytest.mark.parametrize('unlocked_language', ('php', 'javascript', 'cpp'))
def test_activity_pages_unlock_for_their_own_completed_language_modules(
    monkeypatch, unlocked_language,
):
    class FakeCursor:
        def execute(self, query, params=()):
            pass

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConnection())
    monkeypatch.setattr('backend.app.get_student_activity_scores', lambda *args: [])
    monkeypatch.setattr(
        'backend.app.are_activities_unlocked',
        lambda cursor, student_id, language=None: language == unlocked_language,
    )

    with app.test_client() as client:
        with client.session_transaction() as student_session:
            student_session.update({
                'role': 'student',
                'user_id': 99,
                'student_name_loaded': True,
            })

        response = client.get('/get_activities')

    assert response.status_code == 200
    result = response.get_json()
    assert result['activities_unlocked'] is False
    assert result['activities_unlocked_by_language'] == {
        language: language == unlocked_language
        for language in ('php', 'javascript', 'cpp')
    }
    language_examples = {
        'php': 'Hello, PHP!',
        'javascript': 'Hello, JavaScript!',
        'cpp': 'Hello, C++!',
    }
    activity_statuses = {
        activity['language']: activity['status']
        for activity in result['activities']
        if activity['name'] in language_examples.values()
    }
    for language in ('php', 'javascript', 'cpp'):
        expected_status = 'AVAILABLE' if language == unlocked_language else 'LOCKED'
        assert activity_statuses[language] == expected_status


def test_get_progress_uses_assessment_and_activity_tables(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._result = []
            self._fetchone_result = None
            self._fetchall_result = []

        def execute(self, query, params=()):
            if 'FROM assessment_attempts aa' in query and 'a.language IN (\'python\', \'java\')' in query:
                self._fetchone_result = {'completed': 2}
            elif 'FROM assessment_attempts aa' in query and 'a.language IN (\'php\', \'javascript\', \'cpp\')' in query:
                self._fetchall_result = [
                    {'language': 'php', 'completed': 2},
                    {'language': 'javascript', 'completed': 1},
                ]
            elif 'FROM activities' in query and 'student_id = %s' in query:
                self._fetchall_result = []
            else:
                self._fetchone_result = {'completed': 0}

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            result = self._fetchall_result
            self._fetchall_result = []
            return result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/get_progress')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['completed_assessments'] == 2
    assert data['completed_activities'] == 3
    assert data['completed'] == 5
    assert data['progress'] == 20


def test_get_activity_progress_includes_submitted_activity_assessments(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._fetchall_result = []
            self._fetchone_result = None

        def execute(self, query, params=()):
            if 'SELECT language, COUNT(*) AS total' in query:
                self._fetchall_result = [
                    {'language': 'python', 'total': 5},
                    {'language': 'java', 'total': 5},
                    {'language': 'php', 'total': 5},
                    {'language': 'javascript', 'total': 5},
                    {'language': 'cpp', 'total': 5},
                ]
            elif "a.language IN ('python', 'java')" in query:
                self._fetchall_result = [{'language': 'python', 'completed': 1, 'passed': 1}]
            elif "a.language IN ('php', 'javascript', 'cpp')" in query:
                self._fetchall_result = [{'language': 'php', 'completed': 2, 'passed': 2}]
            elif 'AS score_count' in query:
                self._fetchone_result = {'score_count': 0, 'average_score': 0}

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            result = self._fetchall_result
            self._fetchall_result = []
            return result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/get_activity_progress')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['php']['completed'] == 2
    assert data['completed_assessments'] == 1
    assert data['completed_activities'] == 2
    assert data['total_completed'] == 3
    assert data['overall_percentage'] == 12


def test_student_progress_results_prefer_teacher_reviewed_score(monkeypatch):
    executed_queries = []

    class FakeCursor:
        def execute(self, query, params=()):
            if 'FROM students' in query:
                self.student = {'id': 99, 'username': 'student'}
                return
            executed_queries.append(query)

        def fetchone(self):
            return getattr(self, 'student', None)

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/get_progress_results')

    assert response.status_code == 200
    assert response.get_json() == {'success': True, 'results': []}
    assert 'ROUND(aa.teacher_score / 10, 1)' in executed_queries[0]
    assert "WHERE d.language IN ('python', 'java')" in executed_queries[0]
    assert "WHERE d.language IN ('javascript', 'cpp', 'php')" in executed_queries[1]
    assert 'WHEN aa.teacher_score IS NOT NULL THEN' in executed_queries[1]
    assert 'WHEN aa.auto_score IS NOT NULL THEN' in executed_queries[1]
    assert 'ROUND(aa.score / 10, 1)' in executed_queries[1]


def test_student_progress_renders_catalog_counts_and_student_completions(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            if 'FROM students' in query:
                self.student = {'id': 99, 'username': 'student'}
                return
            if 'FROM module_assessment_attempts' in query:
                assert params == (99,)
                self.results = [{
                    'module_id': 'python-01-basics',
                    'score': 85,
                    'points_earned': 8,
                    'max_points': 10,
                    'attempts': 2,
                    'status': 'passed',
                    'submitted_at': '2026-10-29 08:00:00',
                }, {
                    'module_id': 'php-02-conditionals',
                    'score': 42,
                    'points_earned': 4,
                    'max_points': 10,
                    'attempts': 3,
                    'status': 'failed',
                    'submitted_at': '2026-10-29 09:00:00',
                }]
                return

            assert params == (99,)
            assert 'COUNT(DISTINCT a.id) AS total' in query
            assert "aa.status IN ('submitted', 'completed', 'pending_review')" in query
            assert 'AS scored_attempts' in query
            assert 'AS points_earned' in query
            assert 'WHEN aa.teacher_score IS NOT NULL THEN' in query
            assert 'aa.auto_score IS NOT NULL' in query
            self.results = [
                {'language': 'php', 'total': 5, 'completed': 2, 'scored_attempts': 2, 'points_earned': 18},
                {'language': 'javascript', 'total': 5, 'completed': 1, 'scored_attempts': 1, 'points_earned': 9},
                {'language': 'cpp', 'total': 5, 'completed': 3, 'scored_attempts': 3, 'points_earned': 21},
                {'language': 'python', 'total': 4, 'completed': 3, 'scored_attempts': 3, 'points_earned': 20},
                {'language': 'java', 'total': 5, 'completed': 1, 'scored_attempts': 1, 'points_earned': 7},
            ]

        def fetchall(self):
            return getattr(self, 'results', [])

        def fetchone(self):
            return getattr(self, 'student', None)

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/student_progress')

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="scoreSummary"' not in page
    assert "fetch('/get_score_summary'" not in page
    assert '12 of 34 activities, assessments, and module finals completed.' in page
    assert 'Activities Completed' in page
    assert '6<span class="stat-unit">/15</span>' in page
    assert 'Assessments Completed' in page
    assert '6<span class="stat-unit">/19</span>' in page
    assert '87<span class="stat-unit">/340 pts</span>' in page
    assert '18 / 50 pts earned' in page
    assert '20 / 40 pts earned' in page
    assert '75%' in page
    assert 'class="detail-group-heading">Activities</li>' in page
    assert 'class="detail-group-heading detail-group-heading--separated">Assessments</li>' in page
    assert 'Activities completed</small>' not in page
    assert '12 / 18 modules' not in page
    assert 'Average Score' not in page
    assert '+4% this month' not in page
    assert 'Module Final Assessments' in page
    assert 'Python Basics' in page and '85 / 100' in page
    assert '2 attempts' in page
    assert 'PHP Conditionals' in page and '42 / 100' in page
    assert 'Failed · 3 attempts' in page


def test_module_assessment_progress_endpoint_lists_every_available_module(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            if 'FROM students' in query:
                self.student = {'id': 99, 'username': 'student'}
                return
            assert 'FROM module_assessment_attempts' in query
            assert params == (99,)

        def fetchone(self):
            return getattr(self, 'student', None)

        def fetchall(self):
            return [{
                'module_id': 'java-02-loops',
                'score': 80,
                'points_earned': 8,
                'max_points': 10,
                'attempts': 3,
                'status': 'passed',
            }]

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99
        response = client.get('/api/student/module-assessment-progress')

    data = response.get_json()
    assert response.status_code == 200
    assert data['success'] is True
    assert len(data['modules']) == 10
    java_loops = next(item for item in data['modules'] if item['module_id'] == 'java-02-loops')
    assert java_loops['score'] == 80
    assert java_loops['attempts'] == 3
    assert java_loops['status'] == 'passed'


def test_student_dashboard_links_to_all_module_assessments(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            pass

        def fetchone(self):
            return {'id': 99, 'username': 'student', 'full_name': 'Test Student'}

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99
        response = client.get('/student_dashboard')

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert page.count('class="dashboard-module-row dashboard-module-summary"') == 10
    assert 'data-module-id="python-01-basics" href="/student_modules/python/1"' in page
    assert 'data-module-id="cpp-02-loops" href="/student_modules/cpp/2"' in page
    assert "fetch('/api/student/module-assessment-progress')" in page


def test_assessments_modules_page_has_shared_navigation_and_all_ten_modules(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            pass

        def fetchone(self):
            return {'id': 99, 'username': 'student', 'full_name': 'Test Student'}

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99
            session['full_name'] = 'Test Student'
            session['grade_level'] = 'Grade 11'
            session['student_name_loaded'] = True
        response = client.get('/module_assessments')

    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<h1><i class="fas fa-layer-group"></i>Modules</h1>' in page
    assert page.count('>Modules</h1>') == 1
    assert '5 languages · 2 modules each' not in page
    assert 'Student Dashboard</span>' not in page
    assert 'class="dashboard-home"' not in page
    assert 'class="profile-trigger"' not in page
    assert 'class="module-profile"' in page
    assert page.count('class="module-profile"') == 1
    assert 'Test Student' in page
    assert 'Grade 11' in page
    assert 'class="theme-btn"' in page
    assert 'class="library-switch active" href="/student_modules"' in page
    assert 'href="/notifications"' in page
    assert '<title>BlockLearn · Modules</title>' in page
    assert page.count('class="card card--activity"') == 10
    assert 'aria-label="Student navigation"' in page
    assert 'href="/student_modules" class="nav-link-custom active" aria-current="page"' in page
    assert 'href="/student_progress"' in page
    assert 'href="/student_activities_cpp"' in page
    assert 'Additional Learning Modules' not in page


def test_module_library_aliases_redirect_to_single_assessments_modules_page():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'

        for path in ('/student_modules', '/assessments', '/assessment'):
            response = client.get(path)
            assert response.status_code == 302
            assert response.headers['Location'].endswith('/module_assessments')


def test_module_pages_expose_logged_in_student_id():
    module_paths = (
        '/student_modules/javascript/1',
        '/student_modules/javascript/2',
        '/student_modules/python/1',
        '/student_modules/python/2',
        '/student_modules/java/1',
        '/student_modules/java/2',
        '/student_modules/php/1',
        '/student_modules/php/2',
        '/student_modules/cpp/1',
        '/student_modules/cpp/2',
    )
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 9876

        for path in module_paths:
            response = client.get(path)
            assert response.status_code == 200
            assert 'data-student-id="9876"' in response.get_data(as_text=True)


def test_dashboard_awards_script_targets_and_refreshes_existing_language_cards():
    with app.test_client() as client:
        response = client.get('/static/js/module_awards.js')

    script = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '.dashboard-module-card[data-language="${language}"]' in script
    assert "card.querySelector('[data-injected=\"true\"]')" in script
    assert 'card.appendChild(block)' in script
    assert "Module status: Complete" in script
    assert 'mod.complete' in script and 'finalsProgress' in script and 'lessonsDone' in script
    assert "window.addEventListener('storage'" in script
    assert 'card.insertAdjacentElement' not in script
