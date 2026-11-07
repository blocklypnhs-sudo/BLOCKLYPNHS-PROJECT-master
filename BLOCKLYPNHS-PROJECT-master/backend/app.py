# app.py - Main Flask Application for Blockly Learning Platform
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import mysql.connector
import hashlib
import json
import secrets
import random
from datetime import datetime, timedelta
import os
import re
import traceback
from backend.notification_service import (
    notify_new_assessment_submission,
    notify_assessment_checked,
    notify_student_assessment_result,
    notify_module_assessment_result,
    notify_new_support_ticket,
    notify_student_ticket_received,
    notify_ticket_updated,
    get_notifications_for_user,
    get_unread_notification_count,
    mark_notification_read,
    mark_all_notifications_read,
)
from backend.staff_auth import initialize_staff_code_hashes, verify_staff_code
from backend.security import (
    make_password_hash,
    verify_password,
    validate_password_strength,
    ensure_security_tables,
    attempt_key,
    lockout_seconds_remaining,
    record_failed_attempt,
    clear_failed_attempts,
    lockout_message,
    MAX_FAILED_ATTEMPTS,
    generate_token,
    hash_token,
    recent_count,
    record_event,
)
from backend.email_utils import (
    email_configured,
    verification_enforced,
    is_real_email,
    base_url,
    send_password_reset_email,
    send_verification_email,
    RESET_LINK_MINUTES,
    VERIFY_LINK_HOURS,
)
from backend.module_awards import (
    run_migrations,
    get_module_progress,
    try_award_after_lesson,
    try_award_after_submission,
    mark_lesson_complete,
    _normalize_score,
    are_activities_unlocked,
    is_attempt_passed,
    prefer_attempt_for_progress,
    PASS_THRESHOLD,
)
from backend.awards_routes import register_awards_routes
from backend.module_scoring import score_module_output
from backend.schema_heal import heal_catalog_table
from backend.auto_grading import normalize_output
from backend.cpp_verify import run_cpp_blocks
from backend.verify import run_python
from backend.java_verify import run_java_blocks
from backend.javascript_verify import run_javascript_blocks
from backend.php_verify import run_php_blocks
from backend.feedback import (
    get_student_feedback, get_learning_summary, get_learning_by_category,
    get_learning_by_language, get_learning_recent, get_learning_keywords,
    get_technical_summary, get_technical_by_category,
    get_technical_recent, get_technical_keywords, submit_feedback,
)
from backend.audit import init_audit_table, log_audit
from backend.scores import (
    ACTIVITY_LANGUAGES,
    ASSESSMENT_LANGUAGES,
    get_student_activity_scores,
    get_student_total_scores,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'your-secret-key-change-this-in-production-2024'
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
CORS(app)


@app.after_request
def audit_authenticated_action(response):
    """Record authenticated state-changing requests without storing request data."""
    if response.mimetype == 'text/html':
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return response
    if request.path == '/login' or session.get('role') not in {'student', 'teacher', 'ict'}:
        return response

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if not hasattr(cursor, 'fetchone'):
            return response
        endpoint = request.endpoint or request.path.strip('/').replace('/', '_') or 'unknown'
        log_audit(
            cursor,
            f'{request.method.lower()}_{endpoint}',
            entity_type='route',
            entity_id=request.path,
            details={'status_code': response.status_code},
            commit=False,
        )
        conn.commit()
    except Exception as exc:
        print(f'Audit request logging error: {exc}')
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return response


# Serve the BL logo as the browser favicon to replace the default/blank icon.
@app.route('/favicon.ico')
def favicon():
    logo_path = os.path.join(app.static_folder, 'BL-LOGO.png')
    if os.path.exists(logo_path):
        return send_from_directory(app.static_folder, 'BL-LOGO.png', mimetype='image/png')
    return ('', 204)

@app.route('/module-assets/<path:filename>')
def module_assets(filename):
    """Serve CSS and JavaScript assets used by module lesson pages."""
    modules_dir = os.path.join(BASE_DIR, 'frontend', 'modules_activities')
    return send_from_directory(modules_dir, filename)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'C@ryll025',
    'database': 'blocklypnhsproject'
}

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        raise Exception("Database connection failed")

def hash_password(password):
    """Salted hash (see backend/security.py). Verify with verify_password()."""
    return make_password_hash(password)

def validate_lrn(lrn):
    return lrn and re.match(r'^\d{12}$', str(lrn))

# ==================== DATABASE INITIALIZATION ====================

def init_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Create students table with full_name
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                full_name VARCHAR(200),
                password VARCHAR(255) NOT NULL,
                lrn VARCHAR(50) UNIQUE NOT NULL,
                grade_level VARCHAR(20) NOT NULL,
                email VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add full_name column if it doesn't exist
        cursor.execute("SHOW COLUMNS FROM students LIKE 'full_name'")
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE students ADD COLUMN full_name VARCHAR(200) AFTER username")
            print("✅ Added full_name column to students table")

        for column_name, column_definition in (
            ('reset_token', 'VARCHAR(128) NULL'),
            ('reset_token_expires', 'DATETIME NULL'),
            ('email_verified', 'TINYINT(1) NOT NULL DEFAULT 1'),
            ('email_verify_token', 'VARCHAR(128) NULL'),
            ('email_verify_expires', 'DATETIME NULL'),
        ):
            cursor.execute(f"SHOW COLUMNS FROM students LIKE '{column_name}'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {column_name} {column_definition}")
        
        # Create teachers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                staff_code_hash VARCHAR(255),
                full_name VARCHAR(200),
                email VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_support (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                staff_code_hash VARCHAR(255),
                full_name VARCHAR(200) NOT NULL,
                role_type ENUM('admin', 'tech', 'helpdesk', 'coordinator') NOT NULL DEFAULT 'tech',
                email VARCHAR(100) UNIQUE,
                status ENUM('active', 'inactive', 'suspended') NOT NULL DEFAULT 'active',
                last_login DATETIME NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        for table in ('teachers', 'ict_support'):
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'staff_code_hash'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN staff_code_hash VARCHAR(255) NULL")

        ensure_security_tables(cursor)

        ict_password = hash_password('Tech123@')
        cursor.execute("SELECT id, password, status FROM ict_support WHERE LOWER(username) = LOWER(%s)", ('ICT-Tech',))
        ict_user = cursor.fetchone()
        if not ict_user:
            cursor.execute("""
                INSERT INTO ict_support (username, password, full_name, role_type, email)
                VALUES (%s, %s, %s, %s, %s)
            """, ('ICT-Tech', ict_password, 'ICT Technician', 'tech', 'ict.tech@pnhs.edu.ph'))
            print("✅ ICT account created: username='ICT-Tech'")
        elif not verify_password(ict_user['password'], 'Tech123@')[0] or ict_user['status'] != 'active':
            cursor.execute("""
                UPDATE ict_support
                SET password = %s, status = 'active'
                WHERE id = %s
            """, (ict_password, ict_user['id']))
            print("ℹ️ ICT-Tech account credentials/status refreshed")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ict_tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_number VARCHAR(30) UNIQUE NOT NULL,
                student_id INT NOT NULL,
                student_name VARCHAR(200),
                student_lrn VARCHAR(50),
                subject VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
                category VARCHAR(100) NOT NULL DEFAULT 'other',
                status ENUM('pending', 'in_progress', 'resolved', 'closed') NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                resolved_at DATETIME NULL,
                INDEX idx_ict_tickets_student (student_id),
                INDEX idx_ict_tickets_status (status)
            )
        """)

        # Keep graded Python and Java assessments separate from practice activities.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                assessment_number TINYINT NOT NULL,
                language ENUM('python', 'java') NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                duration_minutes SMALLINT UNSIGNED NOT NULL,
                points SMALLINT UNSIGNED NOT NULL,
                difficulty ENUM('Easy', 'Medium', 'Hard') NOT NULL,
                expected_output TEXT NOT NULL,
                hint TEXT NOT NULL,
                required_blocks TEXT NOT NULL,
                starter_blocks_xml TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_assessment_language_number (language, assessment_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INT AUTO_INCREMENT PRIMARY KEY,
                assessment_number TINYINT NOT NULL,
                language ENUM('cpp', 'javascript', 'php') NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                duration_minutes SMALLINT UNSIGNED NOT NULL,
                points SMALLINT UNSIGNED NOT NULL,
                difficulty ENUM('Easy', 'Medium', 'Hard') NOT NULL,
                expected_output TEXT NOT NULL,
                hint TEXT NOT NULL,
                required_blocks TEXT NOT NULL,
                starter_blocks_xml TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_activity_language_number (language, assessment_number)
            )
        """)

        # Older databases may lack columns (e.g. assessment_number); add them before splitting.
        heal_catalog_table(cursor, 'assessments')
        heal_catalog_table(cursor, 'activities')

        # Existing installations may have a wider language column and mixed records.
        cursor.execute("ALTER TABLE assessments MODIFY language VARCHAR(20) NOT NULL")
        cursor.execute("""
            UPDATE assessments
            SET language = CASE LOWER(TRIM(language))
                WHEN 'c++' THEN 'cpp'
                WHEN 'c plus plus' THEN 'cpp'
                WHEN 'js' THEN 'javascript'
                ELSE LOWER(TRIM(language))
            END
        """)
        cursor.execute("""
            SELECT COUNT(*) AS total FROM assessments
            WHERE language NOT IN ('python', 'java', 'php', 'javascript', 'cpp')
        """)
        unsupported_count = cursor.fetchone()['total']
        if unsupported_count:
            raise RuntimeError(
                f"Cannot split assessment catalog: {unsupported_count} rows use unsupported languages"
            )
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM (
                SELECT language, assessment_number
                FROM assessments
                WHERE language IN ('php', 'javascript', 'cpp')
                GROUP BY language, assessment_number
                HAVING COUNT(*) > 1
            ) AS duplicate_activities
        """)
        duplicate_activity_count = cursor.fetchone()['total']
        if duplicate_activity_count:
            raise RuntimeError(
                f"Cannot split assessment catalog: {duplicate_activity_count} activity numbers are duplicated"
            )
        cursor.execute("""
            INSERT INTO activities
                (id, language, assessment_number, title, description, duration_minutes,
                 points, difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            SELECT id, language, assessment_number, title, description, duration_minutes,
                   points, difficulty, expected_output, hint, required_blocks, starter_blocks_xml
            FROM assessments
            WHERE language IN ('php', 'javascript', 'cpp')
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks),
                starter_blocks_xml = VALUES(starter_blocks_xml)
        """)

        cursor.execute("SELECT COUNT(*) AS total FROM assessments WHERE language IN ('python', 'java')")
        count_row = cursor.fetchone()
        if not count_row or count_row.get('total', 0) == 0:
            default_assessments = [
                ('python', 1, 'Python Fundamentals', 'Write a Python program that prints exactly: Hello, World!', 10, 10, 'Easy', 'Hello, World!', 'Use print("Hello, World!") in Python.', 'print,TEXT'),
                ('python', 2, 'Variables & Data Types', 'Understanding variables, strings, integers, and type conversion.', 12, 15, 'Easy', 'Juan', 'Use name = "Juan" then print(name).', 'SET VARIABLE,PRINT,TEXT,GET VARIABLE'),
                ('python', 3, 'Conditional Statements', 'Write a Python program that prints the score if it is greater than or equal to 80.', 15, 20, 'Medium', 'Positive', 'Use 10 > 5 with GT operator.', 'IF-ELSE,COMPARE,PRINT,NUMBER'),
                ('python', 4, 'Loops & Iterations', 'Learn for loops, while loops, and iteration techniques in Python.', 18, 20, 'Medium', '1\n2\n3\n4\n5', 'Use for i in range(1, 6).', 'FOR LOOP,PRINT,GET VARIABLE'),
                ('python', 5, 'Functions & Modules', 'Create and use functions, understand scope, and import modules.', 20, 25, 'Hard', 'Welcome to BlockLearn!', 'Define def greet() then call greet().', 'DEFINE FUNCTION,PRINT,CALL FUNCTION,TEXT'),
                ('java', 1, 'Java Fundamentals', 'Basic Java syntax, System.out.println, and program output.', 10, 10, 'Easy', 'Hello, World!', 'Use System.out.println("Hello, World!"); in Java.', 'System.out.println,TEXT'),
                ('java', 2, 'Variables & Data Types', 'Understanding int, double, String variables in Java.', 12, 15, 'Easy', '16', 'Use int age = 16; then System.out.println(age);', 'CREATE VARIABLE,System.out.println,GET VARIABLE,NUMBER'),
                ('java', 3, 'Conditional Statements', 'Write a Java program that prints the score to 80 if it is greater than or equal to 80.', 15, 20, 'Medium', 'Passed', 'Use score >= 75 with GTE operator.', 'IF-ELSE,CREATE VARIABLE,System.out.println,COMPARE,NUMBER'),
                ('java', 4, 'Loops & Repetition', 'Learn for loops and while loops in Java programming.', 18, 20, 'Medium', '1\n2\n3\n4\n5', 'Use for (int i = 1; i <= 5; i++).', 'FOR LOOP,System.out.println,GET VARIABLE'),
                ('java', 5, 'Methods & Problem Solving', 'Create and call methods, understand reusable code in Java.', 20, 25, 'Hard', 'Welcome to Java!', 'Create void welcome() then call welcome();', 'CREATE METHOD,System.out.println,CALL METHOD,TEXT')
            ]
            cursor.executemany("""
                INSERT INTO assessments
                    (language, assessment_number, title, description, duration_minutes, points,
                     difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    description = VALUES(description),
                    duration_minutes = VALUES(duration_minutes),
                    points = VALUES(points),
                    difficulty = VALUES(difficulty),
                    expected_output = VALUES(expected_output),
                    hint = VALUES(hint),
                    required_blocks = VALUES(required_blocks),
                    starter_blocks_xml = VALUES(starter_blocks_xml)
            """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in default_assessments])

        cursor.execute("UPDATE assessments SET points = 10 WHERE language IN ('python', 'java')")
        cpp_assessments = [
            (1, 'Hello C++', 'Print Hello, C++! to the console.', 5, 10, 'Easy', 'Hello, C++!', 'Use cout << "Hello, C++!";', 'cout,TEXT'),
            (2, 'Store Age', 'Create an age variable with value 17 and print it.', 5, 10, 'Easy', '17', 'Use int age = 17; then cout << age;', 'int variable,cout,NUMBER,GET VARIABLE'),
            (3, 'Multiply Numbers', 'Multiply 6 by 5 and print the result.', 8, 10, 'Medium', '30', 'Use cout << 6 * 5;', 'cout,MULTIPLY,NUMBER'),
            (4, 'Less Than', 'Check whether 15 is less than 20 and print the message.', 10, 10, 'Medium', '15 is less than 20', 'Use if (15 < 20) with cout inside.', 'if,LESS THAN,cout,NUMBER,TEXT'),
            (5, 'Display Numbers', 'Display numbers 1 to 5 using a for loop.', 12, 10, 'Hard', '1\n2\n3\n4\n5', 'Use for (int i = 1; i <= 5; i++).', 'FOR LOOP,cout,NUMBER,GET VARIABLE')
        ]
        cursor.executemany("""
            INSERT INTO activities
                (assessment_number, language, title, description, duration_minutes, points,
                 difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            VALUES (%s, 'cpp', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks)
        """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in cpp_assessments])

        javascript_assessments = [
            (1, 'Hello, JavaScript!', 'Print Hello, JavaScript! to the console.', 5, 10, 'Easy', 'Hello, JavaScript!', 'Use console.log("Hello, JavaScript!");', 'console.log,TEXT'),
            (2, 'Store and Display a Score', 'Create a score variable with value 90 and print it.', 5, 10, 'Easy', '90', 'Use var score = 90; then console.log(score);', 'var,console.log,NUMBER,variable_get'),
            (3, 'Add Two Numbers', 'Add 25 and 15 and print the result.', 8, 10, 'Medium', '40', 'Use console.log(25 + 15);', 'console.log,+,NUMBER'),
            (4, 'Greater Than', 'Check whether 20 is greater than 10 and print the message.', 10, 10, 'Medium', '20 is greater than 10', 'Use if (20 > 10) with console.log inside.', 'if,>,console.log,NUMBER,TEXT'),
            (5, 'Repeat a Message Five Times', 'Print I love programming! five times with a loop.', 12, 10, 'Hard', 'I love programming!\nI love programming!\nI love programming!\nI love programming!\nI love programming!', 'Use a for loop that repeats 5 times.', 'for loop,console.log,NUMBER,TEXT')
        ]
        cursor.executemany("""
            INSERT INTO activities
                (assessment_number, language, title, description, duration_minutes, points,
                 difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            VALUES (%s, 'javascript', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks)
        """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in javascript_assessments])

        php_assessments = [
            (1, 'Hello PHP', 'Print Hello, PHP! to the console.', 5, 10, 'Easy', 'Hello, PHP!', 'Use echo "Hello, PHP!".', 'echo,TEXT'),
            (2, 'Store a Name', 'Create a name variable and display it.', 5, 10, 'Easy', 'Caryll', 'Use $name = "Caryll" then echo $name.', 'variable,echo,TEXT,GET VARIABLE'),
            (3, 'Subtract Numbers', 'Subtract 50 from 80 and display the result.', 8, 10, 'Medium', '30', 'Use echo 80 - 50.', 'echo,SUBTRACT,NUMBER'),
            (4, 'Greater Than', 'Check whether 25 is greater than 18.', 10, 10, 'Medium', '25 is greater than 18', 'Use if (25 > 18) with echo.', 'if,>,echo,NUMBER,TEXT'),
            (5, 'Repeat a Message', 'Display Learning PHP! three times using a loop.', 12, 10, 'Hard', 'Learning PHP!\nLearning PHP!\nLearning PHP!', 'Use a loop that repeats three times.', 'FOR LOOP,echo,NUMBER,TEXT')
        ]
        cursor.executemany("""
            INSERT INTO activities
                (assessment_number, language, title, description, duration_minutes, points,
                 difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            VALUES (%s, 'php', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks)
        """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in php_assessments])

        cursor.execute("UPDATE activities SET points = 10")
        cursor.execute("UPDATE assessments SET points = 10")

        # Keep the database definition aligned with the Python Fundamentals playground.
        cursor.execute("""
            UPDATE assessments
            SET title = %s,
                description = %s,
                duration_minutes = %s,
                points = %s,
                difficulty = %s,
                expected_output = %s,
                hint = %s,
                required_blocks = %s,
                starter_blocks_xml = %s
            WHERE language = 'python' AND assessment_number = 1
        """, (
            'Python Fundamentals',
            'Write a Python program that prints exactly: Hello, World!',
            10,
            10,
            'Easy',
            'Hello, World!',
            'Use print("Hello, World!") in Python.',
            'print,TEXT',
            '<xml xmlns="https://developers.google.com/blockly/xml"><block type="text_print" x="20" y="20"><value name="TEXT"><block type="text"><field name="TEXT">Hello, World!</field></block></value></block></xml>'
        ))

        # Keep one saved attempt per student and assessment.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessment_attempts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                assessment_id INT NOT NULL,
                language VARCHAR(20) NOT NULL,
                student_id INT NOT NULL,
                code_blocks TEXT NOT NULL,
                generated_code TEXT,
                output TEXT,
                score SMALLINT UNSIGNED DEFAULT 0,
                auto_score SMALLINT UNSIGNED DEFAULT 0,
                teacher_score SMALLINT UNSIGNED NULL,
                teacher_feedback TEXT,
                reviewed_by INT NULL,
                reviewed_at DATETIME NULL,
                status ENUM('in_progress', 'submitted') NOT NULL DEFAULT 'in_progress',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                submitted_at DATETIME NULL,
                completed_at DATETIME NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE KEY uq_student_learning_item_attempt (language, assessment_id, student_id)
            )
        """)

        cursor.execute("""
            UPDATE assessment_attempts a
            SET a.score = CASE
                WHEN a.teacher_score IS NULL THEN a.score
                ELSE a.score
            END
            WHERE a.teacher_score IS NULL
        """)

        attempt_columns = {
            'language': 'VARCHAR(20) NULL',
            'generated_code': 'TEXT NULL',
            'auto_score': 'SMALLINT UNSIGNED NOT NULL DEFAULT 0',
            'teacher_score': 'SMALLINT UNSIGNED NULL',
            'teacher_feedback': 'TEXT NULL',
            'reviewed_by': 'INT NULL',
            'reviewed_at': 'DATETIME NULL',
            'completed_at': 'DATETIME NULL',
        }
        for column_name, column_definition in attempt_columns.items():
            try:
                cursor.execute(f"ALTER TABLE assessment_attempts ADD COLUMN {column_name} {column_definition}")
            except mysql.connector.Error as alter_error:
                if getattr(alter_error, 'errno', None) != 1060:
                    raise

        cursor.execute("""
            UPDATE assessment_attempts aa
            JOIN assessments d ON d.id = aa.assessment_id
            SET aa.language = d.language
            WHERE aa.language IS NULL OR aa.language = ''
        """)
        cursor.execute("""
            SELECT COUNT(*) AS total FROM assessment_attempts
            WHERE language IS NULL OR language = ''
        """)
        unmapped_attempts = cursor.fetchone()['total']
        if unmapped_attempts:
            raise RuntimeError(
                f"Cannot split assessment catalog: {unmapped_attempts} attempts have no matching definition"
            )

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'assessment_attempts'
              AND COLUMN_NAME = 'assessment_id'
              AND REFERENCED_TABLE_NAME = 'assessments'
        """)
        for constraint in cursor.fetchall():
            constraint_name = constraint['CONSTRAINT_NAME'].replace('`', '``')
            cursor.execute(f"ALTER TABLE assessment_attempts DROP FOREIGN KEY `{constraint_name}`")

        cursor.execute("SHOW INDEX FROM assessment_attempts WHERE Key_name = 'uq_student_assessment_attempt'")
        legacy_attempt_indexes = cursor.fetchall()
        if legacy_attempt_indexes:
            cursor.execute("ALTER TABLE assessment_attempts DROP INDEX uq_student_assessment_attempt")
        cursor.execute("SHOW INDEX FROM assessment_attempts WHERE Key_name = 'uq_student_learning_item_attempt'")
        learning_item_attempt_indexes = cursor.fetchall()
        if not learning_item_attempt_indexes:
            cursor.execute("""
                ALTER TABLE assessment_attempts
                ADD UNIQUE KEY uq_student_learning_item_attempt (language, assessment_id, student_id)
            """)
        cursor.execute("ALTER TABLE assessment_attempts MODIFY language VARCHAR(20) NOT NULL")

        cursor.execute("DELETE FROM assessments WHERE language IN ('php', 'javascript', 'cpp')")
        cursor.execute("ALTER TABLE assessments MODIFY language ENUM('python', 'java') NOT NULL")
        cursor.execute("""
            CREATE OR REPLACE VIEW learning_items AS
            SELECT id, assessment_number, language, title, description, duration_minutes,
                   points, difficulty, expected_output, hint, required_blocks,
                   starter_blocks_xml, created_at
            FROM assessments
            UNION ALL
            SELECT id, assessment_number, language, title, description, duration_minutes,
                   points, difficulty, expected_output, hint, required_blocks,
                   starter_blocks_xml, created_at
            FROM activities
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS module_assessment_attempts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                module_id VARCHAR(100) NOT NULL,
                language VARCHAR(20) NOT NULL,
                module_number TINYINT UNSIGNED NOT NULL,
                module_title VARCHAR(200) NOT NULL,
                code_blocks TEXT NOT NULL,
                generated_code TEXT,
                output TEXT,
                expected_output TEXT NOT NULL,
                score SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                points_earned SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                max_points SMALLINT UNSIGNED NOT NULL DEFAULT 10,
                attempts SMALLINT UNSIGNED NOT NULL DEFAULT 1,
                status ENUM('passed', 'failed') NOT NULL,
                submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_student_module_assessment (student_id, module_id),
                INDEX idx_module_attempts_student (student_id),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("SHOW COLUMNS FROM module_assessment_attempts LIKE 'attempts'")
        if cursor.fetchone() is None:
            cursor.execute(
                "ALTER TABLE module_assessment_attempts "
                "ADD COLUMN attempts SMALLINT UNSIGNED NOT NULL DEFAULT 1 AFTER max_points"
            )

        # Store student learning and technical feedback.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                student_name VARCHAR(200),
                student_lrn VARCHAR(50),
                assessment_id INT NULL,
                activity_id INT NULL,
                module_id INT NULL,
                language VARCHAR(30) NULL,
                rating TINYINT UNSIGNED NOT NULL,
                category VARCHAR(100) NOT NULL,
                comment TEXT NULL,
                feedback_type ENUM('learning', 'technical') NOT NULL DEFAULT 'learning',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_feedback_student_type (student_id, feedback_type),
                INDEX idx_feedback_type_created (feedback_type, created_at)
            )
        """)

        # CREATE ADMIN/TEACHER ACCOUNT
        cursor.execute("SELECT id FROM teachers WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_password = hash_password("admin123")
            cursor.execute("""
                INSERT INTO teachers (username, password, full_name, email, created_at) 
                VALUES (%s, %s, %s, %s, %s)
            """, ("admin", admin_password, "System Administrator", "admin@blocklearn.edu.ph", datetime.now()))
            print("✅ Admin account created: username='admin', password='admin123'")
        else:
            print("Admin account already exists")

        cursor.execute("SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'")
        teacher1_row = cursor.fetchone()
        if not teacher1_row:
            teacher1_password = hash_password("Teacher123@")
            cursor.execute("""
                INSERT INTO teachers (username, password, full_name, email, created_at) 
                VALUES (%s, %s, %s, %s, %s)
            """, ("teacher1", teacher1_password, "Teacher One", "teacher1@blocklearn.edu.ph", datetime.now()))
            print("✅ Teacher account created: username='teacher1'")
        else:
            if teacher1_row['username'] != 'teacher1':
                cursor.execute("UPDATE teachers SET username = %s WHERE id = %s", ("teacher1", teacher1_row['id']))
                print("ℹ️ Normalized existing teacher1 username to lowercase")
            if not verify_password(teacher1_row['password'], "Teacher123@")[0]:
                cursor.execute("UPDATE teachers SET password = %s WHERE id = %s", (hash_password("Teacher123@"), teacher1_row['id']))
                print("ℹ️ Updated teacher1 password to the provided default")
            print("Teacher1 account already exists")
        
        initialize_staff_code_hashes(cursor)
        init_audit_table(cursor)
        run_migrations(cursor)
        conn.commit()
        print("Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Initialize database on startup
init_database()
register_awards_routes(app, get_db_connection)

# ==================== PAGE ROUTES ====================

@app.route('/')
def index():
    if session.get('role') == 'student':
        return redirect('/student_dashboard')
    elif session.get('role') == 'teacher':
        return redirect('/teacher_dashboard')
    elif session.get('role') == 'ict':
        return redirect('/ict_support_dashboard')
    return render_template('public/homepage.html')

@app.route('/about')
def about():
    return render_template('public/about.html')

@app.route('/registeracc')
def registeracc():
    return render_template('auth/register.html')

@app.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    return render_template('auth/forgot.password.html')

@app.route('/reset-password', methods=['GET'])
def reset_password_page():
    return render_template('auth/Reset_Password.html')

# ===== STUDENT ROUTES =====
def _get_student_identity():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM students WHERE id = %s",
            (session.get('user_id'),),
        )
        return cursor.fetchone() or {}
    finally:
        cursor.close()
        conn.close()


def _student_display_name(student):
    lrn = str(student.get('lrn') or '').strip()

    def usable_name(value):
        name = str(value or '').strip()
        if not name or name == lrn or validate_lrn(name):
            return None
        return name

    composed_name = ''
    if student.get('first_name') and student.get('last_name'):
        composed_name = ' '.join(
            str(student.get(field) or '').strip()
            for field in ('first_name', 'middle_initial', 'last_name')
            if str(student.get(field) or '').strip()
        )
    return (
        usable_name(composed_name)
        or usable_name(student.get('full_name'))
        or usable_name(student.get('username'))
        or 'Student'
    )


def _student_name_sql(cursor, alias='s'):
    """Build a name expression using only student columns present in this schema."""
    cursor.execute("SHOW COLUMNS FROM students")
    columns = {column['Field'] for column in cursor.fetchall()}
    name_parts = []
    if {'first_name', 'last_name'}.issubset(columns):
        name_parts = [
            f"NULLIF(TRIM({alias}.{column}), '')"
            for column in ('first_name', 'middle_initial', 'last_name')
            if column in columns
        ]
    expressions = []
    if name_parts:
        expressions.append(
            f"NULLIF(CONCAT_WS(' ', {', '.join(name_parts)}), '')"
        )
    if 'full_name' in columns:
        expressions.append(
            f"NULLIF(CASE WHEN TRIM({alias}.full_name) <> TRIM({alias}.lrn) "
            f"AND TRIM({alias}.full_name) NOT REGEXP '^[0-9]{{12}}$' "
            f"THEN TRIM({alias}.full_name) END, '')"
        )
    if 'username' in columns:
        expressions.append(
            f"NULLIF(CASE WHEN TRIM({alias}.username) <> TRIM({alias}.lrn) "
            f"AND TRIM({alias}.username) NOT REGEXP '^[0-9]{{12}}$' "
            f"THEN TRIM({alias}.username) END, '')"
        )
    return f"COALESCE({', '.join(expressions)}, 'Student')"


@app.before_request
def refresh_student_session_name():
    """Replace legacy LRN-backed display names once for existing sessions."""
    if (
        session.get('role') == 'student'
        and not session.get('student_name_loaded')
        and request.endpoint != 'static'
    ):
        student = _get_student_identity()
        session['full_name'] = _student_display_name(student)
        session['student_name_loaded'] = True


@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect('/')

    student = _get_student_identity()

    student_lrn = student.get('lrn') or session.get('lrn')
    student_username = student.get('username') or session.get('username')
    student_name = _student_display_name({
        **student,
        'username': student_username,
        'lrn': student_lrn,
    })
    session['full_name'] = student_name
    grade_level = student.get('grade_level') or session.get('grade_level')

    return render_template('student/student_dashboard.html', 
                          lrn=student_lrn,
                          grade_level=grade_level,
                          username=student_username,
                          full_name=student_name,
                          display_name=student_name)

@app.route('/student_leaderboard')
def student_leaderboard():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/student_leader_board.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/student_modules')
def student_modules():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('modules_activities/ass&act_library.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          library_mode='modules')

@app.route('/get_module_statuses')
def get_module_statuses():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT module_id, status FROM module_assessment_attempts
            WHERE student_id = %s
        """, (session['user_id'],))
        attempts = cursor.fetchall()
        passed_modules = {
            row['module_id'] for row in attempts if row.get('status') == 'passed'
        }
        statuses = {}
        for language, module_ids in MODULE_SEQUENCE_IDS.items():
            language_statuses = []
            for number in range(1, 4):
                module_id = module_ids[number]
                language_statuses.append({
                    'number': number,
                    'passed': module_id in passed_modules,
                    'locked': number > 1 and module_ids[number - 1] not in passed_modules,
                })
            statuses[language] = language_statuses
        return jsonify({'success': True, 'statuses': statuses})
    except Exception as e:
        print(f"Get module statuses error: {e}")
        return jsonify({'success': False, 'message': 'Failed to load module statuses'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/student_modules/cpp')
def student_modules_cpp():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_modules/cpp/1')

@app.route('/student_modules/java')
def student_modules_java():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_modules/java/1')

MODULE_SEQUENCE_IDS = {
    'python': {
        1: 'python-01-basics', 2: 'python-02-loops', 3: 'python-03-functions',
    },
    'java': {
        1: 'java-01-basics', 2: 'java-02-loops', 3: 'java-03-conditionals',
    },
    'php': {
        1: 'php-01-variables', 2: 'php-02-conditionals', 3: 'php-03-loops',
    },
    'javascript': {
        1: 'js-01-variables', 2: 'js-02-functions', 3: 'js-03-conditionals',
    },
    'cpp': {
        1: 'cpp-01-basics', 2: 'cpp-02-loops', 3: 'cpp-03-conditionals',
    },
}

MODULE_03_DETAILS = {
    'python': ('Functions and Conditions', 'Learn how Python functions and conditional statements make programs reusable and responsive.'),
    'java': ('Conditionals and Methods', 'Practice Java decision-making and organize reusable logic with methods.'),
    'php': ('Loops and Repetition', 'Use PHP loops to repeat instructions and build predictable output.'),
    'javascript': ('Conditions and Decisions', 'Use JavaScript conditions and comparisons to control program flow.'),
    'cpp': ('Conditions and Decisions', 'Use C++ comparisons and conditionals to choose which instructions run.'),
}

def _build_module_question_banks():
    language_syntax = {
        'python': {
            'output': 'print("Hello")', 'assignment': 'score = 10', 'comment': '#',
            'truth': 'True', 'condition': 'if score >= 10:', 'loop': 'for i in range(3):',
            'function': 'def greet():', 'string': 'str', 'array': 'scores = [1, 2, 3]',
        },
        'java': {
            'output': 'System.out.println("Hello");', 'assignment': 'int score = 10;',
            'comment': '//', 'truth': 'true', 'condition': 'if (score >= 10) {',
            'loop': 'for (int i = 0; i < 3; i++) {', 'function': 'void greet() {',
            'string': 'String', 'array': 'int[] scores = {1, 2, 3};',
        },
        'php': {
            'output': 'echo "Hello";', 'assignment': '$score = 10;', 'comment': '//',
            'truth': 'true', 'condition': 'if ($score >= 10) {',
            'loop': 'for ($i = 0; $i < 3; $i++) {', 'function': 'function greet() {',
            'string': 'string', 'array': '$scores = [1, 2, 3];',
        },
        'javascript': {
            'output': 'console.log("Hello");', 'assignment': 'let score = 10;',
            'comment': '//', 'truth': 'true', 'condition': 'if (score >= 10) {',
            'loop': 'for (let i = 0; i < 3; i++) {', 'function': 'function greet() {',
            'string': 'string', 'array': 'const scores = [1, 2, 3];',
        },
        'cpp': {
            'output': 'std::cout << "Hello";', 'assignment': 'int score = 10;',
            'comment': '//', 'truth': 'true', 'condition': 'if (score >= 10) {',
            'loop': 'for (int i = 0; i < 3; i++) {', 'function': 'void greet() {',
            'string': 'std::string', 'array': 'int scores[] = {1, 2, 3};',
        },
    }
    questions = {}
    for language, syntax in language_syntax.items():
        questions[language] = [
            ('output', 'Which statement displays the text Hello?', [syntax['output'], 'show("Hello")', 'display "Hello"', 'echo("Hello")'], f'Use {syntax["output"]} to display text.'),
            ('assignment', 'Which line assigns 10 to score?', [syntax['assignment'], 'score == 10', 'score :=: 10', 'set score equals 10'], f'Use {syntax["assignment"]} to assign the value.'),
            ('comment', 'Which token starts a single-line comment?', [syntax['comment'], '<!--', '**', ';;'], f'A single-line comment starts with {syntax["comment"]}.'),
            ('boolean', 'Which value represents true?', [syntax['truth'], '"true"', 'YES', '1 == 0'], f'The true boolean value is {syntax["truth"]}.'),
            ('equals', 'Which operator checks whether two values are equal?', ['==', '=', '=>', '<>'], 'Use == for an equality comparison.'),
            ('condition', 'Which line begins a check that score is at least 10?', [syntax['condition'], 'when score >= 10 then', 'score >= 10 if', 'check(score, 10)'], f'Use {syntax["condition"]} to begin the condition.'),
            ('loop', 'Which line begins a loop that repeats three times?', [syntax['loop'], 'repeat = 3 forever', 'loop(i, 3, 0)', 'while i == 3'], f'Use {syntax["loop"]} to begin the loop.'),
            ('function', 'Which line begins a function named greet?', [syntax['function'], 'make greet:', 'function = greet()', 'start greet'], f'Use {syntax["function"]} to define the function.'),
            ('string', 'Which type is used for text values?', [syntax['string'], 'boolean', 'integer', 'decimal'], f'Text values use the {syntax["string"]} type.'),
            ('remainder', 'Which operator gives the remainder after division?', ['%', '/', '*', '**'], 'The % operator returns the remainder after division.'),
            ('array', 'Which line creates a collection containing 1, 2, and 3?', [syntax['array'], 'scores = (1; 2; 3)', 'scores = 1 | 2 | 3', 'array scores: 1, 2, 3'], f'Use {syntax["array"]} to create the collection.'),
            ('addition', 'What is the result of 8 + 4?', ['12', '2', '32', '84'], 'Addition combines the values: 8 + 4 = 12.'),
        ]
    return questions

MODULE_QUESTION_BANKS = _build_module_question_banks()

def _issue_learning_quiz(language, purpose, target_id):
    question_pool = MODULE_QUESTION_BANKS.get(language)
    if not question_pool:
        raise ValueError(f'No quiz question bank for {language}')

    token = secrets.token_urlsafe(18)
    selected = random.sample(question_pool, 10)
    history_key = f'{purpose}:{target_id}'
    quiz_history = session.get('learning_quiz_history', {})
    previous_set = set(quiz_history.get(history_key, []))
    for _ in range(20):
        question_ids = {question[0] for question in selected}
        if question_ids != previous_set:
            break
        selected = random.sample(question_pool, 10)
    quiz_history[history_key] = sorted(question[0] for question in selected)
    if len(quiz_history) > 5:
        quiz_history = dict(list(quiz_history.items())[-5:])
    session['learning_quiz_history'] = quiz_history

    answer_key = {}
    public_questions = []
    for question_id, prompt, options, _explanation in selected:
        shuffled_options = list(options)
        random.shuffle(shuffled_options)
        answer_key[question_id] = shuffled_options.index(options[0])
        public_questions.append({
            'id': question_id,
            'question': prompt,
            'options': shuffled_options,
        })

    active_quizzes = session.get('active_learning_quizzes', {})
    if len(active_quizzes) >= 3:
        active_quizzes = dict(list(active_quizzes.items())[-2:])
    active_quizzes[token] = {
        'language': language,
        'purpose': purpose,
        'target_id': str(target_id),
        'answer_key': answer_key,
    }
    session['active_learning_quizzes'] = active_quizzes
    return token, public_questions

def _module_is_unlocked(student_id, language, module_number):
    if module_number <= 1:
        return module_number == 1
    previous_module_id = MODULE_SEQUENCE_IDS.get(language, {}).get(module_number - 1)
    if not previous_module_id:
        return False
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT status FROM module_assessment_attempts
            WHERE student_id = %s AND module_id = %s
            LIMIT 1
        """, (student_id, previous_module_id))
        previous = cursor.fetchone()
        return bool(previous and previous.get('status') == 'passed')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _previous_assessment_passed(cursor, student_id, language, assessment_number):
    if assessment_number <= 1:
        return assessment_number == 1
    cursor.execute("""
        SELECT attempt.status, attempt.teacher_score, attempt.auto_score, attempt.score
        FROM learning_items item
        JOIN assessment_attempts attempt
          ON attempt.assessment_id = item.id
         AND attempt.language = item.language
         AND attempt.student_id = %s
        WHERE item.language = %s AND item.assessment_number = %s
        LIMIT 1
    """, (student_id, language, assessment_number - 1))
    previous = cursor.fetchone()
    if not previous or previous.get('status') != 'submitted':
        return False
    return _normalize_score(
        previous.get('teacher_score'),
        previous.get('auto_score'),
        previous.get('score'),
    ) >= 75

def _grade_learning_quiz(token, language, purpose, target_id, answers):
    active_quizzes = session.get('active_learning_quizzes', {})
    if not isinstance(token, str):
        return None
    quiz = active_quizzes.get(token)
    if (
        not isinstance(quiz, dict)
        or quiz.get('language') != language
        or quiz.get('purpose') != purpose
        or quiz.get('target_id') != str(target_id)
        or not isinstance(answers, list)
    ):
        return None

    answer_key = quiz.get('answer_key', {})
    if len(answers) != 10:
        return None
    submitted = {}
    for answer in answers:
        if not isinstance(answer, dict):
            return None
        question_id = answer.get('id')
        choice = answer.get('choice')
        if (
            not isinstance(question_id, str)
            or question_id not in answer_key
            or question_id in submitted
            or not isinstance(choice, int)
            or isinstance(choice, bool)
            or not 0 <= choice < 4
        ):
            return None
        submitted[question_id] = choice
    if set(submitted) != set(answer_key):
        return None

    correct = sum(
        1 for question_id, choice in submitted.items()
        if answer_key[question_id] == choice
    )
    del active_quizzes[token]
    session['active_learning_quizzes'] = active_quizzes
    return correct

@app.route('/student_modules/<language>/<int:module_number>')
def student_module(language, module_number):
    if session.get('role') != 'student':
        return redirect('/')

    module_templates = {
        ('python', 1): 'modules_activities/modules_assessments/python_01_bascis.html',
        ('python', 2): 'modules_activities/modules_assessments/python_02_loops.html',
        ('php', 1): 'modules_activities/php_modules_01_variables.html',
        ('php', 2): 'modules_activities/php_modules_02_condition.html',
        ('javascript', 1): 'modules_activities/javascript_01_variables.html',
        ('javascript', 2): 'modules_activities/javascript_02_functions.html',
        ('cpp', 1): 'modules_activities/cpp_module_01_basics.html',
        ('cpp', 2): 'modules_activities/cpp_module_02_loops.html',
        ('java', 1): 'modules_activities/modules_assessments/java01_basics.html',
        ('java', 2): 'modules_activities/modules_assessments/java_02_loops.html',
    }
    language = language.lower()
    if module_number == 3 and language in MODULE_03_DETAILS:
        template = 'modules_activities/module_03_quiz.html'
    else:
        template = module_templates.get((language, module_number))
    if not template:
        return redirect('/student_modules')

    if not _module_is_unlocked(session['user_id'], language, module_number):
        return render_template(
            'modules_activities/module_locked.html',
            language=language,
            module_number=module_number,
            previous_module_number=module_number - 1,
        ), 403

    if module_number == 3:
        module_title, module_description = MODULE_03_DETAILS[language]
        quiz_token, quiz_questions = _issue_learning_quiz(
            language, 'module', MODULE_SEQUENCE_IDS[language][module_number]
        )
        return render_template(
            template,
            username=session.get('username'),
            full_name=session.get('full_name'),
            language=language,
            language_name=language.title(),
            module_id=MODULE_SEQUENCE_IDS[language][module_number],
            module_title=module_title,
            module_description=module_description,
            quiz_token=quiz_token,
            quiz_questions=quiz_questions,
        )

    module_completed = False
    module_completion_score = None
    module_completion_date = None
    module_assessment_id = MODULE_SEQUENCE_IDS.get(language, {}).get(module_number)
    if module_assessment_id:
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            progress = get_module_progress(cursor, session['user_id'], language.lower())
            module_completed = progress['complete']
            if module_completed:
                cursor.execute(
                    """
                    SELECT score, submitted_at
                    FROM module_assessment_attempts
                    WHERE student_id = %s AND module_id = %s AND status = 'passed'
                    LIMIT 1
                    """,
                    (session['user_id'], module_assessment_id),
                )
                attempt = cursor.fetchone()
                if attempt:
                    module_completion_score = attempt['score']
                    submitted_at = attempt['submitted_at']
                    module_completion_date = (
                        submitted_at.strftime('%B %d, %Y') if submitted_at else None
                    )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template(template,
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'),
                          module_completed=module_completed,
                          module_completion_score=module_completion_score,
                          module_completion_date=module_completion_date)

@app.route('/student_playground')
def student_playground():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('public/student_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_playground_python')
def student_playground_python():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/python_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/playground_javascript')
@app.route('/student_playground_javascript')
def student_playground_javascript():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/javascript_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_playground_html')
def student_playground_html():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_playground_python')

@app.route('/playground_php')
@app.route('/student_playground_php')
def student_playground_php():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/php_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/playground_cpp')
@app.route('/student_playground_cpp')
def student_playground_cpp():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/cpp_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_activities')
def student_activities():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('activities/php_activities.html',
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_php')
def student_activities_php():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('activities/php_activities.html',
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_javascript')
def student_activities_javascript():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('public/student_activities_javascript.html', 
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_java')
def student_activities_java():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_modules/java/1')

@app.route('/student_activities_html')
def student_activities_html():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_activities_cpp')

@app.route('/student_activities_cpp')
def student_activities_cpp():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('public/student_activities_cpp.html',
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_progress')
def student_progress():
    if session.get('role') != 'student':
        return redirect('/')

    language_details = {
        'php': ('PHP', 'php', 'logos:php'),
        'javascript': ('JavaScript', 'js', 'logos:javascript'),
        'cpp': ('C++', 'cpp', 'logos:cplusplus'),
        'python': ('Python', 'py', 'logos:python'),
        'java': ('Java', 'java', 'logos:java'),
    }
    progress_by_language = {
        language: {
            'language': language,
            'name': language_details[language][0],
            'category': 'Activities' if language in ACTIVITY_LANGUAGES else 'Assessments',
            'icon_class': language_details[language][1],
            'icon': language_details[language][2],
            'completed': 0,
            'total': 0,
            'percentage': 0,
            'scored_attempts': 0,
            'points_earned': 0,
            'points_possible': 0,
            'score_percentage': 0,
        }
        for language in (*ACTIVITY_LANGUAGES, *ASSESSMENT_LANGUAGES)
    }

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.language,
                   COUNT(DISTINCT a.id) AS total,
                   COUNT(DISTINCT CASE
                       WHEN (
                           a.language IN ('php', 'javascript', 'cpp')
                           AND (aa.status IN ('submitted', 'completed', 'pending_review')
                                OR aa.teacher_score IS NOT NULL)
                       ) OR (
                           a.language IN ('python', 'java')
                           AND aa.status = 'submitted'
                       ) THEN a.id
                   END) AS completed,
                   COUNT(DISTINCT CASE
                       WHEN (
                           a.language IN ('php', 'javascript', 'cpp')
                           AND (aa.status IN ('submitted', 'completed', 'pending_review')
                                OR aa.teacher_score IS NOT NULL)
                       ) OR (
                           a.language IN ('python', 'java')
                           AND aa.status = 'submitted'
                       ) THEN aa.id
                   END) AS scored_attempts,
                   COALESCE(SUM(CASE
                       WHEN (
                           a.language IN ('php', 'javascript', 'cpp')
                           AND (aa.status IN ('submitted', 'completed', 'pending_review')
                                OR aa.teacher_score IS NOT NULL)
                       ) OR (
                           a.language IN ('python', 'java')
                           AND aa.status = 'submitted'
                       ) THEN CASE
                           WHEN aa.teacher_score IS NOT NULL THEN
                               CASE WHEN aa.teacher_score > 10 THEN ROUND(aa.teacher_score / 10) ELSE aa.teacher_score END
                           WHEN aa.auto_score IS NOT NULL AND (aa.auto_score > 0 OR aa.score = 0) THEN
                               CASE WHEN aa.auto_score > 10 THEN ROUND(aa.auto_score / 10) ELSE aa.auto_score END
                           ELSE COALESCE(
                               CASE WHEN aa.score > 10 THEN ROUND(aa.score / 10) ELSE aa.score END,
                               0
                           )
                       END
                       ELSE 0
                   END), 0) AS points_earned
            FROM learning_items a
            LEFT JOIN assessment_attempts aa
                ON aa.assessment_id = a.id AND aa.language = a.language AND aa.student_id = %s
            WHERE (a.language IN ('php', 'javascript', 'cpp')
                   AND a.assessment_number BETWEEN 1 AND 5)
               OR a.language IN ('python', 'java')
            GROUP BY a.language
        """, (session.get('user_id'),))

        for row in cursor.fetchall():
            language = (row.get('language') or '').lower()
            if language not in progress_by_language:
                continue
            language_progress = progress_by_language[language]
            language_progress['total'] = int(row.get('total') or 0)
            language_progress['completed'] = int(row.get('completed') or 0)
            language_progress['scored_attempts'] = int(row.get('scored_attempts') or 0)
            language_progress['points_earned'] = int(row.get('points_earned') or 0)
            language_progress['points_possible'] = language_progress['total'] * 10
            if language_progress['total']:
                language_progress['percentage'] = round(
                    language_progress['completed'] / language_progress['total'] * 100
                )
            if language_progress['points_possible']:
                language_progress['score_percentage'] = round(
                    language_progress['points_earned'] / language_progress['points_possible'] * 100
                )
            else:
                language_progress['score_percentage'] = 0
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    activities = [progress_by_language[language] for language in ACTIVITY_LANGUAGES]
    assessments = [progress_by_language[language] for language in ASSESSMENT_LANGUAGES]

    def summarize(items):
        completed = sum(item['completed'] for item in items)
        total = sum(item['total'] for item in items)
        return {
            'completed': completed,
            'total': total,
            'percentage': round(completed / total * 100) if total else 0,
        }

    activity_summary = summarize(activities)
    assessment_summary = summarize(assessments)
    overall_summary = summarize(activities + assessments)
    total_points = sum(item['points_earned'] for item in progress_by_language.values())
    total_points_possible = sum(item['points_possible'] for item in progress_by_language.values())
    scored_attempts = sum(item['scored_attempts'] for item in progress_by_language.values())
    average_score = round(total_points / (scored_attempts * 10) * 100) if scored_attempts else 0

    return render_template(
        'student/student_progress.html',
        username=session.get('username'),
        full_name=session.get('full_name'),
        grade_level=session.get('grade_level'),
        progress={
            'overall': overall_summary,
            'activities': activity_summary,
            'assessments': assessment_summary,
            'by_language': activities + assessments,
        },
        activities_done=activity_summary['completed'],
        activities_total=activity_summary['total'],
        activities_pct=activity_summary['percentage'],
        assessments_done=assessment_summary['completed'],
        assessments_total=assessment_summary['total'],
        assessments_pct=assessment_summary['percentage'],
        overall_pct=overall_summary['percentage'],
        average_score=average_score,
        score_summary={
            'points_earned': total_points,
            'points_possible': total_points_possible,
            'percentage': round(total_points / total_points_possible * 100) if total_points_possible else 0,
            'by_language': progress_by_language,
        },
        **{
            f'{language}_{suffix}': progress_by_language[language][key]
            for language in progress_by_language
            for suffix, key in (
                ('done', 'completed'),
                ('total', 'total'),
                ('pct', 'percentage'),
                ('score_done', 'points_earned'),
                ('score_total', 'points_possible'),
                ('score_pct', 'score_percentage'),
            )
        },
        js_done=progress_by_language['javascript']['completed'],
        js_total=progress_by_language['javascript']['total'],
        js_pct=progress_by_language['javascript']['percentage'],
    )

@app.route('/student_profile')
def student_profile():
    if session.get('role') != 'student':
        return redirect('/')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            "SELECT * FROM students WHERE id = %s",
            (session.get('user_id'),),
        )
        student = cursor.fetchone()
        student_name = _student_display_name(student or {})
        if student:
            student['display_name'] = student_name
        session['full_name'] = student_name
        
        return render_template('student/student_profile.html', 
                                  student=student,
                                  lrn=session.get('lrn'),
                                  username=session.get('username'),
                                  full_name=student_name)
    finally:
        cursor.close()
        conn.close()

@app.route('/student_settings')
def student_settings():
    if session.get('role') != 'student':
        return redirect('/')
    student = _get_student_identity()
    student_username = student.get('username') or session.get('username')
    student_name = _student_display_name({
        **student,
        'username': student_username,
        'lrn': student.get('lrn') or session.get('lrn'),
    })
    session['full_name'] = student_name
    return render_template('student/student_settings.html', 
                          username=student_username,
                          full_name=student_name,
                          grade_level=student.get('grade_level') or session.get('grade_level'))

@app.route('/student_help')
def student_help():
    if session.get('role') != 'student':
        return redirect('/')
    student = _get_student_identity()
    student_username = student.get('username') or session.get('username')
    student_name = _student_display_name({
        **student,
        'username': student_username,
        'lrn': student.get('lrn') or session.get('lrn'),
    })
    session['full_name'] = student_name
    return render_template('student/HELP_FAQ.html', 
                          username=student_username,
                          full_name=student_name,
                          grade_level=student.get('grade_level') or session.get('grade_level'))

@app.route('/assessments')
def assessments_overview():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('modules_activities/ass&act_library.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          library_mode='assessment')

@app.route('/assessment')
def assessment_overview_alias():
    return redirect('/assessments')

@app.route('/module_assessments')
def module_assessments():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('modules_activities/ass&act_library.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          library_mode='assessment')

@app.route('/assessments_python')
def assessments_python():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('assessments/python_assessments.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          score_language='python',
                          score_language_name='Python')

@app.route('/assessments_java')
def assessments_java():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('assessments/java_assessments.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          score_language='java',
                          score_language_name='Java')

@app.route('/get_assessment_statuses')
def get_assessment_statuses():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    language = request.args.get('language', 'java')
    if language not in ('python', 'java', 'cpp', 'javascript', 'php'):
        return jsonify({'success': False, 'message': 'Invalid language'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.assessment_number, aa.status, aa.score,
                   aa.auto_score, aa.teacher_score
            FROM learning_items a
            LEFT JOIN assessment_attempts aa
                ON aa.assessment_id = a.id AND aa.language = a.language AND aa.student_id = %s
            WHERE a.language = %s
            ORDER BY a.assessment_number
        """, (session['user_id'], language))
        rows = cursor.fetchall()
        statuses = []
        passed_by_number = {}
        for row in rows:
            attempt_status = row['status']
            score = None
            if attempt_status == 'submitted':
                score = _normalize_score(
                    row['teacher_score'], row['auto_score'], row['score']
                )
                status = 'passed' if score >= 75 else 'failed'
            elif attempt_status == 'in_progress':
                status = 'in_progress'
            else:
                status = 'not_started'
            assessment_number = row['assessment_number']
            locked = assessment_number > 1 and not passed_by_number.get(assessment_number - 1, False)
            statuses.append({
                'assessment_number': assessment_number,
                'status': status,
                'score': score,
                'locked': locked,
            })
            passed_by_number[assessment_number] = status == 'passed'
        submitted_scores = [
            item['score'] for item in statuses
            if item['status'] in ('passed', 'failed') and item['score'] is not None
        ]
        passed_count = sum(1 for item in statuses if item['status'] == 'passed')
        failed_count = sum(1 for item in statuses if item['status'] == 'failed')
        return jsonify({
            'success': True,
            'statuses': statuses,
            'total': len(statuses),
            'completed': passed_count + failed_count,
            'passed': passed_count,
            'failed': failed_count,
            'in_progress': sum(1 for item in statuses if item['status'] == 'in_progress'),
            'average_score': round(sum(submitted_scores) / len(submitted_scores)) if submitted_scores else 0
        })
    except Exception as e:
        print(f"Get assessment statuses error: {e}")
        return jsonify({'success': False, 'message': 'Failed to load assessment statuses'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _render_assessment_quiz(language):
    if session.get('role') != 'student':
        return redirect('/')
    assessment_number = request.args.get('id', type=int)
    if assessment_number is None or not 1 <= assessment_number <= 5:
        return redirect('/assessments_python' if language == 'python' else '/assessments_java')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if not _previous_assessment_passed(
            cursor, session['user_id'], language, assessment_number
        ):
            return render_template(
                'assessments/assessment_locked.html',
                language_name=language.title(),
                previous_number=assessment_number - 1,
                overview_url='/assessments_python' if language == 'python' else '/assessments_java',
            ), 403
        cursor.execute("""
            SELECT title, description FROM learning_items
            WHERE language = %s AND assessment_number = %s
            LIMIT 1
        """, (language, assessment_number))
        assessment = cursor.fetchone()
        if not assessment:
            return redirect('/assessments_python' if language == 'python' else '/assessments_java')
        quiz_token, questions = _issue_learning_quiz(
            language, 'assessment', assessment_number
        )
        return render_template(
            'assessments/quiz.html',
            language=language,
            language_name=language.title(),
            assessment_number=assessment_number,
            assessment_title=assessment['title'],
            assessment_description=assessment['description'],
            quiz_token=quiz_token,
            quiz_questions=questions,
        )
    except Exception as e:
        print(f"Load {language} assessment error: {e}")
        return jsonify({'success': False, 'message': 'Failed to load assessment'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/assessment_python_activity')
def assessment_python_activity():
    return _render_assessment_quiz('python')

@app.route('/assessment_java_activity')
def assessment_java_activity():
    return _render_assessment_quiz('java')

@app.route('/submit_assessment_quiz', methods=['POST'])
def submit_assessment_quiz():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    language = data.get('language')
    assessment_number = data.get('assessment_number')
    if (
        language not in ASSESSMENT_LANGUAGES
        or not isinstance(assessment_number, int)
        or isinstance(assessment_number, bool)
        or not 1 <= assessment_number <= 5
    ):
        return jsonify({'success': False, 'message': 'Invalid assessment quiz'}), 400
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if not _previous_assessment_passed(
            cursor, session['user_id'], language, assessment_number
        ):
            return jsonify({'success': False, 'message': 'Complete the previous assessment first'}), 403
        cursor.execute("""
            SELECT id FROM learning_items
            WHERE language = %s AND assessment_number = %s
            LIMIT 1
        """, (language, assessment_number))
        assessment = cursor.fetchone()
        if not assessment:
            return jsonify({'success': False, 'message': 'Assessment not found'}), 404
        correct = _grade_learning_quiz(
            data.get('quiz_token'), language, 'assessment', assessment_number,
            data.get('answers'),
        )
        if correct is None:
            return jsonify({'success': False, 'message': 'Invalid or expired quiz submission'}), 400

        points = correct
        score = correct * 10
        passed = points >= 8
        submitted_at = datetime.now()

        cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, language, code_blocks, output, score,
                 auto_score, status, submitted_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'submitted', %s, %s)
            ON DUPLICATE KEY UPDATE
                code_blocks = IF(VALUES(score) >= score, VALUES(code_blocks), code_blocks),
                output = IF(VALUES(score) >= score, VALUES(output), output),
                submitted_at = IF(VALUES(score) >= score, VALUES(submitted_at), submitted_at),
                completed_at = IF(VALUES(score) >= 75, COALESCE(completed_at, VALUES(completed_at)), completed_at),
                status = 'submitted',
                score = GREATEST(score, VALUES(score)),
                auto_score = GREATEST(auto_score, VALUES(auto_score))
        """, (
            assessment['id'], session['user_id'], language,
            json.dumps(data['answers'], separators=(',', ':')),
            f'{points}/10', score, points, submitted_at,
            submitted_at if passed else None,
        ))
        conn.commit()
        cursor.execute("""
            SELECT score, auto_score, teacher_score, id
            FROM assessment_attempts
            WHERE assessment_id = %s AND language = %s AND student_id = %s
        """, (assessment['id'], language, session['user_id']))
        saved = cursor.fetchone() or {}
        best_score = _normalize_score(
            saved.get('teacher_score'), saved.get('auto_score'), saved.get('score')
        )
        new_badges = []
        certificate_issued = False
        module_complete = False
        if best_score >= 75:
            try:
                award_result = try_award_after_submission(
                    cursor, session['user_id'], language, assessment_number
                )
                new_badges = award_result['new_badges']
                certificate_issued = award_result['certificate_issued']
                module_complete = award_result['module_complete']
                conn.commit()
            except Exception as award_error:
                print(f"[submit_assessment_quiz] award error: {award_error}")
                conn.rollback()
        try:
            notify_new_assessment_submission(
                session.get('full_name') or session.get('username') or 'Student',
                f'{language.title()} Assessment #{assessment_number}',
                assessment['id'],
            )
            notify_student_assessment_result(
                session['user_id'],
                f'{language.title()} Assessment #{assessment_number}',
                points, 10, 'passed' if passed else 'failed', assessment['id'],
            )
        except Exception as notify_error:
            print(f"[submit_assessment_quiz] notification error: {notify_error}")
        return jsonify({
            'success': True,
            'assessment_number': assessment_number,
            'points': points,
            'best_points': min(10, max(0, round(best_score / 10))),
            'max_points': 10,
            'passed': passed or best_score >= 75,
            'status': 'passed' if passed or best_score >= 75 else 'failed',
            'new_badges': new_badges,
            'certificate_issued': certificate_issued,
            'module_complete': module_complete,
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Submit assessment quiz error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save assessment score'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/notifications')
def notifications_page():
    role = session.get('role')
    templates = {
        'student': 'student/student_notifications.html',
        'teacher': 'teacher/teacher_notifications.html',
        'ict': 'ict-support/ict_notifications.html',
    }
    if role not in templates:
        return redirect('/')
    return render_template(templates[role])

@app.route('/get_notifications')
def get_notifications():
    role = session.get('role')
    if role not in ('student', 'teacher', 'ict'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        notifications = get_notifications_for_user(session.get('user_id'), role)
    except Exception:
        app.logger.exception("Unable to load notifications")
        return jsonify({'success': False, 'message': 'Unable to load notifications'}), 500
    return jsonify({
        'success': True,
        'notifications': notifications,
        'unread_count': sum(1 for item in notifications if not item['is_read']),
    })

@app.route('/get_unread_count')
def get_unread_count():
    role = session.get('role')
    if role not in ('student', 'teacher', 'ict'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        count = get_unread_notification_count(session.get('user_id'), role)
    except Exception:
        app.logger.exception("Unable to load unread notification count")
        return jsonify({'success': False, 'message': 'Unable to load unread notification count'}), 500
    return jsonify({'success': True, 'count': count, 'unread_count': count})

@app.route('/mark_notification_read', methods=['POST'])
def mark_notification_read_route():
    role = session.get('role')
    if role not in ('student', 'teacher', 'ict'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    payload = request.get_json(silent=True)
    notification_id = payload.get('notification_id') if isinstance(payload, dict) else None
    if isinstance(notification_id, bool):
        notification_id = None
    try:
        notification_id = int(notification_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid notification ID'}), 400
    if notification_id < 1:
        return jsonify({'success': False, 'message': 'Invalid notification ID'}), 400
    try:
        updated = mark_notification_read(notification_id, session.get('user_id'), role)
    except Exception:
        app.logger.exception("Unable to mark notification as read")
        return jsonify({'success': False, 'message': 'Unable to update notification'}), 500
    if not updated:
        return jsonify({'success': False, 'message': 'Notification not found or already read'}), 404
    return jsonify({'success': True})

@app.route('/mark_all_notifications_read', methods=['POST'])
@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    role = session.get('role')
    if role not in ('student', 'teacher', 'ict'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    success = mark_all_notifications_read(session.get('user_id'), role)
    return jsonify({
        'success': success,
        **({'message': 'Unable to update notifications'} if not success else {}),
    }), (200 if success else 500)

@app.route('/submit_activity', methods=['POST'])
@app.route('/submit_assessment', methods=['POST'])
def submit_assessment():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    language = str(data.get('language') or '').lower()
    assessment_number = data.get('assessment_number')
    code_blocks = data.get('code_blocks')
    generated_code = str(data.get('generated_code') or '')
    client_output = str(data.get('output') or '').strip()

    if (
        language not in ('python', 'java', 'cpp', 'javascript', 'php')
        or not isinstance(assessment_number, int)
        or isinstance(assessment_number, bool)
        or not isinstance(code_blocks, str)
        or not code_blocks.strip()
    ):
        return jsonify({'success': False, 'message': 'Invalid assessment submission'}), 400
    if request.path == '/submit_activity' and language not in ACTIVITY_LANGUAGES:
        return jsonify({'success': False, 'message': 'Invalid activity submission'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if request.path == '/submit_assessment' and not _previous_assessment_passed(
            cursor, session['user_id'], language, assessment_number
        ):
            return jsonify({'success': False, 'message': 'Complete the previous assessment first'}), 403
        cursor.execute(
            """
            SELECT id, expected_output, points
            FROM learning_items
            WHERE language = %s AND assessment_number = %s
            """,
            (language, assessment_number),
        )
        assessment = cursor.fetchone()
        if not assessment:
            return jsonify({'success': False, 'message': 'Assessment not found'}), 404

        expected_output = normalize_output(assessment['expected_output'] or '')
        server_output = '__PENDING_REVIEW__'
        if language == 'python' and generated_code.strip():
            server_output = normalize_output(run_python(generated_code))
        elif language == 'java' and code_blocks.strip():
            server_output = normalize_output(run_java_blocks(code_blocks))
        elif language == 'php' and code_blocks.strip():
            server_output = normalize_output(run_php_blocks(code_blocks))
        elif language == 'cpp' and code_blocks.strip():
            server_output = normalize_output(run_cpp_blocks(code_blocks))
        elif language == 'javascript' and code_blocks.strip():
            server_output = normalize_output(run_javascript_blocks(code_blocks))

        verified_pass = server_output == expected_output
        server_result_verified = server_output not in {
            '__PENDING_REVIEW__', '__ERROR__', '__TIMEOUT__',
        }
        earned_points = 10 if verified_pass else 0
        score = 100 if verified_pass else 0
        result_status = (
            'completed' if verified_pass else
            'failed' if language in ('python', 'java', 'cpp', 'javascript', 'php') and server_result_verified else
            'pending_review'
        )
        database_status = 'submitted'
        output_to_store = (
            server_output if language in ('python', 'java', 'cpp', 'javascript', 'php') and server_result_verified
            else normalize_output(client_output)
        )
        submitted_at = datetime.now()

        cursor.execute(
            """
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, generated_code, output, score,
                 auto_score, teacher_score, status, submitted_at, completed_at, language)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                code_blocks = IF(VALUES(score) >= score, VALUES(code_blocks), code_blocks),
                generated_code = IF(
                    VALUES(score) >= score OR generated_code IS NULL OR generated_code = '',
                    VALUES(generated_code), generated_code
                ),
                output = IF(VALUES(score) >= score, VALUES(output), output),
                teacher_score = IF(VALUES(score) > score, NULL, teacher_score),
                teacher_feedback = IF(VALUES(score) > score, NULL, teacher_feedback),
                reviewed_by = IF(VALUES(score) > score, NULL, reviewed_by),
                reviewed_at = IF(VALUES(score) > score, NULL, reviewed_at),
                status = 'submitted',
                submitted_at = IF(VALUES(score) >= score, VALUES(submitted_at), submitted_at),
                completed_at = IF(VALUES(score) >= 75, COALESCE(completed_at, VALUES(completed_at)), completed_at),
                score = GREATEST(score, VALUES(score)),
                auto_score = GREATEST(auto_score, VALUES(auto_score))
            """,
            (
                assessment['id'], session['user_id'], code_blocks, generated_code,
                output_to_store, score, earned_points, database_status, submitted_at,
                submitted_at if verified_pass else None, language,
            ),
        )
        conn.commit()

        new_badges = []
        certificate_issued = False
        module_complete = False
        if verified_pass:
            cursor.execute(
                """
                SELECT teacher_score, auto_score, score
                FROM assessment_attempts
                WHERE assessment_id = %s AND language = %s AND student_id = %s
                """,
                (assessment['id'], language, session['user_id']),
            )
            row = cursor.fetchone()
            effective = _normalize_score(
                row.get('teacher_score'), row.get('auto_score'), row.get('score')
            ) if row else 0

            if effective >= 75:
                try:
                    result = try_award_after_submission(
                        cursor, session['user_id'], language, assessment_number
                    )
                    new_badges = result['new_badges']
                    certificate_issued = result['certificate_issued']
                    module_complete = result['module_complete']
                    conn.commit()
                except Exception as award_err:
                    print(f"[submit_assessment] award error: {award_err}")
                    conn.rollback()

        try:
            notify_new_assessment_submission(
                session.get('full_name') or session.get('username') or 'Student',
                f'{language.title()} Assessment #{assessment_number}',
                assessment['id'],
            )
            notify_student_assessment_result(
                session['user_id'],
                f'{language.title()} Assessment #{assessment_number}',
                earned_points,
                10,
                result_status,
                assessment['id'],
            )
        except Exception as notify_err:
            print(f"[submit_assessment] notify error: {notify_err}")

        return jsonify({
            'success': True,
            'score': score,
            'points': earned_points,
            'max_points': 10,
            'status': result_status,
            'activity_number': assessment_number,
            'expected_output': expected_output,
            'new_badges': new_badges,
            'certificate_issued': certificate_issued,
            'module_complete': module_complete,
            'message': (
                'Assessment completed successfully' if verified_pass else
                'Assessment evaluated and did not pass' if result_status == 'failed' else
                'Assessment submitted for review'
            ),
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Submit assessment error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to save assessment score'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

MODULE_ASSESSMENTS = {
    'php-01-variables': {
        'language': 'php', 'number': 1, 'title': 'PHP Variables', 'expected_output': '16',
    },
    'php-02-conditionals': {
        'language': 'php', 'number': 2, 'title': 'PHP Conditionals', 'expected_output': 'Passed',
    },
    'python-01-basics': {
        'language': 'python', 'number': 1, 'title': 'Python Basics', 'expected_output': '16',
    },
    'python-02-loops': {
        'language': 'python', 'number': 2, 'title': 'Python Loops', 'expected_output': '1\n2\n3\n4\n5',
    },
    'java-01-basics': {
        'language': 'java', 'number': 1, 'title': 'Java Basics', 'expected_output': '16',
    },
    'java-02-loops': {
        'language': 'java', 'number': 2, 'title': 'Java Loops', 'expected_output': '1\n2\n3\n4\n5',
    },
    'js-01-variables': {
        'language': 'javascript', 'number': 1, 'title': 'JavaScript Variables & Basics',
        'expected_output': 'I love programming!\nI love programming!\nI love programming!\nI love programming!\nI love programming!',
    },
    'js-02-functions': {
        'language': 'javascript', 'number': 2, 'title': 'JavaScript Functions',
        'expected_output': '42',
    },
    'cpp-01-basics': {
        'language': 'cpp', 'number': 1, 'title': 'C++ Basics & Variables',
        'expected_output': '1\n2\n3\n4\n5',
    },
    'cpp-02-loops': {
        'language': 'cpp', 'number': 2, 'title': 'C++ Loops',
        'expected_output': '1\n2\n3\n4\n5\n6\n7\n8\n9\n10',
    },
    'python-03-functions': {
        'language': 'python', 'number': 3, 'title': 'Python Functions and Conditions',
        'expected_output': '12',
    },
    'java-03-conditionals': {
        'language': 'java', 'number': 3, 'title': 'Java Conditionals and Methods',
        'expected_output': '12',
    },
    'php-03-loops': {
        'language': 'php', 'number': 3, 'title': 'PHP Loops and Repetition',
        'expected_output': '12',
    },
    'js-03-conditionals': {
        'language': 'javascript', 'number': 3, 'title': 'JavaScript Conditions and Decisions',
        'expected_output': '12',
    },
    'cpp-03-conditionals': {
        'language': 'cpp', 'number': 3, 'title': 'C++ Conditions and Decisions',
        'expected_output': '12',
    },
}

@app.route('/submit_module_quiz', methods=['POST'])
def submit_module_quiz():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    module_id = data.get('module_id')
    module = MODULE_ASSESSMENTS.get(module_id)
    if not module or module['number'] != 3:
        return jsonify({'success': False, 'message': 'Invalid module quiz'}), 400

    if not _module_is_unlocked(session['user_id'], module['language'], module['number']):
        return jsonify({'success': False, 'message': 'Complete the previous module first'}), 403

    correct = _grade_learning_quiz(
        data.get('quiz_token'), module['language'], 'module', module_id,
        data.get('answers'),
    )
    if correct is None:
        return jsonify({'success': False, 'message': 'Invalid or expired quiz submission'}), 400

    points = correct
    score = correct * 10
    passed = points >= 8
    submitted_at = datetime.now()
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            INSERT INTO module_assessment_attempts
                (student_id, module_id, language, module_number, module_title,
                 code_blocks, generated_code, output, expected_output, score,
                 points_earned, max_points, attempts, status, submitted_at)
            VALUES (%s, %s, %s, 3, %s, %s, '', %s, '10', %s, %s, 10, 1, %s, %s)
            ON DUPLICATE KEY UPDATE
                attempts = attempts + 1,
                code_blocks = IF(VALUES(score) >= score, VALUES(code_blocks), code_blocks),
                output = IF(VALUES(score) >= score, VALUES(output), output),
                points_earned = GREATEST(points_earned, VALUES(points_earned)),
                submitted_at = IF(VALUES(score) >= score, VALUES(submitted_at), submitted_at),
                status = IF(status = 'passed' OR VALUES(status) = 'passed', 'passed', 'failed'),
                score = GREATEST(score, VALUES(score))
        """, (
            session['user_id'], module_id, module['language'], module['title'],
            json.dumps(data.get('answers'), separators=(',', ':')),
            f'{points}/10', score, points, 'passed' if passed else 'failed',
            submitted_at,
        ))
        conn.commit()
        cursor.execute("""
            SELECT score, points_earned, attempts, status
            FROM module_assessment_attempts
            WHERE student_id = %s AND module_id = %s
        """, (session['user_id'], module_id))
        saved = cursor.fetchone() or {}
        module_passed = saved.get('status') == 'passed'

        if passed:
            try:
                mark_lesson_complete(cursor, session['user_id'], module['language'], 3)
                award_result = try_award_after_lesson(cursor, session['user_id'], module['language'])
                conn.commit()
            except Exception as award_error:
                print(f"[submit_module_quiz] award error: {award_error}")
                conn.rollback()
                award_result = {'new_badges': [], 'certificate_issued': False, 'module_complete': False}
        else:
            award_result = {'new_badges': [], 'certificate_issued': False, 'module_complete': False}

        notify_module_assessment_result(
            session['user_id'], module['title'], points, 10,
            'passed' if passed else 'failed',
        )
        return jsonify({
            'success': True,
            'module_id': module_id,
            'points': points,
            'max_points': 10,
            'score': score,
            'best_score': int(saved.get('score') or score),
            'best_points': int(saved.get('points_earned') or points),
            'attempts': int(saved.get('attempts') or 1),
            'passed': module_passed,
            'module_passed': module_passed,
            'new_badges': award_result['new_badges'],
            'certificate_issued': award_result['certificate_issued'],
            'module_complete': award_result['module_complete'],
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Submit module quiz error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save module quiz score'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_module_assessment_score')
def get_module_assessment_score():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    module_id = request.args.get('module_id', '')
    if module_id not in MODULE_ASSESSMENTS:
        return jsonify({'success': False, 'message': 'Invalid module'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT score, points_earned, max_points, attempts, status, submitted_at
            FROM module_assessment_attempts
            WHERE student_id = %s AND module_id = %s
            LIMIT 1
        """, (session['user_id'], module_id))
        attempt = cursor.fetchone()
        return jsonify({'success': True, 'module_id': module_id, 'attempt': attempt})
    except Exception as e:
        print(f"Get module assessment score error: {e}")
        return jsonify({'success': False, 'message': 'Failed to load module score'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/submit_module_assessment', methods=['POST'])
def submit_module_assessment():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    module_id = data.get('module_id')
    module = MODULE_ASSESSMENTS.get(module_id)
    language = data.get('language')
    code_blocks = data.get('code_blocks')
    if not module or language != module['language'] or not isinstance(code_blocks, str) or not code_blocks.strip():
        return jsonify({'success': False, 'message': 'Invalid module assessment submission'}), 400
    if not _module_is_unlocked(session['user_id'], language, module['number']):
        return jsonify({'success': False, 'message': 'Complete the previous module first'}), 403

    client_output = normalize_output(str(data.get('output') or '').replace('\r\n', '\n'))
    generated_code = str(data.get('generated_code') or '').strip()
    expected_output = normalize_output(module['expected_output'])
    output = client_output
    if language == 'python':
        output = normalize_output(run_python(generated_code)) if generated_code else '__ERROR__'
    elif language == 'php':
        output = normalize_output(run_php_blocks(code_blocks))
    score = score_module_output(
        output, expected_output, case_insensitive=(language == 'javascript')
    )
    passed = score >= PASS_THRESHOLD
    points_earned = round(10 * score / 100)
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # The row keeps the BEST score; a later failed retry never overwrites a pass.
        # (MySQL evaluates assignments left to right, so `score` is updated last.)
        cursor.execute("""
            INSERT INTO module_assessment_attempts
                (student_id, module_id, language, module_number, module_title,
                 code_blocks, generated_code, output, expected_output, score,
                 points_earned, max_points, attempts, status, submitted_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            ON DUPLICATE KEY UPDATE
                language = VALUES(language),
                module_number = VALUES(module_number),
                module_title = VALUES(module_title),
                expected_output = VALUES(expected_output),
                max_points = VALUES(max_points),
                attempts = attempts + 1,
                code_blocks = IF(VALUES(score) >= score, VALUES(code_blocks), code_blocks),
                generated_code = IF(VALUES(score) >= score, VALUES(generated_code), generated_code),
                output = IF(VALUES(score) >= score, VALUES(output), output),
                points_earned = IF(VALUES(score) >= score, VALUES(points_earned), points_earned),
                submitted_at = IF(VALUES(score) >= score, VALUES(submitted_at), submitted_at),
                status = IF(status = 'passed' OR VALUES(status) = 'passed', 'passed', 'failed'),
                score = GREATEST(score, VALUES(score))
        """, (
            session['user_id'], module_id, language, module['number'], module['title'],
            code_blocks, generated_code, output, expected_output,
            score, points_earned, 10, 'passed' if passed else 'failed', datetime.now(),
        ))
        conn.commit()
        cursor.execute(
            "SELECT score, attempts, status FROM module_assessment_attempts "
            "WHERE student_id = %s AND module_id = %s",
            (session['user_id'], module_id),
        )
        saved = cursor.fetchone() or {}
        module_passed = (saved.get('status') == 'passed') or passed
        # Module-final attempts are separate from the five curriculum items in assessment_attempts.
        lesson_completion_recorded = False
        new_badges = []
        certificate_issued = False
        module_complete = False
        if passed:
            try:
                mark_lesson_complete(
                    cursor, session['user_id'], language, module['number']
                )
                award_result = try_award_after_lesson(
                    cursor, session['user_id'], language
                )
                new_badges = award_result['new_badges']
                certificate_issued = award_result['certificate_issued']
                module_complete = award_result['module_complete']
                conn.commit()
                lesson_completion_recorded = True
            except Exception as award_err:
                print(f"[submit_module_assessment] award error: {award_err}")
                conn.rollback()
        notify_module_assessment_result(
            session['user_id'], module['title'], points_earned, 10,
            'passed' if passed else 'failed',
        )
        return jsonify({
            'success': True,
            'module_id': module_id,
            'score': score,
            'best_score': int(saved.get('score') or score),
            'attempts': int(saved.get('attempts') or 1),
            'pass_mark': PASS_THRESHOLD,
            'points': points_earned,
            'max_points': 10,
            'passed': passed,
            'module_passed': module_passed,
            'retry_required': not module_passed,
            'status': 'passed' if passed else 'failed',
            'lesson_completion_recorded': lesson_completion_recorded,
            'new_badges': new_badges,
            'certificate_issued': certificate_issued,
            'module_complete': module_complete,
            'expected_output': expected_output,
            'message': (
                'Module assessment passed' if passed else
                f'Score {score}/100 is below the pass mark of {PASS_THRESHOLD}. Please retry.'
            ),
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Submit module assessment error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save module assessment'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/save_assessment_blocks', methods=['POST'])
def save_assessment_blocks():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    language = data.get('language')
    assessment_number = data.get('assessment_number')
    code_blocks = data.get('code_blocks')

    if language not in ('python', 'java', 'cpp', 'javascript', 'php') or not isinstance(assessment_number, int) or not code_blocks:
        return jsonify({'success': False, 'message': 'Invalid workspace data'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if not _previous_assessment_passed(
            cursor, session['user_id'], language, assessment_number
        ):
            return jsonify({'success': False, 'message': 'Complete the previous assessment first'}), 403
        cursor.execute("""
            SELECT id FROM learning_items
            WHERE language = %s AND assessment_number = %s
        """, (language, assessment_number))
        assessment = cursor.fetchone()
        if not assessment:
            return jsonify({'success': False, 'message': 'Assessment not found'}), 404

        cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, status, language)
            VALUES (%s, %s, %s, 'in_progress', %s)
            ON DUPLICATE KEY UPDATE
                code_blocks = VALUES(code_blocks)
        """, (assessment['id'], session['user_id'], code_blocks, language))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Save assessment blocks error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save workspace'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/assessments/activity')
def assessment_activity():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/assessments_python')

# ===== TEACHER ROUTES =====
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_home_dashboard.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/get_teacher_dashboard_data')
def get_teacher_dashboard_data():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total_students FROM students")
        total_students = cursor.fetchone()['total_students']
        cursor.execute("""
            SELECT COUNT(*) AS total_submissions, IFNULL(ROUND(AVG(score), 0), 0) AS average_score
            FROM assessment_attempts
            WHERE status = 'submitted'
        """)
        stats = cursor.fetchone()
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT {student_name} AS student_name, s.lrn, d.title, d.language,
                   a.score, DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS submitted_at
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted'
            ORDER BY a.submitted_at DESC
            LIMIT 5
        """)
        recent = cursor.fetchall()
        return jsonify({
            'success': True,
            'total_students': total_students,
            'average_score': stats['average_score'] or 0,
            'total_activities': stats['total_submissions'] or 0,
            'pending_submissions': 0,
            'recent_submissions': recent
        })
    except Exception as e:
        print(f"Get teacher dashboard data error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve dashboard data'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher_students')
def teacher_students():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_students_list.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_leaderboard')
def teacher_leaderboard():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_leaderboard.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_score_results')
def teacher_score_results():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_score_results.html', 
                          username=session.get('username'))

@app.route('/teacher_scores')
def teacher_scores():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/teacher_score_results')

@app.route('/teacher_passed_assessments')
def teacher_passed_assessments():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/assessments_result')

@app.route('/assessments_result')
def assessments_result():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/assessments_result.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/assessment_results')
@app.route('/teacher_assessments')
def assessment_results_alias():
    return redirect('/assessments_result')

@app.route('/teacher_reports')
def teacher_reports():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/teacher_reports_analytics')

# ===== NEW ROUTE: Combined Reports & Analytics =====
@app.route('/teacher_reports_analytics')
def teacher_reports_analytics():
    """Combined Reports and Analytics page"""
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('analytics/teacher_reports_analytics.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_feedback_analytics')
def teacher_feedback_analytics():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_feedback_analytics.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_profile')
def teacher_profile():
    if session.get('role') != 'teacher':
        return redirect('/')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, username, full_name, email,
                   DATE_FORMAT(created_at, '%M %d, %Y') as created_at
            FROM teachers 
            WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total, IFNULL(AVG(score), 0) as avg_score
            FROM assessment_attempts
            WHERE status = 'submitted'
        """)
        stats = cursor.fetchone()
        total_activities = stats['total'] if stats['total'] else 0
        average_score = round(stats['avg_score']) if stats['avg_score'] else 0
        
        return render_template('teacher/teacher_profile.html', 
                              teacher=teacher,
                              full_name=teacher['full_name'] if teacher else '',
                              email=teacher['email'] if teacher else '',
                              phone=teacher.get('phone', '') if teacher else '',
                              employee_id=teacher.get('employee_id', '') if teacher else '',
                              department=teacher.get('department', '') if teacher else '',
                              total_students=total_students,
                              total_activities=total_activities,
                              average_score=average_score,
                              username=session.get('username'))
    finally:
        cursor.close()
        conn.close()

@app.route('/teacher_settings')
def teacher_settings():
    if session.get('role') != 'teacher':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT username, full_name, email
            FROM teachers
            WHERE id = %s
        """, (session.get('user_id'),))
        settings = cursor.fetchone() or {}
        return render_template('teacher/teacher_settings.html',
                              settings=settings,
                              username=session.get('username'),
                              full_name=settings.get('full_name', ''),
                              email=settings.get('email', ''))
    finally:
        cursor.close()
        conn.close()

@app.route('/teacher_tickets')
def teacher_tickets():
    if session.get('role') not in ['teacher', 'student']:
        return redirect('/')
    return render_template('ict-support/tickets.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/student_tickets')
def student_tickets():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/tickets.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

# ==================== ICT SUPPORT ROUTES ====================

@app.route('/ict_support_dashboard')
def ict_support_dashboard():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/ict-dasboard.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          role=session.get('role'))

@app.route('/ict_support_audit_logs')
def ict_support_audit_logs():
    if session.get('role') != 'ict':
        return redirect('/')
    return render_template('ict-support/audit.logs.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/get_audit_logs')
def get_audit_logs():
    if session.get('role') != 'ict':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    conn = None
    cursor = None
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = min(max(request.args.get('per_page', 25, type=int), 1), 100)
        filters = []
        params = []

        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        action = request.args.get('action', '').strip()
        role = request.args.get('role', '').strip()
        search = request.args.get('search', '').strip()

        if date_from:
            filters.append('created_at >= %s')
            params.append(date_from)
        if date_to:
            filters.append('created_at < DATE_ADD(%s, INTERVAL 1 DAY)')
            params.append(date_to)
        if action:
            filters.append('action = %s')
            params.append(action)
        if role:
            filters.append('actor_role = %s')
            params.append(role)
        if search:
            filters.append('(actor_display_name LIKE %s OR actor_username LIKE %s OR action LIKE %s OR entity_type LIKE %s)')
            search_value = f'%{search}%'
            params.extend([search_value] * 4)

        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ''
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        log_audit(
            cursor,
            'view_audit_logs',
            entity_type='audit_logs',
            details={'page': page, 'per_page': per_page},
            commit=False,
        )
        conn.commit()

        cursor.execute(f'SELECT COUNT(*) AS total FROM audit_logs {where_sql}', params)
        total = cursor.fetchone()['total'] or 0
        offset = (page - 1) * per_page

        cursor.execute(f"""
            SELECT id, actor_role, actor_id, actor_display_name, actor_username,
                   actor_lrn, actor_grade_level, action, entity_type, entity_id,
                   details, ip_address, user_agent, created_at
            FROM audit_logs
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        logs = cursor.fetchall()

        cursor.execute('SELECT DISTINCT action FROM audit_logs ORDER BY action')
        actions = [row['action'] for row in cursor.fetchall()]

        cursor.execute('SELECT COUNT(*) AS total FROM audit_logs')
        total_all = cursor.fetchone()['total'] or 0
        cursor.execute('SELECT COUNT(*) AS total FROM audit_logs WHERE DATE(created_at) = CURDATE()')
        today = cursor.fetchone()['total'] or 0
        cursor.execute('SELECT COUNT(DISTINCT actor_id, actor_role) AS total FROM audit_logs')
        unique_actors = cursor.fetchone()['total'] or 0
        cursor.execute("SELECT COUNT(*) AS total FROM audit_logs WHERE action LIKE '%login%' AND (action LIKE '%fail%' OR action LIKE '%invalid%')")
        failed_logins = cursor.fetchone()['total'] or 0

        return jsonify({
            'success': True,
            'logs': logs,
            'actions': actions,
            'stats': {
                'total': total_all,
                'today': today,
                'unique_actors': unique_actors,
                'failed_logins': failed_logins,
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': max((total + per_page - 1) // per_page, 1),
            },
        })
    except Exception as e:
        print(f'Get audit logs error: {e}')
        return jsonify({'success': False, 'message': 'Failed to retrieve audit logs'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/ict_support_reports')
def ict_support_reports():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/reports.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_feedback_analytics')
def ict_feedback_analytics():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/ict_feedback_analytics.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_support_settings')
def ict_support_settings():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/settings.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_support_students')
def ict_support_students():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/students.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_support_tickets')
@app.route('/ict_tickets')
@app.route('/ict-support/tickets')
def ict_support_tickets():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/tickets.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

# ==================== PROFILE DATA API ROUTES ====================

@app.route('/student_profile_data')
def student_profile_data():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
                 "SELECT * FROM students WHERE id = %s",
                 (session.get('user_id'),),
        )
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if student:
            return jsonify({
                'success': True,
                'username': student.get('username'),
                'lrn': student.get('lrn'),
                'full_name': _student_display_name(student),
                'grade_level': student.get('grade_level'),
                'email': student.get('email'),
                'created_at': (
                    student['created_at'].strftime('%B %d, %Y')
                    if student.get('created_at') else ''
                ),
            })
        return jsonify({'success': False, 'message': 'Student not found'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher_profile_data')
def teacher_profile_data():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT username, full_name, email,
                   DATE_FORMAT(created_at, '%M %d, %Y') as created_at
            FROM teachers WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        total_students = cursor.fetchone()['total_students']
        
        cursor.execute("""
            SELECT COUNT(*) as total_activities, IFNULL(ROUND(AVG(score), 0), 0) as avg_score
            FROM assessment_attempts
            WHERE status = 'submitted'
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'username': teacher['username'] if teacher else '',
            'full_name': teacher['full_name'] if teacher else '',
            'email': teacher['email'] if teacher else 'admin@blocklearn.edu.ph',
            'created_at': teacher['created_at'] if teacher else '',
            'total_students': total_students,
            'total_activities': stats['total_activities'] or 0,
            'average_score': stats['avg_score'] or 0
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_ict_dashboard_data')
def get_ict_dashboard_data():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total_students FROM students")
        total_students = cursor.fetchone()['total_students'] or 0

        cursor.execute("""
            SELECT COUNT(*) AS registered_today
            FROM students
            WHERE DATE(created_at) = CURDATE()
        """)
        registered_today = cursor.fetchone()['registered_today'] or 0

        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT s.id, s.username, {student_name} AS full_name, s.lrn, s.created_at
            FROM students s
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT 5
        """)
        students = cursor.fetchall()

        total_tickets = None
        pending_tickets = None
        try:
            cursor.execute("SELECT COUNT(*) AS total_tickets FROM ict_tickets")
            total_tickets = cursor.fetchone()['total_tickets'] or 0
            cursor.execute("""
                SELECT COUNT(*) AS pending_tickets
                FROM ict_tickets
                WHERE status IN ('pending', 'in_progress')
            """)
            pending_tickets = cursor.fetchone()['pending_tickets'] or 0
        except mysql.connector.Error:
            app.logger.exception("Unable to retrieve ICT ticket counts")

        return jsonify({
            'success': True,
            'total_students': total_students,
            'registered_today': registered_today,
            'total_tickets': total_tickets,
            'pending_tickets': pending_tickets,
            'students': students
        })
    except Exception:
        app.logger.exception("Error getting ICT dashboard data")
        return jsonify({'success': False, 'message': 'Failed to retrieve dashboard data'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== AUTHENTICATION ROUTES ====================

RESET_EMAILS_PER_HOUR = 3
RESET_GENERIC_MESSAGE = (
    "If an account with that LRN or username exists and has a valid email address, "
    f"a password reset link has been sent. It works for {RESET_LINK_MINUTES} minutes. "
    "No email? Ask your teacher or ICT support to reset it for you."
)


@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier', '')).strip()
    if not identifier:
        return jsonify({'success': False, 'message': 'LRN or username is required'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, full_name, email
            FROM students
            WHERE lrn = %s OR LOWER(username) = LOWER(%s)
            LIMIT 1
        """, (identifier, identifier))
        student = cursor.fetchone()

        # The same answer is returned whether or not the account exists, so this
        # form can't be used to find out which LRNs are registered.
        if student:
            rate_key = f"reset:{student['id']}"
            if recent_count(cursor, rate_key, 60) < RESET_EMAILS_PER_HOUR:
                record_event(cursor, rate_key, _client_ip())
                token = generate_token()
                cursor.execute("""
                    UPDATE students
                    SET reset_token = %s, reset_token_expires = %s
                    WHERE id = %s
                """, (hash_token(token), datetime.now() + timedelta(minutes=RESET_LINK_MINUTES), student['id']))
                conn.commit()

                reset_url = f"{base_url(request.host_url)}/reset-password?token={token}"
                if email_configured() and is_real_email(student.get('email')):
                    send_password_reset_email(
                        student['email'], student.get('full_name') or student['username'], reset_url
                    )
                else:
                    # Developer aid only: shown in the server console, never sent to the browser.
                    print(f"[DEV] Email not configured or no real email on file. Reset link for {student['username']}: {reset_url}")
            else:
                conn.commit()
        return jsonify({'success': True, 'message': RESET_GENERIC_MESSAGE})
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Forgot password error: {e}")
        return jsonify({'success': False, 'message': 'Unable to process the request. Please try again.'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json(silent=True) or {}
    token = str(data.get('token', '')).strip()
    password = str(data.get('password', ''))
    confirm_password = str(data.get('confirm_password', ''))

    if not token or password != confirm_password:
        return jsonify({'success': False, 'message': 'Provide a valid token and matching passwords'}), 400
    strong, strength_msg = validate_password_strength(password)
    if not strong:
        return jsonify({'success': False, 'message': strength_msg}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, lrn, username
            FROM students
            WHERE reset_token = %s AND reset_token_expires > NOW()
            LIMIT 1
        """, (hash_token(token),))
        student = cursor.fetchone()
        if not student:
            return jsonify({'success': False, 'message': 'This reset link is invalid or expired'}), 400

        cursor.execute("""
            UPDATE students
            SET password = %s, reset_token = NULL, reset_token_expires = NULL
            WHERE id = %s
        """, (hash_password(password), student['id']))
        # A reset also lifts any login lockout on that account.
        for ident in {student.get('lrn'), student.get('username')}:
            if ident:
                clear_failed_attempts(cursor, attempt_key('student', ident))
        conn.commit()
        return jsonify({'success': True, 'message': 'Password reset successfully. You can now log in.'})
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': 'Unable to reset password'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/change_password', methods=['POST'])
def change_password():
    """Change the password for the currently signed-in ICT support user."""
    if session.get('role') != 'ict':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Current and new passwords are required'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT password FROM ict_support WHERE id = %s AND status = 'active'",
            (session.get('user_id'),),
        )
        user = cursor.fetchone()
        if not user or not verify_password(user['password'], current_password)[0]:
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        strong, strength_msg = validate_password_strength(new_password)
        if not strong:
            return jsonify({'success': False, 'message': strength_msg}), 400

        cursor.execute(
            "UPDATE ict_support SET password = %s WHERE id = %s AND status = 'active'",
            (hash_password(new_password), session.get('user_id')),
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Password updated successfully!'})
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"ICT password update error: {exc}")
        return jsonify({'success': False, 'message': 'Unable to update password'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _client_ip():
    return request.remote_addr or ''


def _complete_login(cursor, table, user, plain_password):
    """Upgrade a legacy hash to a salted one after a successful login."""
    _, needs_upgrade = verify_password(user['password'], plain_password)
    if needs_upgrade:
        cursor.execute(
            f"UPDATE {table} SET password = %s WHERE id = %s",
            (hash_password(plain_password), user['id']),
        )


@app.route('/login', methods=['POST'])
def login_post():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        role = data.get('role')
        password = data.get('password')

        if not password or not role:
            return jsonify({'success': False, 'message': 'Missing required fields'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Which value identifies the account being attacked (for lockout).
            if role == 'student':
                identifier = data.get('lrn')
            elif role == 'ict_support':
                identifier = data.get('username') or data.get('employee_id')
            else:
                identifier = data.get('username')
            key = attempt_key(role, identifier)

            locked_for = lockout_seconds_remaining(cursor, key)
            if locked_for:
                return jsonify({
                    'success': False,
                    'locked': True,
                    'retry_after': locked_for,
                    'message': lockout_message(locked_for),
                }), 429

            def fail(message):
                remaining = record_failed_attempt(cursor, key, _client_ip())
                conn.commit()
                if remaining == 0:
                    wait = lockout_seconds_remaining(cursor, key)
                    return jsonify({
                        'success': False,
                        'locked': True,
                        'retry_after': wait,
                        'message': lockout_message(wait),
                    }), 429
                if remaining <= 2:
                    message += f' {remaining} attempt{"s" if remaining != 1 else ""} left before your account is temporarily locked.'
                return jsonify({'success': False, 'message': message})

            def start_session():
                session.clear()  # new session on login prevents session fixation

            if role == 'student':
                lrn = data.get('lrn')
                if not lrn:
                    return jsonify({'success': False, 'message': 'LRN is required for students'})

                if not validate_lrn(lrn):
                    return jsonify({'success': False, 'message': 'LRN must be exactly 12 digits'})

                cursor.execute("SELECT * FROM students WHERE lrn = %s OR username = %s", (lrn, lrn))
                user = cursor.fetchone()

                if user and verify_password(user['password'], password)[0]:
                    verified = user.get('email_verified')
                    if verification_enforced() and verified is not None and int(verified) == 0:
                        return jsonify({
                            'success': False,
                            'needs_verification': True,
                            'message': 'Please verify your email first. Check your inbox for the verification link.',
                        })
                    _complete_login(cursor, 'students', user, password)
                    clear_failed_attempts(cursor, key)
                    start_session()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = _student_display_name(user)
                    session['student_name_loaded'] = True
                    session['lrn'] = user['lrn']
                    session['grade_level'] = user['grade_level']
                    session['role'] = 'student'
                    log_audit(cursor, 'login_success', entity_type='student', entity_id=user['id'], commit=False)
                    conn.commit()
                    return jsonify({'success': True, 'role': 'student', 'redirect': '/student_dashboard'})
                return fail('Invalid LRN or password.')

            elif role == 'ict_support':
                username = data.get('username') or data.get('employee_id')
                validation_code = data.get('validation_code')
                if not username:
                    return jsonify({'success': False, 'message': 'ICT support username is required'})
                if not validation_code:
                    return jsonify({'success': False, 'message': 'ICT support validation code is required'})

                cursor.execute("""
                    SELECT * FROM ict_support
                    WHERE LOWER(username) = LOWER(%s) AND status = 'active'
                """, (username,))
                user = cursor.fetchone()

                if user and verify_password(user['password'], password)[0] and verify_staff_code(user.get('staff_code_hash'), validation_code):
                    _complete_login(cursor, 'ict_support', user, password)
                    cursor.execute("UPDATE ict_support SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user['id'],))
                    clear_failed_attempts(cursor, key)
                    start_session()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user['full_name']
                    session['role'] = 'ict'
                    log_audit(cursor, 'login_success', entity_type='ict_support', entity_id=user['id'], commit=False)
                    conn.commit()
                    return jsonify({'success': True, 'role': 'ict_support', 'redirect': '/ict_support_dashboard'})
                return fail('Invalid ICT support username or password.')

            else:  # teacher
                username = data.get('username')
                validation_code = data.get('validation_code')
                if not username:
                    return jsonify({'success': False, 'message': 'Username is required for teachers'})
                if not validation_code:
                    return jsonify({'success': False, 'message': 'Teacher validation code is required'})

                cursor.execute("SELECT * FROM teachers WHERE LOWER(username) = LOWER(%s)", (username,))
                user = cursor.fetchone()

                if user and verify_password(user['password'], password)[0] and verify_staff_code(user.get('staff_code_hash'), validation_code):
                    _complete_login(cursor, 'teachers', user, password)
                    clear_failed_attempts(cursor, key)
                    start_session()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user.get('full_name', user['username'])
                    session['role'] = 'teacher'
                    log_audit(cursor, 'login_success', entity_type='teacher', entity_id=user['id'], commit=False)
                    conn.commit()
                    return jsonify({'success': True, 'role': 'teacher', 'redirect': '/teacher_dashboard'})
                return fail('Invalid username or password.')

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==================== CREATE ACCOUNT ROUTE ====================

@app.route('/create_account', methods=['POST'])
def create_account():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        lrn = data.get('lrn')
        full_name = data.get('full_name', '')
        password = data.get('password')
        grade_level = data.get('grade_level')
        email = data.get('email')

        if not lrn:
            return jsonify({'success': False, 'message': 'LRN is required'})
        if not full_name or not str(full_name).strip():
            return jsonify({'success': False, 'message': 'Full name is required'})
        if not password:
            return jsonify({'success': False, 'message': 'Password is required'})
        if not grade_level:
            return jsonify({'success': False, 'message': 'Grade level is required'})

        if str(grade_level).strip().lower() != 'grade 11':
            return jsonify({'success': False, 'message': 'Registration is open only for Grade 11 students.'})

        if not validate_lrn(lrn):
            return jsonify({'success': False, 'message': 'LRN must be exactly 12 digits'})

        strong, strength_msg = validate_password_strength(password)
        if not strong:
            return jsonify({'success': False, 'message': strength_msg})

        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})

        hashed_password = hash_password(password)
        username = str(lrn)

        if not email:
            email = f"{lrn}@student.blocklearn.edu.ph"

        verify_required = verification_enforced()
        verify_token = generate_token() if verify_required else None

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM students WHERE lrn = %s", (lrn,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'LRN already exists. Please use a different LRN.'})

            cursor.execute("SELECT id FROM students WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Username already exists.'})

            cursor.execute("""
                INSERT INTO students (username, full_name, password, lrn, grade_level, email, created_at,
                                      email_verified, email_verify_token, email_verify_expires)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                username, full_name, hashed_password, lrn, grade_level, email, datetime.now(),
                0 if verify_required else 1,
                hash_token(verify_token) if verify_required else None,
                datetime.now() + timedelta(hours=VERIFY_LINK_HOURS) if verify_required else None,
            ))

            conn.commit()
            print(f"✅ [SUCCESS] Account created for LRN: {lrn} - Name: {full_name}")
            if verify_required:
                verify_url = f"{base_url(request.host_url)}/verify-email?token={verify_token}"
                send_verification_email(email, full_name, verify_url)
                return jsonify({
                    'success': True,
                    'verify_email': True,
                    'message': f'Account created! We sent a verification link to {email}. Open it, then log in.',
                })
            return jsonify({'success': True, 'message': 'Account created successfully! You can now login.'})
            
        except mysql.connector.IntegrityError as err:
            if err.errno == 1062:
                return jsonify({'success': False, 'message': 'LRN or username already exists'})
            else:
                print(f"❌ [ERROR] IntegrityError: {err}")
                return jsonify({'success': False, 'message': f'Database error: {str(err)}'})
        except mysql.connector.Error as err:
            print(f"❌ [ERROR] MySQL Error: {err}")
            if "Unknown column 'email'" in str(err):
                cursor.execute("""
                    INSERT INTO students (username, full_name, password, lrn, grade_level, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (username, full_name, hashed_password, lrn, grade_level, datetime.now()))
                conn.commit()
                return jsonify({'success': True, 'message': 'Account created successfully!'})
            return jsonify({'success': False, 'message': f'Database error: {str(err)}'})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"❌ [ERROR] Create account error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Account creation failed: {str(e)}'})

# ==================== EMAIL VERIFICATION ROUTES ====================

def _simple_page(title, message, ok=True):
    color = '#16a34a' if ok else '#dc2626'
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><body style="font-family:Arial,sans-serif;background:#f3f4f6;display:flex;'
        'align-items:center;justify-content:center;min-height:100vh;margin:0">'
        '<div style="background:#fff;padding:32px;border-radius:14px;max-width:420px;text-align:center;'
        'box-shadow:0 8px 30px rgba(0,0,0,.08)">'
        f'<h2 style="color:{color};margin-top:0">{title}</h2><p>{message}</p>'
        '<a href="/" style="display:inline-block;margin-top:12px;background:#4f46e5;color:#fff;padding:10px 20px;'
        'border-radius:8px;text-decoration:none;font-weight:bold">Go to login</a></div></body>'
    )


@app.route('/verify-email', methods=['GET'])
def verify_email():
    token = str(request.args.get('token', '')).strip()
    if not token:
        return _simple_page('Invalid link', 'This verification link is not valid.', ok=False), 400
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id FROM students
            WHERE email_verify_token = %s AND email_verify_expires > NOW()
            LIMIT 1
        """, (hash_token(token),))
        student = cursor.fetchone()
        if not student:
            return _simple_page(
                'Link expired',
                'This verification link is invalid or has expired. Try logging in to request a new one.',
                ok=False,
            ), 400
        cursor.execute("""
            UPDATE students
            SET email_verified = 1, email_verify_token = NULL, email_verify_expires = NULL
            WHERE id = %s
        """, (student['id'],))
        conn.commit()
        return _simple_page('Email verified', 'Your email is confirmed. You can now log in to BlockLearn.')
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Verify email error: {e}")
        return _simple_page('Something went wrong', 'Please try again later.', ok=False), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier', '')).strip()
    generic = {'success': True, 'message': 'If that account is waiting for verification, a new link has been sent.'}
    if not identifier or not verification_enforced():
        return jsonify(generic)
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, full_name, email, email_verified
            FROM students
            WHERE lrn = %s OR LOWER(username) = LOWER(%s)
            LIMIT 1
        """, (identifier, identifier))
        student = cursor.fetchone()
        if student and student.get('email_verified') is not None and int(student['email_verified']) == 0 \
                and is_real_email(student.get('email')):
            rate_key = f"verify:{student['id']}"
            if recent_count(cursor, rate_key, 60) < RESET_EMAILS_PER_HOUR:
                record_event(cursor, rate_key, _client_ip())
                token = generate_token()
                cursor.execute("""
                    UPDATE students SET email_verify_token = %s, email_verify_expires = %s WHERE id = %s
                """, (hash_token(token), datetime.now() + timedelta(hours=VERIFY_LINK_HOURS), student['id']))
                conn.commit()
                send_verification_email(
                    student['email'], student.get('full_name') or student['username'],
                    f"{base_url(request.host_url)}/verify-email?token={token}",
                )
        return jsonify(generic)
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Resend verification error: {e}")
        return jsonify(generic)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== STUDENT API ROUTES ====================

@app.route('/get_progress')
def get_progress():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        student_id = session.get('user_id')
        if not student_id:
            return jsonify({'success': False, 'message': 'User not authenticated'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT COUNT(DISTINCT aa.assessment_id) AS completed
                FROM assessment_attempts aa
                JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('python', 'java')
            """, (student_id,))
            assessment_result = cursor.fetchone()

            cursor.execute("""
                  SELECT a.language,
                      COUNT(DISTINCT aa.assessment_id) AS completed,
                       COUNT(DISTINCT CASE WHEN aa.score >= 75 THEN aa.assessment_id END) AS passed
                FROM assessment_attempts aa
                JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('php', 'javascript', 'cpp')
                GROUP BY a.language
            """, (student_id,))
            submitted_activity_stats = {
                row['language']: min(row['completed'], 5)
                for row in cursor.fetchall()
            }

            completed_assessments = min(assessment_result['completed'] if assessment_result else 0, 10)
            completed_activities = sum(submitted_activity_stats.values())
            total_completed = completed_assessments + completed_activities
            progress = round(total_completed / 25 * 100)
            return jsonify({
                'success': True,
                'progress': progress,
                'completed': total_completed,
                'completed_assessments': completed_assessments,
                'completed_activities': completed_activities,
                'total': 25,
                'total_assessments': 10,
                'total_activities': 15,
            })
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get progress error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve progress'})

@app.route('/get_score_summary')
def get_score_summary():
    """Return the current student's total scores by language and difficulty."""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    student_id = session.get('user_id')
    if not student_id:
        return jsonify({'success': False, 'message': 'User not authenticated'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        summary = get_student_total_scores(cursor, student_id)
        summary['by_language'] = {
            **summary['activities']['by_language'],
            **summary['assessments']['by_language'],
        }

        return jsonify({'success': True, **summary})
    except Exception as e:
        print(f"Get score summary error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to retrieve scores'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_student_stats')
def get_student_stats():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT a.title AS activity_name, aa.score,
                   DATE_FORMAT(aa.submitted_at, '%Y-%m-%d %H:%i') as completed_at
            FROM assessment_attempts aa
            JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
            WHERE aa.student_id = %s AND aa.status = 'submitted'
            ORDER BY aa.submitted_at DESC
            LIMIT 5
        """, (student_id,))
        recent = cursor.fetchall()
        
        cursor.execute("""
            SELECT IFNULL(AVG(score), 0) as avg_score, COUNT(*) as total
            FROM assessment_attempts
            WHERE student_id = %s AND status = 'submitted'
        """, (student_id,))
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'recent_activities': recent,
            'average_score': round(stats['avg_score']) if stats['avg_score'] else 0,
            'total_activities': stats['total'] or 0
        })
    except Exception as e:
        print(f"Error in get_student_stats: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json or {}
        full_name = data.get('full_name')
        grade_level = data.get('grade_level')
        email = data.get('email')
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        user_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            updates = []
            params = []

            if full_name:
                updates.append('full_name = %s')
                params.append(full_name)
                session['full_name'] = full_name

            if grade_level:
                updates.append('grade_level = %s')
                params.append(grade_level)
                session['grade_level'] = grade_level

            if email:
                updates.append('email = %s')
                params.append(email)

            if current_password and new_password:
                cursor.execute("SELECT password FROM students WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if user and not verify_password(user['password'], current_password)[0]:
                    return jsonify({'success': False, 'message': 'Current password is incorrect'})
                strong, strength_msg = validate_password_strength(new_password)
                if not strong:
                    return jsonify({'success': False, 'message': strength_msg})

                updates.append('password = %s')
                params.append(hash_password(new_password))

            if updates:
                query = f"UPDATE students SET {', '.join(updates)} WHERE id = %s"
                params = tuple(params + [user_id])
                cursor.execute(query, params)
                conn.commit()

            return jsonify({'success': True, 'message': 'Profile updated successfully!'})

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"Update profile error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_activities')
def get_activities():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        saved_activity_rows = get_student_activity_scores(cursor, student_id)

        cursor.execute("""
            SELECT a.language, a.assessment_number, a.title, a.points,
                   a.expected_output, aa.status, aa.score, aa.auto_score,
                   aa.teacher_score, COALESCE(aa.completed_at, aa.submitted_at) AS completed_at
            FROM assessment_attempts aa
            JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
            WHERE aa.student_id = %s
            ORDER BY aa.id
        """, (student_id,))
        assessment_attempts = cursor.fetchall()
        attempts_by_item = {}
        for attempt in assessment_attempts:
            key = (
                (attempt.get('language') or '').lower(),
                int(attempt.get('assessment_number') or 0),
            )
            attempts_by_item[key] = prefer_attempt_for_progress(
                attempts_by_item.get(key), attempt,
            )
        
        all_activities = [
            {'id': 1, 'name': 'Say Hello!', 'language': 'python', 'difficulty': 'easy'},
            {'id': 2, 'name': 'Print Your Name', 'language': 'python', 'difficulty': 'easy'},
            {'id': 3, 'name': 'Simple Math', 'language': 'python', 'difficulty': 'easy'},
            {'id': 4, 'name': 'If-Else Statement', 'language': 'python', 'difficulty': 'medium'},
            {'id': 5, 'name': 'While Loop', 'language': 'python', 'difficulty': 'medium'},
            {'id': 6, 'name': 'Conditions', 'language': 'python', 'difficulty': 'medium'},
            {'id': 7, 'name': 'Console Log', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 8, 'name': 'Alert Message', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 9, 'name': 'Simple Calculation', 'language': 'javascript', 'difficulty': 'medium'},
            {'id': 10, 'name': 'Create Heading', 'language': 'html', 'difficulty': 'easy'},
            {'id': 11, 'name': 'Create Paragraph', 'language': 'html', 'difficulty': 'easy'},
            {'id': 12, 'name': 'Hello, PHP!', 'language': 'php', 'difficulty': 'easy'},
            {'id': 13, 'name': 'Store a Name', 'language': 'php', 'difficulty': 'easy'},
            {'id': 14, 'name': 'Subtract Two Numbers', 'language': 'php', 'difficulty': 'medium'},
            {'id': 15, 'name': 'Greater Than', 'language': 'php', 'difficulty': 'medium'},
            {'id': 16, 'name': 'Repeat a Message Three Times', 'language': 'php', 'difficulty': 'hard'},
            {'id': 17, 'name': 'Hello, JavaScript!', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 18, 'name': 'Store and Display a Score', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 19, 'name': 'Add Numbers', 'language': 'javascript', 'difficulty': 'medium'},
            {'id': 20, 'name': 'Greater Than', 'language': 'javascript', 'difficulty': 'medium'},
            {'id': 21, 'name': 'Repeat a Message Five Times', 'language': 'javascript', 'difficulty': 'hard'},
            {'id': 22, 'name': 'Hello, C++!', 'language': 'cpp', 'difficulty': 'easy'},
            {'id': 23, 'name': 'Store an Age', 'language': 'cpp', 'difficulty': 'easy'},
            {'id': 24, 'name': 'Multiply Two Numbers', 'language': 'cpp', 'difficulty': 'medium'},
            {'id': 25, 'name': 'Less Than', 'language': 'cpp', 'difficulty': 'medium'},
            {'id': 26, 'name': 'Display Numbers 1 to 5', 'language': 'cpp', 'difficulty': 'hard'},
        ]
        
        activities_unlocked = are_activities_unlocked(cursor, student_id)
        saved_activities = {
            (row['language'], row['name']): row
            for row in saved_activity_rows
        }
        activity_languages = {'php', 'javascript', 'cpp'}

        for activity in all_activities:
            activity['completed'] = False
            activity['status'] = 'LOCKED'
            activity['activity_number'] = activity['id']
            activity['max_score'] = 10

            if activity['language'] not in activity_languages:
                continue

            saved = saved_activities.get((activity['language'], activity['name']))
            if saved:
                activity['completed'] = True
                activity['score'] = saved['score']
                attempt = attempts_by_item.get((
                    activity['language'],
                    int(saved.get('activity_number') or 0),
                ))
                passed = is_attempt_passed(attempt)
                activity['passed'] = passed
                activity['status'] = 'COMPLETED' if passed else 'SUBMITTED'
                if saved.get('completed_at'):
                    activity['completed_at'] = saved['completed_at']
            elif activities_unlocked:
                activity['passed'] = False
                activity['status'] = 'AVAILABLE'
            else:
                activity['passed'] = False
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'activities': all_activities,
            'activities_unlocked': activities_unlocked,
        })
        
    except Exception as e:
        print(f"Get activities error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_achievements')
def get_achievements():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM assessment_attempts
            WHERE student_id = %s AND status = 'submitted'
        """, (student_id,))
        completed_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT IFNULL(AVG(score), 0) as avg FROM assessment_attempts
            WHERE student_id = %s AND status = 'submitted'
        """, (student_id,))
        avg_score = cursor.fetchone()['avg']
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM assessment_attempts aa
            JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
            WHERE aa.student_id = %s AND aa.status = 'submitted' AND a.language = 'python'
        """, (student_id,))
        python_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM assessment_attempts aa
            JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
            WHERE aa.student_id = %s AND aa.status = 'submitted' AND a.language = 'javascript'
        """, (student_id,))
        js_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM assessment_attempts aa
            JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
            WHERE aa.student_id = %s AND aa.status = 'submitted' AND a.language = 'html'
        """, (student_id,))
        html_count = cursor.fetchone()['total']
        
        achievements = [
            {'id': 1, 'name': 'First Code', 'icon': 'fa-code', 'description': 'Complete your first activity', 'unlocked': completed_count >= 1},
            {'id': 2, 'name': 'Blockly Beginner', 'icon': 'fa-rocket', 'description': 'Complete 3 activities', 'unlocked': completed_count >= 3},
            {'id': 3, 'name': 'Bronze Coder', 'icon': 'fa-medal', 'description': 'Complete 5 activities', 'unlocked': completed_count >= 5},
            {'id': 4, 'name': 'Silver Coder', 'icon': 'fa-medal', 'description': 'Complete 10 activities', 'unlocked': completed_count >= 10},
            {'id': 5, 'name': 'Gold Coder', 'icon': 'fa-crown', 'description': 'Complete 15 activities', 'unlocked': completed_count >= 15},
            {'id': 6, 'name': 'High Achiever', 'icon': 'fa-star', 'description': 'Average score 80% or higher', 'unlocked': avg_score >= 80},
            {'id': 7, 'name': 'Python Master', 'icon': 'fa-python', 'description': 'Complete all Python activities (6)', 'unlocked': python_count >= 6},
            {'id': 8, 'name': 'JS Ninja', 'icon': 'fa-js', 'description': 'Complete all JavaScript activities (3)', 'unlocked': js_count >= 3},
            {'id': 9, 'name': 'HTML Hero', 'icon': 'fa-html5', 'description': 'Complete all HTML activities (2)', 'unlocked': html_count >= 2},
            {'id': 10, 'name': 'Perfect Score', 'icon': 'fa-trophy', 'description': 'Get 100% on any activity', 'unlocked': False},
        ]
        
        cursor.close()
        conn.close()
        
        unlocked_count = sum(1 for a in achievements if a['unlocked'])
        
        return jsonify({
            'success': True, 
            'achievements': achievements, 
            'total_unlocked': unlocked_count,
            'total_achievements': len(achievements)
        })
        
    except Exception as e:
        print(f"Get achievements error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_dashboard_stats')
def get_dashboard_stats():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT COUNT(DISTINCT DATE(COALESCE(aa.completed_at, aa.submitted_at))) AS days
            FROM assessment_attempts aa
            JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
            WHERE aa.student_id = %s
              AND aa.status = 'submitted'
              AND a.language IN ('php', 'javascript', 'cpp')
              AND COALESCE(aa.completed_at, aa.submitted_at) >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (student_id,))
        streak_result = cursor.fetchone()
        streak = min(streak_result['days'] if streak_result else 0, 7)
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'streak': streak})
        
    except Exception as e:
        print(f"Get dashboard stats error: {e}")
        return jsonify({'success': False, 'streak': 0})

@app.route('/get_activity_progress')
def get_activity_progress():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        student_id = session.get('user_id')
        if not student_id:
            return jsonify({'success': False, 'message': 'User not authenticated'}), 401
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT language, COUNT(*) AS total
                FROM learning_items
                WHERE language IN ('python', 'java', 'php', 'javascript', 'cpp')
                GROUP BY language
            """)
            language_totals = {
                row['language']: row['total']
                for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT a.language,
                       COUNT(DISTINCT aa.assessment_id) AS completed,
                       COUNT(DISTINCT CASE
                           WHEN (
                               CASE
                                   WHEN aa.teacher_score IS NOT NULL THEN aa.teacher_score * 10
                                   WHEN aa.auto_score IS NOT NULL
                                       AND (aa.auto_score > 0 OR COALESCE(aa.score, 0) = 0)
                                       THEN aa.auto_score * 10
                                   ELSE COALESCE(aa.score, 0)
                               END
                           ) >= 75 THEN aa.assessment_id
                       END) AS passed
                FROM assessment_attempts aa
                JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('python', 'java')
                GROUP BY a.language
            """, (student_id,))
            assessment_stats = {
                row['language']: {
                    'completed': min(row['completed'], language_totals.get(row['language'], 0)),
                    'passed': min(row['passed'], language_totals.get(row['language'], 0)),
                }
                for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT a.language,
                       COUNT(DISTINCT aa.assessment_id) AS completed,
                       COUNT(DISTINCT CASE
                           WHEN (
                               CASE
                                   WHEN aa.teacher_score IS NOT NULL THEN aa.teacher_score * 10
                                   WHEN aa.auto_score IS NOT NULL
                                       AND (aa.auto_score > 0 OR COALESCE(aa.score, 0) = 0)
                                       THEN aa.auto_score * 10
                                   ELSE COALESCE(aa.score, 0)
                               END
                           ) >= 75 THEN aa.assessment_id
                       END) AS passed
                FROM assessment_attempts aa
                JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('php', 'javascript', 'cpp')
                GROUP BY a.language
            """, (student_id,))
            activity_rows = cursor.fetchall()
            submitted_activity_stats = {
                row['language']: min(row['completed'], language_totals.get(row['language'], 0))
                for row in activity_rows
            }
            activity_pass_stats = {
                row['language']: min(row['passed'], language_totals.get(row['language'], 0))
                for row in activity_rows
            }

            activity_stats = submitted_activity_stats
            activities_unlocked = are_activities_unlocked(cursor, student_id)

            cursor.execute("""
                SELECT COUNT(*) AS score_count, IFNULL(AVG(score), 0) AS average_score
                FROM assessment_attempts
                WHERE student_id = %s AND status = 'submitted' AND score IS NOT NULL
            """, (student_id,))
            score_stats = cursor.fetchone()

        finally:
            cursor.close()
            conn.close()

        python_count = assessment_stats.get('python', {}).get('completed', 0)
        java_count = assessment_stats.get('java', {}).get('completed', 0)
        php_count = activity_stats.get('php', 0)
        js_count = activity_stats.get('javascript', 0)
        cpp_count = activity_stats.get('cpp', 0)
        completed_assessments = python_count + java_count
        total_assessments_passed = sum(
            stats.get('passed', 0) for stats in assessment_stats.values()
        )
        completed_activities = php_count + js_count + cpp_count
        total_completed = completed_assessments + completed_activities
        python_total = language_totals.get('python', 0)
        java_total = language_totals.get('java', 0)
        php_total = language_totals.get('php', 0)
        javascript_total = language_totals.get('javascript', 0)
        cpp_total = language_totals.get('cpp', 0)
        total_assessments = python_total + java_total
        total_activities = php_total + javascript_total + cpp_total
        total_items = total_assessments + total_activities
        total_assessments_passed = sum(
            stats.get('passed', 0) for stats in assessment_stats.values()
        )
        total_activity_passed = sum(activity_pass_stats.values())

        response = {
            'success': True,
            'python': {
                'completed': python_count,
                'passed': assessment_stats.get('python', {}).get('passed', 0),
                'total': python_total,
            },
            'java': {
                'completed': java_count,
                'passed': assessment_stats.get('java', {}).get('passed', 0),
                'total': java_total,
            },
            'php': {
                'completed': php_count,
                'passed': activity_pass_stats.get('php', 0),
                'total': php_total,
            },
            'javascript': {
                'completed': js_count,
                'passed': activity_pass_stats.get('javascript', 0),
                'total': javascript_total,
            },
            'cpp': {
                'completed': cpp_count,
                'passed': activity_pass_stats.get('cpp', 0),
                'total': cpp_total,
            },
            'completed_assessments': completed_assessments,
            'assessments_passed': total_assessments_passed,
            'assessments_pass_total': total_assessments,
            'completed_activities': completed_activities,
            'activities_passed': total_activity_passed,
            'activities_pass_total': total_activities,
            'average_score': round(float(score_stats['average_score']), 1) if score_stats['score_count'] else None,
            'average_score_count': score_stats['score_count'],
            'total_completed': total_completed,
            'total_assessments': total_assessments,
            'total_activities': total_activities,
            'total_items': total_items,
            'overall_percentage': round(total_completed / total_items * 100) if total_items else 0,
            'activities_unlocked': activities_unlocked,
        }
        print(
            f"[progress] student_id={student_id} assessments="
            f"{completed_assessments}/{total_assessments} activities="
            f"{completed_activities}/{total_activities} "
            f"overall={response['overall_percentage']}%"
        )
        return jsonify(response)
    except Exception as e:
        print(f"Get activity progress error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve progress'}), 500

@app.route('/get_progress_results')
def get_progress_results():
    """Return database-backed assessment and activity status for the current student."""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    student_id = session.get('user_id')
    if not student_id:
        return jsonify({'success': False, 'message': 'User not authenticated'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.language, d.assessment_number AS item_number,
                   d.title AS item_name,
                   CASE WHEN aa.status = 'submitted' THEN 'COMPLETED' ELSE 'NOT COMPLETED' END AS status,
                    CASE WHEN aa.status = 'submitted' THEN
                        COALESCE(ROUND(aa.teacher_score / 10, 1), ROUND(aa.auto_score / 10, 1), ROUND(aa.score / 10, 1), 0)
                        ELSE NULL END AS score,
                   10 AS max_score,
                   COALESCE(aa.completed_at, aa.submitted_at) AS completed_at,
                   'assessment' AS item_type
            FROM learning_items d
            LEFT JOIN assessment_attempts aa
              ON aa.assessment_id = d.id
             AND aa.language = d.language
             AND aa.student_id = %s
            WHERE d.language IN ('python', 'java')
            ORDER BY d.language, d.assessment_number
        """, (student_id,))
        assessments = cursor.fetchall()

        cursor.execute("""
            SELECT d.language, d.assessment_number AS item_number,
                   d.title AS item_name,
                   CASE WHEN aa.status = 'submitted' THEN 'COMPLETED' ELSE 'NOT COMPLETED' END AS status,
                   CASE WHEN aa.status = 'submitted' THEN
                       CASE
                           WHEN aa.teacher_score IS NOT NULL THEN
                               CASE WHEN aa.teacher_score > 10 THEN ROUND(aa.teacher_score / 10, 1) ELSE aa.teacher_score END
                           WHEN aa.auto_score IS NOT NULL THEN
                               CASE WHEN aa.auto_score > 10 THEN ROUND(aa.auto_score / 10, 1) ELSE aa.auto_score END
                           ELSE ROUND(aa.score / 10, 1)
                       END
                       ELSE NULL END AS score,
                   10 AS max_score,
                   COALESCE(aa.completed_at, aa.submitted_at) AS completed_at,
                   'activity' AS item_type
            FROM activities d
            LEFT JOIN assessment_attempts aa
              ON aa.assessment_id = d.id
             AND aa.language = d.language
             AND aa.student_id = %s
            WHERE d.language IN ('javascript', 'cpp', 'php')
            ORDER BY d.language, d.assessment_number
        """, (student_id,))
        activities = cursor.fetchall()
        results = assessments + activities
        print(f"[progress-results] student_id={student_id} rows={len(results)}")
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        print(f"Get progress results error for student_id={student_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve progress results'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== TICKET API ROUTES ====================

from backend.tickets import (
    create_ticket, get_student_tickets, get_all_tickets,
    get_ticket_by_id, update_ticket_status, get_ticket_counts
)

@app.route('/submit_ticket', methods=['POST'])
def submit_ticket():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        subject = data.get('subject')
        message = data.get('message')
        priority = data.get('priority', 'medium')
        category = data.get('category', 'other')
        
        if not subject or not message:
            return jsonify({'success': False, 'message': 'Subject and message are required'})
        
        student_id = session.get('user_id')
        student_name = session.get('full_name') or 'Student'
        
        result = create_ticket(student_id, student_name, subject, message, priority, category)
        if result.get('success'):
            notify_new_support_ticket(result['ticket_number'], subject, result['ticket_id'])
            notify_student_ticket_received(
                student_id, result['ticket_number'], subject, result['ticket_id'],
            )
        return jsonify(result)
        
    except Exception as e:
        print(f"Error submitting ticket: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_tickets')
def get_tickets():
    if session.get('role') not in ['student', 'teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        if session.get('role') == 'student':
            result = get_student_tickets(session.get('user_id'))
        else:
            result = get_all_tickets(request.args.get('status'))
        return jsonify(result)
    except Exception as e:
        print(f"Error getting tickets: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        ticket_id = data.get('ticket_id')
        status = data.get('status')
        
        if not ticket_id:
            return jsonify({'success': False, 'message': 'Ticket ID required'})
        
        result = update_ticket_status(ticket_id, status)
        if result.get('success'):
            ticket = get_ticket_by_id(ticket_id).get('ticket') or {}
            notify_ticket_updated(
                ticket.get('student_id'),
                ticket.get('ticket_number', f'Ticket #{ticket_id}'),
                ticket.get('subject', 'Support ticket'),
                status,
                ticket_id,
            )
        return jsonify(result)
        
    except Exception as e:
        print(f"Error updating ticket: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_ticket_count')
def get_ticket_count():
    if session.get('role') != 'teacher':
        return jsonify({'success': False})
    
    try:
        result = get_ticket_counts()
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting ticket count: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== TEACHER API ROUTES ====================

@app.route('/get_students')
def get_students():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            student_name = _student_name_sql(cursor)
            cursor.execute(f"""
                SELECT
                    s.id,
                    s.lrn,
                    {student_name} AS full_name,
                    s.grade_level,
                    DATE_FORMAT(s.created_at, '%Y-%m-%d') as created_at
                FROM students s
                ORDER BY s.created_at DESC, s.id DESC
            """)
            students = cursor.fetchall()
            
            for student in students:
                student['has_activities'] = False
            
            return jsonify({'success': True, 'students': students})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get students error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve students'})

# ==================== IMPROVED GET_SCORES ROUTE ====================

@app.route('/get_scores')
def get_scores():
    """Get all student scores (teacher only)"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            student_name = _student_name_sql(cursor)
            cursor.execute(f"""
                SELECT
                    s.lrn,
                    {student_name} AS student_name,
                    d.title as activity_name,
                    a.score,
                    d.language,
                    DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') as completed_at
                FROM assessment_attempts a
                JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
                JOIN students s ON a.student_id = s.id
                WHERE a.status = 'submitted'
                ORDER BY a.submitted_at DESC
                LIMIT 100
            """)
            scores = cursor.fetchall()
            
            print(f"📊 Retrieved {len(scores)} scores")
            
            return jsonify({'success': True, 'scores': scores})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"❌ Get scores error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve scores'})

@app.route('/get_activity_scores')
def get_activity_scores():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT aa.id AS submission_id,
                   s.id AS student_id,
                   s.lrn,
                   {student_name} AS student_name,
                   d.assessment_number AS activity_number,
                   d.title AS activity_name,
                   d.language,
                        CASE WHEN aa.teacher_score IS NOT NULL THEN
                               CASE WHEN aa.teacher_score > 10 THEN ROUND(aa.teacher_score / 10) ELSE aa.teacher_score END
                        WHEN aa.auto_score > 0 OR aa.score = 0 THEN aa.auto_score
                        ELSE ROUND(aa.score / 10) END AS score,
                   aa.auto_score,
                   aa.teacher_score,
                   aa.teacher_feedback,
                   aa.code_blocks,
                   aa.generated_code,
                   aa.output AS student_output,
                   d.expected_output,
                   CASE WHEN aa.score >= 75 THEN 'Passed' ELSE 'Failed' END AS result,
                   CASE WHEN aa.status = 'submitted' THEN 'COMPLETED' ELSE 'AVAILABLE' END AS status,
                   DATE_FORMAT(COALESCE(aa.completed_at, aa.submitted_at), '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts aa
            JOIN learning_items d ON d.id = aa.assessment_id AND d.language = aa.language
            JOIN students s ON s.id = aa.student_id
            WHERE d.language IN ('php', 'javascript', 'cpp')
              AND aa.status = 'submitted'
            ORDER BY COALESCE(aa.completed_at, aa.submitted_at) DESC, aa.id DESC
        """)
        scores = cursor.fetchall()

        return jsonify({'success': True, 'scores': scores})
    except Exception as e:
        print(f"Get activity scores error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve activity scores'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_passed_assessments')
def get_passed_assessments():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT {student_name} AS student_name, s.lrn,
                   d.title AS activity_name, d.language, d.points,
                   a.score, DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted' AND a.score >= 75
            ORDER BY a.submitted_at DESC
        """)
        passed = cursor.fetchall()
        return jsonify({'success': True, 'passed': passed})
    except Exception as e:
        print(f"Get passed assessments error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve passed assessments'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_assessment_results')
def get_assessment_results():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT s.lrn, {student_name} AS student_name,
                   d.title AS assessment_name, d.language,
                   ROUND(a.score / 10, 1) AS score,
                   CASE
                       WHEN a.teacher_score IS NOT NULL THEN
                           CASE WHEN a.score >= 75 THEN 'Passed' ELSE 'Failed' END
                       WHEN a.generated_code IS NOT NULL
                         AND a.output NOT IN ('__ERROR__', '__TIMEOUT__', '__PENDING_REVIEW__') THEN
                           CASE WHEN a.score >= 75 THEN 'Passed' ELSE 'Failed' END
                       ELSE 'Needs Review'
                   END AS result,
                   DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted'
              AND d.language IN ('python', 'java')
            ORDER BY a.submitted_at DESC
            LIMIT 200
        """)
        return jsonify({'success': True, 'results': cursor.fetchall()})
    except Exception as e:
        print(f"Get assessment results error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve assessment results'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/get_submissions')
def get_teacher_score_submissions():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT a.id AS submission_id,
                   a.student_id,
                   {student_name} AS student_name,
                   s.lrn AS student_lrn,
                   d.title AS activity_title,
                   d.description AS question,
                   d.hint AS guide,
                   d.expected_output AS expected_output,
                   d.language,
                   CASE WHEN d.language IN ('php', 'javascript', 'cpp') THEN 'activity'
                        ELSE 'assessment' END AS item_type,
                   10 AS max_score,
                    a.score AS raw_score,
                   a.auto_score,
                   a.teacher_score,
                   a.teacher_feedback,
                   a.code_blocks AS code_blocks,
                   a.generated_code AS code,
                   a.output,
                   a.submitted_at,
                   CASE
                       WHEN a.teacher_score IS NOT NULL THEN
                           CASE WHEN a.score >= 75 THEN 'passed' ELSE 'failed' END
                       WHEN d.language = 'python'
                         AND a.generated_code IS NOT NULL
                         AND a.output NOT IN ('__ERROR__', '__TIMEOUT__', '__PENDING_REVIEW__') THEN
                           CASE WHEN a.score >= 75 THEN 'passed' ELSE 'failed' END
                       WHEN a.score >= 75 THEN 'passed'
                       ELSE 'pending'
                   END AS status
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted'
            ORDER BY COALESCE(a.completed_at, a.submitted_at) DESC, a.id DESC
        """)
        return jsonify({'success': True, 'submissions': cursor.fetchall()})
    except Exception as e:
        print(f"Get teacher score submissions error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve submissions'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/submissions')
def teacher_submissions():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT a.id, {student_name} AS student_name, s.username, d.title AS activity_name,
                   d.language, d.points, ROUND(a.score * d.points / 100) AS score,
                   a.status, DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS submitted_at
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted'
            ORDER BY a.submitted_at DESC
        """)
        checked = cursor.fetchall()
        return jsonify({'success': True, 'pending': [], 'checked': checked, 'total': len(checked)})
    except Exception as e:
        print(f"Get teacher submissions error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve submissions'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/submission/<int:submission_id>')
def teacher_submission(submission_id):
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
                 SELECT a.id, {student_name} AS student_name, s.username,
                     d.assessment_number AS activity_number, d.title AS activity_name,
                     d.language, d.expected_output, a.code_blocks, a.generated_code,
                       a.output AS student_output, a.score, a.auto_score,
                       CASE WHEN a.teacher_score > 10 THEN ROUND(a.teacher_score / 10) ELSE a.teacher_score END AS teacher_score,
                     a.teacher_feedback, a.status, a.submitted_at, a.completed_at
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            JOIN students s ON s.id = a.student_id
            WHERE a.id = %s
        """, (submission_id,))
        submission = cursor.fetchone()
        if not submission:
            return jsonify({'success': False, 'message': 'Submission not found'}), 404
        return jsonify({'success': True, 'submission': submission})
    except Exception as e:
        print(f"Get teacher submission error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve submission'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/review_submission', methods=['POST'])
def review_teacher_submission():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    submission_id = data.get('submission_id')
    score = data.get('score')
    if not isinstance(submission_id, int) or not isinstance(score, int):
        return jsonify({'success': False, 'message': 'Invalid review data'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.points, d.title, d.language, d.assessment_number, a.student_id
            FROM learning_items d
            JOIN assessment_attempts a ON a.assessment_id = d.id AND a.language = d.language
            WHERE a.id = %s
        """, (submission_id,))
        assessment = cursor.fetchone()
        if not assessment or score < 0 or score > 10:
            return jsonify({'success': False, 'message': 'Invalid score'}), 400
        stored_score = score * 10
        feedback = data.get('feedback', '')
        cursor.execute("""
            UPDATE assessment_attempts
            SET score = %s,
                teacher_score = %s,
                teacher_feedback = %s,
                reviewed_by = %s,
                reviewed_at = %s,
                status = 'submitted',
                completed_at = COALESCE(completed_at, submitted_at)
            WHERE id = %s
        """, (stored_score, score, feedback, session['user_id'], datetime.now(), submission_id))
        conn.commit()
        new_badges = []
        certificate_issued = False
        module_complete = False
        if _normalize_score(score, None, stored_score) >= 75:
            try:
                award_result = try_award_after_submission(
                    cursor,
                    assessment['student_id'],
                    assessment['language'],
                    assessment['assessment_number'],
                )
                new_badges = award_result['new_badges']
                certificate_issued = award_result['certificate_issued']
                module_complete = award_result['module_complete']
                conn.commit()
            except Exception as award_err:
                print(f"[review_teacher_submission] award error: {award_err}")
                conn.rollback()
        notify_assessment_checked(
            assessment['student_id'],
            assessment['title'],
            stored_score,
            feedback,
            submission_id,
        )
        return jsonify({
            'success': True,
            'message': 'Review saved',
            'new_badges': new_badges,
            'certificate_issued': certificate_issued,
            'module_complete': module_complete,
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Review teacher submission error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save review'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== END OF GET_SCORES ====================

@app.route('/get_performance_reports')
def get_performance_reports():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            student_name = _student_name_sql(cursor)
            cursor.execute(f"""
                                        SELECT s.id, s.lrn,
                                            {student_name} AS student_name,
                                            s.grade_level,
                      COUNT(a.id) as total_activities,
                      IFNULL(ROUND(AVG(a.score), 1), 0) as average_score,
                      SUM(CASE WHEN a.score < 50 THEN 1 ELSE 0 END) as low_scores
                FROM students s
                  LEFT JOIN assessment_attempts a ON s.id = a.student_id AND a.status = 'submitted'
                GROUP BY s.id
                ORDER BY average_score DESC
            """)
            reports = cursor.fetchall()
            return jsonify({'success': True, 'reports': reports})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get performance reports error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve performance reports'})

@app.route('/get_student_detail/<lrn>')
def get_student_detail(lrn):
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM students WHERE lrn = %s", (lrn,))
        student_record = cursor.fetchone()
        
        if not student_record:
            return jsonify({'success': False, 'message': 'Student not found'})
        student = {
            'id': student_record['id'],
            'lrn': student_record.get('lrn'),
            'full_name': _student_display_name(student_record),
            'grade_level': student_record.get('grade_level'),
            'email': student_record.get('email'),
            'joined_date': (
                student_record['created_at'].strftime('%B %d, %Y')
                if student_record.get('created_at') else ''
            ),
        }
        
        cursor.execute("""
            SELECT CONCAT(d.language, ' Assessment #', d.assessment_number) AS activity_name,
                   a.score, d.language,
                   DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts a
            JOIN learning_items d ON d.id = a.assessment_id AND d.language = a.language
            WHERE a.student_id = %s AND a.status = 'submitted'
            ORDER BY a.submitted_at DESC
        """, (student['id'],))
        activities = cursor.fetchall()
        
        total_activities = len(activities)
        avg_score = round(sum(a['score'] for a in activities) / total_activities) if total_activities > 0 else 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'student': student,
            'activities': activities,
            'total_activities': total_activities,
            'average_score': avg_score
        })
        
    except Exception as e:
        print(f"Get student detail error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_teacher_profile', methods=['POST'])
def update_teacher_profile():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        full_name = data.get('full_name')
        email = data.get('email')
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        user_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            updates = []
            params = []
            
            if full_name:
                updates.append("full_name = %s")
                params.append(full_name)
                session['full_name'] = full_name
            
            if email:
                updates.append("email = %s")
                params.append(email)
            
            if current_password and new_password:
                cursor.execute("SELECT password FROM teachers WHERE id = %s", (user_id,))
                teacher = cursor.fetchone()
                
                if teacher and not verify_password(teacher['password'], current_password)[0]:
                    return jsonify({'success': False, 'message': 'Current password is incorrect'})
                strong, strength_msg = validate_password_strength(new_password)
                if not strong:
                    return jsonify({'success': False, 'message': strength_msg})
                
                updates.append("password = %s")
                params.append(hash_password(new_password))
            
            if updates:
                query = f"UPDATE teachers SET {', '.join(updates)} WHERE id = %s"
                params.append(user_id)
                cursor.execute(query, params)
                conn.commit()
            
            return jsonify({'success': True, 'message': 'Profile updated successfully!'})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Update teacher profile error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_class_stats')
def get_class_stats():
    if session.get('role') != 'teacher':
        return jsonify({'success': False})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) AS total_submissions,
                   COUNT(DISTINCT student_id) AS active_students,
                   IFNULL(ROUND(AVG(activity_score), 1), 0) AS class_average,
                   COALESCE(SUM(activity_score >= 7), 0) AS passing
            FROM (
                SELECT aa.student_id,
                       CASE
                           WHEN aa.teacher_score IS NOT NULL THEN
                               CASE WHEN aa.teacher_score > 10 THEN ROUND(aa.teacher_score / 10, 1) ELSE aa.teacher_score END
                           WHEN aa.auto_score IS NOT NULL THEN
                               CASE WHEN aa.auto_score > 10 THEN ROUND(aa.auto_score / 10, 1) ELSE aa.auto_score END
                           ELSE ROUND(aa.score / 10, 1)
                       END AS activity_score
                FROM assessment_attempts aa
                JOIN learning_items d ON d.id = aa.assessment_id AND d.language = aa.language
                WHERE aa.status = 'submitted'
                  AND d.language IN ('php', 'javascript', 'cpp')
            ) AS activity_results
        """)
        stats = cursor.fetchone()
        active_students = stats['active_students'] or 0
        total_submissions = stats['total_submissions'] or 0
        class_avg = stats['class_average'] or 0
        passing = stats['passing'] or 0
        passing_rate = round((passing / total_submissions) * 100) if total_submissions > 0 else 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_students': total_students,
            'active_students': active_students,
            'total_submissions': total_submissions,
            'class_average': class_avg,
            'passing_rate': passing_rate
        })
        
    except Exception as e:
        print(f"Get class stats error: {e}")
        return jsonify({'success': False})

def _get_leaderboard_rows():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT scored.id,
                   scored.name,
                   scored.student_lrn,
                   scored.grade,
                   SUM(scored.is_completed) AS completed,
                   SUM(CASE WHEN scored.is_completed = 1 THEN scored.item_score ELSE 0 END) AS points,
                   IFNULL(ROUND(AVG(CASE WHEN scored.is_completed = 1 THEN scored.item_score END), 1), 0) AS avg_score,
                   ROUND(SUM(CASE WHEN scored.is_completed = 1 THEN scored.item_score ELSE 0 END) / 150 * 100, 1) AS activity_percentage
            FROM (
                SELECT s.id,
                       {student_name} AS name,
                       s.lrn AS student_lrn,
                       s.grade_level AS grade,
                       d.id AS assessment_id,
                       CASE
                           WHEN aa.id IS NOT NULL AND (aa.status IN ('submitted', 'completed', 'pending_review') OR aa.teacher_score IS NOT NULL)
                           THEN 1 ELSE 0
                       END AS is_completed,
                       LEAST(10, GREATEST(0, CASE
                           WHEN aa.id IS NOT NULL
                             AND (aa.status IN ('submitted', 'completed', 'pending_review') OR aa.teacher_score IS NOT NULL)
                           THEN CASE
                               WHEN aa.teacher_score IS NOT NULL THEN
                                   CASE WHEN aa.teacher_score > 10 THEN ROUND(aa.teacher_score / 10) ELSE aa.teacher_score END
                               WHEN aa.auto_score IS NOT NULL AND (aa.auto_score > 0 OR aa.score = 0) THEN
                                   CASE WHEN aa.auto_score > 10 THEN ROUND(aa.auto_score / 10) ELSE aa.auto_score END
                               WHEN aa.score IS NOT NULL THEN
                                   CASE WHEN aa.score > 10 THEN ROUND(aa.score / 10) ELSE aa.score END
                               ELSE 0
                           END
                           ELSE 0
                       END)) AS item_score
                FROM students s
                CROSS JOIN activities d
                LEFT JOIN assessment_attempts aa
                  ON aa.student_id = s.id
                 AND aa.assessment_id = d.id
                 AND aa.language = d.language
                WHERE d.language IN ('php', 'javascript', 'cpp')
                  AND d.assessment_number BETWEEN 1 AND 5
            ) AS scored
            GROUP BY scored.id, scored.name, scored.student_lrn, scored.grade
            HAVING SUM(scored.is_completed) = 15
            ORDER BY activity_percentage DESC, points DESC, scored.name
        """)
        rows = cursor.fetchall()
        for row in rows:
            row['completed'] = int(row['completed'] or 0)
            row['points'] = int(row['points'] or 0)
            row['avg_score'] = float(row['avg_score'] or 0)
            row['activity_percentage'] = float(row.get('activity_percentage') or row.get('avg_score') or 0)
            row['progress'] = min(round(row['completed'] / 15 * 100), 100)
        return rows
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/leaderboard')
def leaderboard():
    if session.get('role') not in ['student', 'teacher']:
        return jsonify({'success': False})

    try:
        rows = _get_leaderboard_rows()
        leaderboard_rows = [{
            'student_name': row.get('name') or row.get('student_name') or 'Student',
            'student_lrn': row.get('student_lrn'),
            'activities_completed': int(row.get('completed') or row.get('activities_completed') or 0),
            'average_score': float(row.get('avg_score') or row.get('average_score') or 0),
            'activity_percentage': float(row.get('activity_percentage') or row.get('avg_score') or 0),
        } for row in rows]
        return jsonify({'success': True, 'leaderboard': leaderboard_rows})
    except Exception as e:
        print(f"Leaderboard error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher/leaderboard_data')
def teacher_leaderboard_data():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        rows = _get_leaderboard_rows()
        leaderboard_rows = [{
            **row,
            'rank': rank,
        } for rank, row in enumerate(rows, start=1)]
        return jsonify({'success': True, 'leaderboard': leaderboard_rows})
    except Exception as e:
        print(f"Teacher leaderboard error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve leaderboard'}), 500

# ==================== ICT SUPPORT API ROUTES ====================

@app.route('/get_monitoring_data')
def get_monitoring_data():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        monitoring = {
            'cpu_usage': 45.2,
            'memory_usage': 62.5,
            'disk_usage': 78.3,
            'network_bandwidth': 150.5,
            'uptime': '45 days, 12 hours',
            'active_users': 12,
            'services': [
                {'name': 'Web Server', 'status': 'Running', 'uptime': '15 days'},
                {'name': 'Database', 'status': 'Running', 'uptime': '45 days'},
                {'name': 'Email Service', 'status': 'Running', 'uptime': '8 days'},
                {'name': 'Backup Service', 'status': 'Stopped', 'uptime': 'N/A'}
            ]
        }
        return jsonify({'success': True, 'data': monitoring})
    except Exception as e:
        print(f"Error getting monitoring data: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_ict_reports')
def get_ict_reports():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        reports = {
            'system_health': 92,
            'uptime_percentage': 99.8,
            'incidents_this_month': 3,
            'resolved_tickets': 28,
            'pending_tickets': 5,
            'average_resolution_time': '4.5 hours'
        }
        return jsonify({'success': True, 'data': reports})
    except Exception as e:
        print(f"Error getting ICT reports: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/generate_report')
def generate_report():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    report_type = request.args.get('type', 'ticket')
    if report_type not in ['user', 'performance']:
        return jsonify({'success': False, 'message': 'Unsupported report type'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if report_type == 'user':
            student_name = _student_name_sql(cursor)
            cursor.execute(f"""
                SELECT s.id, {student_name} AS full_name, s.username, s.lrn, s.grade_level,
                       s.created_at AS last_active, COUNT(t.id) AS ticket_count
                FROM students s
                LEFT JOIN ict_tickets t ON t.student_id = s.id
                GROUP BY s.id, {student_name}, s.username, s.lrn, s.grade_level, s.created_at
                ORDER BY full_name, s.username
            """)
            users = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) AS total FROM ict_tickets")
            total_tickets = cursor.fetchone()['total']
            return jsonify({
                'success': True,
                'total_users': len(users),
                'active_users': len(users),
                'inactive_users': 0,
                'total_tickets': total_tickets,
                'users': users
            })

        cursor.execute("""
            SELECT COUNT(*) AS total_tickets,
                   COALESCE(AVG(CASE WHEN status IN ('resolved', 'closed')
                       THEN TIMESTAMPDIFF(MINUTE, created_at, COALESCE(resolved_at, updated_at)) END), 0) AS avg_resolution_time,
                   COALESCE(SUM(status IN ('resolved', 'closed')) / NULLIF(COUNT(*), 0) * 100, 0) AS resolution_rate
            FROM ict_tickets
        """)
        summary = cursor.fetchone()
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m-%d') AS date,
                   COUNT(*) AS tickets_created,
                   SUM(status IN ('resolved', 'closed')) AS tickets_resolved,
                   COALESCE(AVG(CASE WHEN status IN ('resolved', 'closed')
                       THEN TIMESTAMPDIFF(MINUTE, created_at, COALESCE(resolved_at, updated_at)) END), 0) AS avg_resolution_time
            FROM ict_tickets
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m-%d')
            ORDER BY DATE_FORMAT(created_at, '%Y-%m-%d') DESC
        """)
        performance_data = cursor.fetchall()
        for row in performance_data:
            row['tickets_created'] = int(row['tickets_created'] or 0)
            row['tickets_resolved'] = int(row['tickets_resolved'] or 0)
            row['avg_resolution_time'] = round(float(row['avg_resolution_time'] or 0), 1)
        return jsonify({
            'success': True,
            'avg_resolution_time': round(float(summary['avg_resolution_time'] or 0), 1),
            'resolution_rate': round(float(summary['resolution_rate'] or 0), 1),
            'total_tickets': summary['total_tickets'] or 0,
            'avg_rating': 0,
            'performance_data': performance_data
        })
    except Exception as e:
        print(f"Error generating {report_type} report: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_ict_students')
def get_ict_students():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        student_name = _student_name_sql(cursor)
        cursor.execute(f"""
            SELECT s.id, s.username, {student_name} AS full_name, s.lrn, s.grade_level, s.email,
                   s.created_at, COUNT(a.id) AS activity_count,
                   COALESCE(AVG(a.score), 0) AS avg_score
            FROM students s
            LEFT JOIN assessment_attempts a
                ON s.id = a.student_id AND a.status = 'submitted'
            GROUP BY s.id, s.username, {student_name}, s.lrn, s.grade_level,
                     s.email, s.created_at
            ORDER BY full_name
        """)
        
        students = cursor.fetchall()
        cursor.execute("""
            SELECT id, username, full_name, role_type, email, status, last_login
            FROM ict_support
            ORDER BY full_name, username
        """)
        ict_supports = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'students': students,
            'ict_supports': ict_supports
        })
    except Exception as e:
        print(f"Error getting ICT students: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"Internal server error: {error}")
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback_route():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    try:
        rating = int(data.get('rating'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid rating'}), 400

    result = submit_feedback(
        student_id=session['user_id'],
        student_name=session.get('full_name') or session.get('username'),
        student_lrn=session.get('lrn'),
        rating=rating,
        category=str(data.get('category') or '').strip(),
        comment=str(data.get('comment') or '').strip(),
        feedback_type=data.get('feedback_type', 'learning'),
        language=data.get('language'),
        assessment_id=data.get('assessment_id'),
        activity_id=data.get('activity_id'),
        module_id=data.get('module_id'),
    )
    return jsonify(result), (200 if result.get('success') else 400)

@app.route('/get_my_feedback')
def get_my_feedback_route():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    return jsonify(get_student_feedback(session['user_id']))

@app.route('/api/teacher/feedback/summary')
def api_teacher_fb_summary():
    if session.get('role') not in ('teacher', 'student'):
        return jsonify({'success': False}), 403
    return jsonify(get_learning_summary(_fb_filters_from_request()))

@app.route('/api/teacher/feedback/by-category')
def api_teacher_fb_by_cat():
    if session.get('role') not in ('teacher', 'student'):
        return jsonify({'success': False}), 403
    return jsonify(get_learning_by_category(_fb_filters_from_request()))

@app.route('/api/teacher/feedback/by-language')
def api_teacher_fb_by_lang():
    if session.get('role') not in ('teacher', 'student'):
        return jsonify({'success': False}), 403
    return jsonify(get_learning_by_language(_fb_filters_from_request()))

@app.route('/api/teacher/feedback/recent')
def api_teacher_fb_recent():
    if session.get('role') not in ('teacher', 'student'):
        return jsonify({'success': False}), 403
    limit = request.args.get('limit', 20, type=int)
    return jsonify(get_learning_recent(limit, _fb_filters_from_request()))

@app.route('/api/teacher/feedback/keywords')
def api_teacher_fb_keywords():
    if session.get('role') not in ('teacher', 'student'):
        return jsonify({'success': False}), 403
    return jsonify(get_learning_keywords(_fb_filters_from_request()))

@app.route('/api/ict/feedback/summary')
def api_ict_fb_summary():
    if session.get('role') not in ('teacher', 'ict'):
        return jsonify({'success': False}), 403
    return jsonify(get_technical_summary(_fb_filters_from_request()))

@app.route('/api/ict/feedback/by-category')
def api_ict_fb_by_cat():
    if session.get('role') not in ('teacher', 'ict'):
        return jsonify({'success': False}), 403
    return jsonify(get_technical_by_category(_fb_filters_from_request()))

@app.route('/api/ict/feedback/recent')
def api_ict_fb_recent():
    if session.get('role') not in ('teacher', 'ict'):
        return jsonify({'success': False}), 403
    limit = request.args.get('limit', 20, type=int)
    return jsonify(get_technical_recent(limit, _fb_filters_from_request()))

@app.route('/api/ict/feedback/keywords')
def api_ict_fb_keywords():
    if session.get('role') not in ('teacher', 'ict'):
        return jsonify({'success': False}), 403
    return jsonify(get_technical_keywords(_fb_filters_from_request()))

def _fb_filters_from_request():
    filters = {
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
        'language': request.args.get('language'),
        'category': request.args.get('category'),
    }
    if session.get('role') == 'student':
        filters['student_id'] = session.get('user_id')
    return filters

if __name__ == '__main__':
    print('=' * 60)
    print('BLOCKLEARN - Drag-and-Drop Programming Platform')
    print('=' * 60)
    print(f"Database: {db_config['database']}")
    print(f"Host: {db_config['host']}")
    print('=' * 60)
    print('Run the app and open http://127.0.0.1:5000')
    print('=' * 60)
    app.run(debug=True, host='127.0.0.1', port=5000)