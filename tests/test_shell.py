import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentron.kit.shell import ShellExecutionError, bash


class BashToolTests(unittest.TestCase):
    def test_bash_executes_commands_with_bash_features(self) -> None:
        result = bash('if [[ -n "$BASH_VERSION" ]]; then printf "bash"; fi')

        self.assertEqual(result, 'bash')

    def test_bash_returns_combined_stdout_and_stderr(self) -> None:
        result = bash('printf "alpha\\n"; printf "beta\\n" >&2')

        self.assertEqual(result, 'alpha\nbeta')

    def test_bash_failures_raise_tool_error_with_output(self) -> None:
        with self.assertRaises(ShellExecutionError) as ctx:
            bash('printf "before failure\\n"; printf "problem\\n" >&2; exit 7')

        message = str(ctx.exception)

        self.assertIn('Bash command failed (7):', message)
        self.assertIn('before failure', message)
        self.assertIn('problem', message)

    def test_bash_timeouts_raise_tool_error(self) -> None:
        with self.assertRaises(ShellExecutionError) as ctx:
            bash('printf "starting\\n"; sleep 5', timeout=0.1)

        self.assertIn('Bash command timed out after 0.1 seconds.', str(ctx.exception))

    def test_bash_rejects_non_positive_timeout(self) -> None:
        with self.assertRaisesRegex(ValueError, 'timeout must be positive'):
            bash('printf "ok"', timeout=0)


if __name__ == '__main__':
    unittest.main()
