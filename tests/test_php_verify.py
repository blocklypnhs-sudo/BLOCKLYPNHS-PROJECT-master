from backend.php_verify import run_php_blocks


def test_php_block_interpreter_prints_text_and_variable():
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="php_variable">
        <field name="NAME">name</field>
        <value name="VALUE"><block type="php_text"><field name="TEXT">Alice</field></block></value>
        <next><block type="php_echo">
          <value name="TEXT"><block type="php_variable_get"><field name="NAME">name</field></block></value>
        </block></next>
      </block>
    </xml>'''

    assert run_php_blocks(source) == 'Alice'


def test_php_block_interpreter_selects_elseif_branch():
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="php_variable">
        <field name="NAME">grade</field>
        <value name="VALUE"><block type="php_number"><field name="NUM">88</field></block></value>
        <next><block type="php_if_elseif">
          <value name="IF0"><block type="php_compare"><field name="OP">GTE</field>
            <value name="A"><block type="php_variable_get"><field name="NAME">grade</field></block></value>
            <value name="B"><block type="php_number"><field name="NUM">90</field></block></value>
          </block></value>
          <statement name="DO0"><block type="php_echo">
            <value name="TEXT"><block type="php_text"><field name="TEXT">Excellent</field></block></value>
          </block></statement>
          <value name="IF1"><block type="php_compare"><field name="OP">GTE</field>
            <value name="A"><block type="php_variable_get"><field name="NAME">grade</field></block></value>
            <value name="B"><block type="php_number"><field name="NUM">75</field></block></value>
          </block></value>
          <statement name="DO1"><block type="php_echo">
            <value name="TEXT"><block type="php_text"><field name="TEXT">Passed</field></block></value>
          </block></statement>
          <statement name="ELSE"><block type="php_echo">
            <value name="TEXT"><block type="php_text"><field name="TEXT">Failed</field></block></value>
          </block></statement>
        </block></next>
      </block>
    </xml>'''

    assert run_php_blocks(source) == 'Passed'


def test_php_block_interpreter_runs_echo_inside_for_loop():
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="php_for">
        <field name="VAR">i</field>
        <value name="FROM"><block type="php_number"><field name="NUM">0</field></block></value>
        <value name="TO"><block type="php_number"><field name="NUM">2</field></block></value>
        <statement name="DO"><block type="php_echo">
          <value name="TEXT"><block type="php_text"><field name="TEXT">Learning PHP!</field></block></value>
        </block></statement>
      </block>
    </xml>'''

    assert run_php_blocks(source) == 'Learning PHP!\nLearning PHP!\nLearning PHP!'


def test_php_block_interpreter_rejects_unsupported_blocks():
    assert run_php_blocks('<xml><block type="unsupported"></block></xml>') == '__ERROR__'