import io
import ast
import types
import builtins
import traceback
import contextlib

from agentron.tool.error import ToolError


class REPLExecutionError(ToolError):
    pass


class RunInPythonREPL:
    def __init__(self):
        # Using <stdin> in exceptions keeps it consistent with the actual Python REPL.
        self.filename = '<stdin>'
        self.main_module = types.ModuleType(
            '__main__',  # __name__
            'REPL main module',  # __doc__
        )
        self.globals = self.main_module.__dict__
        self.globals['__builtins__'] = builtins
        self._execution_index = 0

    def __call__(self, code: str) -> str:
        """
        Execute Python code in a stateful REPL environment.

        Args:
            code: The Python code to execute.
        Returns:
            The output of the executed code or expression, or any error messages if execution fails.
        """
        output_buffer = io.StringIO()
        result_sentinel = object()
        result_value = result_sentinel

        try:
            module = ast.parse(code, filename=self.filename, mode='exec')
        except SyntaxError as error:
            raise REPLExecutionError(_format_exception_only(error))

        temp_result_name = None
        if module.body and isinstance(module.body[-1], ast.Expr):
            # Rewrite the final expression into an assignment so exec can evaluate it.
            self._execution_index += 1
            temp_result_name = f'__repl_result_{id(self)}_{self._execution_index}'
            module.body[-1] = ast.Assign(
                targets=[ast.Name(id=temp_result_name, ctx=ast.Store())],
                value=module.body[-1].value,
            )
            ast.fix_missing_locations(module)

        try:
            compiled = compile(module, self.filename, 'exec')
        except SyntaxError as error:
            raise REPLExecutionError(_format_exception_only(error))

        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            try:
                exec(compiled, self.globals, self.globals)
            except Exception as error:
                buffer_text = output_buffer.getvalue()
                exception_text = _format_runtime_exception(error, filename=self.filename)
                raise REPLExecutionError(f'{buffer_text}{exception_text}')

        if temp_result_name is not None and temp_result_name in self.globals:
            result_value = self.globals.pop(temp_result_name)

        captured_output = output_buffer.getvalue()
        if result_value is not result_sentinel and result_value is not None:
            expression_output = repr(result_value)
            if not captured_output:
                return expression_output
            if captured_output.endswith('\n'):
                return captured_output + expression_output
            return captured_output + '\n' + expression_output

        return captured_output


def _format_exception_only(error: BaseException) -> str:
    return ''.join(traceback.format_exception_only(type(error), error))


def _format_runtime_exception(error: BaseException, filename: str) -> str:
    stack = traceback.extract_tb(error.__traceback__)
    user_stack = [frame for frame in stack if frame.filename == filename]

    formatted = ['Traceback (most recent call last):\n']
    formatted.extend(traceback.format_list(user_stack or stack[-1:]))
    formatted.extend(traceback.format_exception_only(type(error), error))
    return ''.join(formatted)
