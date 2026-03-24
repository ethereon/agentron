import subprocess
import shlex


def git(command: str) -> str:
    """
    Executes a git command and returns the output as a string.

    Args:
        command: The git command to execute, e.g. 'status' or 'commit -m "message"'.
    """
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
        raise RuntimeError(f'Git command failed ({result.returncode}):\n{result.stderr.strip()}')

    return result.stdout.strip()
