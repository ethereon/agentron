import os
import shutil
import subprocess


class ShellExecutionError(Exception):
    pass


def bash(command: str, timeout: float | None = None) -> str:
    """
    Execute shell commands or scripts in bash and return the output.

    Args:
        command: The bash command or script to execute.
        timeout: The maximum number of seconds to allow the command to run.
    """
    bash_path = shutil.which('bash')
    if bash_path is None:
        raise RuntimeError('bash executable not found on PATH.')
    return execute(
        [bash_path, '-c', command],
        timeout=timeout,
        desc='Bash command',
    )


def execute(
    command: list[str],
    desc: str,
    timeout: float | None = None,
    cwd: str | None = None,
    ok_returncodes: tuple[int, ...] = (0,),
) -> str:
    if timeout is not None and timeout <= 0:
        raise ValueError('timeout must be positive')
    if not ok_returncodes:
        raise ValueError('ok_returncodes must not be empty')
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout,
            cwd=cwd,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as err:
        partial_output = _normalize_output(err.output)
        suffix = f'\n{partial_output}' if partial_output else ''
        raise ShellExecutionError(f'{desc} timed out after {timeout:g} seconds.{suffix}') from err

    output = _normalize_output(result.stdout)
    if result.returncode not in ok_returncodes:
        if output:
            raise ShellExecutionError(f'{desc} failed ({result.returncode}):\n{output}')
        raise ShellExecutionError(f'{desc} failed ({result.returncode}).')

    return output


def _normalize_output(output: str | bytes | bytearray | memoryview | None) -> str:
    if output is None:
        return ''
    if not isinstance(output, str):
        output = bytes(output).decode(errors='replace')
    return output.rstrip('\n')
