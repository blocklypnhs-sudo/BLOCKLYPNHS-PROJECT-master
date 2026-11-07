"""Safely interpret the Java playground's supported Blockly blocks for grading."""
import math
import re
import xml.etree.ElementTree as ET


MAX_XML_LENGTH = 16000
MAX_OUTPUT_LENGTH = 4096
MAX_STEPS = 2000
MAX_LOOP_ITERATIONS = 500
MAX_BLOCK_DEPTH = 50


class _JavaBlocklyInterpreter:
    def __init__(self):
        self.output = []
        self.methods = {}
        self.steps = 0

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

    def _input(self, block, name):
        for child in block:
            if self._tag(child) == 'value' and child.get('name') == name:
                return next(
                    (nested for nested in child if self._tag(nested) in {'block', 'shadow'}),
                    None,
                )
        return None

    def _statement(self, block, name):
        for child in block:
            if self._tag(child) == 'statement' and child.get('name') == name:
                return next(
                    (nested for nested in child if self._tag(nested) == 'block'),
                    None,
                )
        return None

    def _next(self, block):
        for child in block:
            if self._tag(child) == 'next':
                return next(
                    (nested for nested in child if self._tag(nested) == 'block'),
                    None,
                )
        return None

    @staticmethod
    def _number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Expected a number')
        if not math.isfinite(value) or abs(value) > 1_000_000:
            raise ValueError('Number is out of range')
        return value

    def _value(self, block, variables, depth=0):
        if block is None:
            raise ValueError('Missing value block')
        self._step(depth)
        block_type = block.get('type')

        if block_type == 'text':
            value = self._field(block, 'TEXT', '')
            if len(value) > 2048:
                raise ValueError('Text is too long')
            return value
        if block_type == 'math_number':
            raw = self._field(block, 'NUM', '0')
            value = float(raw) if any(char in raw.lower() for char in ('.', 'e')) else int(raw)
            return self._number(value)
        if block_type == 'java_variable_get':
            name = self._field(block, 'NAME')
            if name not in variables:
                raise ValueError('Variable is not defined')
            return variables[name]
        if block_type == 'logic_boolean':
            value = self._field(block, 'BOOL')
            if value not in {'TRUE', 'FALSE'}:
                raise ValueError('Invalid boolean')
            return value == 'TRUE'
        if block_type == 'math_arithmetic':
            left = self._number(self._value(self._input(block, 'A'), variables, depth + 1))
            right = self._number(self._value(self._input(block, 'B'), variables, depth + 1))
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
        if block_type == 'logic_compare':
            left = self._value(self._input(block, 'A'), variables, depth + 1)
            right = self._value(self._input(block, 'B'), variables, depth + 1)
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

    def _run_chain(self, block, variables, depth=0, call_depth=0):
        while block is not None:
            self._step(depth)
            block_type = block.get('type')

            if block_type == 'java_print':
                value = self._value(self._input(block, 'TEXT'), variables, depth + 1)
                self.output.append(str(value))
                if sum(map(len, self.output)) + len(self.output) > MAX_OUTPUT_LENGTH:
                    raise ValueError('Output limit exceeded')
            elif block_type == 'java_variable':
                name = self._field(block, 'NAME')
                if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,63}', name):
                    raise ValueError('Invalid variable name')
                variables[name] = self._value(self._input(block, 'VALUE'), variables, depth + 1)
            elif block_type == 'java_if':
                condition = self._value(self._input(block, 'IF0'), variables, depth + 1)
                if not isinstance(condition, bool):
                    raise ValueError('Condition must be boolean')
                branch = 'DO0' if condition else 'ELSE'
                self._run_chain(self._statement(block, branch), variables, depth + 1, call_depth)
            elif block_type == 'java_for':
                name = self._field(block, 'VAR')
                if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,63}', name):
                    raise ValueError('Invalid loop variable')
                start = self._number(self._value(self._input(block, 'FROM'), variables, depth + 1))
                end = self._number(self._value(self._input(block, 'TO'), variables, depth + 1))
                if not isinstance(start, int) or not isinstance(end, int):
                    raise ValueError('Loop bounds must be integers')
                iterations = max(0, min(end - start + 1, MAX_LOOP_ITERATIONS + 1))
                if iterations > MAX_LOOP_ITERATIONS:
                    raise ValueError('Loop limit exceeded')
                for value in range(start, end + 1):
                    variables[name] = value
                    self._run_chain(self._statement(block, 'DO'), variables, depth + 1, call_depth)
            elif block_type == 'java_while':
                condition_block = self._input(block, 'CONDITION')
                iterations = 0
                while self._value(condition_block, variables, depth + 1):
                    iterations += 1
                    if iterations > MAX_LOOP_ITERATIONS:
                        raise ValueError('Loop limit exceeded')
                    self._run_chain(self._statement(block, 'DO'), variables, depth + 1, call_depth)
            elif block_type == 'java_method':
                name = self._field(block, 'NAME')
                if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,63}', name):
                    raise ValueError('Invalid method name')
                self.methods[name] = self._statement(block, 'STACK')
            elif block_type == 'java_method_call':
                name = self._field(block, 'NAME')
                if name not in self.methods or call_depth >= 10:
                    raise ValueError('Method is undefined or recursion limit exceeded')
                self._run_chain(self.methods[name], variables, depth + 1, call_depth + 1)
            else:
                raise ValueError('Unsupported statement block')

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
        variables = {}
        for block in root:
            if self._tag(block) == 'block':
                self._run_chain(block, variables)
        return '\n'.join(self.output)


def run_java_blocks(source):
    """Run the supported Java playground Blockly subset without executing source code."""
    try:
        return _JavaBlocklyInterpreter().run(source)
    except Exception:
        return '__ERROR__'