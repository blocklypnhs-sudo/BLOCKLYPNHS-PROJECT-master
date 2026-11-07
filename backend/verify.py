# backend/verify.py
"""
Server-side code execution for verified grading.
Only Python is executed. Other languages return '__PENDING_REVIEW__' upstream.
"""
import subprocess
import tempfile
import os
import sys
import ast
import math


MAX_SOURCE_LENGTH = 16000
MAX_OUTPUT_LENGTH = 4096
MAX_RANGE_ITEMS = 500
SAFE_CALLS = {'print', 'range', 'int', 'float', 'str', 'bool', 'len', 'abs', 'min', 'max', 'round'}
ALLOWED_NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.FunctionDef, ast.arguments,
    ast.Return, ast.If, ast.For, ast.Pass, ast.Break, ast.Continue,
    ast.Name, ast.Load, ast.Store, ast.Constant, ast.Call, ast.keyword,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Add, ast.Sub, ast.Div, ast.FloorDiv, ast.Mod,
    ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


class _StudentCodeValidator(ast.NodeVisitor):
    def __init__(self, function_names):
        self.function_names = function_names
        self.function_depth = 0
        self.visited_nodes = 0

    def generic_visit(self, node):
        self.visited_nodes += 1
        if self.visited_nodes > 1000 or not isinstance(node, ALLOWED_NODES):
            raise ValueError('Unsupported Python syntax')
        super().generic_visit(node)

    def visit_Name(self, node):
        if node.id.startswith('_'):
            raise ValueError('Private names are not allowed')
        self.generic_visit(node)

    def visit_Assign(self, node):
        if any(not isinstance(target, ast.Name) for target in node.targets):
            raise ValueError('Only simple variable assignments are allowed')
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if not isinstance(node.target, ast.Name):
            raise ValueError('Only simple variable assignments are allowed')
        self.generic_visit(node)

    def visit_For(self, node):
        if not isinstance(node.target, ast.Name):
            raise ValueError('Only simple loop variables are allowed')
        if not (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == 'range'
        ):
            raise ValueError('Loops must iterate over range()')
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if self.function_depth or node.decorator_list or node.args.args or node.args.kwonlyargs:
            raise ValueError('Only simple top-level functions are allowed')
        if node.name.startswith('_') or node.name in SAFE_CALLS:
            raise ValueError('Invalid function name')
        self.function_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self.function_depth -= 1

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ValueError('Only direct function calls are allowed')
        function_name = node.func.id
        if function_name not in SAFE_CALLS and function_name not in self.function_names:
            raise ValueError('Function is not allowed')
        if self.function_depth and function_name in self.function_names:
            raise ValueError('Calls between student-defined functions are not allowed')
        if any(keyword.arg not in {'sep', 'end'} for keyword in node.keywords):
            raise ValueError('Unsupported function argument')
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and len(node.value) > 2048:
            raise ValueError('String literal is too long')
        if isinstance(node.value, (int, float)):
            if not math.isfinite(node.value) or abs(node.value) > 1_000_000:
                raise ValueError('Numeric literal is out of range')
        elif not isinstance(node.value, (str, bool, type(None))):
            raise ValueError('Unsupported literal')
        self.generic_visit(node)


def _validate_student_code(source: str) -> None:
    if len(source) > MAX_SOURCE_LENGTH:
        raise ValueError('Source is too long')
    tree = ast.parse(source, mode='exec')
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    _StudentCodeValidator(function_names).visit(tree)


def _execution_wrapper(source: str) -> str:
    return f'''import builtins
import sys

_output_size = 0
def _limited_print(*values, sep=' ', end='\\n'):
    global _output_size
    text = sep.join(str(value) for value in values) + end
    _output_size += len(text)
    if _output_size > {MAX_OUTPUT_LENGTH}:
        raise ValueError('Output limit exceeded')
    sys.stdout.write(text)

def _limited_range(*args):
    values = range(*args)
    if len(values) > {MAX_RANGE_ITEMS}:
        raise ValueError('Loop limit exceeded')
    return values

_safe_builtins = {{
    'print': _limited_print,
    'range': _limited_range,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'len': len,
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
}}
_namespace = {{'__builtins__': _safe_builtins, '__name__': '__main__'}}
exec(compile({source!r}, '<student>', 'exec'), _namespace, _namespace)
'''


def run_python(source: str, timeout: int = 5) -> str:
    """
    Run a restricted Blockly-style Python subset with time, loop, and output limits.
    Unsupported or invalid source returns a failure sentinel for manual review.
    """
    path = None
    try:
        _validate_student_code(source)
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(_execution_wrapper(source))
            path = f.name
        result = subprocess.run(
            [sys.executable, '-I', path],
            capture_output=True,
            text=True,
            timeout=min(max(timeout, 1), 5),
        )
        if result.returncode != 0:
            return '__ERROR__'
        return (result.stdout or '').strip()
    except subprocess.TimeoutExpired:
        return '__TIMEOUT__'
    except Exception as exc:
        print(f"[verify] run_python error: {exc}")
        return '__ERROR__'
    finally:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except Exception:
                pass