# backend/feedback.py — Feedback System for BlockLearn
# Companion to backend/tickets.py — pure addition, walang binago sa existing

from backend.db_config import get_db_connection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter
import re

PHILIPPINES_TIMEZONE = ZoneInfo('Asia/Manila')


def feedback_now():
    """Return current Philippines time for MySQL DATETIME fields."""
    return datetime.now(PHILIPPINES_TIMEZONE).replace(tzinfo=None)


# ============================================================
# CONSTANTS — Categories per role
# ============================================================
LEARNING_CATEGORIES = [
    'Difficulty',
    'Learning Experience',
    'Usability',
    'Content',
    'Activity',
    'Other',
]

TECHNICAL_CATEGORIES = [
    'Login Problem',
    'System Error',
    'Page/Interface Problem',
    'Performance Problem',
    'Activity/Module Technical Issue',
    'Other',
]

VALID_LANGUAGES = ['python', 'java', 'cpp', 'javascript', 'php', None]

STOPWORDS = {
    'the','a','an','is','are','was','were','be','been','being','to','of','and','or',
    'but','in','on','at','by','for','with','about','against','between','into','through',
    'during','before','after','above','below','from','up','down','out','off','over',
    'under','again','further','then','once','here','there','when','where','why','how',
    'all','any','both','each','few','more','most','other','some','such','no','nor',
    'not','only','own','same','so','than','too','very','can','will','just','should',
    'now','i','me','my','we','our','you','your','he','him','his','she','her','it',
    'its','they','them','their','this','that','these','those','am','have','has','had',
    'do','does','did','if','because','as','until','while','also','would','could',
    'may','might','must','shall','like','really','get','got','one','two','thing',
    'things','want','need'
}


# ============================================================
# HELPERS
# ============================================================
def _extract_keywords(text, limit=10):
    """Simple keyword extraction from a text block."""
    if not text:
        return []
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    return [w for w, _ in Counter(filtered).most_common(limit)]


def _build_date_filter(filters):
    """Build WHERE clause fragments for date/language/category filters."""
    where = []
    params = []
    if filters.get('date_from'):
        where.append("created_at >= %s")
        params.append(filters['date_from'])
    if filters.get('date_to'):
        where.append("created_at <= %s")
        params.append(filters['date_to'] + " 23:59:59")
    if filters.get('language'):
        where.append("language = %s")
        params.append(filters['language'])
    if filters.get('category'):
        where.append("category = %s")
        params.append(filters['category'])
    if filters.get('assessment_id'):
        where.append("assessment_id = %s")
        params.append(filters['assessment_id'])
    if filters.get('module_id'):
        where.append("module_id = %s")
        params.append(filters['module_id'])
    if filters.get('student_id'):
        where.append("student_id = %s")
        params.append(filters['student_id'])
    return where, params


# ============================================================
# FEEDBACK MANAGER
# ============================================================
class FeedbackManager:

    # ---------- STUDENT ----------
    @staticmethod
    def submit_feedback(student_id, student_name, student_lrn,
                        rating, category, comment,
                        feedback_type='learning',
                        assessment_id=None, activity_id=None,
                        module_id=None, language=None):
        """Student submits feedback. Uses session for identity — never trust frontend."""
        conn = None
        cursor = None
        try:
            # Validate
            if not isinstance(rating, int) or not (1 <= rating <= 5):
                return {'success': False, 'message': 'Rating must be 1-5'}
            if feedback_type not in ('learning', 'technical'):
                return {'success': False, 'message': 'Invalid feedback type'}
            valid_cats = LEARNING_CATEGORIES if feedback_type == 'learning' else TECHNICAL_CATEGORIES
            if category not in valid_cats:
                return {'success': False, 'message': 'Invalid category'}
            if language not in VALID_LANGUAGES:
                return {'success': False, 'message': 'Invalid language'}
            if comment and len(comment) > 2000:
                return {'success': False, 'message': 'Comment too long (max 2000 chars)'}

            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Only context-linked feedback is updated; general feedback is append-only.
            check_where = None
            check_params = []
            if assessment_id:
                check_where = ["student_id = %s", "assessment_id = %s"]
                check_params = [student_id, assessment_id]
            elif activity_id:
                check_where = ["student_id = %s", "activity_id = %s"]
                check_params = [student_id, activity_id]
            elif module_id:
                check_where = ["student_id = %s", "module_id = %s"]
                check_params = [student_id, module_id]

            existing = None
            if check_where:
                check_where.append("feedback_type = %s")
                check_params.append(feedback_type)
                cursor.execute(
                    f"SELECT id FROM feedback WHERE {' AND '.join(check_where)} LIMIT 1",
                    check_params
                )
                existing = cursor.fetchone()

            now = feedback_now()
            safe_comment = (comment or '').strip()[:2000] or None

            if existing:
                cursor.execute("""
                    UPDATE feedback
                    SET rating = %s, category = %s, comment = %s,
                        feedback_type = %s, updated_at = %s
                    WHERE id = %s
                """, (rating, category, safe_comment, feedback_type, now, existing['id']))
                action = 'updated'
            else:
                cursor.execute("""
                    INSERT INTO feedback
                        (student_id, student_name, student_lrn,
                         assessment_id, activity_id, module_id, language,
                         rating, category, comment, feedback_type, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (student_id, student_name, student_lrn,
                      assessment_id, activity_id, module_id, language,
                      rating, category, safe_comment, feedback_type, now))
                action = 'created'

            conn.commit()
            return {'success': True, 'message': f'Feedback {action} successfully'}
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"[feedback] submit error: {e}")
            return {'success': False, 'message': 'Failed to save feedback'}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_student_feedback(student_id, limit=50):
        """Student sees own feedback only."""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, rating, category, comment, feedback_type,
                       language, created_at,
                       DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i') AS created_at
                FROM feedback
                WHERE student_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (student_id, limit))
            return {'success': True, 'feedback': cursor.fetchall()}
        except Exception as e:
            print(f"[feedback] get_student error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ---------- TEACHER (learning) ----------
    @staticmethod
    def get_learning_summary(filters=None):
        """Total, avg rating, most common category — learning feedback only."""
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'learning'")
            where_sql = " AND ".join(where)

            cursor.execute(f"""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(AVG(rating), 0) AS avg_rating,
                    SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS r5,
                    SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS r4,
                    SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS r3,
                    SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS r2,
                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS r1
                FROM feedback
                WHERE {where_sql}
            """, params)
            summary = cursor.fetchone()

            cursor.execute(f"""
                SELECT category, COUNT(*) AS count
                FROM feedback
                WHERE {where_sql}
                GROUP BY category
                ORDER BY count DESC
                LIMIT 1
            """, params)
            top_cat = cursor.fetchone()

            return {
                'success': True,
                'total': summary['total'] or 0,
                'avg_rating': round(float(summary['avg_rating'] or 0), 2),
                'most_common_category': top_cat['category'] if top_cat else '—',
                'distribution': {
                    '5': summary['r5'] or 0,
                    '4': summary['r4'] or 0,
                    '3': summary['r3'] or 0,
                    '2': summary['r2'] or 0,
                    '1': summary['r1'] or 0,
                }
            }
        except Exception as e:
            print(f"[feedback] learning_summary error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_learning_by_category(filters=None):
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'learning'")
            where_sql = " AND ".join(where)
            cursor.execute(f"""
                SELECT category, COUNT(*) AS count,
                       COALESCE(AVG(rating), 0) AS avg_rating
                FROM feedback
                WHERE {where_sql}
                GROUP BY category
                ORDER BY count DESC
            """, params)
            rows = cursor.fetchall()
            for r in rows:
                r['avg_rating'] = round(float(r['avg_rating'] or 0), 2)
            return {'success': True, 'categories': rows}
        except Exception as e:
            print(f"[feedback] learning_by_category error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_learning_by_language(filters=None):
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'learning'")
            where_sql = " AND ".join(where)
            cursor.execute(f"""
                SELECT COALESCE(language, 'general') AS language,
                       COUNT(*) AS count,
                       COALESCE(AVG(rating), 0) AS avg_rating
                FROM feedback
                WHERE {where_sql}
                GROUP BY language
                ORDER BY count DESC
            """, params)
            rows = cursor.fetchall()
            for r in rows:
                r['avg_rating'] = round(float(r['avg_rating'] or 0), 2)
            return {'success': True, 'languages': rows}
        except Exception as e:
            print(f"[feedback] learning_by_language error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_learning_by_item(filters=None):
        """Feedback grouped by assessment/activity/module."""
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "f.feedback_type = 'learning'")
            where_sql = " AND ".join(where)

            cursor.execute(f"""
                SELECT
                    COALESCE(a.title, CONCAT('Assessment #', f.assessment_id)) AS item_name,
                    COALESCE(f.assessment_id, f.activity_id) AS assessment_id,
                    'assessment' AS item_type,
                    COUNT(*) AS count,
                    COALESCE(AVG(f.rating), 0) AS avg_rating
                FROM feedback f
                LEFT JOIN learning_items a
                    ON a.id = COALESCE(f.assessment_id, f.activity_id)
                   AND (f.language IS NULL OR a.language = f.language)
                WHERE {where_sql}
                  AND (f.assessment_id IS NOT NULL OR f.activity_id IS NOT NULL)
                GROUP BY COALESCE(f.assessment_id, f.activity_id), a.title
                ORDER BY count DESC
                LIMIT 20
            """, params)
            rows = cursor.fetchall()
            for r in rows:
                r['avg_rating'] = round(float(r['avg_rating'] or 0), 2)
            return {'success': True, 'items': rows}
        except Exception as e:
            print(f"[feedback] learning_by_item error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_learning_recent(limit=20, filters=None):
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'learning'")
            where_sql = " AND ".join(where)
            params.append(limit)
            cursor.execute(f"""
                SELECT id, student_name, rating, category, comment,
                       language, created_at,
                       DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i') AS created_at
                FROM feedback
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT %s
            """, params)
            return {'success': True, 'feedback': cursor.fetchall()}
        except Exception as e:
            print(f"[feedback] learning_recent error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # ---------- ICT (technical) ----------
    @staticmethod
    def get_technical_summary(filters=None):
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'technical'")
            where_sql = " AND ".join(where)

            cursor.execute(f"""
                SELECT COUNT(*) AS total,
                       COALESCE(AVG(rating), 0) AS avg_rating,
                       SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS r5,
                       SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS r4,
                       SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS r3,
                       SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS r2,
                       SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS r1
                FROM feedback
                WHERE {where_sql}
            """, params)
            summary = cursor.fetchone()

            cursor.execute(f"""
                SELECT category, COUNT(*) AS count
                FROM feedback
                WHERE {where_sql}
                GROUP BY category
                ORDER BY count DESC
                LIMIT 1
            """, params)
            top_cat = cursor.fetchone()

            return {
                'success': True,
                'total': summary['total'] or 0,
                'avg_rating': round(float(summary['avg_rating'] or 0), 2),
                'most_common_issue': top_cat['category'] if top_cat else '—',
                'distribution': {
                    '5': summary['r5'] or 0,
                    '4': summary['r4'] or 0,
                    '3': summary['r3'] or 0,
                    '2': summary['r2'] or 0,
                    '1': summary['r1'] or 0,
                }
            }
        except Exception as e:
            print(f"[feedback] technical_summary error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_technical_by_category(filters=None):
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'technical'")
            where_sql = " AND ".join(where)
            cursor.execute(f"""
                SELECT category, COUNT(*) AS count,
                       COALESCE(AVG(rating), 0) AS avg_rating
                FROM feedback
                WHERE {where_sql}
                GROUP BY category
                ORDER BY count DESC
            """, params)
            rows = cursor.fetchall()
            for r in rows:
                r['avg_rating'] = round(float(r['avg_rating'] or 0), 2)
            return {'success': True, 'categories': rows}
        except Exception as e:
            print(f"[feedback] technical_by_category error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_technical_recent(limit=20, filters=None):
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'technical'")
            where_sql = " AND ".join(where)
            params.append(limit)
            cursor.execute(f"""
                SELECT id, student_name, rating, category, comment,
                       created_at,
                       DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i') AS created_at
                FROM feedback
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT %s
            """, params)
            return {'success': True, 'feedback': cursor.fetchall()}
        except Exception as e:
            print(f"[feedback] technical_recent error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_technical_keywords(filters=None, limit=15):
        """Top keywords from technical comments."""
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'technical'")
            where.append("comment IS NOT NULL")
            where_sql = " AND ".join(where)
            cursor.execute(f"""
                SELECT comment FROM feedback
                WHERE {where_sql}
                LIMIT 500
            """, params)
            rows = cursor.fetchall()
            all_text = ' '.join((r['comment'] or '') for r in rows)
            kws = _extract_keywords(all_text, limit=limit)
            return {'success': True, 'keywords': [{'word': w, 'count': c} for w, c in kws]}
        except Exception as e:
            print(f"[feedback] technical_keywords error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    @staticmethod
    def get_learning_keywords(filters=None, limit=15):
        """Top keywords from learning comments."""
        filters = filters or {}
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            where, params = _build_date_filter(filters)
            where.insert(0, "feedback_type = 'learning'")
            where.append("comment IS NOT NULL")
            where_sql = " AND ".join(where)
            cursor.execute(f"""
                SELECT comment FROM feedback
                WHERE {where_sql}
                LIMIT 500
            """, params)
            rows = cursor.fetchall()
            all_text = ' '.join((r['comment'] or '') for r in rows)
            kws = _extract_keywords(all_text, limit=limit)
            return {'success': True, 'keywords': [{'word': w, 'count': c} for w, c in kws]}
        except Exception as e:
            print(f"[feedback] learning_keywords error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor: cursor.close()
            if conn: conn.close()


# ============================================================
# SIMPLE FUNCTION INTERFACE
# ============================================================
def submit_feedback(*args, **kwargs):
    return FeedbackManager.submit_feedback(*args, **kwargs)

def get_student_feedback(student_id, limit=50):
    return FeedbackManager.get_student_feedback(student_id, limit)

def get_learning_summary(filters=None):
    return FeedbackManager.get_learning_summary(filters)

def get_learning_by_category(filters=None):
    return FeedbackManager.get_learning_by_category(filters)

def get_learning_by_language(filters=None):
    return FeedbackManager.get_learning_by_language(filters)

def get_learning_by_item(filters=None):
    return FeedbackManager.get_learning_by_item(filters)

def get_learning_recent(limit=20, filters=None):
    return FeedbackManager.get_learning_recent(limit, filters)

def get_learning_keywords(filters=None, limit=15):
    return FeedbackManager.get_learning_keywords(filters, limit)

def get_technical_summary(filters=None):
    return FeedbackManager.get_technical_summary(filters)

def get_technical_by_category(filters=None):
    return FeedbackManager.get_technical_by_category(filters)

def get_technical_recent(limit=20, filters=None):
    return FeedbackManager.get_technical_recent(limit, filters)

def get_technical_keywords(filters=None, limit=15):
    return FeedbackManager.get_technical_keywords(filters, limit)