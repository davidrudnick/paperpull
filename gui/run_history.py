"""Panel-observed successful exits, stored with each provider installation."""
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
import os
import tempfile

_LOCK = Lock()
NAME = '.panel-runs.json'


def read(folder: Path) -> dict:
    try:
        data = json.loads((folder / NAME).read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record(folder: Path, account: str, action: str) -> None:
    if action not in {'all', 'resume', 'pilot', 'discover', 'verify'}:
        return
    with _LOCK:
        data = read(folder)
        if not isinstance(data.get(account), dict):
            data[account] = {}
        data[account][action] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        fd, temporary = tempfile.mkstemp(prefix=NAME, suffix='.tmp', dir=folder)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, indent=2)
                stream.write('\n')
            os.replace(temporary, folder / NAME)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def completed(folder: Path) -> dict:
    result = {}
    for account, actions in read(folder).items():
        if not isinstance(actions, dict):
            continue
        stamps = []
        for action in ('all', 'resume'):
            stamp = actions.get(action)
            if not isinstance(stamp, str):
                continue
            try:
                value = datetime.fromisoformat(stamp)
                if value.tzinfo is not None:
                    stamps.append(value)
            except ValueError:
                continue
        if stamps:
            result[account] = max(stamps).isoformat(timespec='seconds')
    return result
