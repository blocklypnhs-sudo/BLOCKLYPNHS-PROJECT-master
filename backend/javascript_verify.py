"""Safely interpret the JavaScript playground's supported Blockly blocks."""
import math
import re
import xml.etree.ElementTree as ET


MAX_XML_LENGTH = 16000
MAX_OUTPUT_LENGTH = 4096
MAX_STEPS = 2000
MAX_LOOP_ITERATIONS = 500
MAX_BLOCK_DEPTH = 50
MAX_FUNCTION_CALL_DEPTH = 20
_UNDEFINED = object()


class _ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class _JavaScriptBlocklyInterpreter:
    def __init__(self):
        self.output = []
        self.variables = {}
        self.functions = {}
        self.steps = 0
        self.call_depth = 0

    @staticmethod
    def _tag(element):
        return element.tag.rsplit('}', 1)[-1]

    def _step(self, depth):
        self.steps += 1
        if self.steps > MAX_STEPS or depth > MAX_BLOCK_DEPTH:
            raise ValueError('Execution limit exceeded')

    def _field(self, block, name, default=None):
        for child in block:
            if self._tag(child) == 'field' and child.get('name') == name:
                return child.text or ''
        if default is not None:
            return default
        raise ValueError('Missing block field')

    def _nested_block(self, block, container_tag, name=None):
        for child in block:
            if self._tag(child) == container_tag and (
                name is None or child.get('name') == name
            ):
                return next(
                    (nested for nested in child if self._tag(nested) in {'block', 'shadow'}),
                    None,
                )
        return None

    def _input(self, block, name):
        return self._nested_block(block, 'value', name)

    def _statement(self, block, name):
        return self._nested_block(block, 'statement', name)

    def _next(self, block):
        return self._nested_block(block, 'next')

    @staticmethod
    def _number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Expected a number')
        if not math.isfinite(value) or abs(value) > 1_000_000:
            raise ValueError('Number is out of range')
        return value

    @staticmethod
    def _format_number(value):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)

    def _value(self, block, depth=0, variables=None):
        if block is None:
            raise ValueError('Missing value block')
        variables = self.variables if variables is None else variables
        self._step(depth)
        block_type = block.get('type')

        if block_type == 'js_text':
            value = self._field(block, 'TEXT', '')
            if len(value) > 2048:
                raise ValueError('Text is too long')
            return value
        if block_type == 'js_number':
            raw = self._field(block, 'NUM', '0')
            value = float(raw) if any(char in raw.lower() for char in ('.', 'e')) else int(raw)
            return self._number(value)
        if block_type == 'js_get':
            name = self._field(block, 'NAME')
            if name not in variables:
                raise ValueError('Variable is not defined')
            return variables[name]
        if block_type == 'js_function_call_value':
            name = self._field(block, 'NAME')
            arguments = [
                self._value(self._input(block, input_name), depth + 1, variables)
                for input_name in ('ARG1', 'ARG2')
                if self._input(block, input_name) is not None
            ]
            return self._call_function(name, arguments, depth + 1, variables)
        if block_type == 'js_math':
            left = self._number(self._value(self._input(block, 'A'), depth + 1, variables))
            right = self._number(self._value(self._input(block, 'B'), depth + 1, variables))
            operation = self._field(block, 'OP')
            if operation == 'ADD':
                result = left + right
            elif operation == 'SUBTRACT':
                result = left - right
            elif operation == 'MULTIPLY':
                result = left * right
            elif operation == 'DIVIDE' and right != 0:
                result = left / right
            else:
                raise ValueError('Invalid arithmetic operation')
            return self._number(result)
        if block_type == 'js_compare':
            left = self._value(self._input(block, 'A'), depth + 1, variables)
            right = self._value(self._input(block, 'B'), depth + 1, variables)
            operation = self._field(block, 'OP')
            comparisons = {
                'EQ': lambda: left == right,
                'NEQ': lambda: left != right,
                'GT': lambda: left > right,
                'LT': lambda: left < right,
                'GTE': lambda: left >= right,
                'LTE': lambda: left <= right,
            }
            if operation not in comparisons:
                raise ValueError('Invalid comparison')
            return comparisons[operation]()
        raise ValueError('Unsupported value block')

    def _output_value(self, value):
        if value is _UNDEFINED:
            return 'undefined'
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (int, float)):
            return self._format_number(value)
        return str(value)

    def _call_function(self, name, arguments, depth, caller_variables):
        function = self.functions.get(name)
        if function is None or self.call_depth >= MAX_FUNCTION_CALL_DEPTH:
            raise ValueError('Function is undefined or recursion limit exceeded')
        parameters, body = function
        if len(arguments) != len(parameters):
            raise ValueError('Incorrect number of function arguments')
        local_variables = dict(caller_variables)
        local_variables.update(zip(parameters, arguments))
        self.call_depth += 1
        try:
            self._run_chain(body, depth + 1, local_variables, in_function=True)
        except _ReturnSignal as result:
            return result.value
        finally:
            self.call_depth -= 1
        return _UNDEFINED

    @staticmethod
    def _identifier(name):
        reserved = {
            'await', 'break', 'case', 'catch', 'class', 'const', 'continue',
            'debugger', 'default', 'delete', 'do', 'else', 'enum', 'export',
            'extends', 'false', 'finally', 'for', 'function', 'if', 'import',
            'in', 'instanceof', 'let', 'new', 'null', 'return', 'static',
            'super', 'switch', 'this', 'throw', 'true', 'try', 'typeof', 'var',
            'void', 'while', 'with', 'yield',
        }
        return bool(re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,63}', name)) and name not in reserved

    def _run_chain(self, block, depth=0, variables=None, in_function=False):
        variables = self.variables if variables is None else variables
        while block is not None:
            self._step(depth)
            block_type = block.get('type')

            if block_type == 'js_print':
                self.output.append(self._output_value(self._value(self._input(block, 'TEXT'), depth + 1, variables)))
            elif block_type == 'js_set':
                name = self._field(block, 'NAME')
                if not self._identifier(name):
                    raise ValueError('Invalid variable name')
                variables[name] = self._value(self._input(block, 'VALUE'), depth + 1, variables)
            elif block_type == 'js_if':
                condition = self._value(self._input(block, 'IF0'), depth + 1, variables)
                if not isinstance(condition, bool):
                    raise ValueError('Condition must be boolean')
                branch = 'DO0' if condition else 'ELSE'
                self._run_chain(self._statement(block, branch), depth + 1, variables, in_function)
            elif block_type == 'js_for':
                name = self._field(block, 'VAR')
                if not self._identifier(name):
                    raise ValueError('Invalid loop variable')
                start = self._number(self._value(self._input(block, 'FROM'), depth + 1, variables))
                end = self._number(self._value(self._input(block, 'TO'), depth + 1, variables))
                if not isinstance(start, int) or not isinstance(end, int):
                    raise ValueError('Loop bounds must be integers')
                condition = self._field(block, 'CONDITION', 'LTE')
                update = self._field(block, 'UPDATE', 'INC')
                if condition not in {'LTE', 'GTE'} or update not in {'INC', 'DEC', 'STEP_TWO'}:
                    raise ValueError('Invalid loop operation')
                value = start
                iterations = 0
                while (value <= end if condition == 'LTE' else value >= end):
                    if iterations >= MAX_LOOP_ITERATIONS:
                        raise ValueError('Loop limit exceeded')
                    variables[name] = value
                    self._run_chain(self._statement(block, 'DO'), depth + 1, variables, in_function)
                    value = variables[name] + (
                        -1 if update == 'DEC' else 2 if update == 'STEP_TWO' else 1
                    )
                    iterations += 1
            elif block_type in {'js_while', 'js_do_while'}:
                condition_name = 'CONDITION'
                condition_block = self._input(block, condition_name)
                iterations = 0
                while True:
                    if block_type == 'js_while':
                        condition = self._value(condition_block, depth + 1, variables)
                        if not isinstance(condition, bool):
                            raise ValueError('Condition must be boolean')
                        if not condition:
                            break
                    if iterations >= MAX_LOOP_ITERATIONS:
                        raise ValueError('Loop limit exceeded')
                    self._run_chain(self._statement(block, 'DO'), depth + 1, variables, in_function)
                    iterations += 1
                    if block_type == 'js_do_while':
                        condition = self._value(condition_block, depth + 1, variables)
                        if not isinstance(condition, bool):
                            raise ValueError('Condition must be boolean')
                        if not condition:
                            break
            elif block_type == 'js_increment':
                name = self._field(block, 'NAME')
                if name not in variables or isinstance(variables[name], bool) or not isinstance(variables[name], (int, float)):
                    raise ValueError('Increment target must be a number variable')
                variables[name] = self._number(variables[name] + 1)
            elif block_type == 'js_function_def':
                name = self._field(block, 'NAME')
                parameters = [
                    parameter for parameter in (
                        self._field(block, 'PARAM1', ''),
                        self._field(block, 'PARAM2', ''),
                    ) if parameter
                ]
                if not self._identifier(name) or any(
                    not self._identifier(parameter) for parameter in parameters
                ) or len(set(parameters)) != len(parameters):
                    raise ValueError('Invalid function name or parameter')
                self.functions[name] = (parameters, self._statement(block, 'BODY'))
            elif block_type == 'js_function_call':
                name = self._field(block, 'NAME')
                argument = self._input(block, 'ARG')
                arguments = [self._value(argument, depth + 1, variables)] if argument is not None else []
                self._call_function(name, arguments, depth + 1, variables)
            elif block_type == 'js_return':
                if not in_function:
                    raise ValueError('Return block must be inside a function')
                value_block = self._input(block, 'VALUE')
                value = self._value(value_block, depth + 1, variables) if value_block is not None else _UNDEFINED
                raise _ReturnSignal(value)
            else:
                raise ValueError('Unsupported statement block')

            if sum(map(len, self.output)) + max(0, len(self.output) - 1) > MAX_OUTPUT_LENGTH:
                raise ValueError('Output limit exceeded')
            block = self._next(block)

    def run(self, source):
        if not isinstance(source, str) or not source.strip() or len(source) > MAX_XML_LENGTH:
            raise ValueError('Invalid Blockly XML')
        if '<!DOCTYPE' in source.upper() or '<!ENTITY' in source.upper():
            raise ValueError('XML declarations are not allowed')
        root = ET.fromstring(source)
        if self._tag(root) != 'xml':
            raise ValueError('Invalid Blockly XML root')
        if sum(1 for node in root.iter() if self._tag(node) == 'block') > MAX_STEPS:
            raise ValueError('Too many blocks')
        for block in root:
            if self._tag(block) == 'block':
                self._run_chain(block)
        return '\n'.join(self.output)


def run_javascript_blocks(source):
    """Interpret supported JavaScript Blockly XML without executing source code."""
    try:
        return _JavaScriptBlocklyInterpreter().run(source)
    except Exception:
        return '__ERROR__'
