import subprocess

from agentron.rpc.flux import get_flux_path


def main():
    flux_path = get_flux_path()
    subprocess.run(['node', flux_path, 'login'])


if __name__ == '__main__':
    main()
