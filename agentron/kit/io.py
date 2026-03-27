import shlex
import shutil

from pathlib import Path

from agentron.kit.shell import execute
from agentron.kit.patch import apply_patch as apply_patch


def read_file(
    path: str,
    prefix_line_numbers: bool = False,
    offset: int = 0,
    limit: int | None = None,
) -> str:
    """
    Reads the content of a file at the given path and returns it as a string.

    Args:
        path: The absolute path to the file to read.

        prefix_line_numbers: If True, each line in the returned content will be prefixed
                             with its line number (e.g., "1: ...").

        offset: The zero-based line offset to start reading from.

        limit: The maximum number of lines to read. If None, reads through the end
               of the file.
    """
    if offset < 0:
        raise ValueError('offset must be non-negative')
    if limit is not None and limit < 0:
        raise ValueError('limit must be non-negative')

    _path = Path(path)
    if not _path.is_file():
        raise FileNotFoundError(f'File not found: {path}')

    content = _path.read_text()
    end = None if limit is None else offset + limit

    if prefix_line_numbers:
        lines = content.splitlines()[offset:end]
        return '\n'.join(
            # Inject line numbers like "1: ..."
            f'{offset + i + 1}: {line}'
            for i, line in enumerate(lines)
        )

    if offset == 0 and limit is None:
        return content

    return ''.join(content.splitlines(keepends=True)[offset:end])


def list_dir(path: str) -> str:
    """
    Lists the contents of a directory.

    Args:
        path: The absolute path to the directory to list.
    """
    directory = Path(path)
    if not directory.exists():
        raise FileNotFoundError(f'Directory not found: {path}')
    if not directory.is_dir():
        raise NotADirectoryError(f'Not a directory: {path}')

    return '\n'.join(
        sorted(
            # Append a "/" suffix to directories to distinguish them from files.
            f'{entry.name}/' if entry.is_dir() else entry.name
            for entry in directory.iterdir()
        )
    )


def write_file(path: str, content: str) -> str:
    """
    Writes text content to the file at the given path.

    Args:
        path: The absolute path to the file to write. The parent directory
              must already exist.

        content: The text content to write to the file.
    """
    destination = Path(path)
    destination.write_text(content)

    return 'File successfully written.'


def grep(args: str) -> str:
    """
    Executes grep and returns its output.

    Args:
        args: The arguments to pass to grep as a single string.
    """
    if not args.strip():
        raise ValueError('args must not be empty')

    grep_path = shutil.which('grep')
    if grep_path is None:
        raise RuntimeError('grep executable not found on PATH.')

    return execute(
        [grep_path, *shlex.split(args)],
        desc='grep command',
        ok_returncodes=(0, 1),
    )
