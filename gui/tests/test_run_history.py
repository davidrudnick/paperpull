import importlib.util
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

spec = importlib.util.spec_from_file_location('run_history', Path(__file__).parents[1] / 'run_history.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def test_only_full_runs_count_and_accounts_stay_separate(tmp_path):
    history.record(tmp_path, 'primary', 'verify')
    history.record(tmp_path, 'primary', 'login')
    assert history.completed(tmp_path) == {}
    history.record(tmp_path, 'primary', 'all')
    history.record(tmp_path, 'secondary', 'resume')
    assert set(history.completed(tmp_path)) == {'primary', 'secondary'}
    assert 'login' not in history.read(tmp_path)['primary']


def test_parallel_records_do_not_lose_accounts(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda n: history.record(tmp_path, str(n), 'all'), range(20)))
    assert len(history.completed(tmp_path)) == 20


def test_invalid_state_and_timezone_order(tmp_path):
    (tmp_path / history.NAME).write_text('{broken')
    assert history.completed(tmp_path) == {}
    (tmp_path / history.NAME).write_text(json.dumps({'primary': {
        'all': '2026-01-01T10:00:00+02:00', 'resume': '2026-01-01T09:00:00+00:00'},
        'invalid': {'all': 'not a date'}}))
    assert history.completed(tmp_path) == {'primary': '2026-01-01T09:00:00+00:00'}
