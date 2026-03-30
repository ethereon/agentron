from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentron.kit.utils import resolve_path

BEGIN_PATCH_MARKER = '*** Begin Patch'
END_PATCH_MARKER = '*** End Patch'
ADD_FILE_MARKER = '*** Add File: '
DELETE_FILE_MARKER = '*** Delete File: '
UPDATE_FILE_MARKER = '*** Update File: '
MOVE_TO_MARKER = '*** Move to: '
EOF_MARKER = '*** End of File'
CHANGE_CONTEXT_MARKER = '@@ '
EMPTY_CHANGE_CONTEXT_MARKER = '@@'


@dataclass(slots=True)
class AddFileHunk:
    path: str
    contents: str


@dataclass(slots=True)
class DeleteFileHunk:
    path: str


@dataclass(slots=True)
class UpdateFileChunk:
    change_context: str | None
    old_lines: list[str]
    new_lines: list[str]
    is_end_of_file: bool = False


@dataclass(slots=True)
class UpdateFileHunk:
    path: str
    move_path: str | None
    chunks: list[UpdateFileChunk]


type Hunk = AddFileHunk | DeleteFileHunk | UpdateFileHunk


# Implementation Notes:
#
# This is based off the OpenAI Codex apply_patch tool, as described here:
# https://github.com/openai/codex/tree/main/codex-rs/apply-patch
#
# The primary motivation for porting this over is that the newer GPT models (e.g.: GPT 5.4)
# *strongly* want to use this format for patching files. They *will* frequently ignore the
# tool description of the original apply_patch tool and attempt to use this format.
# Thus, this variant aims to align the behavior of tool with the expectations of the model.


def apply_patch(patch: str, workdir: str | None = None) -> str:
    """
    Use the apply_patch tool to edit files.

    The patch envelope format is as follows:

    - Begin with ``*** Begin Patch`` and end with ``*** End Patch``.
    - Include one or more file hunks using ``*** Add File:``,
        ``*** Delete File:``, or ``*** Update File:``.
    - ``Update File`` hunks may optionally include ``*** Move to:`` and one or
        more change chunks introduced by ``@@`` or ``@@ <context>``.
    - Change chunk lines must start with a space for context, ``-`` for removed
        lines, or ``+`` for added lines. ``*** End of File`` marks an update chunk
        that must match at end-of-file.

    Relative paths are resolved against ``workdir``. Absolute paths are applied
    as given.

    Args:
        patch: The patch payload.

        workdir: Optional base directory used to resolve relative file paths.
                 Defaults to the current working directory.
    """
    hunks = _parse_patch(patch)
    if not hunks:
        raise ValueError('No files were modified.')

    cwd = resolve_path(workdir or Path.cwd())
    added: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []

    for hunk in hunks:
        if isinstance(hunk, AddFileHunk):
            destination = _resolve_hunk_path(cwd, hunk.path)
            if destination.parent != destination:
                destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(hunk.contents)
            added.append(_display_path(hunk.path, destination))
            continue

        if isinstance(hunk, DeleteFileHunk):
            target = _resolve_hunk_path(cwd, hunk.path)
            try:
                target.unlink()
            except OSError as exc:
                raise OSError(f'Failed to delete file {hunk.path}') from exc
            deleted.append(_display_path(hunk.path, target))
            continue

        source = _resolve_hunk_path(cwd, hunk.path)
        try:
            original_contents = source.read_text()
        except OSError as exc:
            raise type(exc)(f'Failed to read file to update {hunk.path}: {exc}') from exc

        new_contents = _derive_new_contents(original_contents, hunk.chunks, hunk.path)
        destination = _resolve_hunk_path(cwd, hunk.move_path) if hunk.move_path else source

        if destination.parent != destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(new_contents)

        if hunk.move_path:
            try:
                source.unlink()
            except OSError as exc:
                raise OSError(f'Failed to remove original {hunk.path}: {exc}') from exc

        modified.append(_display_path(hunk.move_path or hunk.path, destination))

    lines = ['Success. Updated the following files:']
    lines.extend(f'A {path}' for path in added)
    lines.extend(f'M {path}' for path in modified)
    lines.extend(f'D {path}' for path in deleted)
    return '\n'.join(lines) + '\n'


def _parse_patch(patch: str) -> list[Hunk]:
    lines = _normalise_patch_lines(patch)
    _check_patch_boundaries(lines)

    hunks: list[Hunk] = []
    index = 1
    line_number = 2
    last_line_index = len(lines) - 1

    while index < last_line_index:
        if not lines[index].strip():
            index += 1
            line_number += 1
            continue

        hunk, consumed = _parse_one_hunk(lines[index:last_line_index], line_number)
        hunks.append(hunk)
        index += consumed
        line_number += consumed

    return hunks


def _normalise_patch_lines(patch: str) -> list[str]:
    stripped = patch.strip()
    if not stripped:
        return []

    lines = stripped.splitlines()
    if _is_heredoc_wrapper(lines):
        lines = lines[1:-1]

    return lines


def _is_heredoc_wrapper(lines: list[str]) -> bool:
    return len(lines) >= 4 and lines[0] in {'<<EOF', "<<'EOF'", '<<"EOF"'} and lines[-1].endswith('EOF')


def _check_patch_boundaries(lines: list[str]) -> None:
    first_line = lines[0].strip() if lines else None
    last_line = lines[-1].strip() if lines else None

    if first_line != BEGIN_PATCH_MARKER:
        raise ValueError("The first line of the patch must be '*** Begin Patch'")
    if last_line != END_PATCH_MARKER:
        raise ValueError("The last line of the patch must be '*** End Patch'")


def _parse_one_hunk(lines: list[str], line_number: int) -> tuple[Hunk, int]:
    header = lines[0].strip()

    if header.startswith(ADD_FILE_MARKER):
        path = header.removeprefix(ADD_FILE_MARKER)
        contents: list[str] = []
        consumed = 1
        for line in lines[1:]:
            if not line.startswith('+'):
                break
            contents.append(line[1:])
            consumed += 1
        return AddFileHunk(path=path, contents='\n'.join(contents) + '\n'), consumed

    if header.startswith(DELETE_FILE_MARKER):
        return DeleteFileHunk(path=header.removeprefix(DELETE_FILE_MARKER)), 1

    if header.startswith(UPDATE_FILE_MARKER):
        path = header.removeprefix(UPDATE_FILE_MARKER)
        consumed = 1
        index = 1
        move_path: str | None = None

        if index < len(lines):
            maybe_move = lines[index].strip()
            if maybe_move.startswith(MOVE_TO_MARKER):
                move_path = maybe_move.removeprefix(MOVE_TO_MARKER)
                index += 1
                consumed += 1

        chunks: list[UpdateFileChunk] = []
        while index < len(lines):
            current = lines[index]
            stripped = current.strip()
            if not stripped:
                index += 1
                consumed += 1
                continue
            if stripped.startswith('***'):
                break

            chunk, chunk_lines = _parse_update_file_chunk(
                lines[index:],
                line_number + consumed,
                allow_missing_context=not chunks,
            )
            chunks.append(chunk)
            index += chunk_lines
            consumed += chunk_lines

        if not chunks:
            raise ValueError(f"Invalid patch hunk on line {line_number}: Update file hunk for path '{path}' is empty")
        return UpdateFileHunk(path=path, move_path=move_path, chunks=chunks), consumed

    raise ValueError(
        f"Invalid patch hunk on line {line_number}: '{header}' is not a valid hunk header. Valid hunk headers: '*** Add File: {{path}}', '*** Delete File: {{path}}', '*** Update File: {{path}}'"
    )


def _parse_update_file_chunk(
    lines: list[str],
    line_number: int,
    allow_missing_context: bool,
) -> tuple[UpdateFileChunk, int]:
    if not lines:
        raise ValueError(f'Invalid patch hunk on line {line_number}: Update hunk does not contain any lines')

    first_line = lines[0]
    stripped = first_line.strip()
    if stripped == EMPTY_CHANGE_CONTEXT_MARKER:
        change_context = None
        start_index = 1
    elif stripped.startswith(CHANGE_CONTEXT_MARKER):
        change_context = stripped.removeprefix(CHANGE_CONTEXT_MARKER)
        start_index = 1
    else:
        if not allow_missing_context:
            raise ValueError(f"Invalid patch hunk on line {line_number}: Expected update hunk to start with a @@ context marker, got: '{first_line}'")
        change_context = None
        start_index = 0

    if start_index >= len(lines):
        raise ValueError(f'Invalid patch hunk on line {line_number + 1}: Update hunk does not contain any lines')

    chunk = UpdateFileChunk(change_context=change_context, old_lines=[], new_lines=[])
    parsed_lines = 0
    for line in lines[start_index:]:
        stripped_line = line.strip()
        if stripped_line == EOF_MARKER:
            if parsed_lines == 0:
                raise ValueError(f'Invalid patch hunk on line {line_number + 1}: Update hunk does not contain any lines')
            chunk.is_end_of_file = True
            parsed_lines += 1
            break

        if line == '':
            chunk.old_lines.append('')
            chunk.new_lines.append('')
            parsed_lines += 1
            continue

        prefix = line[0]
        if prefix == ' ':
            chunk.old_lines.append(line[1:])
            chunk.new_lines.append(line[1:])
            parsed_lines += 1
            continue
        if prefix == '+':
            chunk.new_lines.append(line[1:])
            parsed_lines += 1
            continue
        if prefix == '-':
            chunk.old_lines.append(line[1:])
            parsed_lines += 1
            continue

        if parsed_lines == 0:
            raise ValueError(
                'Invalid patch hunk on line '
                f"{line_number + 1}: Unexpected line found in update hunk: '{line}'. "
                "Every line should start with ' ' (context line), '+' (added line), or '-' (removed line)"
            )
        break

    return chunk, parsed_lines + start_index


def _derive_new_contents(original_contents: str, chunks: list[UpdateFileChunk], display_path: str) -> str:
    original_lines = original_contents.split('\n')
    if original_lines and original_lines[-1] == '':
        original_lines.pop()

    replacements = _compute_replacements(original_lines, chunks, display_path)
    new_lines = _apply_replacements(original_lines, replacements)
    if not new_lines or new_lines[-1] != '':
        new_lines.append('')
    return '\n'.join(new_lines)


def _compute_replacements(
    original_lines: list[str],
    chunks: list[UpdateFileChunk],
    display_path: str,
) -> list[tuple[int, int, list[str]]]:
    replacements: list[tuple[int, int, list[str]]] = []
    line_index = 0

    for chunk in chunks:
        if chunk.change_context is not None:
            context_index = _seek_sequence(original_lines, [chunk.change_context], line_index, False)
            if context_index is None:
                raise ValueError(f"Failed to find context '{chunk.change_context}' in {display_path}")
            line_index = context_index + 1

        if not chunk.old_lines:
            replacements.append((len(original_lines), 0, chunk.new_lines.copy()))
            continue

        pattern = chunk.old_lines
        new_slice = chunk.new_lines
        found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)

        if found is None and pattern[-1:] == ['']:
            pattern = pattern[:-1]
            if new_slice[-1:] == ['']:
                new_slice = new_slice[:-1]
            found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)

        if found is None:
            raise ValueError(f'Failed to find expected lines in {display_path}:\n' + '\n'.join(chunk.old_lines))

        replacements.append((found, len(pattern), new_slice.copy()))
        line_index = found + len(pattern)

    replacements.sort(key=lambda item: item[0])
    return replacements


def _apply_replacements(
    lines: list[str],
    replacements: list[tuple[int, int, list[str]]],
) -> list[str]:
    updated = list(lines)
    for start_index, old_len, new_segment in reversed(replacements):
        del updated[start_index : start_index + old_len]
        updated[start_index:start_index] = new_segment
    return updated


def _seek_sequence(lines: list[str], pattern: list[str], start: int, eof: bool) -> int | None:
    if not pattern:
        return start
    if len(pattern) > len(lines):
        return None

    search_start = len(lines) - len(pattern) if eof and len(lines) >= len(pattern) else start
    search_end = len(lines) - len(pattern)

    for index in range(search_start, search_end + 1):
        if lines[index : index + len(pattern)] == pattern:
            return index

    for matcher in (_rstrip_equal, _trim_equal, _normalised_equal):
        for index in range(search_start, search_end + 1):
            if all(matcher(lines[index + offset], pattern[offset]) for offset in range(len(pattern))):
                return index

    return None


def _rstrip_equal(lhs: str, rhs: str) -> bool:
    return lhs.rstrip() == rhs.rstrip()


def _trim_equal(lhs: str, rhs: str) -> bool:
    return lhs.strip() == rhs.strip()


def _normalised_equal(lhs: str, rhs: str) -> bool:
    return _normalise_line(lhs) == _normalise_line(rhs)


def _normalise_line(value: str) -> str:
    replacements = {
        '\u2010': '-',
        '\u2011': '-',
        '\u2012': '-',
        '\u2013': '-',
        '\u2014': '-',
        '\u2015': '-',
        '\u2212': '-',
        '\u2018': "'",
        '\u2019': "'",
        '\u201a': "'",
        '\u201b': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u201e': '"',
        '\u201f': '"',
        '\u00a0': ' ',
        '\u2002': ' ',
        '\u2003': ' ',
        '\u2004': ' ',
        '\u2005': ' ',
        '\u2006': ' ',
        '\u2007': ' ',
        '\u2008': ' ',
        '\u2009': ' ',
        '\u200a': ' ',
        '\u202f': ' ',
        '\u205f': ' ',
        '\u3000': ' ',
    }
    return ''.join(replacements.get(char, char) for char in value.strip())


def _resolve_hunk_path(cwd: Path, raw_path: str | None) -> Path:
    if raw_path is None:
        raise ValueError('Missing patch path')
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else cwd / path


def _display_path(raw_path: str, resolved_path: Path) -> str:
    path = Path(raw_path).expanduser()
    return str(resolved_path if path.is_absolute() else path)
