import os

from pathlib import Path

from agentron.kit.utils import resolve_path


def test_resolve_path_returns_absolute_paths_unchanged() -> None:
    absolute = Path('/tmp/example.txt')

    assert resolve_path(absolute) == absolute


def test_resolve_path_resolves_relative_string_against_cwd(tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert resolve_path('nested/file.txt') == tmp_path / 'nested' / 'file.txt'
    finally:
        os.chdir(original_cwd)


def test_resolve_path_resolves_relative_path_object_against_cwd(tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert resolve_path(Path('nested/file.txt')) == tmp_path / 'nested' / 'file.txt'
    finally:
        os.chdir(original_cwd)


def test_resolve_path_expands_user_home() -> None:
    expected = Path.home() / 'example.txt'

    assert resolve_path('~/example.txt') == expected
