"""Synthetic fixtures for provider parsing, filing and control checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage


def test_provider_string_is_unchanged():
    storage.set_filename_owner("")
    assert storage.build_pdf_filename("2026-08-05", "Statement - Mortgage (...5678)", "") == \
        "2026-08-05 Huntington Bank Statement - Mortgage (...5678).pdf"


def test_csv_filenames_are_unchanged(tmp_path):
    paths = storage.Paths(tmp_path)
    assert paths.document_index_csv.name == "Huntington Bank Document Index.csv"


def test_precreated_folders_are_unchanged(tmp_path):
    paths = storage.Paths(tmp_path)
    paths.ensure()
    made = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    assert made == ['Backups', 'Correspondence', 'Diagnostics', 'Escrow Analyses',
                    'Logs', 'Manual Review', 'Statements', 'Tax Documents']


def test_every_declared_route_resolves(tmp_path):
    paths = storage.Paths(tmp_path)
    for key in storage.SPEC.routes:
        assert paths.folder_for(key).is_dir()


def test_escrow_analyses_are_filed_apart_from_statements(tmp_path):
    paths = storage.Paths(tmp_path)
    assert paths.folder_for(storage.ESCROW) != paths.folder_for(storage.STATEMENT)
    assert paths.folder_for(storage.ESCROW).name == "Escrow Analyses"


def test_the_orchestrator_imports():
    import importlib
    here = Path(__file__).resolve().parents[1]
    entry = next(p for p in list(here.glob("*_docs.py")) + list(here.glob("*_receipts.py")))
    module = importlib.import_module(entry.stem)
    assert hasattr(module, "main")
    assert hasattr(module, "App")
