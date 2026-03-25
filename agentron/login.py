import subprocess
import sys

from agentron.rpc.flux import get_flux_path


def main():
    flux_path = get_flux_path()
    result = subprocess.run(['node', flux_path, 'login'])
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
