from backend.verify import run_python


def test_run_python_executes_bounded_blockly_style_source():
    assert run_python('for number in range(1, 4):\n    print(number)') == '1\n2\n3'


def test_run_python_rejects_imports_and_attribute_access():
    assert run_python('import os\nprint(os.getcwd())') == '__ERROR__'
    assert run_python('print((1).__class__)') == '__ERROR__'