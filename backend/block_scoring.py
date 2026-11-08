"""Blockly structure and program-output scoring for coding submissions."""
import math
import re
import xml.etree.ElementTree as ET

from backend.module_scoring import score_output_breakdown

BLOCK_TYPES = {
    'output': {
        'python': {'text_print'},
        'java': {'java_print'},
        'php': {'php_echo'},
        'javascript': {'js_print'},
        'cpp': {'cpp_cout'},
    },
    'text': {
        'python': {'text'},
        'java': {'text'},
        'php': {'php_text'},
        'javascript': {'js_text'},
        'cpp': {'cpp_text'},
    },
    'variable_set': {
        'python': {'variables_set'},
        'java': {'java_variable'},
        'php': {'php_variable'},
        'javascript': {'js_set'},
        'cpp': {'cpp_variable'},
    },
    'variable_get': {
        'python': {'variables_get', 'pnhs_variables_get'},
        'java': {'java_variable_get'},
        'php': {'php_variable_get'},
        'javascript': {'js_get'},
        'cpp': {'cpp_variable_get'},
    },
    'number': {
        'python': {'math_number'},
        'java': {'math_number'},
        'php': {'php_number'},
        'javascript': {'js_number'},
        'cpp': {'cpp_number'},
    },
    'math_operation': {
        'python': {'math_arithmetic'},
        'java': {'math_arithmetic'},
        'php': {'php_math_operation'},
        'javascript': {'js_math'},
        'cpp': {'cpp_math_operation'},
    },
    'comparison': {
        'python': {'logic_compare'},
        'java': {'logic_compare'},
        'php': {'php_compare'},
        'javascript': {'js_compare'},
        'cpp': {'cpp_compare'},
    },
    'conditional': {
        'python': {'controls_if'},
        'java': {'java_if'},
        'php': {'php_if', 'php_if_elseif'},
        'javascript': {'js_if'},
        'cpp': {'cpp_if'},
    },
    'loop': {
        'python': {'controls_for', 'controls_while', 'pnhs_controls_for'},
        'java': {'java_for', 'java_while'},
        'php': {'php_for', 'php_while'},
        'javascript': {'js_for', 'js_while'},
        'cpp': {'cpp_for', 'cpp_while', 'cpp_do_while'},
    },
    'function_definition': {
        'python': {
            'procedures_defnoreturn',
            'procedures_defreturn',
            'python_function_def',
        },
        'java': {'java_method'},
        'php': {'php_function_def'},
        'javascript': {'js_function_def'},
        'cpp': {'cpp_function_def'},
    },
    'function_call': {
        'python': {
            'procedures_callnoreturn',
            'procedures_callreturn',
            'python_function_call',
        },
        'java': {'java_method_call'},
        'php': {'php_function_call'},
        'javascript': {'js_function_call', 'js_function_call_value'},
        'cpp': {'cpp_function_call'},
    },
    'return': {
        'python': {'procedures_defreturn'},
        'java': {'java_return'},
        'php': {'php_return'},
        'javascript': {'js_return'},
        'cpp': {'cpp_return'},
    },
}

MODULE_RUBRICS = {
    'php-01-variables': (
        'php', ['variable_set', 'variable_get', 'number', 'output'], 'age', None, ['16'], [],
    ),
    'php-02-conditionals': (
        'php',
        ['variable_set', 'variable_get', 'number', 'comparison', 'conditional', 'output', 'text'],
        'grade', None, ['88', '90', '75'], ['Excellent', 'Passed', 'Failed'],
    ),
    'python-01-basics': (
        'python', ['variable_set', 'variable_get', 'number', 'output'], 'age', None, ['16'], [],
    ),
    'python-02-loops': (
        'python', ['loop', 'variable_get', 'number', 'output'], 'i', None, ['1', '5'], [],
    ),
    'java-01-basics': (
        'java', ['variable_set', 'variable_get', 'number', 'output'], 'age', None, ['16'], [],
    ),
    'java-02-loops': (
        'java', ['loop', 'variable_get', 'number', 'output'], 'i', None, ['1', '5'], [],
    ),
    'js-01-variables': (
        'javascript', ['loop', 'number', 'text', 'output'], None, None, ['5'], ['I love programming!'],
    ),
    'js-02-functions': (
        'javascript',
        ['function_definition', 'return', 'math_operation', 'function_call', 'output', 'number'],
        None, 'multiply', ['6', '7'], [],
    ),
    'cpp-01-basics': (
        'cpp', ['loop', 'variable_get', 'number', 'output'], 'i', None, ['1', '5'], [],
    ),
    'cpp-02-loops': (
        'cpp', ['loop', 'variable_get', 'number', 'output'], 'i', None, ['1', '10'], [],
    ),
}

MODULE_OPERATORS = {
    'php-02-conditionals': {'comparison': 'GTE'},
    'js-02-functions': {'math_operation': 'MULTIPLY'},
}

REQUIRED_TOKEN_FAMILIES = (
    (re.compile(r'\b(?:print|cout|echo|console\.log|system\.out\.println)\b', re.I), 'output'),
    (re.compile(r'\btext\b', re.I), 'text'),
    (re.compile(r'\b(?:multiply|subtract|addition|add two numbers|math operation)\b|[+*]', re.I), 'math_operation'),
    (re.compile(r'\b(?:compare|less than|greater than|comparison)\b|[<>]', re.I), 'comparison'),
    (re.compile(r'\b(?:if-else|if statement|if)\b', re.I), 'conditional'),
    (re.compile(r'\b(?:for loop|while loop|loop)\b', re.I), 'loop'),
    (re.compile(r'\b(?:define function|create method|function definition)\b', re.I), 'function_definition'),
    (re.compile(r'\b(?:call function|call method|function call)\b', re.I), 'function_call'),
    (re.compile(r'\breturn\b', re.I), 'return'),
)


def _requirements_from_catalog(required_blocks):
    families = []
    for token in (required_blocks or '').split(','):
        token = token.strip()
        if not token:
            continue
        normalized_token = token.lower().replace('_', ' ').strip()
        if normalized_token in {'get variable', 'variable get'}:
            family = 'variable_get'
        elif normalized_token in {'set variable', 'create variable', 'int variable', 'var', 'variable'}:
            family = 'variable_set'
        elif re.fullmatch(r'number', normalized_token):
            family = 'number'
        else:
            family = None
        if family is None:
            for pattern, candidate_family in REQUIRED_TOKEN_FAMILIES:
                if pattern.search(token):
                    family = candidate_family
                    break
        if family and family not in families:
            families.append(family)
    if not families:
        families = ['output']
    return families


def _expected_variable_name(task_description, hint):
    text = f'{task_description or ""} {hint or ""}'
    patterns = (
        r'\bvariable named\s+\$?([A-Za-z_]\w*)',
        r'\b([A-Za-z_]\w*)\s+variable\s+with value\b',
        r'\bvariable\s+(?:called|named)\s+\$?([A-Za-z_]\w*)',
        r'\bfor\s+([A-Za-z_]\w*)\s+in\b',
        r'\bname\s+\$?([A-Za-z_]\w*)\s+with value',
        r'\$([A-Za-z_]\w*)\s*=',
        r'\b(?:var|int|let|const)\s+([A-Za-z_]\w*)\s*=',
        r'\b([A-Za-z_]\w*)\s*=',
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _expected_function_name(task_description, hint):
    text = f'{task_description or ""} {hint or ""}'
    match = re.search(
        r'\b(?:function|method|def)\s+([A-Za-z_]\w*)\s*\(',
        text,
        re.I,
    )
    if not match:
        match = re.search(
            r'\b(?:void|int|double|String|bool)\s+([A-Za-z_]\w*)\s*\(',
            text,
            re.I,
        )
    return match.group(1) if match else None


def _expected_math_operator(task_description, hint):
    text = f'{task_description or ""} {hint or ""}'.lower()
    for words, operator in (
        (('multiply', 'multiplication'), 'MULTIPLY'),
        (('subtract', 'subtraction'), 'SUBTRACT'),
        (('add', 'addition', 'sum'), 'ADD'),
        (('divide', 'division'), 'DIVIDE'),
    ):
        if any(word in text for word in words):
            return operator
    return None


def _expected_comparison_operator(task_description, hint):
    text = f'{task_description or ""} {hint or ""}'.lower()
    for marker, operator in (
        ('>=', 'GTE'), ('<=', 'LTE'), ('>', 'GT'), ('<', 'LT'),
    ):
        if marker in text:
            return operator
    if 'greater than' in text:
        return 'GT'
    if 'less than' in text:
        return 'LT'
    return None


def _parse_block_types(code_blocks):
    try:
        root = ET.fromstring(code_blocks or '')
    except ET.ParseError:
        return []
    return [
        block for block in root.iter()
        if block.tag.rsplit('}', 1)[-1] in {'block', 'shadow'}
    ]


def _expected_numeric_values(task_description, hint, language=''):
    text = f'{task_description or ""} {hint or ""}'
    range_match = re.search(r'\brange\s*\(\s*(\d+)\s*,\s*(\d+)', text)
    if language == 'python' and range_match:
        start, stop = range_match.groups()
        return list(dict.fromkeys((start, str(max(int(stop) - 1, int(start))))))
    values = re.findall(r'(?<![A-Za-z_])\d+(?:\.\d+)?', text)
    repeat_match = re.search(
        r'\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+times\b',
        text,
        re.I,
    )
    if repeat_match:
        values.append(str({
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        }[repeat_match.group(1).lower()]))
    return list(dict.fromkeys(values))


def _expected_text_values(task_description, hint):
    text = f'{task_description or ""} {hint or ""}'
    quoted_values = re.findall(
        r'"([^"]+)"|(?<!\w)\'([^\'\n]+)\'(?!\w)',
        text,
    )
    return list(dict.fromkeys(
        value for quote_pair in quoted_values for value in quote_pair if value
    ))


def _field_values(block, names):
    return {
        (field.get('name') or '').upper(): (field.text or '').strip()
        for field in block
        if field.tag.rsplit('}', 1)[-1] == 'field'
        if (field.get('name') or '').upper() in names
    }


def _numeric_field_values(blocks):
    return {
        (field.text or '').strip()
        for block in blocks
        for field in block.iter()
        if field.tag.rsplit('}', 1)[-1] == 'field'
        and re.fullmatch(r'-?\d+(?:\.\d+)?', (field.text or '').strip())
    }


def _block_names(block):
    names = set(_field_values(block, {'NAME', 'VAR'}).values())
    names.update(
        (element.get('name') or '').strip()
        for element in block
        if element.tag.rsplit('}', 1)[-1] == 'mutation'
        and element.get('name')
    )
    return names


def normalize_breakdown_points(breakdown):
    """Normalize legacy score breakdowns and merge repeated ten-point criteria."""
    if not isinstance(breakdown, list):
        return breakdown
    total_max = sum(float(row.get('max_points') or 0) for row in breakdown)
    if (
        abs(total_max - 10) < 0.01
        and all(
            row.get('criterion_number') == index
            and row.get('criterion')
            and float(row.get('max_points') or 0).is_integer()
            and float(row.get('points_earned') or 0).is_integer()
            for index, row in enumerate(breakdown, start=1)
        )
    ):
        grouped = {}
        for row in breakdown:
            grouped.setdefault(row['criterion'], []).append(row)
        if all(len(rows) == 1 for rows in grouped.values()):
            return breakdown

        normalized = []
        for criterion, rows in grouped.items():
            points_earned = sum(int(row.get('points_earned') or 0) for row in rows)
            max_points = sum(int(row.get('max_points') or 0) for row in rows)
            criterion_correct = (
                all(row.get('correct') is True for row in rows)
                if criterion == 'Expected program output'
                else any(row.get('correct') is True for row in rows)
            )
            feedback = rows[0].get('feedback', '')
            if 0 < points_earned < max_points and criterion_correct:
                feedback = (
                    'This requirement is met, but not all allocated points were '
                    'awarded because the complete output did not match.'
                )
            normalized.append({
                **rows[0],
                'criterion_number': len(normalized) + 1,
                'criterion': criterion,
                'correct': criterion_correct,
                'points_earned': points_earned,
                'max_points': max_points,
                'feedback': feedback,
            })
        return normalized

    if total_max <= 0 or abs(total_max - 100) < 0.01:
        return breakdown

    scale = 100 / total_max
    normalized = []
    earned_so_far = 0
    max_so_far = 0
    for index, row in enumerate(breakdown):
        item = dict(row)
        if index == len(breakdown) - 1:
            item['max_points'] = round(100 - max_so_far, 2)
            item['points_earned'] = round(
                sum(float(entry.get('points_earned') or 0) for entry in breakdown) * scale
                - earned_so_far,
                2,
            )
        else:
            item['max_points'] = round(float(row.get('max_points') or 0) * scale, 2)
            item['points_earned'] = round(
                float(row.get('points_earned') or 0) * scale, 2,
            )
            max_so_far += item['max_points']
            earned_so_far += item['points_earned']
        normalized.append(item)
    return normalized


def _largest_remainder(total, weights):
    weight_sum = sum(weights)
    if not weights or total <= 0 or weight_sum <= 0:
        return [0] * len(weights)
    exact = [total * weight / weight_sum for weight in weights]
    allocated = [math.floor(value) for value in exact]
    remainder = total - sum(allocated)
    order = sorted(
        range(len(weights)),
        key=lambda index: (exact[index] - allocated[index], -index),
        reverse=True,
    )
    for index in order[:remainder]:
        allocated[index] += 1
    return allocated


def _ten_point_breakdown(breakdown, score, require_exact_module_output):
    """Convert weighted checks into distinct criteria totaling ten whole points."""
    rows = []
    output_rows = []
    for row in breakdown:
        if row['criterion'].startswith(('Output line ', 'Unexpected output line ')):
            output_rows.append(row)
        elif float(row.get('max_points') or 0) > 0:
            rows.append(row)
    if output_rows:
        matched_lines = sum(1 for row in output_rows if row.get('correct'))
        special_feedback = next(
            (
                row.get('feedback', '')
                for row in output_rows
                if 'teacher review' in row.get('feedback', '').lower()
                or 'could not produce output' in row.get('feedback', '').lower()
                or 'exceeded the time limit' in row.get('feedback', '').lower()
            ),
            None,
        )
        rows.append({
            'criterion': 'Expected program output',
            'correct': matched_lines == len(output_rows),
            'points_earned': sum(float(row.get('points_earned') or 0) for row in output_rows),
            'max_points': sum(float(row.get('max_points') or 0) for row in output_rows),
            'expected_answer': '\n'.join(
                row.get('expected_answer', '')
                for row in output_rows
                if not row['criterion'].startswith('Unexpected output line ')
            ).rstrip('\n'),
            'student_answer': '\n'.join(row.get('student_answer', '') for row in output_rows),
            'feedback': special_feedback or (
                'Every output line matches.'
                if matched_lines == len(output_rows)
                else f'{matched_lines} of {len(output_rows)} output lines match.'
            ),
        })

    if not rows:
        return [
            {
                'criterion_number': 1,
                'criterion': 'Meet the activity requirements',
                'correct': False,
                'points_earned': 0,
                'max_points': 10,
                'expected_answer': 'Meet the assessment requirements.',
                'student_answer': 'No scorable Blockly submission.',
                'feedback': 'Submit a Blockly solution to earn these points.',
            }
        ]

    weights = [float(row['max_points']) for row in rows]
    allocations = _largest_remainder(10, weights)
    exact_earned_points = []
    earned_points = []
    fractional_points = []
    for row, slot_count in zip(rows, allocations):
        max_points = float(row['max_points'])
        earned_ratio = min(
            max(float(row.get('points_earned') or 0) / max_points, 0),
            1,
        )
        exact_earned = slot_count * earned_ratio
        exact_earned_points.append(exact_earned)
        earned_points.append(math.floor(exact_earned))
        fractional_points.append(exact_earned - math.floor(exact_earned))

    target_points = min(
        max(math.floor(sum(exact_earned_points) + 0.5), 0),
        10,
    )
    if require_exact_module_output:
        target_points = min(target_points, max(math.floor(score / 10), 0))
    current_points = sum(earned_points)
    if current_points < target_points:
        order = sorted(
            range(len(rows)),
            key=lambda index: (
                fractional_points[index],
                float(rows[index].get('points_earned') or 0),
                -index,
            ),
            reverse=True,
        )
        for index in order:
            if current_points >= target_points:
                break
            if (
                earned_points[index] < allocations[index]
                and earned_points[index] < exact_earned_points[index]
            ):
                earned_points[index] += 1
                current_points += 1
    elif current_points > target_points:
        order = sorted(
            range(len(rows)),
            key=lambda index: (
                fractional_points[index],
                float(rows[index].get('points_earned') or 0),
                index,
            ),
        )
        for index in order:
            while earned_points[index] and current_points > target_points:
                earned_points[index] -= 1
                current_points -= 1

    result = []
    for row, max_points, points in zip(rows, allocations, earned_points):
        criterion_correct = bool(row.get('correct'))
        feedback = row.get('feedback', '')
        if (
            criterion_correct
            and points < max_points
            and require_exact_module_output
        ):
            feedback = (
                'This code requirement is met, but the complete output must match '
                'to earn full points.'
            )
        result.append({
            'criterion_number': len(result) + 1,
            'criterion': row['criterion'],
            'correct': criterion_correct,
            'points_earned': int(points),
            'max_points': int(max_points),
            'expected_answer': row.get('expected_answer', ''),
            'student_answer': row.get('student_answer', ''),
            'feedback': feedback,
        })

    return result


def score_block_submission(
    language,
    code_blocks,
    output,
    expected_output,
    max_points=10,
    required_blocks='',
    task_description='',
    hint='',
    module_id=None,
    case_insensitive=False,
):
    """Score required Blockly concepts (70%) and actual output (30%)."""
    language = (language or '').lower()
    parsed_blocks = _parse_block_types(code_blocks)
    present_types = {
        block.get('type') for block in parsed_blocks if block.get('type')
    }
    variable_name = _expected_variable_name(task_description, hint)
    function_name = _expected_function_name(task_description, hint)
    expected_numbers = _expected_numeric_values(task_description, hint, language)
    expected_text = _expected_text_values(task_description, hint)
    expected_math_operator = _expected_math_operator(task_description, hint)
    expected_comparison_operator = _expected_comparison_operator(task_description, hint)
    if module_id in MODULE_OPERATORS:
        operators = MODULE_OPERATORS[module_id]
        expected_math_operator = operators.get('math_operation', expected_math_operator)
        expected_comparison_operator = operators.get(
            'comparison', expected_comparison_operator,
        )
    if module_id in MODULE_RUBRICS:
        (
            rubric_language,
            families,
            rubric_variable,
            rubric_function,
            rubric_numbers,
            rubric_text,
        ) = MODULE_RUBRICS[module_id]
        if rubric_language != language:
            families = ['output']
        else:
            variable_name = rubric_variable or variable_name
            function_name = rubric_function or function_name
            expected_numbers = rubric_numbers
            expected_text = rubric_text
    else:
        families = _requirements_from_catalog(required_blocks)
    families = list(dict.fromkeys(families))

    block_weight = 70 if families else 0
    points_per_family = block_weight / len(families) if families else 0
    block_breakdown = []
    for index, family in enumerate(families):
        types = BLOCK_TYPES.get(family, {}).get(language, set())
        family_blocks = [
            block for block in parsed_blocks if block.get('type') in types
        ]
        correct = bool(family_blocks)
        if family == 'number' and expected_numbers:
            # Blockly may serialize numeric inputs on a parent block instead.
            number_values = _numeric_field_values(parsed_blocks)
            correct = set(expected_numbers).issubset(number_values)
        elif correct and family in {'variable_set', 'variable_get'} and variable_name:
            correct = any(
                variable_name in _block_names(block)
                for block in family_blocks
            )
        elif correct and family == 'loop' and variable_name:
            correct = any(
                variable_name in _block_names(block)
                for block in family_blocks
            )
        elif correct and family in {'function_definition', 'function_call'} and function_name:
            correct = any(
                function_name in _block_names(block)
                for block in family_blocks
            )
        elif correct and family == 'text' and expected_text:
            text_values = {
                value
                for block in family_blocks
                for value in _field_values(block, {'TEXT'}).values()
            }
            correct = set(expected_text).issubset(text_values)
        elif correct and family == 'math_operation' and expected_math_operator:
            correct = any(
                expected_math_operator in _field_values(block, {'OP'}).values()
                for block in family_blocks
            )
        elif correct and family == 'comparison' and expected_comparison_operator:
            correct = any(
                expected_comparison_operator in _field_values(block, {'OP'}).values()
                for block in family_blocks
            )

        points = round(points_per_family, 2) if correct else 0
        if index == len(families) - 1:
            points = round(block_weight - sum(
                row['max_points'] for row in block_breakdown
            ), 2) if correct else 0
        block_breakdown.append({
            'criterion': {
                'output': 'Use the required output block',
                'variable_set': 'Create the required variable',
                'variable_get': 'Read the required variable',
                'number': 'Use the required number values',
                'math_operation': 'Use the required math operation',
                'comparison': 'Use the required comparison',
                'conditional': 'Use the required conditional',
                'loop': 'Use the required loop',
                'text': 'Use the required text',
                'function_definition': 'Define the required function',
                'function_call': 'Call the required function',
                'return': 'Return the required value',
            }.get(family, f'Use the required {family.replace("_", " ")} code'),
            'correct': correct,
            'points_earned': points,
            'max_points': round(points_per_family, 2) if index < len(families) - 1
                else round(block_weight - sum(row['max_points'] for row in block_breakdown), 2),
            'expected_answer': (
                f'{family.replace("_", " ")} block'
                + (f' using "{variable_name}"' if family in {'variable_set', 'variable_get'} and variable_name else '')
                + (f' using "{variable_name}"' if family == 'loop' and variable_name else '')
                + (f' named "{function_name}"' if family in {'function_definition', 'function_call'} and function_name else '')
                + (f' with value(s) {", ".join(expected_numbers)}' if family == 'number' and expected_numbers else '')
                + (f' using "{expected_math_operator}"' if family == 'math_operation' and expected_math_operator else '')
                + (f' using "{expected_comparison_operator}"' if family == 'comparison' and expected_comparison_operator else '')
            ),
            'student_answer': (
                ', '.join(sorted(block.get('type') for block in family_blocks))
                + (
                    f' ({", ".join(sorted(_numeric_field_values(parsed_blocks)))})'
                    if family == 'number' and _numeric_field_values(parsed_blocks) else ''
                )
                if family_blocks else
                f'Numeric inputs found: {", ".join(sorted(_numeric_field_values(parsed_blocks)))}'
                if family == 'number' and _numeric_field_values(parsed_blocks) else
                'Required block not found'
            ),
            'feedback': (
                'Required block and name found.' if correct else
                f'Required block found, but use the expected name "{variable_name}".'
                if family_blocks and family in {'variable_set', 'variable_get'} and variable_name else
                f'Required block found, but use the expected function name "{function_name}".'
                if family_blocks and family in {'function_definition', 'function_call'} and function_name else
                f'Use the required numeric value(s): {", ".join(expected_numbers)}.'
                if family == 'number' and expected_numbers else
                f'Use the required text value(s): {", ".join(expected_text)}.'
                if family_blocks and family == 'text' and expected_text else
                f'Use the required operation: {expected_math_operator}.'
                if family_blocks and family == 'math_operation' and expected_math_operator else
                f'Use the required comparison: {expected_comparison_operator}.'
                if family_blocks and family == 'comparison' and expected_comparison_operator else
                'Add the required block type to your Blockly solution.'
            ),
        })

    output_weight = 30 if families else 100
    output_result = score_output_breakdown(
        output,
        expected_output,
        case_insensitive=case_insensitive,
        max_points=output_weight,
    )
    output_breakdown = output_result['breakdown']
    earned_points = sum(row['points_earned'] for row in block_breakdown + output_breakdown)
    score = round(earned_points) if max_points else 0
    if module_id and output_result['score'] < 100:
        score = min(score, 74)

    ten_point_breakdown = _ten_point_breakdown(
        block_breakdown + output_breakdown,
        score,
        bool(module_id and output_result['score'] < 100),
    )
    score = sum(row['points_earned'] for row in ten_point_breakdown) * 10
    return {'score': score, 'breakdown': ten_point_breakdown}
