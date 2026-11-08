from pathlib import Path


def test_python_assessment_preview_closes_indented_function_before_top_level_call():
    template = (
        Path(__file__).resolve().parents[1]
        / 'frontend'
        / 'assessments'
        / 'playground_python.html'
    ).read_text(encoding='utf-8')
    start = template.index('        function pythonPreviewCode(')
    end = template.index('\n        function runPythonCode()', start)
    converter = template[start:end]

    function_body = converter.index('if (statement.startsWith(\'print(\')')
    assert converter.index('closeOpenBlocks(indent);', function_body) < converter.index(
        'const inner = statement.slice(6, -1).trim();',
        function_body,
    )
    assert 'closeOpenBlocks(indent);\n                const finalStatement' in converter
