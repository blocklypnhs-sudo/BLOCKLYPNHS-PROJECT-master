import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.cpp_verify import run_cpp_blocks


def test_interprets_store_age_blocks():
    blocks = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="cpp_variable" x="30" y="30">
        <field name="TYPE">int</field>
        <field name="NAME">age</field>
        <value name="VALUE"><block type="cpp_number"><field name="NUM">17</field></block></value>
      </block>
      <block type="cpp_cout" x="30" y="150">
        <value name="TEXT"><block type="cpp_variable_get"><field name="NAME">age</field></block></value>
      </block>
    </xml>"""
    assert run_cpp_blocks(blocks) == '17'


def test_interprets_cpp_math_condition_and_loop_blocks():
    multiply = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="cpp_cout">
        <value name="TEXT"><block type="cpp_math_operation">
          <value name="A"><block type="cpp_number"><field name="NUM">6</field></block></value>
          <field name="OP">MULTIPLY</field>
          <value name="B"><block type="cpp_number"><field name="NUM">5</field></block></value>
        </block></value>
      </block>
    </xml>"""
    conditional = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="cpp_if">
        <value name="IF0"><block type="cpp_compare">
          <value name="A"><block type="cpp_number"><field name="NUM">15</field></block></value>
          <field name="OP">LT</field>
          <value name="B"><block type="cpp_number"><field name="NUM">20</field></block></value>
        </block></value>
        <statement name="DO0"><block type="cpp_cout">
          <value name="TEXT"><block type="cpp_text"><field name="TEXT">15 is less than 20</field></block></value>
        </block></statement>
      </block>
    </xml>"""
    loop = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="cpp_for">
        <field name="VAR">i</field>
        <value name="FROM"><block type="cpp_number"><field name="NUM">1</field></block></value>
        <value name="TO"><block type="cpp_number"><field name="NUM">5</field></block></value>
        <statement name="DO"><block type="cpp_cout">
          <value name="TEXT"><block type="cpp_variable_get"><field name="NAME">i</field></block></value>
        </block></statement>
      </block>
    </xml>"""
    assert run_cpp_blocks(multiply) == '30'
    assert run_cpp_blocks(conditional) == '15 is less than 20'
    assert run_cpp_blocks(loop) == '1\n2\n3\n4\n5'


def test_rejects_unsupported_cpp_blocks_and_invalid_xml():
    assert run_cpp_blocks('<xml><block type="unknown"/></xml>') == '__ERROR__'
    assert run_cpp_blocks('<!DOCTYPE xml><xml/>') == '__ERROR__'
