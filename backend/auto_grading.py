# auto_grading.py
import subprocess
import tempfile
import os
import re
import shutil

class GradingError(Exception):
    pass

def normalize_output(text):
    """Normalize output for comparison (trim, collapse spaces, handle newlines)"""
    if not text:
        return ''
    # Remove extra whitespace and normalize newlines
    text = text.strip()
    text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    return text

def grade_javascript(code, expected_output, max_score=10):
    """Execute JavaScript code with Node.js and compare output"""
    try:
        # Check if Node.js is installed
        if not shutil.which('node'):
            return 0, max_score, 'Node.js is not installed on the server'
        
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Execute with Node.js
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if stderr:
                return 0, max_score, f'Execution error: {stderr[:200]}'
            
            # Compare output
            actual = normalize_output(stdout)
            expected = normalize_output(expected_output)
            
            if actual == expected:
                return max_score, max_score, '✅ Correct! Output matches expected.'
            else:
                # Show diff
                return 0, max_score, f'❌ Expected: "{expected_output}", got: "{stdout}"'
                
        except subprocess.TimeoutExpired:
            return 0, max_score, '⏱️ Code execution timed out (5s limit)'
        except Exception as e:
            return 0, max_score, f'Runtime error: {str(e)}'
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                
    except Exception as e:
        return 0, max_score, f'Grading error: {str(e)}'

def grade_php(code, expected_output, max_score=10):
    """Execute PHP code with PHP CLI and compare output"""
    try:
        if not shutil.which('php'):
            return 0, max_score, 'PHP is not installed on the server'
        
        # Wrap in PHP tags if not already
        code = code.strip()
        if not code.startswith('<?php'):
            code = f"<?php\n{code}\n?>"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ['php', temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if stderr and 'PHP Warning' not in stderr:
                return 0, max_score, f'Execution error: {stderr[:200]}'
            
            actual = normalize_output(stdout)
            expected = normalize_output(expected_output)
            
            if actual == expected:
                return max_score, max_score, '✅ Correct! Output matches expected.'
            else:
                return 0, max_score, f'❌ Expected: "{expected_output}", got: "{stdout}"'
                
        except subprocess.TimeoutExpired:
            return 0, max_score, '⏱️ Code execution timed out (5s limit)'
        except Exception as e:
            return 0, max_score, f'Runtime error: {str(e)}'
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                
    except Exception as e:
        return 0, max_score, f'Grading error: {str(e)}'

def grade_cpp(code, expected_output, max_score=10):
    """Compile and execute C++ code with g++"""
    try:
        if not shutil.which('g++'):
            return 0, max_score, 'g++ compiler is not installed on the server'
        
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
            f.write(code)
            source_file = f.name
        
        # Compile to temp executable
        output_file = source_file.replace('.cpp', '.out')
        
        try:
            # Compile
            compile_result = subprocess.run(
                ['g++', source_file, '-o', output_file, '-std=c++17'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if compile_result.stderr:
                return 0, max_score, f'Compilation error:\n{compile_result.stderr[:300]}'
            
            # Execute
            exec_result = subprocess.run(
                [output_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            stdout = exec_result.stdout.strip()
            stderr = exec_result.stderr.strip()
            
            if stderr:
                return 0, max_score, f'Runtime error: {stderr[:200]}'
            
            actual = normalize_output(stdout)
            expected = normalize_output(expected_output)
            
            if actual == expected:
                return max_score, max_score, '✅ Correct! Output matches expected.'
            else:
                return 0, max_score, f'❌ Expected: "{expected_output}", got: "{stdout}"'
                
        except subprocess.TimeoutExpired:
            return 0, max_score, '⏱️ Code execution timed out (5s limit)'
        except Exception as e:
            return 0, max_score, f'Runtime error: {str(e)}'
        finally:
            # Clean up
            for f in [source_file, output_file]:
                if os.path.exists(f):
                    os.unlink(f)
                    
    except Exception as e:
        return 0, max_score, f'Grading error: {str(e)}'

# Main dispatcher
def grade_code(language, code, expected_output, max_score=10):
    """Dispatch to appropriate grader based on language"""
    graders = {
        'javascript': grade_javascript,
        'js': grade_javascript,
        'php': grade_php,
        'cpp': grade_cpp,
        'c++': grade_cpp
    }
    
    grader = graders.get(language.lower())
    if not grader:
        return 0, max_score, f'Unsupported language: {language}'
    
    return grader(code, expected_output, max_score)