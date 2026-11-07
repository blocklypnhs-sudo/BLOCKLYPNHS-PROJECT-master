# config.py
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '2004Nath29',
    'database': 'blocklypnhsproject'
}

SECRET_KEY = 'your-secret-key-change-this-in-production-2024'