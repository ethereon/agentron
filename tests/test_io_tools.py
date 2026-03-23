import tempfile
import unittest
import pytest

from pathlib import Path
from agentron.tool.kit.io import list_dir, patch_file, read_file, write_file, grep


class WriteFileTests(unittest.TestCase):
    def test_write_file_writes_to_existing_directory_and_does_not_create_missing_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            destination = root / 'output.txt'

            self.assertEqual(
                write_file(str(destination), 'alpha\nbeta\n'),
                'File successfully written.',
            )
            self.assertEqual(destination.read_text(), 'alpha\nbeta\n')

            missing_destination = root / 'nested' / 'output.txt'
            with self.assertRaises(FileNotFoundError):
                write_file(str(missing_destination), 'gamma\n')


class ReadFileTests(unittest.TestCase):
    def test_read_file_applies_offset_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            source.write_text('alpha\nbeta\ngamma\ndelta\n')

            self.assertEqual(
                read_file(str(source), offset=1, limit=2),
                'beta\ngamma\n',
            )

    def test_read_file_prefix_line_numbers_respects_offset_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            source.write_text('alpha\nbeta\ngamma\ndelta\n')

            self.assertEqual(
                read_file(str(source), prefix_line_numbers=True, offset=1, limit=2),
                '2: beta\n3: gamma',
            )

    def test_read_file_rejects_negative_offset_and_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            source.write_text('alpha\nbeta\n')

            with self.assertRaisesRegex(ValueError, 'offset must be non-negative'):
                read_file(str(source), offset=-1)

            with self.assertRaisesRegex(ValueError, 'limit must be non-negative'):
                read_file(str(source), limit=-1)


class ListDirTests(unittest.TestCase):
    def test_list_dir_returns_sorted_children_and_suffixes_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'beta.txt').write_text('beta\n')
            (root / 'alpha').mkdir()
            (root / 'aardvark.txt').write_text('alpha\n')

            self.assertEqual(
                list_dir(str(root)),
                'aardvark.txt\nalpha/\nbeta.txt',
            )


class PatchFileTests(unittest.TestCase):
    def test_patch_file_applies_unified_diff_to_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            destination = root / 'patched.txt'
            source.write_text('alpha\nbeta\ngamma\n')

            patch = '--- a/source.txt\n+++ b/source.txt\n@@ -1,3 +1,3 @@\n alpha\n-beta\n+delta\n gamma\n'

            patch_file(
                patch=patch,
                source_path=str(source),
                destination_path=str(destination),
            )

            self.assertEqual(source.read_text(), 'alpha\nbeta\ngamma\n')
            self.assertEqual(destination.read_text(), 'alpha\ndelta\ngamma\n')

    def test_patch_file_applies_search_replace_to_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            destination = root / 'patched.txt'
            source.write_text('alpha\nbeta\ngamma\n')

            patch = '<<<<<<< SEARCH\nbeta\n=======\ndelta\n>>>>>>> REPLACE\n'

            patch_file(
                patch=patch,
                source_path=str(source),
                destination_path=str(destination),
            )

            self.assertEqual(source.read_text(), 'alpha\nbeta\ngamma\n')
            self.assertEqual(destination.read_text(), 'alpha\ndelta\ngamma\n')


def test_grep_returns_matching_lines_with_line_numbers(tmp_path: Path) -> None:
    sample = tmp_path / 'sample.txt'
    sample.write_text('alpha\nbeta\nalpha beta\n')

    output = grep(f'-n -- alpha {sample}')

    assert output == '1:alpha\n3:alpha beta'


def test_grep_supports_quoted_patterns(tmp_path: Path) -> None:
    sample = tmp_path / 'sample.txt'
    sample.write_text('alpha beta\nalpha\nbeta\n')

    output = grep(f'-n -- "alpha beta" {sample}')

    assert output == '1:alpha beta'


def test_grep_returns_empty_string_when_no_matches(tmp_path: Path) -> None:
    sample = tmp_path / 'sample.txt'
    sample.write_text('alpha\nbeta\n')

    output = grep(f'-- gamma {sample}')

    assert output == ''


def test_grep_rejects_empty_args() -> None:
    with pytest.raises(ValueError, match='args must not be empty'):
        grep('   ')
