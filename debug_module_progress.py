import mysql.connector
from backend.module_awards import get_all_module_progress

conn = mysql.connector.connect(host='localhost', user='root', password='2004Nath29', database='blocklypnhsproject')
cur = conn.cursor(dictionary=True)
cur.execute('SELECT id, username, full_name FROM students ORDER BY id')
for row in cur.fetchall():
    mods = get_all_module_progress(cur, row['id'])
    python = next((m for m in mods if m['language']=='python'), None)
    if python:
        print('STUDENT', row['id'], row['username'], row['full_name'])
        print(python['lessons'], python['items'], python['module_assessments'], python['complete'], python['certificate'])
        print('---')
conn.close()
