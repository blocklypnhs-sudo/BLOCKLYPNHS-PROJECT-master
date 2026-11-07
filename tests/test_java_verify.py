from backend.java_verify import run_java_blocks


def test_java_block_interpreter_handles_variables_conditions_and_loops():
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="java_variable">
        <field name="TYPE">int</field><field name="NAME">score</field>
        <value name="VALUE"><block type="math_number"><field name="NUM">80</field></block></value>
        <next><block type="java_if">
          <value name="IF0"><block type="logic_compare"><field name="OP">GTE</field>
            <value name="A"><block type="java_variable_get"><field name="NAME">score</field></block></value>
            <value name="B"><block type="math_number"><field name="NUM">75</field></block></value>
          </block></value>
          <statement name="DO0"><block type="java_print">
            <value name="TEXT"><block type="text"><field name="TEXT">Passed</field></block></value>
          </block></statement>
          <statement name="ELSE"><block type="java_print">
            <value name="TEXT"><block type="text"><field name="TEXT">Failed</field></block></value>
          </block></statement>
          <next><block type="java_for">
            <field name="VAR">i</field>
            <value name="FROM"><block type="math_number"><field name="NUM">1</field></block></value>
            <value name="TO"><block type="math_number"><field name="NUM">3</field></block></value>
            <statement name="DO"><block type="java_print">
              <value name="TEXT"><block type="java_variable_get"><field name="NAME">i</field></block></value>
            </block></statement>
          </block></next>
        </block></next>
      </block>
    </xml>'''

    assert run_java_blocks(source) == 'Passed\n1\n2\n3'


def test_java_block_interpreter_runs_called_methods():
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="java_method">
        <field name="NAME">welcome</field>
        <statement name="STACK"><block type="java_print">
          <value name="TEXT"><block type="text"><field name="TEXT">Welcome to Java!</field></block></value>
        </block></statement>
        <next><block type="java_method_call"><field name="NAME">welcome</field></block></next>
      </block>
    </xml>'''

    assert run_java_blocks(source) == 'Welcome to Java!'


def test_java_block_interpreter_rejects_unsupported_blocks():
    assert run_java_blocks('<xml><block type="unsupported"></block></xml>') == '__ERROR__'