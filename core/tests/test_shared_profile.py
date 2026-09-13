import json
from pathlib import Path
from paperpull_core import storage
from paperpull_core.spec import AppSpec, DOCUMENT


def load(tmp_path, config):
    app = tmp_path / 'apps' / 'example'
    app.mkdir(parents=True, exist_ok=True)
    p = app / 'config.json'
    p.write_text(json.dumps(config))
    storage.bind(AppSpec(provider='Example', project_dir=app, kind=DOCUMENT))
    return storage.load_config(p)


def test_shared_mode_is_opt_in(tmp_path):
    ordinary = load(tmp_path, {})
    assert ordinary['profile_dir'] != str(tmp_path / 'browser-profile')
    shared = load(tmp_path, {'browser_profile_mode': 'shared'})
    assert shared['profile_dir'] == str(tmp_path / 'browser-profile')
    assert shared['cdp_url'] == 'http://127.0.0.1:9222'
    assert shared['browser'] == 'installed-chrome'


def test_secondary_account_overrides_win(tmp_path):
    cfg = load(tmp_path, {'browser_profile_mode': 'shared',
        'profile_dir': '/example/secondary-browser-profile',
        'cdp_url': 'http://localhost:9232', 'browser': 'bundled'})
    assert cfg['profile_dir'] == '/example/secondary-browser-profile'
    assert cfg['cdp_url'] == 'http://localhost:9232'
    assert cfg['browser'] == 'bundled'
