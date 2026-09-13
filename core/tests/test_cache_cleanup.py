import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('cache_cleanup', Path(__file__).parents[2] / 'tools/prune_profile.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def test_preview_and_cleanup_preserve_session_and_security_data(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup, 'browser_running', lambda: False)
    for name in ('Default/Cache', 'Default/Network', 'Safe Browsing', 'component_crx_cache'):
        (tmp_path / name).mkdir(parents=True)
        (tmp_path / name / 'data').write_text('example')
    assert cleanup.prune(tmp_path) == ['Default/Cache']
    assert (tmp_path / 'Default/Cache/data').exists()
    cleanup.prune(tmp_path, apply=True)
    assert not (tmp_path / 'Default/Cache').exists()
    for name in ('Default/Network', 'Safe Browsing', 'component_crx_cache'):
        assert (tmp_path / name / 'data').exists()


def test_refuses_running_browser_and_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup, 'browser_running', lambda: True)
    with pytest.raises(ValueError):
        cleanup.prune(tmp_path, apply=True)
    monkeypatch.setattr(cleanup, 'browser_running', lambda: False)
    (tmp_path / 'Default').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        cleanup.prune(tmp_path, apply=True)
