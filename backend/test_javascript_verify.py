import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.javascript_verify import run_javascript_blocks


def test_interprets_store_score_blocks():
    blocks = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="js_set" x="30" y="30">
        <field name="NAME">score</field>
        <value name="VALUE"><block type="js_number"><field name="NUM">90</field></block></value>
      </block>
      <block type="js_print" x="30" y="150">
        <value name="TEXT"><block type="js_get"><field name="NAME">score</field></block></value>
      </block>
    </xml>"""
    assert run_javascript_blocks(blocks) == '90'


def test_interprets_math_and_comparison_blocks():
    blocks = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="js_print">
        <value name="TEXT"><block type="js_math">
          <value name="A"><block type="js_number"><field name="NUM">25</field></block></value>
          <field name="OP">ADD</field>
          <value name="B"><block type="js_number"><field name="NUM">15</field></block></value>
        </block></value>
      </block>
    </xml>"""
    assert run_javascript_blocks(blocks) == '40'


def test_interprets_greater_than_and_repeat_blocks():
    conditional = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="js_if">
        <value name="IF0"><block type="js_compare">
          <value name="A"><block type="js_number"><field name="NUM">20</field></block></value>
          <field name="OP">GT</field>
          <value name="B"><block type="js_number"><field name="NUM">10</field></block></value>
        </block></value>
        <statement name="DO0"><block type="js_print">
          <value name="TEXT"><block type="js_text"><field name="TEXT">20 is greater than 10</field></block></value>
        </block></statement>
      </block>
    </xml>"""
    repeat = """<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="js_for">
        <field name="VAR">i</field>
        <value name="FROM"><block type="js_number"><field name="NUM">0</field></block></value>
        <value name="TO"><block type="js_number"><field name="NUM">4</field></block></value>
        <statement name="DO"><block type="js_print">
          <value name="TEXT"><block type="js_text"><field name="TEXT">I love programming!</field></block></value>
        </block></statement>
      </block>
    </xml>"""
    assert run_javascript_blocks(conditional) == '20 is greater than 10'
    assert run_javascript_blocks(repeat) == '\n'.join(['I love programming!'] * 5)


def test_rejects_unsupported_blocks_and_invalid_xml():
    assert run_javascript_blocks('<xml><block type="unknown"/></xml>') == '__ERROR__'
    assert run_javascript_blocks('<!DOCTYPE xml><xml/>') == '__ERROR__'
