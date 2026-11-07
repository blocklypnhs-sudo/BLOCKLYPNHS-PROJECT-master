# backend/test_security.py
"""
Tests for login lockout, salted hashing and module scoring.
Uses an in-memory SQLite stand-in for MySQL, so no database is required:
    pytest backend/test_security.py -v
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import security
from backend.module_scoring import score_module_output


# ------------------------------------------------------------ SQLite shim
class _Cursor:
    def __init__(self, conn):
        self._c = conn.cursor()

    def execute(self, sql, params=()):
        self._c.execute(sql.replace('%s', '?'), params)

    def fetchone(self):
        row = self._c.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in self._c.fetchall()]

    def close(self):
        self._c.close()


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def cursor(self, dictionary=True):
        return _Cursor(self.raw)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        pass  # shared in-memory DB stays open for the test


@pytest.fixture
def db():
    raw = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute("""CREATE TABLE login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, identifier TEXT, ip_address TEXT,
        attempted_at TIMESTAMP)""")
    raw.execute("""CREATE TABLE students (
        id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, password TEXT,
        lrn TEXT, grade_level TEXT)""")
    yield _Conn(raw)
    raw.close()


# ------------------------------------------------------------- hashing
def test_new_hashes_are_salted_and_verify():
    a, b = security.make_password_hash('Secret123'), security.make_password_hash('Secret123')
    assert a != b
    assert security.verify_password(a, 'Secret123') == (True, False)
    assert security.verify_password(a, 'wrong') == (False, False)


def test_legacy_sha256_hash_verifies_and_requests_upgrade():
    import hashlib
    legacy = hashlib.sha256(b'Secret123').hexdigest()
    assert security.verify_password(legacy, 'Secret123') == (True, True)
    assert security.verify_password(legacy, 'nope') == (False, False)


@pytest.mark.parametrize('pw,ok', [
    ('short1', False), ('allletters', False), ('12345678', False),
    ('abcdefg1', True), ('Str0ngPassw0rd', True),
])
def test_password_policy(pw, ok):
    assert security.validate_password_strength(pw)[0] is ok


# ------------------------------------------------------------- lockout
def test_lock_after_max_failures_and_expires(db):
    cur = db.cursor()
    key = security.attempt_key('student', ' 123456789012 ')
    t0 = datetime(2026, 1, 1, 8, 0, 0)
    remaining = None
    for i in range(security.MAX_FAILED_ATTEMPTS):
        assert security.lockout_seconds_remaining(cur, key, t0 + timedelta(seconds=i)) == 0
        remaining = security.record_failed_attempt(cur, key, '1.2.3.4', t0 + timedelta(seconds=i))
    assert remaining == 0
    locked = security.lockout_seconds_remaining(cur, key, t0 + timedelta(minutes=1))
    assert 0 < locked <= security.LOCKOUT_MINUTES * 60
    after = t0 + timedelta(minutes=security.LOCKOUT_MINUTES, seconds=30)
    assert security.lockout_seconds_remaining(cur, key, after) == 0


def test_clear_failed_attempts_resets_counter(db):
    cur = db.cursor()
    key = 'student:1'
    for _ in range(3):
        security.record_failed_attempt(cur, key, '')
    security.clear_failed_attempts(cur, key)
    assert security.record_failed_attempt(cur, key, '') == security.MAX_FAILED_ATTEMPTS - 1


# ------------------------------------------------------- /login route
@pytest.fixture
def client(db, monkeypatch):
    import backend.app as appmod
    monkeypatch.setattr(appmod, 'get_db_connection', lambda: db)
    monkeypatch.setattr(appmod, 'log_audit', lambda *a, **k: True)
    appmod.app.config['TESTING'] = True
    cur = db.cursor()
    cur.execute(
        "INSERT INTO students (id, username, full_name, password, lrn, grade_level) VALUES (1,%s,%s,%s,%s,%s)",
        ('123456789012', 'Test Student', security.make_password_hash('Passw0rdX'), '123456789012', 'Grade 11'),
    )
    db.commit()
    return appmod.app.test_client()


def _login(client, pw):
    return client.post('/login', json={'role': 'student', 'lrn': '123456789012', 'password': pw})


def test_login_success_then_lockout_flow(client):
    assert _login(client, 'Passw0rdX').get_json()['success'] is True
    for i in range(security.MAX_FAILED_ATTEMPTS - 1):
        r = _login(client, 'bad')
        assert r.status_code == 200 and r.get_json()['success'] is False
    last = _login(client, 'bad')            # 5th failure triggers the lock
    assert last.status_code == 429 and last.get_json()['locked'] is True
    # Even the correct password is refused while locked
    blocked = _login(client, 'Passw0rdX')
    assert blocked.status_code == 429 and blocked.get_json()['success'] is False


def test_success_clears_previous_failures(client, db):
    for _ in range(3):
        _login(client, 'bad')
    assert _login(client, 'Passw0rdX').get_json()['success'] is True
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM login_attempts")
    assert cur.fetchone()['n'] == 0


def test_legacy_hash_is_upgraded_on_login(client, db):
    import hashlib
    cur = db.cursor()
    cur.execute("UPDATE students SET password = %s WHERE id = 1",
                (hashlib.sha256(b'Passw0rdX').hexdigest(),))
    db.commit()
    assert _login(client, 'Passw0rdX').get_json()['success'] is True
    cur.execute("SELECT password FROM students WHERE id = 1")
    stored = cur.fetchone()['password']
    assert not security._LEGACY_SHA256.match(stored)
    assert security.verify_password(stored, 'Passw0rdX')[0]


# ------------------------------------------------------- module scoring
@pytest.mark.parametrize('out,exp,ci,score', [
    ('16', '16', False, 100),
    ('  16\r\n', '16', False, 100),
    ('15', '16', False, 0),
    ('', '16', False, 0),
    ('__ERROR__', '16', False, 0),
    ('1\n2\n3\n4', '1\n2\n3\n4\n5', False, 74),     # 80% match capped below pass mark
    ('1\n2\n9\n4\n5', '1\n2\n3\n4\n5', False, 74),
    ('1\n9\n9\n9\n5', '1\n2\n3\n4\n5', False, 40),
    ('HELLO', 'hello', True, 100),
    ('HELLO', 'hello', False, 0),
])
def test_score_module_output(out, exp, ci, score):
    assert score_module_output(out, exp, ci) == score


def test_only_exact_answers_pass():
    from backend.module_awards import PASS_THRESHOLD
    assert score_module_output('1\n2\n3\n4', '1\n2\n3\n4\n5') < PASS_THRESHOLD
    assert score_module_output('1\n2\n3\n4\n5', '1\n2\n3\n4\n5') >= PASS_THRESHOLD
