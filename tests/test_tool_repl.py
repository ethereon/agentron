from __future__ import annotations

import unittest

from agentron.kit.repl import RunInPythonREPL, REPLExecutionError


class TestRunInPythonREPL(unittest.TestCase):
    def test_returns_expression_result(self):
        repl = RunInPythonREPL()

        result = repl('1 + 2')

        self.assertEqual(result, '3')

    def test_runtime_errors_raise_tool_error_with_traceback_message(self):
        repl = RunInPythonREPL()

        with self.assertRaises(REPLExecutionError) as ctx:
            repl('print("before")\n1 / 0')

        message = str(ctx.exception)

        self.assertTrue(message.startswith('before\nTraceback (most recent call last):\n'))
        self.assertIn('File "<repl>", line 2, in <module>', message)
        self.assertIn('ZeroDivisionError: division by zero', message)

    def test_syntax_errors_raise_tool_error_with_traceback_message(self):
        repl = RunInPythonREPL()

        with self.assertRaises(REPLExecutionError) as ctx:
            repl('def broken(')

        message = str(ctx.exception)

        self.assertIn('Traceback (most recent call last):', message)
        self.assertIn('SyntaxError', message)

    def test_compile_errors_raise_tool_error_with_traceback_message(self):
        repl = RunInPythonREPL()

        with self.assertRaises(REPLExecutionError) as ctx:
            repl('return 1')

        message = str(ctx.exception)

        self.assertIn('Traceback (most recent call last):', message)
        self.assertIn('SyntaxError', message)
        self.assertIn("'return' outside function", message)


if __name__ == '__main__':
    unittest.main()
