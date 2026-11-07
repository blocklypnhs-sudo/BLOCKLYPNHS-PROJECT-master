from backend.scores import get_student_total_scores
from backend.app import app


def test_get_student_total_scores_aggregates_activities_and_assessments():
    class FakeCursor:
        def __init__(self):
            self._queries = []

        def execute(self, query, params=()):
            self._queries.append((query, params))

        def fetchall(self):
            query = self._queries[-1][0]
            if "a.language IN ('php', 'javascript', 'cpp')" in query:
                return [
                    {'language': 'php', 'assessment_number': 1, 'score': 100, 'auto_score': 7, 'teacher_score': None, 'status': 'submitted'},
                    {'language': 'php', 'assessment_number': 2, 'score': 80, 'auto_score': 8, 'teacher_score': None, 'status': 'submitted'},
                    {'language': 'php', 'assessment_number': 3, 'score': 100, 'auto_score': 0, 'teacher_score': None, 'status': 'submitted'},
                ]
            if "a.language IN ('python', 'java')" in query:
                return [
                    {'language': 'python', 'score': 100, 'auto_score': 0, 'teacher_score': None},
                    {'language': 'java', 'score': 100, 'auto_score': 7, 'teacher_score': 10},
                ]
            return []

    result = get_student_total_scores(FakeCursor(), 101)

    assert result['overall']['total'] == 45
    assert result['overall']['max'] == 250
    assert result['activities']['total'] == 25
    assert result['assessments']['total'] == 20
    assert result['activities']['by_language']['php']['total'] == 25
    php_difficulty = result['activities']['by_language']['php']['by_difficulty']
    assert php_difficulty['easy'] == {'total': 15, 'max': 20, 'percentage': 75}
    assert php_difficulty['medium']['max'] == 20
    assert php_difficulty['hard']['max'] == 10
    assert result['assessments']['by_language']['python']['total'] == 10
    assert result['assessments']['by_language']['java']['total'] == 10


def test_get_score_summary_returns_all_languages_and_combined_total(monkeypatch):
    summary = {
        'overall': {'total': 45, 'max': 250, 'percentage': 18},
        'activities': {
            'total': 25,
            'max': 150,
            'percentage': 17,
            'by_language': {'php': {'total': 25, 'max': 50, 'percentage': 50}},
        },
        'assessments': {
            'total': 20,
            'max': 100,
            'percentage': 20,
            'by_language': {
                'python': {'total': 10, 'max': 50, 'percentage': 20},
                'java': {'total': 10, 'max': 50, 'percentage': 20},
            },
        },
    }

    class FakeCursor:
        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_student_total_scores', lambda cursor, student_id: summary)
    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConnection())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 101})
        response = client.get('/get_score_summary')

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['overall'] == {'total': 45, 'max': 250, 'percentage': 18}
    assert set(payload['by_language']) == {'php', 'python', 'java'}
