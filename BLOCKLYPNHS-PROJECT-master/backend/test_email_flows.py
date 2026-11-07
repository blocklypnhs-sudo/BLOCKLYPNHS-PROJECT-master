# backend/test_email_flows.py
"""Tests for emailed password reset and registration verification (SQLite stand-in, no SMTP)."""
import os
import sqlite3
import sys
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import security, email_utils
from backend.test_security import _Conn


@pytest.fixture
def env(monkeypatch):
    import backend.app as appmod

    raw = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.create_function('NOW', 0, lambda: datetime.now().isoformat(' '))
    raw.execute("""CREATE TABLE login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, identifier TEXT, ip_address TEXT, attempted_at TIMESTAMP)""")
    raw.execute("""CREATE TABLE students (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, full_name TEXT, password TEXT,
        lrn TEXT, grade_level TEXT, email TEXT, created_at TIMESTAMP,
        reset_token TEXT, reset_token_expires TIMESTAMP,
        email_verified INTEGER NOT NULL DEFAULT 1, email_verify_token TEXT, email_verify_expires TIMESTAMP)""")
    db = _Conn(raw)

    sent = {'reset': [], 'verify': []}
    monkeypatch.setattr(appmod, 'get_db_connection', lambda: db)
    monkeypatch.setattr(appmod, 'log_audit', lambda *a, **k: True)
    monkeypatch.setattr(appmod, 'send_password_reset_email', lambda to, name, url: sent['reset'].append((to, url)))
    monkeypatch.setattr(appmod, 'send_verification_email', lambda to, name, url: sent['verify'].append((to, url)))
    monkeypatch.setattr(appmod, 'email_configured', lambda: True)
    monkeypatch.setattr(appmod, 'verification_enforced', lambda: True)
    appmod.app.config['TESTING'] = True
    yield appmod, appmod.app.test_client(), db, sent
    raw.close()


def _add_student(db, email='kid@example.com', verified=1):
    cur = db.cursor()
    cur.execute(
        "INSERT INTO students (username, full_name, password, lrn, grade_level, email, email_verified) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        ('123456789012', 'Test Kid', security.make_password_hash('OldPass123'),
         '123456789012', 'Grade 11', email, verified))
    db.commit()


def _token(url):
    return parse_qs(urlparse(url).query)['token'][0]


# ------------------------------------------------------- password reset
def test_forgot_password_never_exposes_link_and_is_uniform(env):
    _, client, db, sent = env
    _add_student(db)
    known = client.post('/forgot-password', json={'identifier': '123456789012'})
    unknown = client.post('/forgot-password', json={'identifier': '999999999999'})
    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()          # no account enumeration
    assert 'reset_url' not in known.get_json()
    assert len(sent['reset']) == 1 and sent['reset'][0][0] == 'kid@example.com'


def test_placeholder_email_gets_no_mail(env):
    _, client, db, sent = env
    _add_student(db, email='123456789012@student.blocklearn.edu.ph')
    assert client.post('/forgot-password', json={'identifier': '123456789012'}).status_code == 200
    assert sent['reset'] == []


def test_reset_requests_are_rate_limited(env):
    _, client, db, sent = env
    _add_student(db)
    for _ in range(5):
        client.post('/forgot-password', json={'identifier': '123456789012'})
    assert len(sent['reset']) == 3


def test_token_stored_hashed_and_reset_works_once(env):
    _, client, db, sent = env
    _add_student(db)
    client.post('/forgot-password', json={'identifier': '123456789012'})
    token = _token(sent['reset'][0][1])
    cur = db.cursor()
    cur.execute("SELECT reset_token FROM students WHERE id = 1")
    stored = cur.fetchone()['reset_token']
    assert stored != token and stored == security.hash_token(token)

    weak = client.post('/reset-password', json={'token': token, 'password': 'abc', 'confirm_password': 'abc'})
    assert weak.status_code == 400
    ok = client.post('/reset-password', json={'token': token, 'password': 'NewPass456', 'confirm_password': 'NewPass456'})
    assert ok.get_json()['success'] is True
    again = client.post('/reset-password', json={'token': token, 'password': 'Another789', 'confirm_password': 'Another789'})
    assert again.status_code == 400                      # single use
    login = client.post('/login', json={'role': 'student', 'lrn': '123456789012', 'password': 'NewPass456'})
    assert login.get_json()['success'] is True


def test_reset_lifts_lockout(env):
    _, client, db, sent = env
    _add_student(db)
    for _ in range(security.MAX_FAILED_ATTEMPTS):
        client.post('/login', json={'role': 'student', 'lrn': '123456789012', 'password': 'bad'})
    assert client.post('/login', json={'role': 'student', 'lrn': '123456789012', 'password': 'OldPass123'}).status_code == 429
    client.post('/forgot-password', json={'identifier': '123456789012'})
    token = _token(sent['reset'][0][1])
    client.post('/reset-password', json={'token': token, 'password': 'NewPass456', 'confirm_password': 'NewPass456'})
    assert client.post('/login', json={'role': 'student', 'lrn': '123456789012', 'password': 'NewPass456'}).get_json()['success']


# ------------------------------------------------- registration verification
REG = {'lrn': '555555555555', 'full_name': 'New Kid', 'password': 'Passw0rdX',
       'grade_level': 'Grade 11', 'email': 'new@example.com'}


def test_registration_requires_verification_before_login(env):
    _, client, db, sent = env
    res = client.post('/create_account', json=REG).get_json()
    assert res['success'] and res.get('verify_email') is True
    assert len(sent['verify']) == 1 and sent['verify'][0][0] == 'new@example.com'

    blocked = client.post('/login', json={'role': 'student', 'lrn': REG['lrn'], 'password': REG['password']}).get_json()
    assert blocked['success'] is False and blocked['needs_verification'] is True

    page = client.get('/verify-email?token=' + _token(sent['verify'][0][1]))
    assert page.status_code == 200 and b'Email verified' in page.data
    assert client.get('/verify-email?token=' + _token(sent['verify'][0][1])).status_code == 400   # single use
    ok = client.post('/login', json={'role': 'student', 'lrn': REG['lrn'], 'password': REG['password']}).get_json()
    assert ok['success'] is True


def test_wrong_password_never_reveals_unverified_state(env):
    _, client, db, sent = env
    client.post('/create_account', json=REG)
    res = client.post('/login', json={'role': 'student', 'lrn': REG['lrn'], 'password': 'wrongpass1'}).get_json()
    assert 'needs_verification' not in res


def test_resend_verification_sends_new_link(env):
    _, client, db, sent = env
    client.post('/create_account', json=REG)
    first = _token(sent['verify'][0][1])
    client.post('/resend-verification', json={'identifier': REG['lrn']})
    assert len(sent['verify']) == 2
    assert client.get('/verify-email?token=' + first).status_code == 400   # old link replaced
    assert client.get('/verify-email?token=' + _token(sent['verify'][1][1])).status_code == 200


def test_without_email_settings_registration_still_works(env, monkeypatch):
    appmod, client, db, sent = env
    monkeypatch.setattr(appmod, 'email_configured', lambda: False)
    monkeypatch.setattr(appmod, 'verification_enforced', lambda: False)
    res = client.post('/create_account', json=REG).get_json()
    assert res['success'] and not res.get('verify_email') and sent['verify'] == []
    assert client.post('/login', json={'role': 'student', 'lrn': REG['lrn'], 'password': REG['password']}).get_json()['success']


# ------------------------------------------------------------ email utils
def test_base_url_prefers_configured_value(monkeypatch):
    monkeypatch.setenv('APP_BASE_URL', 'http://school.example:5000/')
    assert email_utils.base_url('http://evil.test/') == 'http://school.example:5000'
    monkeypatch.delenv('APP_BASE_URL')
    assert email_utils.base_url('http://127.0.0.1:5000/') == 'http://127.0.0.1:5000'


def test_send_email_uses_starttls_and_login(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None): calls.append(('connect', host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): calls.append(('starttls',))
        def login(self, user, pw): calls.append(('login', user))
        def send_message(self, msg): calls.append(('send', msg['To'], msg['Subject']))

    monkeypatch.setenv('MAIL_USERNAME', 'sender@example.com')
    monkeypatch.setenv('MAIL_PASSWORD', 'app-password')
    monkeypatch.setattr(email_utils.smtplib, 'SMTP', FakeSMTP)
    ok, err = email_utils.send_email('to@example.com', 'Hi', 'body', '<b>body</b>')
    assert ok and err == ''
    assert [c[0] for c in calls] == ['connect', 'starttls', 'login', 'send']


def test_send_email_not_configured(monkeypatch):
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    monkeypatch.delenv('MAIL_USERNAME', raising=False)
    monkeypatch.delenv('MAIL_PASSWORD', raising=False)
    assert email_utils.send_email('a@b.com', 's', 'b')[0] is False


# ------------------------------------------------------------------ Resend
def _clear_mail_env(monkeypatch):
    for name in ('RESEND_API_KEY', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_FROM'):
        monkeypatch.delenv(name, raising=False)


def test_resend_is_preferred_and_posts_expected_request(monkeypatch):
    _clear_mail_env(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY', 're_test_123')
    monkeypatch.setenv('MAIL_FROM', 'BlockLearn <noreply@school.edu.ph>')
    monkeypatch.setenv('MAIL_USERNAME', 'smtp@example.com')      # ignored when a Resend key exists
    monkeypatch.setenv('MAIL_PASSWORD', 'x')
    assert email_utils.provider() == 'resend'

    captured = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"id": "abc"}'

    def fake_urlopen(request, timeout=None):
        captured['url'] = request.full_url
        captured['headers'] = {k.lower(): v for k, v in request.header_items()}
        captured['body'] = __import__('json').loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(email_utils.urllib.request, 'urlopen', fake_urlopen)
    ok, err = email_utils.send_email('kid@example.com', 'Subject', 'plain', '<b>html</b>')
    assert ok and err == ''
    assert captured['url'] == 'https://api.resend.com/emails'
    assert captured['headers']['authorization'] == 'Bearer re_test_123'
    assert captured['headers']['user-agent']
    assert captured['body'] == {'from': 'BlockLearn <noreply@school.edu.ph>', 'to': ['kid@example.com'],
                                'subject': 'Subject', 'text': 'plain', 'html': '<b>html</b>'}


def test_resend_http_error_is_reported(monkeypatch):
    import io
    import urllib.error
    _clear_mail_env(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY', 're_test_123')

    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, 'Forbidden', {},
                                     io.BytesIO(b'You can only send testing emails to your own email address'))

    monkeypatch.setattr(email_utils.urllib.request, 'urlopen', fake_urlopen)
    ok, err = email_utils.send_email('kid@example.com', 's', 'b')
    assert ok is False and '403' in err and 'own email address' in err


def test_resend_test_domain_does_not_enforce_verification(monkeypatch):
    _clear_mail_env(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY', 're_test_123')
    assert email_utils.testing_mode() is True              # default sender is onboarding@resend.dev
    assert email_utils.email_configured() and not email_utils.verification_enforced()
    monkeypatch.setenv('MAIL_FROM', 'noreply@school.edu.ph')
    assert email_utils.testing_mode() is False and email_utils.verification_enforced()
