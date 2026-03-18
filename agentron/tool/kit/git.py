import subprocess
import shlex

from agentron.tool.validation import ToolError


def git(command: str) -> str:
    """
    Executes a git command and returns the output as a string.

    Args:
        command: The git command to execute, e.g. 'status' or 'commit -m "message"'.
    """
    try:
        # Split command safely (handles quotes, spaces, etc.)
        args = shlex.split(command)

        # Ensure we're actually calling git
        if not args or args[0] != 'git':
            args.insert(0, 'git')

        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,  # we handle errors manually
        )

        if result.returncode != 0:
            raise ToolError(f'Git command failed ({result.returncode}):\n{result.stderr.strip()}')

        return result.stdout.strip()

    except Exception as e:
        raise ToolError(f'Error running git command: {e}') from e
