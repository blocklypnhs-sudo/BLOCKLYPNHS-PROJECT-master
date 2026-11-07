from backend.module_scoring import score_module_output_breakdown
from backend.module_scoring import score_output_breakdown


def test_module_output_breakdown_shows_correct_and_incorrect_lines():
    result = score_module_output_breakdown('1\nwrong\n3', '1\n2\n3')

    assert result['score'] == 67
    assert [item['correct'] for item in result['breakdown']] == [True, False, True]
    assert [item['student_answer'] for item in result['breakdown']] == ['1', 'wrong', '3']
    assert sum(item['points_earned'] for item in result['breakdown']) == result['score']


def test_extra_output_line_is_reported_and_partial_score_stays_below_pass_mark():
    result = score_module_output_breakdown('1\n2\n3\nextra', '1\n2\n3')

    assert result['score'] == 74
    assert result['breakdown'][-1]['criterion'] == 'Unexpected output line 4'
    assert result['breakdown'][-1]['correct'] is False
    assert sum(item['points_earned'] for item in result['breakdown']) == result['score']


def test_module_output_breakdown_preserves_case_insensitive_scoring():
    result = score_module_output_breakdown(
        'Hello\nworld', 'hello\nWORLD', case_insensitive=True,
    )

    assert result['score'] == 100
    assert all(item['correct'] for item in result['breakdown'])


def test_module_output_breakdown_explains_execution_errors():
    result = score_module_output_breakdown('__ERROR__', 'expected output')

    assert result['score'] == 0
    assert result['breakdown'][0]['student_answer'] == 'Program execution failed.'
    assert 'could not produce output' in result['breakdown'][0]['feedback']


def test_regular_assessment_output_awards_partial_points_per_line():
    result = score_output_breakdown(
        'one\nwrong\nthree', 'one\ntwo\nthree', max_points=100,
    )

    assert result['score'] == 67
    assert [item['points_earned'] for item in result['breakdown']] == [33.33, 0, 33.34]
    assert sum(item['max_points'] for item in result['breakdown']) == 100
