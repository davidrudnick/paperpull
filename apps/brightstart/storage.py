"""Bright Start 529 statements, confirmations and plan inserts."""
from __future__ import annotations

from pathlib import Path

from paperpull_core import storage as _core
from paperpull_core.spec import (AppSpec, CsvSpec, DOCUMENT, Folder,
                                 INFRASTRUCTURE_FOLDERS)


STATEMENT = "Statement"
CONFIRMATION = "Confirmation"
TAX = "Tax Document"
PLAN = "Plan Document"
ALL_CATEGORIES = [STATEMENT, CONFIRMATION, TAX, PLAN]

DOCUMENT_INDEX_COLUMNS = [
    "Account Holder",
    "Document Date", "Category", "Document Summary", "Document Title",
    "Account", "Period", "PDF Filename", "PDF Full Path", "PDF File Size",
    "PDF Page Count", "Source URL", "Classification Confidence",
    "Downloaded At", "Verified At", "Processing Status", "Notes",
]

SPEC = AppSpec(
    provider="Bright Start 529",
    project_dir=Path(__file__).resolve().parent,
    kind=DOCUMENT,
    folders=[
        Folder("statements", "Statements"),
        Folder("confirmations", "Confirmations"),



        Folder("tax_documents", "Tax Documents", precreate=False),
        Folder("plan_documents", "Plan Documents"),



        Folder("other_documents", "Other Documents", precreate=False),
        *INFRASTRUCTURE_FOLDERS,
    ],
    routes={
        STATEMENT: "statements",
        CONFIRMATION: "confirmations",
        TAX: "tax_documents",
        PLAN: "plan_documents",
    },
    default_route="other_documents",
    csv_files=[
        CsvSpec("document_index_csv", "Bright Start 529 Document Index.csv",
                DOCUMENT_INDEX_COLUMNS),
    ],
    config_defaults={
        "pilot_count": 5,
        "document_types": list(ALL_CATEGORIES),






        "account_labels": {},
    },
    base_url="https://www.brightstart-529.com/",
    rules_filename="document_rules.json",
)

_core.bind(SPEC)

PROJECT_DIR = SPEC.project_dir


from paperpull_core.storage import (
    CsvFile, JsonStore, Paths, atomic_write_json, atomic_write_text,
    backup_file, build_pdf_filename, ensure_owner, load_config, now_iso,
    sanitize_component, set_filename_owner, title_case, unique_path,
)
