import subprocess

from agentron.rpc.flux import get_flux_path


def run_login() -> int:
    flux_path = get_flux_path()
    result = subprocess.run(['node', flux_path, 'login'])
    return result.returncode
