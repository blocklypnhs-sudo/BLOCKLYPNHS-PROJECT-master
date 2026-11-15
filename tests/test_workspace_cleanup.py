from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PAGES = (
    'frontend/playground/php_playground.html',
    'frontend/playground/javascript_playground.html',
    'frontend/playground/cpp_playground.html',
    'frontend/assessments/playground_python.html',
    'frontend/assessments/playground_java.html',
    'frontend/modules_activities/php_modules_01_variables.html',
    'frontend/modules_activities/php_modules_02_condition.html',
    'frontend/modules_activities/javascript_01_variables.html',
    'frontend/modules_activities/javascript_02_functions.html',
    'frontend/modules_activities/cpp_module_01_basics.html',
    'frontend/modules_activities/cpp_module_02_loops.html',
    'frontend/modules_activities/modules_assessments/python_01_bascis.html',
    'frontend/modules_activities/modules_assessments/python_02_loops.html',
    'frontend/modules_activities/modules_assessments/java01_basics.html',
    'frontend/modules_activities/modules_assessments/java_02_loops.html',
)


def test_every_student_block_workspace_loads_shared_cleanup():
    for relative_path in WORKSPACE_PAGES:
        page = (ROOT / relative_path).read_text(encoding='utf-8')
        assert '/static/js/workspace_cleanup.js' in page, relative_path


def test_workspace_cleanup_clears_restored_workspaces_and_output():
    cleanup = (ROOT / 'static/js/workspace_cleanup.js').read_text(encoding='utf-8')

    assert "addEventListener('pageshow'" in cleanup
    assert 'event.persisted' in cleanup
    assert 'Blockly.Workspace.getAll()' in cleanup
    assert 'workspace.clear()' in cleanup
    assert "querySelectorAll('.output-text')" in cleanup
