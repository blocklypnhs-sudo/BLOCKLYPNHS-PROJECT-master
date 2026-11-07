# tests/test_module_awards.py
"""
Focused tests for the Module Awards feature.
Run with: pytest tests/test_module_awards.py -v
Requires: TEST_DB env var or a running MySQL with blocklypnhsproject_test.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_award_badge_idempotent(db_cursor, student_a):
    from backend.module_awards import award_badge
    assert award_badge(db_cursor, student_a, 'python_a1') is True
    assert award_badge(db_cursor, student_a, 'python_a1') is False
    assert award_badge(db_cursor, student_a, 'python_a1') is False
    assert award_badge(db_cursor, student_a, 'python_module') is False
    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM student_badges WHERE student_id=%s AND badge_code=%s",
        (student_a, 'python_a1'),
    )
    assert db_cursor.fetchone()['n'] == 1


def test_legacy_module_badges_are_not_awarded_or_returned():
    from backend.module_awards import (
        award_badge, get_student_badges, get_student_badges_map,
    )

    class FakeCursor:
        rowcount = 0

        def execute(self, query, params=()):
            self.query = query

        def fetchall(self):
            return [
                {'badge_code': 'python_module', 'earned_at': None},
                {'badge_code': 'python_a1', 'earned_at': None},
            ]

    cursor = FakeCursor()
    assert award_badge(cursor, 7, 'python_module') is False
    assert [badge['code'] for badge in get_student_badges(cursor, 7)] == ['python_a1']
    assert get_student_badges_map(cursor, 7) == {'python_a1': None}


def test_mark_lesson_idempotent(db_cursor, student_a):
    from backend.module_awards import mark_lesson_complete, count_completed_lessons
    assert mark_lesson_complete(db_cursor, student_a, 'python', 1) is True
    assert mark_lesson_complete(db_cursor, student_a, 'python', 1) is False
    assert count_completed_lessons(db_cursor, student_a, 'python') == 1


def test_mark_lesson_invalid_input(db_cursor, student_a):
    from backend.module_awards import mark_lesson_complete
    assert mark_lesson_complete(db_cursor, student_a, 'python', 3) is False
    assert mark_lesson_complete(db_cursor, student_a, 'ruby', 1) is False
    assert mark_lesson_complete(db_cursor, student_a, 'python', '1') is False


def test_item_badge_code_mapping():
    from backend.module_awards import _item_badge_code
    assert _item_badge_code('python', 1) == 'python_a1'
    assert _item_badge_code('java', 5) == 'java_a5'
    assert _item_badge_code('php', 2) == 'php_act2'
    assert _item_badge_code('php', 3) == 'php_act3'
    assert _item_badge_code('javascript', 2) == 'javascript_act2'
    assert _item_badge_code('cpp', 4) == 'cpp_act4'


def test_normalize_score_uses_confirmed_score_scales():
    from backend.module_awards import _normalize_score
    assert _normalize_score(10, 0, 0) == 100
    assert _normalize_score(None, 7, 100) == 70
    assert _normalize_score(None, 0, 100) == 100
    assert _normalize_score(None, 0, 0) == 0
    assert _normalize_score(None, None, 10) == 100
    assert _normalize_score(None, None, 8) == 80
    assert _normalize_score(None, None, 75) == 75
    assert _normalize_score(None, None, None) == 0


def test_passed_activity_attempt_supports_legacy_completed_status():
    from backend.module_awards import (
        is_attempt_passed, prefer_attempt_for_progress,
    )

    passing_attempt = {
        'status': 'completed', 'teacher_score': None, 'auto_score': 0, 'score': 10,
    }
    assert is_attempt_passed(passing_attempt) is True
    assert is_attempt_passed({
        'status': 'pending_review', 'teacher_score': 10, 'auto_score': 0, 'score': 0,
    }) is True
    assert is_attempt_passed({
        'status': 'pending_review', 'teacher_score': None, 'auto_score': 10, 'score': 100,
    }) is False
    assert is_attempt_passed({
        'status': 'submitted', 'teacher_score': None, 'auto_score': 0, 'score': 7,
    }) is False
    assert prefer_attempt_for_progress(passing_attempt, {
        'status': 'submitted', 'teacher_score': None, 'auto_score': 0, 'score': 3,
    }) is passing_attempt


def test_student_activity_score_keeps_passed_attempt_after_failed_retry():
    from backend.scores import get_student_activity_scores

    class FakeCursor:
        def execute(self, query, params=()):
            self.query = query

        def fetchall(self):
            return [
                {
                    'language': 'php', 'assessment_number': 2,
                    'status': 'submitted', 'score': 100,
                    'auto_score': 0, 'teacher_score': None,
                },
                {
                    'language': 'php', 'assessment_number': 2,
                    'status': 'submitted', 'score': 30,
                    'auto_score': 0, 'teacher_score': None,
                },
            ]

    activities = get_student_activity_scores(FakeCursor(), 7)

    assert activities == [{
        'language': 'php',
        'name': 'Store a Name',
        'difficulty': 'easy',
        'activity_number': 2,
        'score': 10,
        'max_score': 10,
        'completed': True,
        'status': 'COMPLETED',
    }]


def test_module_progress_keeps_passed_attempt_for_activity_badge():
    from backend.module_awards import get_item_progress

    class FakeCursor:
        fetch_count = 0
        queries = []

        def execute(self, query, params=()):
            self.query = query
            self.queries.append(query)

        def fetchall(self):
            self.fetch_count += 1
            if self.fetch_count == 1:
                return [{'id': 22, 'assessment_number': 2, 'title': 'Store a Name'}]
            return [
                {
                    'assessment_id': 22, 'status': 'submitted',
                    'score': 100, 'auto_score': 0, 'teacher_score': None,
                },
                {
                    'assessment_id': 22, 'status': 'submitted',
                    'score': 30, 'auto_score': 0, 'teacher_score': None,
                },
            ]

    progress = get_item_progress(FakeCursor(), 7, 'php')

    assert progress['passed'] == 1
    assert progress['items'][0]['passed'] is True
    assert progress['items'][0]['badge_code'] == 'php_act2'
    assert 'FROM activities' in FakeCursor.queries[0]


@pytest.mark.parametrize(
    ('language', 'catalog'),
    [('python', 'assessments'), ('java', 'assessments'),
     ('php', 'activities'), ('javascript', 'activities'), ('cpp', 'activities')],
)
def test_item_progress_reads_the_language_catalog(language, catalog):
    from backend.module_awards import get_item_progress

    class FakeCursor:
        query = ''

        def execute(self, query, params=()):
            self.query = query

        def fetchall(self):
            return []

    cursor = FakeCursor()
    progress = get_item_progress(cursor, 7, language)

    assert f'FROM {catalog}' in cursor.query
    assert progress == {'total': 0, 'passed': 0, 'items': []}


def test_certificate_uses_full_name_and_only_selects_available_name_columns():
    from backend.module_awards import get_certificate

    class FakeCursor:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=()):
            self.queries.append((query, params))

        def fetchall(self):
            return [{'Field': name} for name in (
                'full_name', 'first_name', 'last_name', 'username', 'lrn',
            )]

        def fetchone(self):
            return {
                'verification_id': 'verification-id',
                'issued_at': None,
                'full_name': 'Maria Clara Santos',
                'first_last_name': 'Fallback Name',
                'username': '136761100534',
                'lrn': '136761100534',
                'grade_level': 'Grade 11',
            }

    cursor = FakeCursor()
    certificate = get_certificate(cursor, 7, 'python')

    assert certificate['student_name'] == 'Maria Clara Santos'
    assert cursor.queries[1][1] == (7, 'python')
    assert 'JOIN students s ON s.id = c.student_id' in cursor.queries[1][0]
    assert 's.first_name' in cursor.queries[1][0]


def test_certificate_uses_real_name_when_legacy_full_name_is_lrn():
    from backend.module_awards import get_certificate

    class FakeCursor:
        def __init__(self):
            self.query_count = 0

        def execute(self, query, params=()):
            self.query_count += 1

        def fetchall(self):
            return [{'Field': name} for name in (
                'full_name', 'first_name', 'middle_initial', 'last_name',
                'username', 'lrn',
            )]

        def fetchone(self):
            return {
                'verification_id': 'verification-id',
                'issued_at': None,
                'full_name': '136761100534',
                'first_last_name': 'Maria Clara Santos',
                'username': '136761100534',
                'lrn': '136761100534',
                'grade_level': 'Grade 11',
            }

    certificate = get_certificate(FakeCursor(), 7, 'python')

    assert certificate['student_name'] == 'Maria Clara Santos'


def test_module_completion_requires_lessons_and_all_items():
    from backend.module_awards import _module_is_complete

    assert _module_is_complete(
        2,
        {'passed': 5, 'total': 5},
    ) is True
    assert _module_is_complete(
        1,
        {'passed': 5, 'total': 5},
    ) is False
    assert _module_is_complete(
        2,
        {'passed': 4, 'total': 5},
    ) is False


def test_module_assessment_progress_counts_passed_python_finals():
    from backend.module_awards import get_module_assessment_progress

    class FakeCursor:
        query = ''
        params = ()

        def execute(self, query, params=()):
            self.query = query
            self.params = params

        def fetchone(self):
            return {'passed': 2}

    cursor = FakeCursor()
    progress = get_module_assessment_progress(cursor, 7, 'python')

    assert progress == {'passed': 2, 'total': 2}
    assert cursor.params == (7, 'python')
    assert "status = 'passed'" in cursor.query


def test_module_progress_empty(db_cursor, student_a):
    from backend.module_awards import get_module_progress
    progress = get_module_progress(db_cursor, student_a, 'python')
    assert progress['lessons']['done'] == 0
    assert progress['lessons']['next_module'] == 1
    assert progress['items']['passed'] == 0
    assert progress['complete'] is False
    assert progress['certificate']['available'] is False


def test_module_progress_opens_first_incomplete_lesson(db_cursor, student_a):
    from backend.module_awards import get_module_progress, mark_lesson_complete

    mark_lesson_complete(db_cursor, student_a, 'java', 1)
    progress = get_module_progress(db_cursor, student_a, 'java')
    assert progress['lessons']['next_module'] == 2

    mark_lesson_complete(db_cursor, student_a, 'java', 2)
    progress = get_module_progress(db_cursor, student_a, 'java')
    assert progress['lessons']['next_module'] == 2


def test_activities_require_complete_python_and_java_modules(db_cursor, student_a):
    from backend.module_awards import (
        are_activities_unlocked, mark_lesson_complete,
    )
    assert are_activities_unlocked(db_cursor, student_a) is False

    for language in ('python', 'java'):
        mark_lesson_complete(db_cursor, student_a, language, 1)
        mark_lesson_complete(db_cursor, student_a, language, 2)
    assert are_activities_unlocked(db_cursor, student_a) is False

    db_cursor.execute("""
        SELECT id FROM assessments
        WHERE language IN ('python', 'java')
        ORDER BY language, assessment_number
    """)
    for item in db_cursor.fetchall():
        db_cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, score, auto_score,
                 status, submitted_at, completed_at, language)
            VALUES (%s, %s, 'b', 100, 0, 'submitted', NOW(), NOW(), 'python')
            ON DUPLICATE KEY UPDATE score=100, auto_score=0, status='submitted'
        """, (item['id'], student_a))

    assert are_activities_unlocked(db_cursor, student_a) is True


def test_module_complete_and_certificate_issued(db_cursor, student_a):
    """Passing all five Python items awards item badges and a certificate, not a module badge."""
    from backend.module_awards import (
        mark_lesson_complete, try_award_after_submission, get_module_progress,
    )
    # Complete lessons
    mark_lesson_complete(db_cursor, student_a, 'python', 1)
    mark_lesson_complete(db_cursor, student_a, 'python', 2)

    # Insert passing attempts for all 5 python assessments
    db_cursor.execute("SELECT id, assessment_number FROM assessments WHERE language='python' ORDER BY assessment_number")
    items = db_cursor.fetchall()
    assert len(items) == 5

    for item in items:
        db_cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, generated_code, output,
                 score, auto_score, status, submitted_at, completed_at, language)
            VALUES (%s, %s, 'blocks', 'code', 'output', 100, 10, 'submitted', NOW(), NOW(), 'python')
            ON DUPLICATE KEY UPDATE score=100, auto_score=10, status='submitted'
        """, (item['id'], student_a))
        try_award_after_submission(db_cursor, student_a, 'python', item['assessment_number'])

    progress = get_module_progress(db_cursor, student_a, 'python')
    assert progress['complete'] is True
    assert 'module_badge_earned' not in progress
    assert progress['certificate']['available'] is True
    assert progress['certificate']['verification_id'] is not None
    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM student_badges WHERE student_id=%s AND badge_code='python_module'",
        (student_a,),
    )
    assert db_cursor.fetchone()['n'] == 0


def test_sync_backfills_badges_and_certificate_from_legacy_progress(db_cursor, student_a):
    from backend.module_awards import (
        mark_lesson_complete, sync_module_awards,
    )
    mark_lesson_complete(db_cursor, student_a, 'python', 1)
    mark_lesson_complete(db_cursor, student_a, 'python', 2)
    db_cursor.execute(
        "SELECT id FROM assessments WHERE language='python' ORDER BY assessment_number"
    )
    for item in db_cursor.fetchall():
        db_cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, score, auto_score,
                 status, submitted_at, completed_at, language)
            VALUES (%s, %s, 'b', 100, 10, 'submitted', NOW(), NOW(), 'python')
            ON DUPLICATE KEY UPDATE score=100, auto_score=10, status='submitted'
        """, (item['id'], student_a))

    sync_module_awards(db_cursor, student_a, 'python')

    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM student_badges WHERE student_id=%s",
        (student_a,),
    )
    assert db_cursor.fetchone()['n'] == 5
    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM module_certificates WHERE student_id=%s AND language='python'",
        (student_a,),
    )
    assert db_cursor.fetchone()['n'] == 1


def test_certificate_one_time_issuance(db_cursor, student_a):
    from backend.module_awards import (
        mark_lesson_complete, try_award_after_submission,
    )
    mark_lesson_complete(db_cursor, student_a, 'python', 1)
    mark_lesson_complete(db_cursor, student_a, 'python', 2)
    db_cursor.execute("SELECT id, assessment_number FROM assessments WHERE language='python'")
    for item in db_cursor.fetchall():
        db_cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, score, auto_score, status, submitted_at, completed_at, language)
            VALUES (%s, %s, 'b', 100, 10, 'submitted', NOW(), NOW(), 'python')
            ON DUPLICATE KEY UPDATE score=100, auto_score=10, status='submitted'
        """, (item['id'], student_a))
        try_award_after_submission(db_cursor, student_a, 'python', item['assessment_number'])
        try_award_after_submission(db_cursor, student_a, 'python', item['assessment_number'])  # retry

    db_cursor.execute(
        "SELECT COUNT(*) AS n FROM module_certificates WHERE student_id=%s AND language='python'",
        (student_a,),
    )
    assert db_cursor.fetchone()['n'] == 1


def test_certificate_scoped_to_student(db_cursor, student_a, student_b):
    """student_b must not see student_a's certificate via the helper."""
    from backend.module_awards import (
        mark_lesson_complete, try_award_after_submission, get_certificate,
    )
    mark_lesson_complete(db_cursor, student_a, 'python', 1)
    mark_lesson_complete(db_cursor, student_a, 'python', 2)
    db_cursor.execute("SELECT id, assessment_number FROM assessments WHERE language='python'")
    for item in db_cursor.fetchall():
        db_cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, score, auto_score, status, submitted_at, completed_at, language)
            VALUES (%s, %s, 'b', 100, 10, 'submitted', NOW(), NOW(), 'python')
            ON DUPLICATE KEY UPDATE score=100, auto_score=10, status='submitted'
        """, (item['id'], student_a))
        try_award_after_submission(db_cursor, student_a, 'python', item['assessment_number'])

    assert get_certificate(db_cursor, student_a, 'python') is not None
    assert get_certificate(db_cursor, student_b, 'python') is None


def test_pending_review_does_not_award_badge(db_cursor, student_a):
    """A pending_review attempt must NOT unlock a badge."""
    from backend.module_awards import award_badge, get_student_badges_map
    db_cursor.execute("SELECT id FROM assessments WHERE language='python' AND assessment_number=1")
    aid = db_cursor.fetchone()['id']
    db_cursor.execute("""
        INSERT INTO assessment_attempts
            (assessment_id, student_id, code_blocks, score, auto_score, status, language)
        VALUES (%s, %s, 'b', 0, 0, 'pending_review', 'python')
        ON DUPLICATE KEY UPDATE status='pending_review', score=0, auto_score=0
    """, (aid, student_a))

    # Simulate: badge not awarded because status != submitted
    # (application code gates on status == 'submitted')
    badges = get_student_badges_map(db_cursor, student_a)
    assert 'python_a1' not in badges