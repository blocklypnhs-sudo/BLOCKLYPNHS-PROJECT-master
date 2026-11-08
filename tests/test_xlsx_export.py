from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.app import app


MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def _enable_teacher_session(client):
    with client.session_transaction() as user_session:
        user_session['role'] = 'teacher'


@pytest.mark.parametrize(
    ('export_type', 'sheet_name', 'filename'),
    [
        ('leaderboard', 'Leaderboard', 'blocklearn-leaderboard.xlsx'),
        ('scores', 'Student Scores', 'blocklearn-student-scores.xlsx'),
        ('assessments', 'Assessment Results', 'blocklearn-assessment-results.xlsx'),
        ('submissions', 'Student Submissions', 'blocklearn-submissions.xlsx'),
    ],
)
def test_teacher_xlsx_export_returns_a_valid_workbook(monkeypatch, export_type, sheet_name, filename):
    class FakeCursor:
        def fetchone(self):
            return {}

        def close(self):
            pass

    class FakeConnection:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', FakeConnection)
    monkeypatch.setattr('backend.app.log_audit', lambda *args, **kwargs: None)

    with app.test_client() as client:
        _enable_teacher_session(client)
        response = client.post('/teacher/export_xlsx', json={
            'type': export_type,
            'rows': [
                ['Student', 'Score'],
                ['=not a formula', 9.5],
                ['Jos\u00e9 & <student>', None],
            ],
        })

    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert filename in response.headers['Content-Disposition']

    with ZipFile(BytesIO(response.data)) as workbook:
        assert workbook.testzip() is None
        workbook_xml = ET.fromstring(workbook.read('xl/workbook.xml'))
        sheet = workbook_xml.find(f'{{{MAIN_NS}}}sheets/{{{MAIN_NS}}}sheet')
        assert sheet is not None
        assert sheet.attrib['name'] == sheet_name

        worksheet = ET.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
        values = [element.text for element in worksheet.findall(f'.//{{{MAIN_NS}}}t')]
        assert values[:4] == ['Student', 'Score', '=not a formula', 'Jos\u00e9 & <student>']
        assert values[4] in (None, '')


def test_teacher_xlsx_export_requires_teacher_role_and_valid_rows(monkeypatch):
    with app.test_client() as client:
        unauthorized = client.post('/teacher/export_xlsx', json={
            'type': 'scores',
            'rows': [['Student']],
        })
        assert unauthorized.status_code == 401

        _enable_teacher_session(client)
        invalid = client.post('/teacher/export_xlsx', json={
            'type': 'scores',
            'rows': [['Student'], ['Too', 'Many']],
        })
        assert invalid.status_code == 400
        assert invalid.get_json()['success'] is False


def test_teacher_report_pages_expose_native_excel_export_actions():
    with app.test_client() as client:
        _enable_teacher_session(client)
        leaderboard = client.get('/teacher_leaderboard')
        reports = client.get('/teacher_reports_analytics')

    assert leaderboard.status_code == 200
    assert 'onclick="exportExcel()"' in leaderboard.get_data(as_text=True)
    assert reports.status_code == 200
    reports_html = reports.get_data(as_text=True)
    assert 'onclick="exportGradingExcel(\'scores\')"' in reports_html
    assert 'onclick="exportGradingExcel(\'assessments\')"' in reports_html

    submissions = client.get('/teacher_score_results')
    assert submissions.status_code == 200
    assert 'onclick="exportScoresExcel()"' in submissions.get_data(as_text=True)
