# backend/audit.py
"""
Audit Logging Module for BlockLearn ICT Support
================================================
Centralized, idempotent audit logging that uses REAL database-backed identities.
Never trusts frontend-supplied names/roles/LRNs.

Access: ICT-ONLY (role == 'ict'). Teachers are NOT allowed.
"""
from datetime import datetime
import json


# ═════════════════════════════════════════════════════════════
# TIME
# ═════════════════════════════════════════════════════════════
def ph_time_now():
    """Return current time using the same convention as app.py (naive datetime)."""
    return datetime.now()


# ═════════════════════════════════════════════════════════════
# TABLE INIT (idempotent)
# ═════════════════════════════════════════════════════════════
def init_audit_table(cursor):
    """
    Create the audit_logs table if it does not exist. Idempotent.
    Schema is aligned with frontend expectations (actor_grade_level, user_agent, JSON details).
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            actor_role ENUM('student', 'teacher', 'ict', 'unknown') NOT NULL DEFAULT 'unknown',
            actor_id INT NULL,
            actor_display_name VARCHAR(200) NOT NULL DEFAULT 'Unknown',
            actor_username VARCHAR(100) NULL,
            actor_lrn VARCHAR(50) NULL,
            actor_grade_level VARCHAR(20) NULL,
            action VARCHAR(80) NOT NULL,
            entity_type VARCHAR(80) NULL,
            entity_id VARCHAR(80) NULL,
            details JSON NULL,
            ip_address VARCHAR(45) NULL,
            user_agent VARCHAR(255) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_audit_created (created_at),
            INDEX idx_audit_actor (actor_id, actor_role),
            INDEX idx_audit_action (action),
            INDEX idx_audit_entity (entity_type, entity_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


# ═════════════════════════════════════════════════════════════
# MASKING
# ═════════════════════════════════════════════════════════════
def mask_identifier(value):
    """
    Mask sensitive identifiers (LRN, username, employee ID).
    '123456789012' -> '********9012'
    'juan'         -> '*uan'
    None/empty     -> '(empty)'
    """
    if value is None:
        return '(empty)'
    s = str(value).strip()
    if not s:
        return '(empty)'
    if len(s) <= 4:
        return '*' * len(s)
    return '*' * (len(s) - 4) + s[-4:]


# ═════════════════════════════════════════════════════════════
# ACTOR RESOLUTION (never trust frontend)
# ═════════════════════════════════════════════════════════════
def _compose_student_display_name(row):
    """Prefer composed name from parts, then full_name, then username."""
    if not row:
        return 'Student'
    parts = [
        (row.get('first_name') or '').strip(),
        (row.get('middle_initial') or '').strip(),
        (row.get('last_name') or '').strip(),
    ]
    composed = ' '.join(p for p in parts if p).strip()
    if composed:
        return composed
    full_name = (row.get('full_name') or '').strip()
    if full_name and full_name != (row.get('lrn') or '').strip():
        return full_name
    return (row.get('username') or 'Student').strip() or 'Student'


def get_actor_from_session(cursor):
    """
    Resolve the authenticated actor from the Flask session + matching DB row.
    NEVER trust names/roles/LRNs sent by the browser.

    NOTE: argument order is (cursor,) ONLY — session is read from Flask's
    `session` proxy inside the function. This matches the app.py usage:
        log_audit(cursor, '...')
    """
    # Local import to avoid loading Flask at module import time
    from flask import session

    role = session.get('role')
    user_id = session.get('user_id')

    if role not in {'student', 'teacher', 'ict'} or not user_id:
        return {
            'role': 'unknown',
            'id': None,
            'display_name': 'Unknown',
            'username': None,
            'lrn': None,
            'grade_level': None,
        }

    role_defaults = {
        'student': 'Student',
        'teacher': 'Teacher',
        'ict': 'ICT Support',
    }
    actor = {
        'role': role,
        'id': user_id,
        'display_name': (session.get('full_name') or session.get('username') or role_defaults[role])[:200],
        'username': session.get('username'),
        'lrn': None,
        'grade_level': None,
    }

    table_by_role = {
        'student': 'students',
        'teacher': 'teachers',
        'ict': 'ict_support',
    }

    try:
        cursor.execute(
            f"SELECT * FROM {table_by_role[role]} WHERE id = %s LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        if not isinstance(row, dict) and row is not None and getattr(cursor, 'description', None):
            row = dict(zip((column[0] for column in cursor.description), row))
        if row:
            if role == 'student':
                actor.update({
                    'display_name': _compose_student_display_name(row),
                    'username': row.get('username'),
                    'lrn': row.get('lrn'),
                    'grade_level': row.get('grade_level'),
                })
            else:
                actor.update({
                    'display_name': (row.get('full_name') or row.get('username') or role_defaults[role]).strip(),
                    'username': row.get('username'),
                })
    except Exception as exc:
        print(f"[audit] get_actor_from_session error: {exc}")

    return actor


# ═════════════════════════════════════════════════════════════
# SAFE DETAILS (never store secrets)
# ═════════════════════════════════════════════════════════════
_FORBIDDEN_KEYS = {
    'password', 'password_hash', 'hashed_password',
    'reset_token', 'reset_token_expires',
    'staff_code', 'staff_code_hash', 'validation_code',
    'token', 'secret', 'session', 'session_id',
}


def _sanitize_details(details):
    """Recursively remove forbidden keys from details."""
    if details is None:
        return None
    if isinstance(details, dict):
        cleaned = {}
        for k, v in details.items():
            if str(k).lower() in _FORBIDDEN_KEYS:
                continue
            cleaned[k] = _sanitize_details(v)
        return cleaned
    if isinstance(details, (list, tuple)):
        return [_sanitize_details(item) for item in details]
    if isinstance(details, str):
        return details[:500]
    return details


# ═════════════════════════════════════════════════════════════
# CLIENT META
# ═════════════════════════════════════════════════════════════
def _get_client_ip():
    try:
        from flask import request
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()[:45]
        return (request.remote_addr or '')[:45] or None
    except Exception:
        return None


def _get_user_agent():
    try:
        from flask import request
        return (request.headers.get('User-Agent') or '')[:255] or None
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════
# MAIN LOG FUNCTION
# ═════════════════════════════════════════════════════════════
def log_audit(
    cursor,
    action,
    entity_type=None,
    entity_id=None,
    details=None,
    *,
    actor_override=None,
    commit=True,
):
    """
    Record an audit event.

    - Actor is auto-resolved from Flask session + DB.
    - For non-authenticated events (e.g. failed login), pass `actor_override`.
    - NEVER raises — a broken audit log must not break the main flow.
    - Set `commit=False` if the caller will commit a larger transaction.

    Returns True on success, False on failure.
    """
    try:
        # Resolve actor
        if actor_override is not None:
            actor = {
                'role': actor_override.get('role', 'unknown'),
                'id': actor_override.get('id'),
                'display_name': actor_override.get('display_name', 'Unknown'),
                'username': actor_override.get('username'),
                'lrn': actor_override.get('lrn'),
                'grade_level': actor_override.get('grade_level'),
            }
        else:
            actor = get_actor_from_session(cursor)

        # Sanitize + serialize details
        safe_details = _sanitize_details(details)
        if safe_details is not None:
            safe_details = json.dumps(safe_details, default=str)[:4000]
        else:
            safe_details = None

        cursor.execute("""
            INSERT INTO audit_logs
                (actor_role, actor_id, actor_display_name, actor_username,
                 actor_lrn, actor_grade_level,
                 action, entity_type, entity_id, details,
                 ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            actor.get('role') or 'unknown',
            actor.get('id'),
            (actor.get('display_name') or 'Unknown')[:200],
            (actor.get('username') or None),
            (actor.get('lrn') or None),
            (actor.get('grade_level') or None),
            str(action)[:80],
            (str(entity_type)[:80] if entity_type is not None else None),
            (str(entity_id)[:80] if entity_id is not None else None),
            safe_details,
            _get_client_ip(),
            _get_user_agent(),
            ph_time_now(),
        ))

        if commit:
            cursor.connection.commit()

        return True

    except Exception as e:
        print(f"[audit] Failed to log '{action}': {e}")
        try:
            if commit:
                cursor.connection.rollback()
        except Exception:
            pass
        return False


# ═════════════════════════════════════════════════════════════
# STANDALONE LOGGER (opens its own DB connection)
# ═════════════════════════════════════════════════════════════
def log_audit_safe(action, entity_type=None, entity_id=None, details=None,
                   actor_override=None):
    """
    Standalone logger that opens its own DB connection.
    Use this from routes that don't already have a cursor.

    NOTE: imports get_db_connection LAZILY to avoid circular import at module load.
    """
    conn = None
    cursor = None
    try:
        from app import get_db_connection  # lazy — no circular at import time
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        log_audit(
            cursor, action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            actor_override=actor_override,
            commit=False,
        )
        conn.commit()
    except Exception as exc:
        print(f"[audit] log_audit_safe error: {exc}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()