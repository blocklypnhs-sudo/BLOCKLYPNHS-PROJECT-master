# tests/conftest.py
"""
Shared pytest fixtures. Uses a dedicated test DB from env var TEST_DB.
Set environment:
    export TEST_DB=blocklypnhsproject_test
    export TEST_DB_USER=root
    export TEST_DB_PASS=...
    export TEST_DB_HOST=localhost
"""
import os
import pytest
import mysql.connector

TEST_DB = os.environ.get('TEST_DB', 'blocklypnhsproject_test')
TEST_USER = os.environ.get('TEST_DB_USER', 'root')
TEST_PASS = os.environ.get('TEST_DB_PASS', '')
TEST_HOST = os.environ.get('TEST_DB_HOST', 'localhost')


@pytest.fixture(scope='session')
def test_conn():
    conn = mysql.connector.connect(
        host=TEST_HOST, user=TEST_USER, password=TEST_PASS, database=TEST_DB,
    )
    yield conn
    conn.close()


@pytest.fixture
def db_cursor(test_conn):
    cursor = test_conn.cursor(dictionary=True)
    yield cursor
    test_conn.commit()
    cursor.close()


@pytest.fixture
def student_a(db_cursor):
    """Insert a fresh student A and return its id. Cleanup after test."""
    db_cursor.execute("""
        INSERT INTO students (username, full_name, password, lrn, grade_level, email)
        VALUES ('test_a', 'Student A', 'x', '999999990001', 'Grade 11', 'a@test.local')
        ON DUPLICATE KEY UPDATE full_name='Student A'
    """)
    db_cursor.execute("SELECT id FROM students WHERE username='test_a'")
    sid = db_cursor.fetchone()['id']
    yield sid
    # Cleanup awards
    for table in ('student_badges', 'lesson_completions', 'module_certificates', 'assessment_attempts'):
        db_cursor.execute(f"DELETE FROM {table} WHERE student_id=%s", (sid,))


@pytest.fixture
def student_b(db_cursor):
    db_cursor.execute("""
        INSERT INTO students (username, full_name, password, lrn, grade_level, email)
        VALUES ('test_b', 'Student B', 'x', '999999990002', 'Grade 11', 'b@test.local')
        ON DUPLICATE KEY UPDATE full_name='Student B'
    """)
    db_cursor.execute("SELECT id FROM students WHERE username='test_b'")
    sid = db_cursor.fetchone()['id']
    yield sid
    for table in ('student_badges', 'lesson_completions', 'module_certificates', 'assessment_attempts'):
        db_cursor.execute(f"DELETE FROM {table} WHERE student_id=%s", (sid,))