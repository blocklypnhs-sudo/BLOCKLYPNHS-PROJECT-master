from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
NAV_PAGES = (
    'frontend/activities/php_activities.html',
    'frontend/activities/javascript_activities.html',
    'frontend/activities/cpp_activities.html',
    'frontend/assessments/python_assessments.html',
    'frontend/assessments/java_assessments.html',
    'frontend/modules_activities/ass&act_library.html',
)


@pytest.mark.parametrize('template_path', NAV_PAGES)
def test_student_assessment_and_module_navigation_collapses_on_mobile(template_path):
    page = (ROOT / template_path).read_text(encoding='utf-8')
    mobile_styles = page.split('@media (max-width: 768px) {', 1)[1]

    assert 'desktop-nav-link' in page
    assert re.search(
        r'\.mobile-nav-toggle,\s*(?:\.student-sidebar\s+)?'
        r'\.mobile-nav-submenu\s*\{\s*display: none;',
        page,
    )
    assert 'mobile-nav-toggle { display: flex !important; }' in mobile_styles
    assert re.search(r'desktop-nav-link[^}]*display: none !important;', mobile_styles)
    assert 'aria-controls="assessmentSubnav"' in page
    assert 'aria-controls="modulesSubnav"' in page
    assert 'aria-expanded="false"' in page
    assert 'Python Assessments' in page
    assert 'Java Assessments' in page
    assert '/module_assessments#python-modules' in page
    assert '/module_assessments#cpp-modules' in page
    nav_toggle = 'toggleLibraryNavGroup(toggleId' if 'ass&act_library' in template_path else 'toggleStudentNavGroup(toggleId'
    assert nav_toggle in page
