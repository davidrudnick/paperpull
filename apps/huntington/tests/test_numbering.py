"""The number that tells same-looking documents apart, and where they sit.

A document's occurrence is part of its key, so it must never move for a
document already downloaded. Its position is where the row sits on the page
now, which is allowed to move and is what the download falls back to when a
record id has changed. Before the two were separated they were one number.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import huntington_docs as docs


def row(account, title="Escrow Analysis", position=0, record_id=""):
    return {"account": account, "record_type": "escrow", "title": title,
            "start": "2025-01-01", "end": "2025-12-31",
            "occurrence": position, "record_id": record_id}


def app_with(known_rows):
    app = docs.App.__new__(docs.App)

    class Store:
        data = {}
    app.discovery = Store()
    for r in known_rows:
        d = docs.Document(**{k: v for k, v in r.items()})
        app.discovery.data[d.key] = d.to_dict()
    return app


def test_two_accounts_with_the_same_document_are_each_the_first():
    """Numbered one account at a time, as the site always numbered them.
    Numbering them together would give the second account's document a new
    key, and its whole downloaded history with it."""
    app = app_with([])
    assert app._stable_numbers([row("Checking ...1111"), row("Savings ...2222")]) == [0, 0]


def test_an_existing_archive_keeps_every_key_when_the_order_flips():
    first = row("Checking ...1111", position=0, record_id="A")
    second = row("Checking ...1111", position=1, record_id="B")
    before = app_with([dict(first, occurrence=0), dict(second, occurrence=1)])
    keys_before = set(before.discovery.data)
    # the same two, answered the other way round
    flipped = [dict(second, occurrence=0), dict(first, occurrence=1)]
    numbers = before._stable_numbers(flipped)
    assert sorted(numbers) == [0, 1]
    keys_after = {docs.Document(**dict(r, occurrence=n)).key
                  for r, n in zip(flipped, numbers)}
    assert keys_after == keys_before


def test_a_record_written_before_positions_existed_finds_its_row_by_occurrence():
    """Those two were equal when it was written, so that is the right row."""
    d = docs.Document.from_dict({"account": "Checking", "record_type": "escrow",
                                 "title": "Escrow Analysis", "occurrence": 2})
    assert d.position == 2


def test_the_position_is_not_part_of_the_key():
    a = docs.Document(account="Checking", record_type="escrow",
                      title="Escrow Analysis", occurrence=1, position=0)
    b = docs.Document(account="Checking", record_type="escrow",
                      title="Escrow Analysis", occurrence=1, position=5)
    assert a.key == b.key
