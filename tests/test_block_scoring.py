import pytest

from backend.block_scoring import (
    BLOCK_TYPES,
    MODULE_OPERATORS,
    MODULE_RUBRICS,
    _expected_comparison_operator,
    _expected_function_name,
    _expected_math_operator,
    _expected_numeric_values,
    _expected_text_values,
    _expected_variable_name,
    _requirements_from_catalog,
    normalize_breakdown_points,
    score_block_submission,
)

def _python_variable_workspace(name):
    return (
        '<xml><block type="variables_set"><field name="VAR">'
        f'{name}</field><value name="VALUE"><block type="text">'
        '<field name="TEXT">Juan</field></block></value><next>'
        '<block type="text_print"><value name="TEXT"><block type="variables_get">'
        f'<field name="VAR">{name}</field></block></value></block></next></block></xml>'
    )


def _module_workspace(module_id):
    language, families, variable_name, function_name, numbers, texts = MODULE_RUBRICS[module_id]
    blocks = []
    for family in families:
        available_types = BLOCK_TYPES[family][language]
        block_type = (
            'php_if_elseif'
            if module_id == 'php-02-conditionals' and family == 'conditional'
            else sorted(available_types)[0]
        )
        fields = []
        if family in {'variable_set', 'variable_get', 'loop'} and variable_name:
            field_name = 'VAR' if family == 'loop' or language == 'python' else 'NAME'
            fields.append(f'<field name="{field_name}">{variable_name}</field>')
        if family in {'function_definition', 'function_call'} and function_name:
            fields.append(f'<field name="NAME">{function_name}</field>')
        if family == 'number':
            fields.extend(f'<field name="NUM">{value}</field>' for value in numbers)
        if family == 'text':
            if texts:
                blocks.extend(
                    f'<block type="{block_type}"><field name="TEXT">{value}</field></block>'
                    for value in texts
                )
                continue
            fields.append('<field name="TEXT">sample</field>')
        if family == 'math_operation':
            fields.append(
                f'<field name="OP">{MODULE_OPERATORS[module_id][family]}</field>'
            )
        if family == 'comparison':
            fields.append(
                f'<field name="OP">{MODULE_OPERATORS[module_id][family]}</field>'
            )
        blocks.append(f'<block type="{block_type}">{"".join(fields)}</block>')
    return f'<xml>{"".join(blocks)}</xml>'


def _activity_workspace(language, families, description, hint):
    variable_name = _expected_variable_name(description, hint)
    function_name = _expected_function_name(description, hint)
    numbers = _expected_numeric_values(description, hint, language)
    texts = _expected_text_values(description, hint)
    math_operator = _expected_math_operator(description, hint)
    comparison_operator = _expected_comparison_operator(description, hint)
    blocks = []
    for family in families:
        block_type = sorted(BLOCK_TYPES[family][language])[0]
        fields = []
        if family in {'variable_set', 'variable_get'} and variable_name:
            fields.append(f'<field name="NAME">{variable_name}</field>')
            fields.append(f'<field name="VAR">{variable_name}</field>')
        if family == 'loop' and variable_name:
            fields.append(f'<field name="VAR">{variable_name}</field>')
        if family in {'function_definition', 'function_call'} and function_name:
            fields.append(f'<field name="NAME">{function_name}</field>')
        if family == 'number':
            fields.extend(
                f'<field name="NUM">{value}</field>' for value in (numbers or ['1'])
            )
        if family == 'text':
            blocks.extend(
                f'<block type="{block_type}"><field name="TEXT">{value}</field></block>'
                for value in (texts or ['sample'])
            )
            continue
        if family == 'math_operation':
            fields.append(f'<field name="OP">{math_operator or "ADD"}</field>')
        if family == 'comparison':
            fields.append(f'<field name="OP">{comparison_operator or "GT"}</field>')
        blocks.append(f'<block type="{block_type}">{"".join(fields)}</block>')
    return f'<xml>{"".join(blocks)}</xml>'


def test_correct_variable_name_receives_full_activity_score():
    result = score_block_submission(
        'python',
        _python_variable_workspace('name'),
        'Juan',
        'Juan',
        required_blocks='SET VARIABLE,PRINT,TEXT,GET VARIABLE',
        task_description='Understanding variables, strings, integers, and type conversion.',
        hint='Use name = "Juan" then print(name).',
    )

    assert result['score'] == 100
    assert len(result['breakdown']) == 5
    assert len({item['criterion'] for item in result['breakdown']}) == len(result['breakdown'])
    assert all(isinstance(item['max_points'], int) for item in result['breakdown'])
    assert all(item['correct'] for item in result['breakdown'])
    assert sum(item['points_earned'] for item in result['breakdown']) == 10
    assert sum(item['max_points'] for item in result['breakdown']) == 10


def test_wrong_variable_name_loses_structure_points_with_correct_output():
    result = score_block_submission(
        'python',
        _python_variable_workspace('studentName'),
        'Juan',
        'Juan',
        required_blocks='SET VARIABLE,PRINT,TEXT,GET VARIABLE',
        task_description='Understanding variables, strings, integers, and type conversion.',
        hint='Use name = "Juan" then print(name).',
    )

    assert result['score'] == 70
    name_criteria = [
        item for item in result['breakdown']
        if item['criterion'] in {
            'Create the required variable',
            'Read the required variable',
        }
    ]
    assert name_criteria
    assert all(item['points_earned'] == 0 for item in name_criteria)
    assert all('expected name "name"' in item['feedback'] for item in name_criteria)


def test_python_module_loop_supports_custom_module_block_types():
    workspace = (
        '<xml><block type="pnhs_controls_for"><field name="VAR">i</field>'
        '<value name="FROM"><block type="math_number"><field name="NUM">1</field></block></value>'
        '<value name="TO"><block type="math_number"><field name="NUM">5</field></block></value>'
        '<statement name="DO"><block type="text_print"><value name="TEXT">'
        '<block type="pnhs_variables_get"><field name="VAR">i</field></block>'
        '</value></block></statement></block></xml>'
    )
    expected_output = '1\n2\n3\n4\n5'

    result = score_block_submission(
        'python',
        workspace,
        expected_output,
        expected_output,
        module_id='python-02-loops',
    )

    assert result['score'] == 100
    assert all(item['correct'] for item in result['breakdown'])


def test_java_loop_number_values_are_scored_when_serialized_on_loop_block():
    workspace = (
        '<xml><block type="java_for"><field name="VAR">i</field>'
        '<field name="FROM">1</field><field name="TO">5</field>'
        '<statement name="DO"><block type="java_print"><value name="TEXT">'
        '<block type="java_variable_get"><field name="NAME">i</field></block>'
        '</value></block></statement></block></xml>'
    )
    result = score_block_submission(
        'java',
        workspace,
        '1\n2\n3\n4\n5',
        '1\n2\n3\n4\n5',
        module_id='java-02-loops',
    )

    number_criterion = next(
        item for item in result['breakdown']
        if item['criterion'] == 'Use the required number values'
    )
    assert number_criterion['correct'] is True
    assert 'Required block not found' not in number_criterion['student_answer']
    assert number_criterion['points_earned'] == number_criterion['max_points']
    assert isinstance(number_criterion['max_points'], int)


def test_java_loop_number_shadow_blocks_are_recognized():
    workspace = (
        '<xml><block type="java_for"><field name="VAR">i</field>'
        '<value name="FROM"><shadow type="math_number"><field name="NUM">1</field></shadow></value>'
        '<value name="TO"><shadow type="math_number"><field name="NUM">5</field></shadow></value>'
        '<statement name="DO"><block type="java_print"><value name="TEXT">'
        '<block type="java_variable_get"><field name="NAME">i</field></block>'
        '</value></block></statement></block></xml>'
    )
    result = score_block_submission(
        'java',
        workspace,
        '1\n2\n3\n4\n5',
        '1\n2\n3\n4\n5',
        module_id='java-02-loops',
    )

    number_criterion = next(
        item for item in result['breakdown']
        if item['criterion'] == 'Use the required number values'
    )
    assert number_criterion['correct'] is True
    assert number_criterion['student_answer'] == 'math_number, math_number (1, 5)'


def test_module_variable_name_is_part_of_the_required_structure_score():
    workspace = (
        '<xml><block type="variables_set"><field name="VAR">studentAge</field>'
        '<value name="VALUE"><block type="math_number"><field name="NUM">16</field></block></value>'
        '<next><block type="text_print"><value name="TEXT"><block type="variables_get">'
        '<field name="VAR">studentAge</field></block></value></block></next></block></xml>'
    )
    result = score_block_submission(
        'python',
        workspace,
        '16',
        '16',
        module_id='python-01-basics',
    )

    assert result['score'] == 60
    variable_criteria = [
        item for item in result['breakdown']
        if item['criterion'] in {
            'Create the required variable',
            'Read the required variable',
        }
    ]
    assert variable_criteria
    assert all(item['points_earned'] == 0 for item in variable_criteria)


def test_module_output_weight_and_partial_output_cannot_award_a_pass():
    workspace = (
        '<xml><block type="pnhs_controls_for"><field name="VAR">i</field>'
        '<value name="FROM"><block type="math_number"><field name="NUM">1</field></block></value>'
        '<value name="TO"><block type="math_number"><field name="NUM">5</field></block></value>'
        '<statement name="DO"><block type="text_print"><value name="TEXT">'
        '<block type="pnhs_variables_get"><field name="VAR">i</field></block>'
        '</value></block></statement></block></xml>'
    )
    result = score_block_submission(
        'python',
        workspace,
        '1\n2\nwrong\n4\n5',
        '1\n2\n3\n4\n5',
        module_id='python-02-loops',
    )

    assert result['score'] == 70
    assert len(result['breakdown']) == 5
    assert len({item['criterion'] for item in result['breakdown']}) == len(result['breakdown'])
    assert sum(item['max_points'] for item in result['breakdown']) == 10
    assert all(
        isinstance(item['points_earned'], int) and isinstance(item['max_points'], int)
        for item in result['breakdown']
    )
    assert sum(item['points_earned'] for item in result['breakdown']) == 7
    code_criteria = [
        item for item in result['breakdown']
        if item['criterion'] != 'Expected program output'
    ]
    assert all(item['correct'] for item in code_criteria)
    assert not next(
        item for item in result['breakdown']
        if item['criterion'] == 'Expected program output'
    )['correct']


def test_legacy_breakdown_points_are_scaled_to_100():
    legacy = [
        {'criterion': 'Required block', 'points_earned': 1.75, 'max_points': 1.75},
        {'criterion': 'Output', 'points_earned': 0.6, 'max_points': 0.6},
    ]

    result = normalize_breakdown_points(legacy)

    assert [row['max_points'] for row in result] == [74.47, 25.53]
    assert [row['points_earned'] for row in result] == [74.47, 25.53]
    assert sum(row['max_points'] for row in result) == 100
    assert sum(row['points_earned'] for row in result) == 100


def test_ten_point_breakdown_is_not_rescaled_as_legacy_data():
    current = [
        {
            'criterion_number': index,
            'criterion': f'Criterion {index}',
            'points_earned': 1,
            'max_points': 1,
        }
        for index in range(1, 11)
    ]

    assert normalize_breakdown_points(current) == current


def test_legacy_repeated_criteria_are_merged_without_fractional_points():
    legacy = [
        {
            'criterion_number': index,
            'criterion': 'Expected program output' if index > 7 else 'Use the required loop',
            'correct': index != 10,
            'points_earned': 1 if index != 10 else 0,
            'max_points': 1,
        }
        for index in range(1, 11)
    ]

    result = normalize_breakdown_points(legacy)

    assert [row['criterion'] for row in result] == [
        'Use the required loop',
        'Expected program output',
    ]
    assert [row['points_earned'] for row in result] == [7, 2]
    assert [row['max_points'] for row in result] == [7, 3]
    assert result[1]['correct'] is False
    assert sum(row['points_earned'] for row in result) == 9


def test_weighted_ten_point_breakdown_keeps_unique_integer_criteria():
    current = [
        {
            'criterion_number': 1,
            'criterion': 'Use the required output block',
            'points_earned': 6,
            'max_points': 6,
        },
        {
            'criterion_number': 2,
            'criterion': 'Expected program output',
            'points_earned': 4,
            'max_points': 4,
        },
    ]

    assert normalize_breakdown_points(current) == current


def test_simple_activity_has_distinct_code_and_output_criteria():
    result = score_block_submission(
        'php',
        '<xml><block type="php_echo"><value name="TEXT">'
        '<block type="php_text"><field name="TEXT">Hello</field></block>'
        '</value></block></xml>',
        'Hello',
        'Hello',
        required_blocks='echo,TEXT',
        task_description='Print "Hello".',
    )
    criteria = result['breakdown']

    assert [row['criterion'] for row in criteria] == [
        'Use the required output block',
        'Use the required text',
        'Expected program output',
    ]
    assert sum(row['max_points'] for row in criteria) == 10
    assert sum(row['points_earned'] for row in criteria) == 10
    assert all(
        isinstance(row['points_earned'], int)
        and isinstance(row['max_points'], int)
        for row in criteria
    )


def test_python_functions_assessment_recognizes_custom_definition_and_call_blocks():
    workspace = (
        '<xml>'
        '<block type="python_function_def">'
        '<field name="NAME">greet</field>'
        '<statement name="STACK">'
        '<block type="text_print">'
        '<value name="TEXT"><block type="text">'
        '<field name="TEXT">Welcome to BlockLearn!</field>'
        '</block></value></block>'
        '</statement>'
        '<next><block type="python_function_call">'
        '<mutation name="greet"></mutation>'
        '<field name="NAME">greet</field>'
        '</block></next></block>'
        '</xml>'
    )
    result = score_block_submission(
        'python',
        workspace,
        'Welcome to BlockLearn!',
        'Welcome to BlockLearn!',
        required_blocks='DEFINE FUNCTION,PRINT,CALL FUNCTION,TEXT',
        task_description='Create and use a Python function named greet.',
        hint='Define def greet() then call greet().',
    )

    assert result['score'] == 100
    assert all(item['correct'] for item in result['breakdown'])
    assert [item['criterion'] for item in result['breakdown']] == [
        'Define the required function',
        'Use the required output block',
        'Call the required function',
        'Use the required text',
        'Expected program output',
    ]


@pytest.mark.parametrize(
    ('module_id', 'output'),
    [
        ('php-01-variables', '16'),
        ('php-02-conditionals', 'Passed'),
        ('python-01-basics', '16'),
        ('python-02-loops', '1\n2\n3\n4\n5'),
        ('java-01-basics', '16'),
        ('java-02-loops', '1\n2\n3\n4\n5'),
        (
            'js-01-variables',
            'I love programming!\nI love programming!\nI love programming!\n'
            'I love programming!\nI love programming!',
        ),
        ('js-02-functions', '42'),
        ('cpp-01-basics', '1\n2\n3\n4\n5'),
        ('cpp-02-loops', '1\n2\n3\n4\n5\n6\n7\n8\n9\n10'),
    ],
)
def test_each_module_rubric_recognizes_its_required_blocks_and_values(module_id, output):
    language = MODULE_RUBRICS[module_id][0]
    result = score_block_submission(
        language,
        _module_workspace(module_id),
        output,
        output,
        module_id=module_id,
        case_insensitive=(language == 'javascript'),
    )

    assert result['score'] == 100
    assert len({item['criterion'] for item in result['breakdown']}) == len(result['breakdown'])
    assert sum(item['max_points'] for item in result['breakdown']) == 10
    assert all(
        isinstance(item['points_earned'], int) and isinstance(item['max_points'], int)
        for item in result['breakdown']
    )
    assert all(item['correct'] for item in result['breakdown'])


@pytest.mark.parametrize(
    ('language', 'required_blocks', 'description', 'hint', 'output'),
    [
        ('php', 'echo,TEXT', 'Print Hello, PHP! to the console.', 'Use echo "Hello, PHP!".', 'Hello, PHP!'),
        ('php', 'variable,echo,TEXT,GET VARIABLE', 'Create a name variable and display it.', 'Use $name = "Caryll" then echo $name.', 'Caryll'),
        ('php', 'echo,SUBTRACT,NUMBER', 'Subtract 50 from 80 and display the result.', 'Use echo 80 - 50.', '30'),
        ('php', 'if,>,echo,NUMBER,TEXT', 'Check whether 25 is greater than 18 and print the message.', 'Use if (25 > 18) with echo.', '25 is greater than 18'),
        ('php', 'FOR LOOP,echo,NUMBER,TEXT', 'Display Learning PHP! three times using a loop.', 'Use a loop that repeats three times.', 'Learning PHP!\nLearning PHP!\nLearning PHP!'),
        ('javascript', 'console.log,TEXT', 'Print Hello, JavaScript! to the console.', 'Use console.log("Hello, JavaScript!");', 'Hello, JavaScript!'),
        ('javascript', 'var,console.log,NUMBER,variable_get', 'Create a score variable with value 90 and print it.', 'Use var score = 90; then console.log(score);', '90'),
        ('javascript', 'console.log,+,NUMBER', 'Add 25 and 15 and print the result.', 'Use console.log(25 + 15);', '40'),
        ('javascript', 'if,>,console.log,NUMBER,TEXT', 'Check whether 20 is greater than 10 and print the message.', 'Use if (20 > 10) with console.log inside.', '20 is greater than 10'),
        ('javascript', 'for loop,console.log,NUMBER,TEXT', 'Print I love programming! five times with a loop.', 'Use a for loop that repeats 5 times.', 'I love programming!\nI love programming!\nI love programming!\nI love programming!\nI love programming!'),
        ('cpp', 'cout,TEXT', 'Print Hello, C++! to the console.', 'Use cout << "Hello, C++!";', 'Hello, C++!'),
        ('cpp', 'int variable,cout,NUMBER,GET VARIABLE', 'Create an age variable with value 17 and print it.', 'Use int age = 17; then cout << age;', '17'),
        ('cpp', 'cout,MULTIPLY,NUMBER', 'Multiply 6 by 5 and print the result.', 'Use cout << 6 * 5;', '30'),
        ('cpp', 'if,LESS THAN,cout,NUMBER,TEXT', 'Check whether 15 is less than 20 and print the message.', 'Use if (15 < 20) with cout inside.', '15 is less than 20'),
        ('cpp', 'FOR LOOP,cout,NUMBER,GET VARIABLE', 'Display numbers 1 to 5 using a for loop.', 'Use for (int i = 1; i <= 5; i++).', '1\n2\n3\n4\n5'),
    ],
)
def test_activity_catalog_rubrics_recognize_the_required_blocks_and_values(
    language, required_blocks, description, hint, output,
):
    families = _requirements_from_catalog(required_blocks)
    result = score_block_submission(
        language,
        _activity_workspace(language, families, description, hint),
        output,
        output,
        required_blocks=required_blocks,
        task_description=description,
        hint=hint,
    )

    assert result['score'] == 100
    assert len({item['criterion'] for item in result['breakdown']}) == len(result['breakdown'])
    assert sum(item['max_points'] for item in result['breakdown']) == 10
    assert all(
        isinstance(item['points_earned'], int) and isinstance(item['max_points'], int)
        for item in result['breakdown']
    )
    assert all(item['correct'] for item in result['breakdown'])
