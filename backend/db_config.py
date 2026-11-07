# backend/db_config.py - Database Configuration

import mysql.connector

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '2004Nath29',
    'database': 'blocklypnhsproject'
}


def get_db_connection():
    return mysql.connector.connect(**db_config)


def test_connection():
    """Return whether the configured database connection can be opened."""
    try:
        conn = get_db_connection()
        conn.close()
        print(" Database connection successful!")
        return True
    except mysql.connector.Error as e:
        print(f"Database connection failed: {e}")
        return False


# ===== DATABASE INITIALIZATION =====

def create_tables():
    """Create all necessary tables for the application"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(100),
                email VARCHAR(100),
                role VARCHAR(20) DEFAULT 'student',
                grade_level VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Student submissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                activity_name VARCHAR(100) NOT NULL,
                code_blocks TEXT NOT NULL,
                language VARCHAR(20) DEFAULT 'python',
                status VARCHAR(20) DEFAULT 'pending_review',
                score INT,
                feedback TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                target_role VARCHAR(20),
                type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                related_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_student ON student_submissions(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_status ON student_submissions(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)')
        
        conn.commit()
        conn.close()
        print(" Database tables created successfully!")
        return True
        
    except mysql.connector.Error as e:
        print(f"Error creating tables: {e}")
        return False


# ===== DEMO DATA =====

def seed_demo_data():
    """Insert demo data for testing"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Demo student
        cursor.execute('''
            INSERT IGNORE INTO users (username, password, name, email, role, grade_level)
            VALUES ('student1', 'password123', 'Juan Dela Cruz', 'juan@example.com', 'student', 'Grade 11')
        ''')
        
        # Demo teacher
        cursor.execute('''
            INSERT IGNORE INTO users (username, password, name, email, role)
            VALUES ('teacher1', 'password123', 'Maria Santos', 'maria@example.com', 'teacher')
        ''')
        
        conn.commit()
        conn.close()
        print(" Demo data seeded!")
        return True
        
    except mysql.connector.Error as e:
        print(f"Error seeding demo data: {e}")
        return False


# Export for use in other files
__all__ = [
    'db_config',
    'get_db_connection', 
    'test_connection',
    'save_submission',
    'get_student_submissions',
    'get_activity_status',
    'get_pending_submissions_for_teachers',
    'get_all_student_submissions_for_teacher',
    'review_submission',
    'create_tables',
    'seed_demo_data'
]

# Run initialization if executed directly
if __name__ == '__main__':
    print(" Initializing database...")
    if test_connection():
        create_tables()
        seed_demo_data()
        print(" Database setup complete!")
    else:
        print(" Database connection failed!")