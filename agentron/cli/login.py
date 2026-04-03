import subprocess
import sys

from agentron.rpc.flux import get_flux_path


def run_login() -> int:
    flux_path = get_flux_path()
    result = subprocess.run(['node', flux_path, 'login'])
    return result.returncode


if __name__ == '__main__':
    run_login()
