# backend/module_awards.py
"""
Item Badges & Certificates for BlockLearn
===========================================
Per-module awards system:
- Per-item badges (25 total): python_a1..a5, java_a1..a5, php_act1..5, js_act1..5, cpp_act1..5
- Per-module certificates (5 total): one certificate per completed language module

Completion rule per module:
  2 lessons completed (manual "Mark as Complete")
  + 5 graded items passed (score >= 75)
Python module finals can record lesson completion but are not a substitute for
the lesson and graded-item requirements.
"""
from datetime import datetime
import uuid


# ============================================================
# CONSTANTS
# ============================================================
MODULE_LANGUAGES = ('python', 'java', 'javascript', 'cpp', 'php')

# Which languages use "assessment" naming vs "activity" naming
ASSESSMENT_LANGUAGES = ('python', 'java')
ACTIVITY_LANGUAGES = ('javascript', 'cpp', 'php')

LESSONS_PER_MODULE = 2
ITEMS_PER_MODULE = 5
PASS_THRESHOLD = 75  # score >= 75 out of 100
MODULE_FINAL_COMPLETION_LANGUAGES = ('python',)

# Display metadata for frontend
LANGUAGE_DISPLAY = {
    'python': {'name': 'Python', 'icon': '🐍', 'color': '#3776ab'},
    'java': {'name': 'Java', 'icon': '☕', 'color': '#f89820'},
    'javascript': {'name': 'JavaScript', 'icon': '🟨', 'color': '#f7df1e'},
    'cpp': {'name': 'C++', 'icon': '⚙️', 'color': '#00599c'},
    'php': {'name': 'PHP', 'icon': '🐘', 'color': '#777bb4'},
}

# Item badges per language — from the verified curriculum
ITEM_BADGE_DEFS = {}
for lang in MODULE_LANGUAGES:
    prefix = f'{lang}_a' if lang in ASSESSMENT_LANGUAGES else f'{lang}_act'
    for n in range(1, ITEMS_PER_MODULE + 1):
        code = f'{prefix}{n}'
        ITEM_BADGE_DEFS[code] = {
            'code': code,
            'language': lang,
            'item_number': n,
            'type': 'item',
            'label': f'{LANGUAGE_DISPLAY[lang]["name"]} {"Assessment" if lang in ASSESSMENT_LANGUAGES else "Activity"} {n}',
        }

ALL_BADGE_DEFS = ITEM_BADGE_DEFS


def run_migrations(cursor):
    """Create the persistence tables required by item badges and certificates."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_badges (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            badge_code VARCHAR(64) NOT NULL,
            earned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_student_badges_student_code (student_id, badge_code),
            CONSTRAINT fk_student_badges_student
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lesson_completions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            language VARCHAR(20) NOT NULL,
            lesson_number TINYINT UNSIGNED NOT NULL,
            completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_lesson_completions_student_lesson
                (student_id, language, lesson_number),
            CONSTRAINT fk_lesson_completions_student
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS module_certificates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            language VARCHAR(20) NOT NULL,
            verification_id CHAR(36) NOT NULL UNIQUE,
            issued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_module_certificates_student_language (student_id, language),
            CONSTRAINT fk_module_certificates_student
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)


# ============================================================
# HELPERS
# ============================================================
def _item_badge_code(language, item_number):
    """Return the badge code for a specific item."""
    prefix = f'{language}_a' if language in ASSESSMENT_LANGUAGES else f'{language}_act'
    return f'{prefix}{item_number}'


def _normalize_score(teacher_score, auto_score, raw_score):
    """Normalize legacy 0-10 and current 0-100 scores to a 0-100 scale."""
    if teacher_score is not None:
        score = int(teacher_score)
        return score if score > 10 else score * 10
    if auto_score is not None and (int(auto_score) > 0 or not raw_score):
        score = int(auto_score)
        return score if score > 10 else score * 10
    if raw_score is not None:
        score = int(raw_score)
        return score if score > 10 else score * 10
    return 0


def is_attempt_passed(attempt):
    """Return whether a submitted or teacher-reviewed attempt meets the pass mark."""
    if not attempt:
        return False
    status = (attempt.get('status') or '').lower()
    is_final = status in {'submitted', 'completed'} or (
        status == 'pending_review' and attempt.get('teacher_score') is not None
    )
    if not is_final:
        return False
    return _normalize_score(
        attempt.get('teacher_score'),
        attempt.get('auto_score'),
        attempt.get('score'),
    ) >= PASS_THRESHOLD


def prefer_attempt_for_progress(current, candidate):
    """Keep a passing attempt over a later failed retry for persistent progress."""
    if current is None:
        return candidate

    current_passed = is_attempt_passed(current)
    candidate_passed = is_attempt_passed(candidate)
    if current_passed != candidate_passed:
        return candidate if candidate_passed else current

    current_final = (
        current.get('status') or ''
    ).lower() in {'submitted', 'completed'} or current.get('teacher_score') is not None
    candidate_final = (
        candidate.get('status') or ''
    ).lower() in {'submitted', 'completed'} or candidate.get('teacher_score') is not None
    if current_final != candidate_final:
        return candidate if candidate_final else current

    current_score = _normalize_score(
        current.get('teacher_score'), current.get('auto_score'), current.get('score'),
    )
    candidate_score = _normalize_score(
        candidate.get('teacher_score'), candidate.get('auto_score'), candidate.get('score'),
    )
    return candidate if candidate_score >= current_score else current


def get_badge_metadata(badge_code):
    """Return badge definition dict or a minimal fallback."""
    meta = ALL_BADGE_DEFS.get(badge_code)
    if meta:
        return dict(meta)
    return {'code': badge_code, 'type': 'unknown', 'label': badge_code, 'language': None}


# ============================================================
# AWARD PRIMITIVES (idempotent)
# ============================================================
def award_badge(cursor, student_id, badge_code):
    """
    Award a badge. Idempotent — returns True only if newly awarded.
    """
    if badge_code not in ALL_BADGE_DEFS:
        return False
    cursor.execute(
        """
        INSERT IGNORE INTO student_badges (student_id, badge_code)
        VALUES (%s, %s)
        """,
        (student_id, badge_code),
    )
    return cursor.rowcount == 1


def get_student_badges(cursor, student_id):
    """Return earned item badges for the student, newest first."""
    cursor.execute(
        """
        SELECT badge_code, earned_at
        FROM student_badges
        WHERE student_id = %s
        ORDER BY earned_at DESC
        """,
        (student_id,),
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        if row['badge_code'] not in ITEM_BADGE_DEFS:
            continue
        meta = get_badge_metadata(row['badge_code'])
        result.append({
            **meta,
            'earned_at': row['earned_at'].strftime('%Y-%m-%d %H:%M') if row['earned_at'] else None,
        })
    return result


def get_student_badges_map(cursor, student_id):
    """Return earned item badges as {badge_code: earned_at_iso}."""
    cursor.execute(
        "SELECT badge_code, earned_at FROM student_badges WHERE student_id = %s",
        (student_id,),
    )
    return {
        row['badge_code']: row['earned_at'].strftime('%Y-%m-%d') if row['earned_at'] else None
        for row in cursor.fetchall()
        if row['badge_code'] in ITEM_BADGE_DEFS
    }


# ============================================================
# LESSON COMPLETION
# ============================================================
def mark_lesson_complete(cursor, student_id, language, lesson_number):
    """
    Mark a lesson as complete. Idempotent.
    Returns True if newly marked, False if already marked or invalid.
    """
    if language not in MODULE_LANGUAGES:
        return False
    if not isinstance(lesson_number, int) or not (1 <= lesson_number <= LESSONS_PER_MODULE):
        return False
    cursor.execute(
        """
        INSERT IGNORE INTO lesson_completions (student_id, language, lesson_number)
        VALUES (%s, %s, %s)
        """,
        (student_id, language, lesson_number),
    )
    return cursor.rowcount == 1


def count_completed_lessons(cursor, student_id, language):
    """Count how many lessons the student has completed in a language."""
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM lesson_completions
        WHERE student_id = %s AND language = %s
        """,
        (student_id, language),
    )
    row = cursor.fetchone()
    return int(row['total'] or 0) if row else 0


def get_completed_lessons(cursor, student_id, language):
    """Return list of lesson numbers completed."""
    cursor.execute(
        """
        SELECT lesson_number FROM lesson_completions
        WHERE student_id = %s AND language = %s
        ORDER BY lesson_number
        """,
        (student_id, language),
    )
    return [int(r['lesson_number']) for r in cursor.fetchall()]


# ============================================================
# ITEM PROGRESS
# ============================================================
def get_item_progress(cursor, student_id, language):
    """
    Return item-level progress for a language:
      {'total': 5, 'passed': N, 'items': [{number, passed, score, title}]}
    A graded item counts as passed when its submitted or legacy-completed attempt
    meets the pass mark. A pending review counts only after a teacher score exists.
    """
    catalog = 'assessments' if language in ASSESSMENT_LANGUAGES else 'activities'
    cursor.execute(
        f"""
        SELECT id, assessment_number, title
        FROM {catalog}
        WHERE language = %s
        ORDER BY assessment_number
        """,
        (language,),
    )
    items = cursor.fetchall()
    if not items:
        return {'total': 0, 'passed': 0, 'items': []}

    assessment_ids = [row['id'] for row in items]
    placeholders = ','.join(['%s'] * len(assessment_ids))
    cursor.execute(
        f"""
        SELECT assessment_id, status, score, auto_score, teacher_score
        FROM assessment_attempts
        WHERE student_id = %s AND language = %s AND assessment_id IN ({placeholders})
        ORDER BY id
        """,
        (student_id, language, *assessment_ids),
    )
    attempts = {}
    for attempt in cursor.fetchall():
        assessment_id = attempt['assessment_id']
        attempts[assessment_id] = prefer_attempt_for_progress(
            attempts.get(assessment_id), attempt,
        )

    result_items = []
    passed_count = 0
    for item in items:
        attempt = attempts.get(item['id'])
        passed = False
        effective_score = 0
        if attempt:
            effective_score = _normalize_score(
                attempt.get('teacher_score'),
                attempt.get('auto_score'),
                attempt.get('score'),
            )
            if is_attempt_passed(attempt):
                passed = True
                passed_count += 1

        result_items.append({
            'number': item['assessment_number'],
            'title': item['title'],
            'passed': passed,
            'score': effective_score,
            'badge_code': _item_badge_code(language, item['assessment_number']),
        })

    return {
        'total': len(items),
        'passed': passed_count,
        'items': result_items,
    }


def get_module_assessment_progress(cursor, student_id, language):
    """Return server-verified module-final passes used for Python completion."""
    if language not in MODULE_FINAL_COMPLETION_LANGUAGES:
        return {'passed': 0, 'total': 0}

    cursor.execute(
        """
        SELECT COUNT(DISTINCT module_number) AS passed
        FROM module_assessment_attempts
        WHERE student_id = %s AND language = %s AND status = 'passed'
        """,
        (student_id, language),
    )
    row = cursor.fetchone() or {}
    return {
        'passed': min(int(row.get('passed') or 0), LESSONS_PER_MODULE),
        'total': LESSONS_PER_MODULE,
    }


def _module_is_complete(lessons_done, items):
    """A module is complete after all lessons and graded items are passed."""
    items_complete = items['passed'] >= items['total'] and items['total'] > 0
    return lessons_done >= LESSONS_PER_MODULE and items_complete


def are_activities_unlocked(cursor, student_id, language=None):
    """Check the existing core-module gate or a language-specific activity gate."""
    if language in ACTIVITY_LANGUAGES:
        return count_completed_lessons(cursor, student_id, language) >= LESSONS_PER_MODULE
    if language is not None:
        return False

    for prerequisite_language in ASSESSMENT_LANGUAGES:
        lessons_done = count_completed_lessons(cursor, student_id, prerequisite_language)
        items = get_item_progress(cursor, student_id, prerequisite_language)
        if (
            lessons_done < LESSONS_PER_MODULE
            or items['total'] == 0
            or items['passed'] < items['total']
        ):
            return False
    return True


# ============================================================
# MODULE PROGRESS
# ============================================================
def get_module_progress(cursor, student_id, language):
    """
    Full module progress for one language.
    Returns:
      {
        'language': str,
        'display_name': str,
        'lessons': {'done': N, 'total': 2, 'next_module': N},
        'items': {'passed': N, 'total': 5, 'list': [...]},
        'complete': bool,
        'badges': {badge_code: date},
        'certificate': {'available': bool, 'issued_at': date|null, 'verification_id': str|null},
      }
    """
    completed_lessons = get_completed_lessons(cursor, student_id, language)
    lessons_done = len(completed_lessons)
    next_module = next(
        (
            number for number in range(1, LESSONS_PER_MODULE + 1)
            if number not in completed_lessons
        ),
        LESSONS_PER_MODULE,
    )
    items = get_item_progress(cursor, student_id, language)
    module_assessments = get_module_assessment_progress(cursor, student_id, language)

    badges_map = get_student_badges_map(cursor, student_id)
    item_badges = {
        item['badge_code']: badges_map.get(item['badge_code'])
        for item in items['items']
    }
    complete = _module_is_complete(lessons_done, items)

    # Look up certificate
    cursor.execute(
        """
        SELECT verification_id, issued_at
        FROM module_certificates
        WHERE student_id = %s AND language = %s
        """,
        (student_id, language),
    )
    cert_row = cursor.fetchone()
    certificate = {
        'available': bool(cert_row),
        'issued_at': cert_row['issued_at'].strftime('%Y-%m-%d') if cert_row else None,
        'verification_id': cert_row['verification_id'] if cert_row else None,
    }

    return {
        'language': language,
        'display_name': LANGUAGE_DISPLAY[language]['name'],
        'icon': LANGUAGE_DISPLAY[language]['icon'],
        'lessons': {
            'done': lessons_done,
            'total': LESSONS_PER_MODULE,
            'next_module': next_module,
        },
        'items': {
            'passed': items['passed'],
            'total': items['total'],
            'list': items['items'],
        },
        'module_assessments': module_assessments,
        'complete': complete,
        'badges': item_badges,
        'certificate': certificate,
    }


def get_all_module_progress(cursor, student_id):
    """Return list of get_module_progress for all languages."""
    return [get_module_progress(cursor, student_id, lang) for lang in MODULE_LANGUAGES]


# ============================================================
# AWARD ORCHESTRATION (called after a submission)
# ============================================================
def try_award_after_submission(cursor, student_id, language, assessment_number):
    """
    Called after a verified pass. Awards:
      - Item badge for that language + number
      - Certificate if the whole module is now complete
    Returns dict: {'new_badges': [...], 'certificate_issued': bool, 'module_complete': bool}
    """
    new_badges = []
    certificate_issued = False

    # Check if this specific item is now passed
    item_code = _item_badge_code(language, assessment_number)
    if award_badge(cursor, student_id, item_code):
        new_badges.append(item_code)

    # Check module completion
    module_progress = get_module_progress(cursor, student_id, language)
    if module_progress['complete']:
        # Issue certificate (idempotent)
        cursor.execute(
            """
            INSERT IGNORE INTO module_certificates
                (student_id, language, verification_id)
            VALUES (%s, %s, %s)
            """,
            (student_id, language, str(uuid.uuid4())),
        )
        if cursor.rowcount == 1:
            certificate_issued = True

    return {
        'new_badges': new_badges,
        'certificate_issued': certificate_issued,
        'module_complete': module_progress['complete'],
    }


def try_award_after_lesson(cursor, student_id, language):
    """Issue a certificate if the module becomes complete after lesson progress."""
    new_badges = []
    certificate_issued = False

    module_progress = get_module_progress(cursor, student_id, language)
    if module_progress['complete']:
        cursor.execute(
            """
            INSERT IGNORE INTO module_certificates
                (student_id, language, verification_id)
            VALUES (%s, %s, %s)
            """,
            (student_id, language, str(uuid.uuid4())),
        )
        if cursor.rowcount == 1:
            certificate_issued = True

    return {
        'new_badges': new_badges,
        'certificate_issued': certificate_issued,
        'module_complete': module_progress['complete'],
    }


# ============================================================
# CERTIFICATE RETRIEVAL
# ============================================================
def ensure_certificate_for_complete_module(cursor, student_id, language):
    """Backfill the certificate row when a module is already complete but no cert exists."""
    if language not in MODULE_LANGUAGES:
        return None
    progress = get_module_progress(cursor, student_id, language)
    if not progress['complete']:
        return None
    existing = get_certificate(cursor, student_id, language)
    if existing is not None:
        return existing
    cursor.execute(
        """
        INSERT IGNORE INTO module_certificates (student_id, language, verification_id)
        VALUES (%s, %s, %s)
        """,
        (student_id, language, str(uuid.uuid4())),
    )
    return get_certificate(cursor, student_id, language)


def sync_module_awards(cursor, student_id, language):
    """Backfill lesson completions, badges, and certificates from verified progress."""
    if language not in MODULE_LANGUAGES:
        return
    if language in MODULE_FINAL_COMPLETION_LANGUAGES:
        cursor.execute(
            """
            SELECT DISTINCT module_number
            FROM module_assessment_attempts
            WHERE student_id = %s AND language = %s AND status = 'passed'
            """,
            (student_id, language),
        )
        for row in cursor.fetchall():
            mark_lesson_complete(cursor, student_id, language, int(row['module_number']))

    items = get_item_progress(cursor, student_id, language)
    for item in items['items']:
        if item['passed']:
            award_badge(cursor, student_id, item['badge_code'])
    return ensure_certificate_for_complete_module(cursor, student_id, language)


def get_certificate(cursor, student_id, language):
    """
    Return certificate info for a student's module, or None if not earned.
    Always scoped by student_id — never trust a student_id from the request.
    """
    if language not in MODULE_LANGUAGES:
        return None
    cursor.execute("SHOW COLUMNS FROM students")
    student_columns = {column['Field'] for column in cursor.fetchall()}
    name_columns = ['s.full_name']
    if {'first_name', 'last_name'}.issubset(student_columns):
        name_parts = [
            f"NULLIF(TRIM(s.{column}), '')"
            for column in ('first_name', 'middle_initial', 'last_name')
            if column in student_columns
        ]
        name_columns.append(
            f"CONCAT_WS(' ', {', '.join(name_parts)}) AS first_last_name"
        )
    name_columns.extend(('s.username', 's.lrn'))
    query = """
        SELECT c.verification_id, c.issued_at,
               {name_columns}, s.grade_level
        FROM module_certificates c
        JOIN students s ON s.id = c.student_id
        WHERE c.student_id = %s AND c.language = %s
        """.format(name_columns=', '.join(name_columns))
    cursor.execute(
        query,
        (student_id, language),
    )
    row = cursor.fetchone()
    if not row:
        return None
    lrn = str(row.get('lrn') or '').strip()
    student_name = 'Student'
    for field in ('full_name', 'first_last_name', 'username'):
        candidate = str(row.get(field) or '').strip()
        if candidate and candidate != lrn and not (
            len(candidate) == 12 and candidate.isdigit()
        ):
            student_name = candidate
            break
    return {
        'language': language,
        'display_name': LANGUAGE_DISPLAY[language]['name'],
        'student_name': student_name,
        'lrn': row.get('lrn'),
        'grade_level': row.get('grade_level'),
        'verification_id': row['verification_id'],
        'issued_at': row['issued_at'].strftime('%B %d, %Y') if row['issued_at'] else None,
        'issued_at_iso': row['issued_at'].strftime('%Y-%m-%d') if row['issued_at'] else None,
    }