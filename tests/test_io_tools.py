import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentron.tool.kit.io import patch_file


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
