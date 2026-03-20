import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentron.tool.kit.io import patch_file, read_file, write_file


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
