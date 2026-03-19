from pathlib import Path


def read_file(path: str, prefix_line_numbers: bool = False) -> str:
    """
    Reads the content of a file at the given path and returns it as a string.

    Args:
        path: The absolute path to the file to read.

        prefix_line_numbers: If True, each line in the returned content will be prefixed
                             with its line number (e.g., "1: ...").
    """
    _path = Path(path)
    if not _path.is_file():
        raise FileNotFoundError(f'File not found: {path}')

    content = _path.read_text()
    if prefix_line_numbers:
        content = '\n'.join(
            # Inject line numbers like "1: ..."
            f'{i + 1}: {line}'
            for i, line in enumerate(content.splitlines())
        )
    return content
