import shutil
import subprocess


class ShellExecutionError(Exception):
    pass


def run_bash(command: str, timeout: float | None = None) -> str:
    """
    Execute shell commands or scripts in bash and return the output.

    Args:
        command: The bash command or script to execute.
        timeout: The maximum number of seconds to allow the command to run.
    """
    if timeout is not None and timeout <= 0:
        raise ValueError('timeout must be positive')

    bash_path = shutil.which('bash')
    if bash_path is None:
        raise RuntimeError('bash executable not found on PATH.')

    try:
        result = subprocess.run(
            [bash_path, '-lc', command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as err:
        partial_output = _normalize_output(err.output)
        suffix = f'\n{partial_output}' if partial_output else ''
        raise ShellExecutionError(f'Bash command timed out after {timeout:g} seconds.{suffix}') from err

    output = _normalize_output(result.stdout)
    if result.returncode != 0:
        if output:
            raise ShellExecutionError(f'Bash command failed ({result.returncode}):\n{output}')
        raise ShellExecutionError(f'Bash command failed ({result.returncode}).')

    return output


def _normalize_output(output: str | bytes | bytearray | memoryview | None) -> str:
    if output is None:
        return ''
    if not isinstance(output, str):
        output = bytes(output).decode(errors='replace')
    return output.rstrip('\n')
