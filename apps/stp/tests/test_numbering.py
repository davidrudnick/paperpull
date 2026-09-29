"""The number that tells same-looking documents apart, where they sit, and
a key that names the account when there is no account id.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stp_docs as docs


def rec(account_id="A1", account_name="Jane", occurrence=0, **kw):
    base = dict(title="Q1 Report", doc_type="Investor Report", date="2026-03-31",
                account_id=account_id, account_name=account_name,
                fund="Growth Fund", occurrence=occurrence)
    base.update(kw)
    return base


def test_an_existing_archive_keeps_every_key_when_the_order_flips():
    a, b = rec(document_id="d-aaa"), rec(document_id="d-bbb", occurrence=1)
    known = {docs.Document(**r).key: docs.Document(**r).to_dict() for r in (a, b)}
    flipped = [dict(b, occurrence=0), dict(a, occurrence=1)]
    numbers = docs._stable_occurrences(
        flipped, known, fields=("doc_type", "title", "date", "account_id", "fund"))
    assert sorted(numbers) == [0, 1]
    assert {docs.Document(**dict(r, occurrence=n)).key
            for r, n in zip(flipped, numbers)} == set(known)


def test_a_record_written_before_positions_existed_finds_its_row_by_occurrence():
    assert docs.Document.from_dict(rec(occurrence=2)).position == 2


def test_a_row_with_an_account_id_keeps_the_key_it_always_had():
    assert docs.Document(**rec()).key == "Growth Fund:A1:Investor Report:2026-03-31:Q1 Report"


def test_a_row_with_neither_id_nor_name_keeps_the_key_it_always_had():
    assert (docs.Document(**rec(account_id="", account_name="")).key
            == "Growth Fund::Investor Report:2026-03-31:Q1 Report")


def test_two_accounts_with_no_id_are_no_longer_one_document():
    one = docs.Document(**rec(account_id="", account_name="Jane"))
    two = docs.Document(**rec(account_id="", account_name="John"))
    assert one.key != two.key


def test_a_record_under_the_empty_id_is_moved_to_its_new_key():
    r = rec(account_id="", account_name="Jane")
    old_key = docs.Document(**dict(r, account_name="")).key
    store = {old_key: docs.Document(**r).to_dict()}
    assert docs.migrate_unnamed_account_keys(store) == 1
    assert list(store) == [docs.Document(**r).key]
    assert docs.migrate_unnamed_account_keys(store) == 0, "a second look moves nothing"


def test_nothing_else_is_moved():
    store = {docs.Document(**r).key: docs.Document(**r).to_dict()
             for r in (rec(), rec(account_id="", account_name=""))}
    before = dict(store)
    assert docs.migrate_unnamed_account_keys(store) == 0
    assert store == before


def test_a_move_onto_a_key_already_taken_is_refused():
    r = rec(account_id="", account_name="Jane")
    old_key = docs.Document(**dict(r, account_name="")).key
    new_key = docs.Document(**r).key
    store = {old_key: docs.Document(**r).to_dict(), new_key: {"already": "here"}}
    assert docs.migrate_unnamed_account_keys(store) == 0
    assert store[new_key] == {"already": "here"}
