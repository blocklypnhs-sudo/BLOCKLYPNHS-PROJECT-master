# backend/security.py
"""
Authentication security helpers for BlockLearn.

1. Salted password hashing (werkzeug) with automatic upgrade of legacy
   unsalted SHA-256 hashes the next time the user logs in.
2. Password strength policy used by registration and password reset.
3. Brute-force protection: after MAX_FAILED_ATTEMPTS wrong passwords for the
   same account within LOCKOUT_MINUTES, further logins are refused until the
   lock expires.
"""
import hashlib
import hmac
import re
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 8

_LEGACY_SHA256 = re.compile(r'^[0-9a-f]{64}$')


# ---------------------------------------------------------------- hashing
def make_password_hash(password):
    """Return a salted hash suitable for storing in the password column."""
    return generate_password_hash(password)


def verify_password(stored_hash, supplied):
    """
    Check a password against a stored hash.
    Returns (ok, needs_upgrade). needs_upgrade is True when the stored value
    is an old unsalted SHA-256 hash that should be replaced after login.
    """
    if not stored_hash or supplied is None:
        return False, False
    if _LEGACY_SHA256.match(stored_hash):
        legacy = hashlib.sha256(supplied.encode()).hexdigest()
        ok = hmac.compare_digest(legacy, stored_hash)
        return ok, ok
    try:
        return check_password_hash(stored_hash, supplied), False
    except (ValueError, TypeError):
        return False, False


# ---------------------------------------------------------- password policy
def validate_password_strength(password):
    """Return (ok, message). Requires 8+ characters with a letter and a digit."""
    password = password or ''
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f'Password must be at least {MIN_PASSWORD_LENGTH} characters'
    if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        return False, 'Password must contain at least one letter and one number'
    return True, ''


# ------------------------------------------------------------ login lockout
def ensure_security_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            identifier VARCHAR(150) NOT NULL,
            ip_address VARCHAR(64) NULL,
            attempted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_login_attempts_identifier (identifier, attempted_at)
        ) ENGINE=InnoDB
    """)


def attempt_key(role, identifier):
    """Normalise the account key so 'ABC' and 'abc ' share one counter."""
    return f"{role}:{str(identifier or '').strip().lower()}"[:150]


def _recent_failures(cursor, key, now):
    since = now - timedelta(minutes=LOCKOUT_MINUTES)
    cursor.execute(
        "SELECT attempted_at FROM login_attempts "
        "WHERE identifier = %s AND attempted_at >= %s ORDER BY attempted_at DESC",
        (key, since),
    )
    return [row['attempted_at'] for row in cursor.fetchall()]


def lockout_seconds_remaining(cursor, key, now=None):
    """Seconds left on the lock for this account, or 0 if it is not locked."""
    now = now or datetime.now()
    failures = _recent_failures(cursor, key, now)
    if len(failures) < MAX_FAILED_ATTEMPTS:
        return 0
    unlock_at = failures[0] + timedelta(minutes=LOCKOUT_MINUTES)
    return max(0, int((unlock_at - now).total_seconds()) + 1)


def record_failed_attempt(cursor, key, ip_address, now=None):
    """Store a failure and return how many attempts remain before the lock."""
    now = now or datetime.now()
    cursor.execute(
        "INSERT INTO login_attempts (identifier, ip_address, attempted_at) VALUES (%s, %s, %s)",
        (key, (ip_address or '')[:64], now),
    )
    cursor.execute(
        "DELETE FROM login_attempts WHERE attempted_at < %s", (now - timedelta(days=1),)
    )
    used = len(_recent_failures(cursor, key, now))
    return max(0, MAX_FAILED_ATTEMPTS - used)


def clear_failed_attempts(cursor, key):
    cursor.execute("DELETE FROM login_attempts WHERE identifier = %s", (key,))


def lockout_message(seconds):
    minutes = max(1, (seconds + 59) // 60)
    unit = 'minute' if minutes == 1 else 'minutes'
    return f'Too many failed login attempts. Please try again in {minutes} {unit}.'
