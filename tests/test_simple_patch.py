import tempfile
import unittest

from pathlib import Path
from agentron.kit.patch import apply_patch


class PatchFileTests(unittest.TestCase):
    def test_patch_file_applies_unified_diff_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            source.write_text('alpha\nbeta\ngamma\n')

            patch = '--- a/source.txt\n+++ b/source.txt\n@@ -1,3 +1,3 @@\n alpha\n-beta\n+delta\n gamma\n'

            apply_patch(
                patch=patch,
                path=str(source),
            )

            self.assertEqual(source.read_text(), 'alpha\ndelta\ngamma\n')

    def test_patch_file_applies_search_replace_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'source.txt'
            source.write_text('alpha\nbeta\ngamma\n')

            patch = '<<<<<<< SEARCH\nbeta\n=======\ndelta\n>>>>>>> REPLACE\n'

            apply_patch(
                patch=patch,
                path=str(source),
            )

            self.assertEqual(source.read_text(), 'alpha\ndelta\ngamma\n')
