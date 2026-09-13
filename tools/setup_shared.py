"""Create the optional root environment used by this fork's launchers."""
from pathlib import Path
import subprocess
import sys
import venv


def main():
    root = Path(__file__).resolve().parents[1]
    environment = root / '.venv'
    if not environment.exists():
        venv.create(environment, with_pip=True)
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    command = [str(python), '-m', 'pip', 'install', '-e', str(root / 'core')]
    for requirement in sorted((root / 'apps').glob('*/requirements.txt')):
        command.extend(['-r', str(requirement)])
    command.extend(['-r', str(root / 'gui/requirements.txt')])
    subprocess.run(command, cwd=root, check=True)
    print('Root environment ready. No browser was downloaded or started.')


if __name__ == '__main__':
    main()
