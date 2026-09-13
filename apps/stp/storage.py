"""STP / BluePrint investment documents."""
from __future__ import annotations

from pathlib import Path

from paperpull_core import storage as _core
from paperpull_core.spec import (AppSpec, CsvSpec, DOCUMENT, Folder,
                                 INFRASTRUCTURE_FOLDERS)


INVESTOR_REPORT = "Investor Report"
TAX = "Tax Document"
ONBOARDING = "Onboarding Document"
FUND_MATERIAL = "Fund Material"
ALL_CATEGORIES = [INVESTOR_REPORT, TAX, ONBOARDING, FUND_MATERIAL]

DOCUMENT_INDEX_COLUMNS = [
    "Account Holder",
    "Document Date", "Category", "Document Summary", "Document Title",
    "Account", "Fund", "Period", "File Name", "Full Path", "File Size",
    "PDF Page Count", "Source URL", "Classification Confidence",
    "Downloaded At", "Verified At", "Processing Status", "Notes",
]

SPEC = AppSpec(
    provider="STP Investment Services",
    project_dir=Path(__file__).resolve().parent,
    kind=DOCUMENT,
    folders=[


        Folder("investor_reporting", "Investor Reporting"),

        Folder("tax_documents", "Tax Documents"),

        Folder("onboarding", "Onboarding"),

        Folder("fund_materials", "Fund Materials"),



        Folder("other_documents", "Other Documents", precreate=False),
        *INFRASTRUCTURE_FOLDERS,
    ],
    routes={
        INVESTOR_REPORT: "investor_reporting",
        TAX: "tax_documents",
        ONBOARDING: "onboarding",
        FUND_MATERIAL: "fund_materials",
    },
    default_route="other_documents",
    csv_files=[
        CsvSpec("document_index_csv", "STP Investment Services Document Index.csv",
                DOCUMENT_INDEX_COLUMNS),
    ],
    config_defaults={
        "pilot_count": 5,
        "document_types": list(ALL_CATEGORIES),






        "account_labels": {},
    },
    base_url="https://app.blueprintplatform.com/",
    rules_filename="document_rules.json",
)

_core.bind(SPEC)

PROJECT_DIR = SPEC.project_dir


from paperpull_core.storage import (
    CsvFile, JsonStore, Paths, atomic_write_json, atomic_write_text,
    backup_file, build_pdf_filename, ensure_owner, load_config, now_iso,
    sanitize_component, set_filename_owner, title_case, unique_path,
)
