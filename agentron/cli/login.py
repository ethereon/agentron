import subprocess

from agentron.path import get_flux_path


def run_login() -> int:
    result = subprocess.run(['node', str(get_flux_path()), 'login'])
    return result.returncode
