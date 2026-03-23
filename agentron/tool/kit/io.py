import re
import shlex
import shutil

from pathlib import Path

from agentron.tool.kit.shell import execute


_UNIFIED_HUNK_HEADER = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


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


def patch_file(patch: str, source_path: str, destination_path: str | None = None) -> str:
    """
    Applies a patch to a source file and writes the patched content to a destination.

    Supported patch formats are auto-detected:

    - Unified diff patches with ``---``, ``+++``, and ``@@`` hunk headers.
    - Search/replace blocks in the form::

          <<<<<<< SEARCH
          old text
          =======
          new text
          >>>>>>> REPLACE

    Args:
        patch: The patch to apply.

        source_path: The absolute path to the source file to patch.

        destination_path: The absolute path where the patched output should be written.
                          If None, the source file will be overwritten with the patched content.
    """
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f'File not found: {source_path}')

    patch_kind = _detect_patch_format(patch)
    original_content = source.read_text()

    if patch_kind == 'unified_diff':
        patched_content = _apply_unified_diff(original_content, patch)
    else:
        patched_content = _apply_search_replace_patch(original_content, patch)

    destination = Path(destination_path) if destination_path else source
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(patched_content)

    return 'File successfully patched.'


def _detect_patch_format(patch: str) -> str:
    first_nonempty_line = ''
    for line in patch.splitlines():
        if line.strip():
            first_nonempty_line = line
            break

    if first_nonempty_line.startswith('<<<<<<< SEARCH'):
        return 'search_replace'

    lines = patch.splitlines()
    has_old_header = any(line.startswith('--- ') for line in lines)
    has_new_header = any(line.startswith('+++ ') for line in lines)
    has_hunk_header = any(line.startswith('@@ ') for line in lines)
    if has_old_header and has_new_header and has_hunk_header:
        return 'unified_diff'

    raise ValueError('Unsupported patch format')


def _apply_search_replace_patch(content: str, patch: str) -> str:
    blocks = _parse_search_replace_blocks(patch)
    patched_content = content

    for search_text, replace_text in blocks:
        if not search_text:
            raise ValueError('Search/replace patches must include search content')

        match_count = patched_content.count(search_text)
        if match_count == 0:
            raise ValueError('Search block did not match the source content')
        if match_count > 1:
            raise ValueError('Search block matched multiple locations in the source content')

        patched_content = patched_content.replace(search_text, replace_text, 1)

    return patched_content


def _parse_search_replace_blocks(patch: str) -> list[tuple[str, str]]:
    lines = patch.splitlines(keepends=True)
    blocks: list[tuple[str, str]] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if not line.startswith('<<<<<<< SEARCH'):
            raise ValueError('Invalid search/replace patch header')
        index += 1

        search_lines: list[str] = []
        while index < len(lines) and not lines[index].startswith('======='):
            search_lines.append(lines[index])
            index += 1
        if index == len(lines):
            raise ValueError('Search/replace patch is missing a separator')
        index += 1

        replace_lines: list[str] = []
        while index < len(lines) and not lines[index].startswith('>>>>>>> REPLACE'):
            replace_lines.append(lines[index])
            index += 1
        if index == len(lines):
            raise ValueError('Search/replace patch is missing a replace footer')
        index += 1

        blocks.append((''.join(search_lines), ''.join(replace_lines)))

    if not blocks:
        raise ValueError('Search/replace patch did not contain any blocks')

    return blocks


def _apply_unified_diff(content: str, patch: str) -> str:
    source_lines = content.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    index = 0
    while index < len(patch_lines) and not patch_lines[index].startswith('--- '):
        index += 1

    if index + 1 >= len(patch_lines) or not patch_lines[index + 1].startswith('+++ '):
        raise ValueError('Unified diff patch is missing file headers')

    index += 2
    source_index = 0
    output_lines: list[str] = []
    saw_hunk = False

    while index < len(patch_lines):
        line = patch_lines[index]
        if not line.strip():
            index += 1
            continue

        if line.startswith('@@ '):
            saw_hunk = True
            old_start, old_count, new_count = _parse_unified_hunk_header(line)
            hunk_start = max(old_start - 1, 0)
            if hunk_start < source_index:
                raise ValueError('Unified diff hunks overlap or are out of order')

            output_lines.extend(source_lines[source_index:hunk_start])
            source_index = hunk_start
            index += 1

            consumed_old_lines = 0
            produced_new_lines = 0

            while index < len(patch_lines):
                line = patch_lines[index]
                if line.startswith('@@ '):
                    break
                if line.startswith('diff --git ') or line.startswith('--- '):
                    raise ValueError('Unified diff patch must target a single file')
                if line.startswith('\\ No newline at end of file'):
                    index += 1
                    continue
                if not line:
                    raise ValueError('Unexpected empty line in unified diff patch')

                prefix = line[0]
                if prefix not in {' ', '+', '-'}:
                    raise ValueError('Unsupported line prefix in unified diff patch')

                line_content, index = _read_unified_hunk_line(patch_lines, index)

                if prefix in {' ', '-'}:
                    if source_index >= len(source_lines):
                        raise ValueError('Unified diff patch extends past the end of the source file')
                    if source_lines[source_index] != line_content:
                        raise ValueError('Unified diff hunk did not match the source content')

                if prefix == ' ':
                    output_lines.append(source_lines[source_index])
                    source_index += 1
                    consumed_old_lines += 1
                    produced_new_lines += 1
                elif prefix == '-':
                    source_index += 1
                    consumed_old_lines += 1
                else:
                    output_lines.append(line_content)
                    produced_new_lines += 1

            if consumed_old_lines != old_count:
                raise ValueError('Unified diff hunk removed an unexpected number of lines')
            if produced_new_lines != new_count:
                raise ValueError('Unified diff hunk added an unexpected number of lines')
            continue

        if line.startswith('diff --git '):
            raise ValueError('Unified diff patch must target a single file')

        raise ValueError('Unexpected content outside a unified diff hunk')

    if not saw_hunk:
        raise ValueError('Unified diff patch did not contain any hunks')

    output_lines.extend(source_lines[source_index:])
    return ''.join(output_lines)


def _parse_unified_hunk_header(header: str) -> tuple[int, int, int]:
    match = _UNIFIED_HUNK_HEADER.match(header)
    if not match:
        raise ValueError('Invalid unified diff hunk header')

    old_start = int(match.group(1))
    old_count = int(match.group(2) or 1)
    new_count = int(match.group(4) or 1)
    return old_start, old_count, new_count


def _read_unified_hunk_line(lines: list[str], index: int) -> tuple[str, int]:
    line_content = lines[index][1:]
    if index + 1 < len(lines) and lines[index + 1].startswith('\\ No newline at end of file') and line_content.endswith('\n'):
        line_content = line_content[:-1]
        index += 1

    return line_content, index + 1


def grep(args: str, cwd: str | None = None) -> str:
    """
    Executes grep and returns its output.

    Args:
        args: The arguments to pass to grep as a single string.

        cwd: The working directory in which to run grep.
    """
    if not args.strip():
        raise ValueError('args must not be empty')

    grep_path = shutil.which('grep')
    if grep_path is None:
        raise RuntimeError('grep executable not found on PATH.')

    return execute(
        [grep_path, *shlex.split(args)],
        cwd=cwd,
        desc='grep command',
        ok_returncodes=(0, 1),
    )
