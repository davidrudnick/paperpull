"""The number that tells same-looking rows apart, and where they sit.

A document's occurrence is part of its key, so it must never move for a
document already downloaded. Its position is where the row sits in its
year's listing now, which is allowed to move and is what the download uses
to find the row. Before the two were separated they were one number.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import brightstart_docs as docs
import brightstart_site as site

LABELS = {"456": "Jane 529 ...456", "789": "John 529 ...789"}


def row(ext, label="Contribution", year="2026", position=0, date="2026-02-01"):
    return {"kind": site.KIND_CONFIRM, "date": date, "label": label,
            "account_number": "123-" + ext, "ext": ext, "year": year,
            "occurrence": position}


def stored(r, occurrence):
    return docs.Document(title=r["label"], kind=r["kind"], date=r["date"],
                         account_number=r["account_number"],
                         account=LABELS.get(r["ext"], ""), year=r["year"],
                         occurrence=occurrence, position=r["occurrence"])


def app_with(records):
    app = docs.App.__new__(docs.App)

    class Store:
        data = {}
    app.discovery = Store()
    for d in records:
        app.discovery.data[d.key] = d.to_dict()
    return app


def test_two_accounts_with_the_same_row_are_each_the_first():
    app = app_with([])
    assert app._stable_numbers([row("456"), row("789")], LABELS) == [0, 0]


def test_the_same_row_in_two_years_is_numbered_in_each_year_on_its_own():
    app = app_with([])
    assert app._stable_numbers([row("456", year="2025"), row("456", year="2026")],
                               LABELS) == [0, 0]


def test_an_existing_archive_keeps_every_key_when_the_order_flips():
    a, b = row("456", position=0), row("456", position=1)
    app = app_with([stored(a, 0), stored(b, 1)])
    keys_before = set(app.discovery.data)
    flipped = [dict(b, occurrence=0), dict(a, occurrence=1)]
    numbers = app._stable_numbers(flipped, LABELS)
    assert sorted(numbers) == [0, 1]
    assert {stored(r, n).key for r, n in zip(flipped, numbers)} == keys_before


def test_plan_inserts_are_never_numbered():
    insert = {"kind": site.KIND_INSERT, "cms_pdf": "a.pdf", "year": "2026",
              "occurrence": 3}
    app = app_with([])
    assert app._stable_numbers([insert, row("456")], LABELS) == [0, 0]


def test_a_record_written_before_positions_existed_finds_its_row_by_occurrence():
    d = docs.Document.from_dict({"kind": site.KIND_CONFIRM, "title": "Contribution",
                                 "account_number": "123-456", "occurrence": 2})
    assert d.position == 2
