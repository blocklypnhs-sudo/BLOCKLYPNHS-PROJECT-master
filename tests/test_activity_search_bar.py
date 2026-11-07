import pytest

from backend.app import app


@pytest.mark.parametrize(
    'path',
    (
        '/student_activities_javascript',
        '/student_activities_php',
        '/student_activities_cpp',
    ),
)
def test_language_activity_pages_include_top_search_bar(path):
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['student_name_loaded'] = True

        response = client.get(path)

    assert response.status_code == 200
    assert response.data.count(b'id="topSearchInput"') == 1
    assert b'<div class="top-search">' in response.data
    assert b'placeholder="Search..."' in response.data
