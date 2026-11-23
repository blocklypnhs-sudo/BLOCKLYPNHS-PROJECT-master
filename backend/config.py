# config.py
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', 'mUHrcybHaK2xYyGn'),
        'database': os.environ.get('DB_NAME', 'blocklypnhsproject'),
        'port': int(os.environ.get('DB_PORT', 3306)),
        'ssl_disabled': False,
}

SECRET_KEY = 'your-secret-key-change-this-in-production-2024'