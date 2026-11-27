from backend.verify import run_python


def test_run_python_executes_bounded_blockly_style_source():
    assert run_python('for number in range(1, 4):\n    print(number)') == '1\n2\n3'


def test_run_python_rejects_imports_and_attribute_access():
    assert run_python('import os\nprint(os.getcwd())') == '__ERROR__'
    assert run_python('print((1).__class__)') == '__ERROR__'


def test_run_python_accepts_blockly_while_loop():
    source = 'number = 1\nwhile number <= 3:\n    print(number)\n    number += 1'
    assert run_python(source) == '1\n2\n3'


def test_run_python_accepts_blockly_repeat_loop_variable():
    assert run_python('for _ in range(3):\n    print("repeat")') == (
        'repeat\nrepeat\nrepeat'
    )