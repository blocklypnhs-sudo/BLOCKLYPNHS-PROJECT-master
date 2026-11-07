"""Central notification service for students, teachers, and ICT support."""

from datetime import datetime
import re
from backend.db_config import get_db_connection


def _insert_notification(notification_type, title, message, user_id=None, target_role=None, related_id=None):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO notifications
                (user_id, target_role, type, title, message, related_id, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
            """,
            (user_id, target_role, notification_type, title, message, related_id, datetime.now()),
        )
        conn.commit()
        return True
    except Exception as exc:
        print(f"Notification error: {exc}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def notify_new_assessment_submission(student_name, assessment_name, submission_id):
    return _insert_notification(
        'assessment_submission',
        'New Assessment Submission',
        f'{student_name} submitted {assessment_name} for checking.',
        target_role='teacher',
        related_id=submission_id,
    )


def notify_assessment_checked(student_id, assessment_name, score, feedback, submission_id, max_points=None, item_label='Assessment'):
    feedback_text = feedback or 'No feedback provided.'
    score_text = f'{score}/{max_points}' if max_points is not None else f'{score}%'
    return _insert_notification(
        'activity_checked' if item_label == 'Activity' else 'assessment_checked',
        f'{item_label} Checked',
        f'{assessment_name} was auto-graded. Score: {score_text}. Feedback: {feedback_text}',
        user_id=student_id,
        target_role='student',
        related_id=submission_id,
    )


def notify_student_assessment_result(student_id, assessment_name, score, max_points, status, submission_id):
    result_text = 'completed' if status == 'completed' else 'submitted for review'
    return _insert_notification(
        'assessment_result',
        'Assessment Result',
        f'{assessment_name} was {result_text}. Score: {score}/{max_points}.',
        user_id=student_id,
        target_role='student',
        related_id=submission_id,
    )


def notify_module_assessment_result(student_id, module_title, points, max_points, status):
    result_text = 'passed' if status == 'passed' else 'submitted'
    return _insert_notification(
        'module_assessment_result',
        'Module Assessment Result',
        f'{module_title} was {result_text}. Score: {points}/{max_points} points.',
        user_id=student_id,
        target_role='student',
        related_id=None,
    )


def notify_new_support_ticket(ticket_number, subject, ticket_id):
    return _insert_notification(
        'support_ticket_created',
        'New Support Ticket',
        f'{ticket_number}: {subject}',
        target_role='ict',
        related_id=ticket_id,
    )


def notify_student_ticket_received(student_id, ticket_number, subject, ticket_id):
    return _insert_notification(
        'support_ticket_received',
        'Support Ticket Received',
        f'{ticket_number}: {subject} was sent to the support team.',
        user_id=student_id,
        target_role='student',
        related_id=ticket_id,
    )


def notify_ticket_updated(student_id, ticket_number, subject, status, ticket_id):
    return _insert_notification(
        'support_ticket_updated',
        'Ticket Updated',
        f'{ticket_number}: {subject} is now {status}.',
        user_id=student_id,
        target_role='student',
        related_id=ticket_id,
    )


def get_notifications_for_user(user_id, role):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT n.id, n.type, n.title, n.message, n.related_id, n.is_read, n.created_at,
                   reviewed_item.points AS max_points
            FROM notifications AS n
            LEFT JOIN assessment_attempts AS attempt_by_id
                ON n.type IN ('assessment_checked', 'activity_checked')
               AND n.related_id = attempt_by_id.id
            LEFT JOIN learning_items AS reviewed_item
                ON reviewed_item.id = attempt_by_id.assessment_id
               AND reviewed_item.language = attempt_by_id.language
            WHERE n.target_role = %s AND (n.user_id IS NULL OR n.user_id = %s)
            ORDER BY n.created_at DESC
            LIMIT 50
            """,
            (role, user_id),
        )
        rows = cursor.fetchall()
        for row in rows:
            if row['type'] in ('assessment_checked', 'activity_checked'):
                row['title'] = 'Activity Checked' if row['type'] == 'activity_checked' else 'Assessment Checked'
                score_match = re.search(r'Score:\s*(\d+)%', row['message'] or '')
                max_points = row.get('max_points')
                if score_match and max_points is not None:
                    percent = int(score_match.group(1))
                    earned_points = round(percent * max_points / 100)
                    row['message'] = re.sub(
                        r'Score:\s*\d+%',
                        f'Score: {earned_points}/{max_points}',
                        row['message'],
                        count=1,
                    )
            if row.get('created_at'):
                created_at = row['created_at']
                age_seconds = max(0, int((datetime.now() - created_at).total_seconds()))
                if age_seconds < 60:
                    row['time_ago'] = 'Just now'
                elif age_seconds < 3600:
                    row['time_ago'] = f'{age_seconds // 60}m ago'
                elif age_seconds < 86400:
                    row['time_ago'] = f'{age_seconds // 3600}h ago'
                else:
                    row['time_ago'] = f'{age_seconds // 86400}d ago'
                row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        return rows
    except Exception as exc:
        print(f"Notification read error: {exc}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_unread_notification_count(user_id, role):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COUNT(*) AS unread_count
            FROM notifications
            WHERE target_role = %s
              AND (user_id IS NULL OR user_id = %s)
              AND is_read = 0
            """,
            (role, user_id),
        )
        result = cursor.fetchone()
        return result['unread_count'] if result else 0
    except Exception as exc:
        print(f"Notification count error: {exc}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def mark_notification_read(notification_id, user_id, role):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE notifications
            SET is_read = 1
            WHERE id = %s
              AND target_role = %s
              AND (user_id IS NULL OR user_id = %s)
              AND is_read = 0
            """,
            (notification_id, role, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        print(f"Notification update error: {exc}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def mark_all_notifications_read(user_id, role):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read = 1 WHERE target_role = %s AND (user_id IS NULL OR user_id = %s) AND is_read = 0",
            (role, user_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        print(f"Notification update error: {exc}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
