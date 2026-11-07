"""Safely interpret the C++ playground's supported Blockly blocks for grading."""
import xml.etree.ElementTree as ET

from backend.javascript_verify import (
    MAX_STEPS,
    MAX_XML_LENGTH,
    _JavaScriptBlocklyInterpreter,
)


CPP_BLOCKS = {
    'cpp_cout': 'js_print',
    'cpp_variable': 'js_set',
    'cpp_variable_get': 'js_get',
    'cpp_math_operation': 'js_math',
    'cpp_number': 'js_number',
    'cpp_text': 'js_text',
    'cpp_if': 'js_if',
    'cpp_compare': 'js_compare',
    'cpp_for': 'js_for',
}


class _CppBlocklyInterpreter(_JavaScriptBlocklyInterpreter):
    def _output_value(self, value):
        if isinstance(value, bool):
            return '1' if value else '0'
        return super()._output_value(value)

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

        for block in root.iter():
            if self._tag(block) == 'block':
                block_type = block.get('type')
                if block_type in CPP_BLOCKS:
                    block.set('type', CPP_BLOCKS[block_type])

        return super().run(ET.tostring(root, encoding='unicode'))


def run_cpp_blocks(source):
    """Interpret supported C++ Blockly XML without executing submitted source code."""
    try:
        return _CppBlocklyInterpreter().run(source)
    except Exception:
        return '__ERROR__'
