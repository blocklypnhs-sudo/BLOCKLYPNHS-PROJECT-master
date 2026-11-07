# backend/module_scoring.py
"""Scoring for module final assessments (partial credit, pass mark 75)."""
from backend.module_awards import PASS_THRESHOLD

MAX_PARTIAL_SCORE = PASS_THRESHOLD - 1


def score_module_output(output, expected, case_insensitive=False):
    return score_module_output_breakdown(
        output, expected, case_insensitive=case_insensitive,
    )['score']


def score_module_output_breakdown(output, expected, case_insensitive=False):
    return score_output_breakdown(
        output,
        expected,
        case_insensitive=case_insensitive,
        max_points=100,
        max_partial_score=MAX_PARTIAL_SCORE,
    )


def score_output_breakdown(
    output,
    expected,
    case_insensitive=False,
    max_points=10,
    max_partial_score=None,
):
    """
    Score output line by line and return a 0-100 score plus point allocations.
    """
    out = (output or '').replace('\r\n', '\n').strip()
    exp = (expected or '').replace('\r\n', '\n').strip()
    is_error = out in {
        '__ERROR__', '__TIMEOUT__', '__PENDING_REVIEW__',
    }
    out_lines = [] if is_error else [line.rstrip() for line in out.split('\n')]
    exp_lines = [line.rstrip() for line in exp.split('\n')]
    comparison_output = [line.casefold() for line in out_lines] if case_insensitive else out_lines
    comparison_expected = [line.casefold() for line in exp_lines] if case_insensitive else exp_lines
    denominator = max(len(out_lines), len(exp_lines), 1)
    matched = sum(
        1 for actual, expected_line in zip(comparison_output, comparison_expected)
        if actual == expected_line
    )
    if not is_error and comparison_output == comparison_expected:
        score = 100
    elif is_error:
        score = 0
    else:
        score = round(100 * matched / denominator)
        if max_partial_score is not None:
            score = min(score, max_partial_score)

    max_points_per_line = round(max_points / denominator, 2)
    line_max_points = [max_points_per_line] * denominator
    if denominator:
        line_max_points[-1] = round(
            max_points - sum(line_max_points[:-1]), 2,
        )
    earned_line_points = [0] * denominator
    if matched:
        if max_partial_score is None:
            earned_line_points = [
                line_max_points[index]
                if index < len(comparison_output)
                and index < len(comparison_expected)
                and comparison_output[index] == comparison_expected[index]
                else 0
                for index in range(denominator)
            ]
        else:
            matched_indexes = [
                index for index in range(denominator)
                if index < len(comparison_output)
                and index < len(comparison_expected)
                and comparison_output[index] == comparison_expected[index]
            ]
            total_earned = round(max_points * score / 100, 2)
            points_per_match = round(total_earned / matched, 2)
            for index in matched_indexes[:-1]:
                earned_line_points[index] = points_per_match
            earned_line_points[matched_indexes[-1]] = round(
                total_earned - sum(earned_line_points), 2,
            )

    breakdown = []
    for index in range(denominator):
        expected_line = exp_lines[index] if index < len(exp_lines) else ''
        actual_line = out_lines[index] if index < len(out_lines) else ''
        correct = (
            index < len(exp_lines)
            and index < len(out_lines)
            and comparison_output[index] == comparison_expected[index]
        )
        breakdown.append({
            'criterion': f'Output line {index + 1}' if index < len(exp_lines)
                else f'Unexpected output line {index + 1}',
            'correct': correct,
            'points_earned': earned_line_points[index],
            'max_points': line_max_points[index],
            'expected_answer': expected_line or '(no line expected)',
            'student_answer': (
                'Program execution failed.' if out == '__ERROR__' else
                'Program timed out.' if out == '__TIMEOUT__' else
                'Awaiting teacher review.' if out == '__PENDING_REVIEW__' else
                actual_line or '(no output)'
            ),
            'feedback': (
                'The program could not produce output; check the code and try again.'
                if out == '__ERROR__' else
                'The program exceeded the time limit; simplify the code and try again.'
                if out == '__TIMEOUT__' else
                'The output could not be verified and may need teacher review.'
                if out == '__PENDING_REVIEW__' else
                'This output line matches.' if correct else
                'This line does not match the expected output.'
            ),
        })

    return {'score': score, 'breakdown': breakdown}
