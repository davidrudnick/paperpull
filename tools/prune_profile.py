"""Optional cache-only cleanup. Preview by default; never runs during login."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

CACHES = ('Default/Cache', 'Default/Code Cache', 'Default/GPUCache')


def browser_running() -> bool:
    try:
        command = ['tasklist', '/FO', 'CSV', '/NH'] if sys.platform == 'win32' else ['ps', '-A', '-o', 'comm=']
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return True  # Refuse cleanup when process status cannot be checked.
    return any(word in result.stdout.lower() for word in ('chrome', 'chromium', 'msedge', 'microsoft edge'))


def prune(profile: Path, apply: bool = False) -> list[str]:
    if profile.is_symlink():
        raise ValueError('A profile symlink is not accepted.')
    profile = profile.resolve(strict=True)
    if browser_running() or any((profile / name).exists() or (profile / name).is_symlink()
                                for name in ('SingletonLock', 'SingletonSocket')):
        raise ValueError('Close all Chrome, Edge and Chromium processes before cleanup.')
    candidates = []
    for name in CACHES:
        path = profile / name
        if any(part.is_symlink() for part in (path, path.parent)):
            raise ValueError('A cache path contains a symlink; refusing cleanup.')
        if path.is_dir():
            candidates.append(name)
    if apply:
        for name in candidates:
            shutil.rmtree(profile / name)
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('--apply', action='store_true', help='delete only the listed caches')
    args = parser.parse_args()
    try:
        paths = prune(args.profile, args.apply)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print('Removed:' if args.apply else 'Would remove:')
    for path in paths:
        print(path)
    if not args.apply:
        print('Preview only. Add --apply to remove these caches.')


if __name__ == '__main__':
    main()
