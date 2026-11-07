# backend/scores.py
"""
Student Total Score Aggregation
================================
Computes total scores per language, per difficulty, and overall.

Scoring rules:
- Each activity max = 10 points
- Easy:   2 activities × 10 = 20 pts
- Medium: 2 activities × 10 = 20 pts
- Hard:   1 activity × 10 = 10 pts
- Total per language: 50 pts
- Overall activity total: 3 languages × 50 = 150 pts

Score priority per activity:
  1. teacher_score (if not NULL)
  2. auto_score (fallback)
"""

from backend.module_awards import prefer_attempt_for_progress

ACTIVITY_DIFFICULTIES = {
    'php': {
        'easy': ('Hello, PHP!', 'Store a Name'),
        'medium': ('Subtract Two Numbers', 'Greater Than'),
        'hard': ('Repeat a Message Three Times',),
    },
    'javascript': {
        'easy': ('Hello, JavaScript!', 'Store and Display a Score'),
        'medium': ('Add Numbers', 'Greater Than'),
        'hard': ('Repeat a Message Five Times',),
    },
    'cpp': {
        'easy': ('Hello, C++!', 'Store an Age'),
        'medium': ('Multiply Two Numbers', 'Less Than'),
        'hard': ('Display Numbers 1 to 5',),
    },
}
ACTIVITY_LANGUAGES = ('php', 'javascript', 'cpp')
ASSESSMENT_LANGUAGES = ('python', 'java')
MAX_PER_ITEM = 10
MAX_ACTIVITY_LANGUAGE = 50
MAX_ASSESSMENT_LANGUAGE = 50
MAX_ACTIVITIES = 150
MAX_ASSESSMENTS = 100
MAX_OVERALL = MAX_ACTIVITIES + MAX_ASSESSMENTS
COMPLETED_ACTIVITY_ATTEMPT_STATUSES = {'submitted', 'completed', 'pending_review'}


def _attempt_points(row):
    """Return a normalized 0-10 score, including legacy raw-score rows."""
    teacher_score = row.get('teacher_score')
    auto_score = row.get('auto_score')
    raw_score = row.get('score')

    if teacher_score is not None:
        value = float(teacher_score)
    elif auto_score is not None and (float(auto_score) > 0 or not raw_score):
        value = float(auto_score)
    else:
        value = float(raw_score or 0)

    if value > MAX_PER_ITEM:
        value = round(value / 10)
    return min(max(int(value), 0), MAX_PER_ITEM)


def _effective_points(row):
    """Return the effective 0-10 score for a submitted assessment."""
    return _attempt_points(row)


def _pct(total, mx):
    if not mx:
        return 0
    return round(total / mx * 100)


def _activity_attempt_points(row):
    return _attempt_points(row)


def get_student_activity_scores(cursor, student_id):
    """Return the student's completed PHP, JavaScript, and C++ assessment activities."""
    scores = {}

    cursor.execute(
        """
        SELECT a.language, a.assessment_number, aa.score, aa.auto_score,
               aa.teacher_score, aa.status
        FROM assessment_attempts aa
        JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
        WHERE aa.student_id = %s
          AND a.language IN ('php', 'javascript', 'cpp')
          AND a.assessment_number BETWEEN 1 AND 5
        ORDER BY aa.id
        """,
        (student_id,),
    )
    attempts = {}
    for row in cursor.fetchall():
        key = ((row.get('language') or '').lower(), int(row.get('assessment_number') or 0))
        attempts[key] = prefer_attempt_for_progress(attempts.get(key), row)

    for row in attempts.values():
        language = (row.get('language') or '').lower()
        status = (row.get('status') or '').lower()
        if language not in ACTIVITY_DIFFICULTIES:
            continue
        if status not in COMPLETED_ACTIVITY_ATTEMPT_STATUSES and row.get('teacher_score') is None:
            continue

        number = int(row.get('assessment_number') or 0)
        activities = [
            (difficulty, name)
            for difficulty, names in ACTIVITY_DIFFICULTIES[language].items()
            for name in names
        ]
        if number < 1 or number > len(activities):
            continue
        _, activity_name = activities[number - 1]
        scores[(language, activity_name)] = _activity_attempt_points(row)

    results = []
    for language, difficulties in ACTIVITY_DIFFICULTIES.items():
        assessment_number = 0
        for difficulty, names in difficulties.items():
            for activity_name in names:
                assessment_number += 1
                key = (language, activity_name)
                if key not in scores:
                    continue
                results.append({
                    'language': language,
                    'name': activity_name,
                    'difficulty': difficulty,
                    'activity_number': assessment_number,
                    'score': scores[key],
                    'max_score': MAX_PER_ITEM,
                    'completed': True,
                    'status': 'COMPLETED',
                })
    return results


def get_student_total_scores(cursor, student_id):
    """Return a structured summary of a student's total scores."""
    activities = {
        lang: {
            'total': 0,
            'max': MAX_ACTIVITY_LANGUAGE,
            'percentage': 0,
            'by_difficulty': {
                difficulty: {
                    'total': 0,
                    'max': len(names) * MAX_PER_ITEM,
                    'percentage': 0,
                }
                for difficulty, names in groups.items()
            },
        }
        for lang in ACTIVITY_LANGUAGES
        for groups in [ACTIVITY_DIFFICULTIES.get(lang, {})]
    }
    assessments = {
        lang: {'total': 0, 'max': MAX_ASSESSMENT_LANGUAGE, 'percentage': 0}
        for lang in ASSESSMENT_LANGUAGES
    }

    for row in get_student_activity_scores(cursor, student_id):
        lang = row['language']
        difficulty = row['difficulty']
        points = row['score']
        activities[lang]['total'] += points
        activities[lang]['by_difficulty'][difficulty]['total'] += points

    cursor.execute(
        """
        SELECT a.language, aa.score, aa.auto_score, aa.teacher_score
        FROM assessment_attempts aa
        JOIN learning_items a ON a.id = aa.assessment_id AND a.language = aa.language
        WHERE aa.student_id = %s AND aa.status = 'submitted'
          AND a.language IN ('python', 'java')
        """,
        (student_id,),
    )
    for row in cursor.fetchall():
        lang = (row.get('language') or '').lower()
        if lang in assessments:
            assessments[lang]['total'] += _effective_points(row)

    for language_data in activities.values():
        language_data['percentage'] = _pct(language_data['total'], language_data['max'])
        for difficulty_data in language_data['by_difficulty'].values():
            difficulty_data['percentage'] = _pct(difficulty_data['total'], difficulty_data['max'])

    for language_data in assessments.values():
        language_data['percentage'] = _pct(language_data['total'], language_data['max'])

    activities_total = sum(item['total'] for item in activities.values())
    assessments_total = sum(item['total'] for item in assessments.values())
    overall_total = activities_total + assessments_total

    return {
        'overall': {
            'total': overall_total,
            'max': MAX_OVERALL,
            'percentage': _pct(overall_total, MAX_OVERALL),
        },
        'activities': {
            'total': activities_total,
            'max': MAX_ACTIVITIES,
            'percentage': _pct(activities_total, MAX_ACTIVITIES),
            'by_language': activities,
        },
        'assessments': {
            'total': assessments_total,
            'max': MAX_ASSESSMENTS,
            'percentage': _pct(assessments_total, MAX_ASSESSMENTS),
            'by_language': assessments,
        },
    }