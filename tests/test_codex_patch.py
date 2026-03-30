import tempfile
import unittest

from pathlib import Path

from agentron.kit.codex_patch import apply_patch


class ApplyCodexPatchTests(unittest.TestCase):
    def test_apply_patch_applies_multiple_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            modify_path = root / 'modify.txt'
            delete_path = root / 'delete.txt'
            modify_path.write_text('line1\nline2\n')
            delete_path.write_text('obsolete\n')

            result = apply_patch(
                '\n'.join(
                    [
                        '*** Begin Patch',
                        '*** Add File: nested/new.txt',
                        '+created',
                        '*** Delete File: delete.txt',
                        '*** Update File: modify.txt',
                        '@@',
                        '-line2',
                        '+changed',
                        '*** End Patch',
                    ]
                ),
                workdir=str(root),
            )

            self.assertEqual(
                result,
                'Success. Updated the following files:\nA nested/new.txt\nM modify.txt\nD delete.txt\n',
            )
            self.assertEqual((root / 'nested/new.txt').read_text(), 'created\n')
            self.assertEqual(modify_path.read_text(), 'line1\nchanged\n')
            self.assertFalse(delete_path.exists())

    def test_apply_patch_moves_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / 'old/name.txt'
            source.parent.mkdir(parents=True)
            source.write_text('old content\n')

            result = apply_patch(
                '\n'.join(
                    [
                        '*** Begin Patch',
                        '*** Update File: old/name.txt',
                        '*** Move to: renamed/dir/name.txt',
                        '@@',
                        '-old content',
                        '+new content',
                        '*** End Patch',
                    ]
                ),
                workdir=str(root),
            )

            self.assertEqual(
                result,
                'Success. Updated the following files:\nM renamed/dir/name.txt\n',
            )
            self.assertFalse(source.exists())
            self.assertEqual((root / 'renamed/dir/name.txt').read_text(), 'new content\n')

    def test_apply_patch_supports_pure_addition_update_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / 'input.txt'
            target.write_text('alpha\n')

            apply_patch(
                '\n'.join(
                    [
                        '*** Begin Patch',
                        '*** Update File: input.txt',
                        '@@',
                        '+added line 1',
                        '+added line 2',
                        '*** End Patch',
                    ]
                ),
                workdir=str(root),
            )

            self.assertEqual(target.read_text(), 'alpha\nadded line 1\nadded line 2\n')

    def test_apply_patch_supports_end_of_file_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / 'tail.txt'
            target.write_text('first\nsecond\n')

            apply_patch(
                '\n'.join(
                    [
                        '*** Begin Patch',
                        '*** Update File: tail.txt',
                        '@@',
                        ' first',
                        '-second',
                        '+second updated',
                        '*** End of File',
                        '*** End Patch',
                    ]
                ),
                workdir=str(root),
            )

            self.assertEqual(target.read_text(), 'first\nsecond updated\n')

    def test_apply_patch_rejects_missing_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / 'modify.txt'
            target.write_text('line1\nline2\n')

            with self.assertRaisesRegex(ValueError, 'Failed to find expected lines in modify.txt'):
                apply_patch(
                    '\n'.join(
                        [
                            '*** Begin Patch',
                            '*** Update File: modify.txt',
                            '@@',
                            '-missing',
                            '+changed',
                            '*** End Patch',
                        ]
                    ),
                    workdir=str(root),
                )

            self.assertEqual(target.read_text(), 'line1\nline2\n')

    def test_apply_patch_rejects_empty_patch(self) -> None:
        with self.assertRaisesRegex(ValueError, 'No files were modified'):
            apply_patch('*** Begin Patch\n*** End Patch')

    def test_apply_patch_accepts_whitespace_padded_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / 'file.txt'
            target.write_text('one\n')

            apply_patch(
                '\n'.join(
                    [
                        ' *** Begin Patch',
                        '  *** Update File: file.txt',
                        '@@',
                        '-one',
                        '+two',
                        ' *** End Patch ',
                    ]
                ),
                workdir=str(root),
            )

            self.assertEqual(target.read_text(), 'two\n')

    def test_apply_patch_accepts_lenient_heredoc_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / 'file.txt'
            target.write_text('one\n')

            apply_patch(
                '\n'.join(
                    [
                        '<<EOF',
                        '*** Begin Patch',
                        '*** Update File: file.txt',
                        '@@',
                        '-one',
                        '+two',
                        '*** End Patch',
                        'EOF',
                    ]
                ),
                workdir=str(root),
            )

            self.assertEqual(target.read_text(), 'two\n')


if __name__ == '__main__':
    unittest.main()
