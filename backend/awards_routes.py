# backend/awards_routes.py
"""
Module Awards routes. Registered via register_awards_routes(app, get_db_connection).
"""
from flask import session, request, jsonify, render_template, redirect

from backend.module_awards import (
    MODULE_LANGUAGES,
    LANGUAGE_DISPLAY,
    ITEM_BADGE_DEFS,
    mark_lesson_complete as _mark_lesson,
    get_all_module_progress,
    get_module_progress,
    get_student_badges,
    try_award_after_lesson,
    sync_module_awards,
)


def register_awards_routes(app, get_db_connection):
    """Register all module-award routes on the Flask app."""

    @app.route('/mark_lesson_complete', methods=['POST'])
    def mark_lesson_complete_route():
        if session.get('role') != 'student':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        data = request.get_json(silent=True) or {}
        language = (data.get('language') or '').lower()
        lesson_number = data.get('lesson_number')

        if language not in MODULE_LANGUAGES:
            return jsonify({'success': False, 'message': 'Invalid language'}), 400
        if not isinstance(lesson_number, int) or not (1 <= lesson_number <= 2):
            return jsonify({'success': False, 'message': 'Invalid lesson number'}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            newly_marked = _mark_lesson(cursor, session['user_id'], language, lesson_number)

            result = try_award_after_lesson(cursor, session['user_id'], language)

            conn.commit()

            return jsonify({
                'success': True,
                'newly_marked': newly_marked,
                'new_badges': result['new_badges'],
                'certificate_issued': result['certificate_issued'],
                'module_complete': result['module_complete'],
            })
        except Exception as exc:
            if conn:
                conn.rollback()
            print(f"[mark_lesson_complete] error: {exc}")
            return jsonify({'success': False, 'message': 'Failed to mark lesson'}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/module_awards')
    def api_module_awards():
        """Return all module progress for the logged-in student."""
        if session.get('role') != 'student':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            for language in MODULE_LANGUAGES:
                sync_module_awards(cursor, session['user_id'], language)

            modules = get_all_module_progress(cursor, session['user_id'])
            all_badges = get_student_badges(cursor, session['user_id'])

            # Summaries
            total_badges = len(all_badges)
            total_certificates = sum(1 for m in modules if m['certificate']['available'])
            modules_complete = sum(1 for m in modules if m['complete'])

            conn.commit()

            return jsonify({
                'success': True,
                'modules': modules,
                'all_badges': all_badges,
                'summary': {
                    'total_badges': total_badges,
                    'max_badges': 25,
                    'total_certificates': total_certificates,
                    'max_certificates': 5,
                    'modules_complete': modules_complete,
                    'max_modules': 5,
                },
            })
        except Exception as exc:
            print(f"[api_module_awards] error: {exc}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': 'Failed to load awards'}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/module_certificate/<language>')
    def module_certificate(language):
        """Display a module certificate. Only for the logged-in student."""
        if session.get('role') != 'student':
            return redirect('/')

        language = (language or '').lower()
        if language not in MODULE_LANGUAGES:
            return redirect('/student_dashboard')

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cert = sync_module_awards(cursor, session['user_id'], language)
            conn.commit()
            if cert is None:
                # Not yet earned — show locked page with progress
                progress = get_module_progress(cursor, session['user_id'], language)
                return render_template(
                    'student/module_certificate_locked.html',
                    progress=progress,
                    display_name=LANGUAGE_DISPLAY[language]['name'],
                    student_name=session.get('full_name') or session.get('username') or 'Student',
                )

            return render_template(
                'student/module_certificate.html',
                cert=cert,
            )
        except Exception as exc:
            print(f"[module_certificate] error: {exc}")
            import traceback
            traceback.print_exc()
            return redirect('/student_dashboard')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/item_badge/<badge_code>')
    def item_badge(badge_code):
        """Display an earned assessment/activity badge for the logged-in student."""
        if session.get('role') != 'student':
            return redirect('/')
        if badge_code not in ITEM_BADGE_DEFS:
            return redirect('/student_dashboard')

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            badge = next(
                (item for item in get_student_badges(cursor, session['user_id'])
                 if item['code'] == badge_code),
                None,
            )
            if badge is None:
                return redirect('/student_dashboard')

            return render_template('student/item_badge.html', badge=badge)
        except Exception as exc:
            print(f"[item_badge] error: {exc}")
            return redirect('/student_dashboard')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
