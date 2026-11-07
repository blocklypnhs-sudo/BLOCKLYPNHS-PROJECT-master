import re
from pathlib import Path

from backend.app import init_database


def test_database_setup_keeps_activity_seeds_out_of_assessments():
    sql = (Path(__file__).resolve().parents[1] / 'database_setup.sql').read_text(encoding='utf-8')
    assessment_section = re.search(
        r'INSERT INTO assessments\b(.*?)INSERT INTO activities\b',
        sql,
        re.DOTALL,
    ).group(1)
    activity_section = re.search(
        r'INSERT INTO activities\b(.*?)CREATE OR REPLACE VIEW learning_items',
        sql,
        re.DOTALL,
    ).group(1)
    assessment_languages = re.findall(
        r"^\s*\(\d+,\s*'([^']+)'",
        assessment_section,
        re.MULTILINE,
    )
    activity_languages = re.findall(
        r"^\s*\(\d+,\s*'([^']+)'",
        activity_section,
        re.MULTILINE,
    )

    assert "language ENUM('python', 'java') NOT NULL" in sql
    assert len(assessment_languages) == 10
    assert set(assessment_languages) == {'python', 'java'}
    assert len(activity_languages) == 15
    assert set(activity_languages) == {'cpp', 'javascript', 'php'}


def test_init_database_moves_activity_definitions_before_cleaning_assessments(monkeypatch):
    query_log = []

    class FakeCursor:
        def __init__(self):
            self._fetchone_result = None
            self._show_index_result = []
            self._has_unread_index_result = False

        def executemany(self, query, params=()):
            self.execute(query, params)

        def execute(self, query, params=()):
            nonlocal query_log
            if self._has_unread_index_result:
                raise AssertionError('An index result was not fully consumed')
            query_log.append(query)
            if "SHOW INDEX FROM assessment_attempts" in query:
                self._has_unread_index_result = True
                self._show_index_result = (
                    [{'Key_name': 'uq_student_assessment_attempt'}]
                    if "uq_student_assessment_attempt'" in query
                    and "uq_student_learning_item_attempt'" not in query
                    else []
                )
                self._fetchone_result = None
                return
            if "SHOW INDEX FROM activity_attempt_sessions" in query:
                self._has_unread_index_result = True
                self._show_index_result = [
                    {'Key_name': 'PRIMARY', 'Seq_in_index': 1},
                    {'Key_name': 'PRIMARY', 'Seq_in_index': 2},
                    {'Key_name': 'PRIMARY', 'Seq_in_index': 3},
                ]
                self._fetchone_result = None
                return
            if "SHOW INDEX FROM module_assessment_attempts" in query:
                self._has_unread_index_result = True
                self._show_index_result = (
                    []
                    if "WHERE Key_name = 'uq_student_module_assessment'" in query
                    else [
                        {
                            'Key_name': 'uq_student_module_number',
                            'Non_unique': 0,
                            'Seq_in_index': 1,
                            'Column_name': 'student_id',
                        },
                        {
                            'Key_name': 'uq_student_module_number',
                            'Non_unique': 0,
                            'Seq_in_index': 2,
                            'Column_name': 'module_number',
                        },
                    ]
                )
                self._fetchone_result = None
                return
            if 'SHOW COLUMNS FROM students LIKE' in query or 'SHOW COLUMNS FROM teachers LIKE' in query:
                self._fetchone_result = {'Field': 'dummy'}
                return

            if "SELECT COUNT(*) AS total FROM assessments" in query:
                self._fetchone_result = {'total': 0}
                return
            if "SELECT COUNT(*) AS total FROM assessment_attempts" in query:
                self._fetchone_result = {'total': 0}
                return
            if "duplicate_activities" in query:
                self._fetchone_result = {'total': 0}
                return

            if "SELECT id, password, status FROM ict_support" in query:
                self._fetchone_result = None
                return

            if "SELECT id FROM teachers WHERE username = 'admin'" in query:
                self._fetchone_result = None
                return

            if "SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'" in query:
                self._fetchone_result = None
                return

            if 'DELETE FROM ict_support' in query:
                self._fetchone_result = None
                return

            self._fetchone_result = None

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            if self._has_unread_index_result:
                self._has_unread_index_result = False
                return self._show_index_result
            return []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    init_database()

    catalog_copy_index = next(
        index for index, query in enumerate(query_log)
        if 'INSERT INTO activity_catalog' in query and 'FROM assessments' in query
    )
    backfill_index = next(
        index for index, query in enumerate(query_log)
        if 'UPDATE assessment_attempts aa' in query and 'JOIN assessments d' in query
    )
    delete_index = next(
        index for index, query in enumerate(query_log)
        if "DELETE FROM assessments WHERE language IN ('php', 'javascript', 'cpp')" in query
    )
    assert catalog_copy_index < backfill_index < delete_index
    assert any("ALTER TABLE assessments MODIFY language ENUM('python', 'java') NOT NULL" in query for query in query_log)
    assert any('CREATE OR REPLACE VIEW learning_items' in query for query in query_log)
    assert any('ADD UNIQUE KEY uq_student_learning_item_attempt' in query for query in query_log)
    assert any(
        'DROP INDEX `uq_student_module_number`' in query
        for query in query_log
    )
    assert any(
        'ADD UNIQUE KEY uq_student_language_module_assessment' in query
        and '(student_id, language, module_number)' in query
        for query in query_log
    )
    assert all(
        any(f'CREATE TABLE IF NOT EXISTS {table}' in query for query in query_log)
        for table in ('student_badges', 'lesson_completions', 'module_certificates')
    )
    assert any(
        'UPDATE assessment_attempts a' in query and 'teacher_score IS NULL' in query
        for query in query_log
    )


def test_init_database_upserts_assessments_when_records_exist(monkeypatch):
    insert_calls = []
    python_fundamentals_updates = []

    class FakeCursor:
        def __init__(self):
            self._fetchone_result = None

        def executemany(self, query, params):
            insert_calls.append((query, list(params)))

        def execute(self, query, params=()):
            if 'UPDATE assessments' in query and "WHERE language = 'python' AND assessment_number = 1" in query:
                python_fundamentals_updates.append(params)

            if "SELECT id, password, status FROM ict_support" in query:
                self._fetchone_result = {'id': 1, 'password': 'abc', 'status': 'active'}
                return

            if "SELECT id FROM teachers WHERE username = 'admin'" in query:
                self._fetchone_result = {'id': 1}
                return

            if "SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'" in query:
                self._fetchone_result = {'id': 1, 'username': 'teacher1', 'password': 'abc'}
                return

            if 'SHOW COLUMNS FROM students LIKE' in query or 'SHOW COLUMNS FROM teachers LIKE' in query:
                self._fetchone_result = {'Field': 'dummy'}
                return
            if "SELECT COUNT(*) AS total FROM assessments" in query:
                self._fetchone_result = {'total': 0}
                return
            if "SELECT COUNT(*) AS total FROM assessment_attempts" in query:
                self._fetchone_result = {'total': 0}
                return
            if "duplicate_activities" in query:
                self._fetchone_result = {'total': 0}
                return

            if 'DELETE FROM ict_support' in query:
                self._fetchone_result = None
                return

            self._fetchone_result = None

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    init_database()

    assert insert_calls
    assert all('ON DUPLICATE KEY UPDATE' in query for query, _ in insert_calls)
    default_rows = next(rows for query, rows in insert_calls if "VALUES (%s, %s, %s" in query)
    assert any(row[0:3] == ('python', 1, 'Python Fundamentals') for row in default_rows)
    assert any('Write a Python program that prints exactly:' in row[3] for row in default_rows)
    assert any(row[0:3] == ('java', 3, 'Conditional Statements') and 'score to 80' in row[3] for row in default_rows)
    assert python_fundamentals_updates
    assert python_fundamentals_updates[0][1] == 'Write a Python program that prints exactly: Hello, World!'
