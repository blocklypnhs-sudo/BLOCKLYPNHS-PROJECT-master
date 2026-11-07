# backend/module_scoring.py
"""Scoring for module final assessments (partial credit, pass mark 75)."""
from backend.module_awards import PASS_THRESHOLD

# A non-exact answer can never reach the pass mark, however many lines match.
MAX_PARTIAL_SCORE = PASS_THRESHOLD - 1


def score_module_output(output, expected, case_insensitive=False):
    """
    Return a 0-100 score comparing a student's output with the expected output.
    Exact match = 100. Otherwise partial credit = share of lines that match in
    position, capped below the pass mark so only a correct answer passes.
    """
    out = (output or '').replace('\r\n', '\n').strip()
    exp = (expected or '').replace('\r\n', '\n').strip()
    if case_insensitive:
        out, exp = out.casefold(), exp.casefold()
    if out == exp:
        return 100
    if not out or out in {'__ERROR__', '__TIMEOUT__', '__PENDING_REVIEW__'}:
        return 0
    out_lines = [l.rstrip() for l in out.split('\n')]
    exp_lines = [l.rstrip() for l in exp.split('\n')]
    matched = sum(1 for a, b in zip(out_lines, exp_lines) if a == b)
    partial = round(100 * matched / max(len(out_lines), len(exp_lines), 1))
    return min(partial, MAX_PARTIAL_SCORE)
