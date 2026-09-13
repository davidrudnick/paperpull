"""Synthetic fixtures for provider parsing, filing and control checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage


def test_provider_string_is_unchanged():
    storage.set_filename_owner("")
    assert storage.build_pdf_filename(
        "2024-06-15", "Capital Call Notice - Example-A (Example Fund A) - 1234", "") == \
        "2024-06-15 STP Investment Services Capital Call Notice - Example-A (Example Fund A) - 1234.pdf"


def test_csv_filenames_are_unchanged(tmp_path):
    paths = storage.Paths(tmp_path)
    assert paths.document_index_csv.name == "STP Investment Services Document Index.csv"


def test_precreated_folders_are_unchanged(tmp_path):
    paths = storage.Paths(tmp_path)
    paths.ensure()
    made = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    assert made == ['Backups', 'Diagnostics', 'Fund Materials',
                    'Investor Reporting', 'Logs', 'Manual Review',
                    'Onboarding', 'Tax Documents']


def test_every_declared_route_resolves(tmp_path):
    paths = storage.Paths(tmp_path)
    for key in storage.SPEC.routes:
        assert paths.folder_for(key).is_dir()


def test_the_portals_own_folders_are_mirrored(tmp_path):
    paths = storage.Paths(tmp_path)
    assert paths.folder_for(storage.INVESTOR_REPORT).name == "Investor Reporting"
    assert paths.folder_for(storage.TAX).name == "Tax Documents"
    assert paths.folder_for(storage.ONBOARDING).name == "Onboarding"
    assert paths.folder_for(storage.FUND_MATERIAL).name == "Fund Materials"


def test_the_orchestrator_imports():
    import importlib
    here = Path(__file__).resolve().parents[1]
    entry = next(p for p in list(here.glob("*_docs.py")) + list(here.glob("*_receipts.py")))
    module = importlib.import_module(entry.stem)
    assert hasattr(module, "main")
    assert hasattr(module, "App")
