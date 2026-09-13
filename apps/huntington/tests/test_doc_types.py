"""Synthetic fixtures for provider parsing, filing and control checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage
from paperpull_core import doc_types
import huntington_site as site
from storage import build_pdf_filename

RULES = doc_types.load_rules()


def test_a_monthly_statement_files_on_its_closing_date():
    cat, date, period, title = site.classify_record(
        {"recordType": "statement", "title": "07/02/2026 - 08/05/2026",
         "startDate": "2026-07-02", "endDate": "2026-08-05"})
    assert cat == "Statement"
    assert date == "2026-08-05"
    assert period == "07/02/2026 - 08/05/2026"


def test_an_escrow_analysis_is_its_own_category():
    cat, date, period, title = site.classify_record(
        {"recordType": "statement", "title": "04/15/2026 Escrow Analysis",
         "startDate": "2026-04-15", "endDate": "2026-04-15"})
    assert cat == "Escrow Analysis"
    assert date == "2026-04-15"
    assert period == ""


def test_a_1098_files_on_the_last_day_of_its_tax_year():
    cat, date, period, title = site.classify_record(
        {"recordType": "taxDocument", "title": "2025 1098 YEAR-END STATEMENT",
         "startDate": "2025-01-01", "endDate": "2025-12-31"})
    assert cat == "Tax Document"
    assert date == "2025-12-31"
    assert period == "2025"

    assert doc_types.classify_document(title, RULES)[:2] == (doc_types.TAX, "1098 Tax Form")


def test_correspondence_files_on_its_own_date_not_its_end_date():
    cat, date, period, title = site.classify_record(
        {"recordType": "correspondence", "title": "07/31/2026 Correspondence",
         "startDate": "2026-07-31", "endDate": "2026-08-04"})
    assert cat == "Correspondence"
    assert date == "2026-07-31"


def test_an_unknown_record_kind_is_kept_not_dropped():
    cat, date, _p, title = site.classify_record(
        {"recordType": "notice", "title": "05/05/2026 Notice",
         "startDate": "2026-05-05", "endDate": "2026-05-05"})
    assert cat == "Other Document"
    assert date == "2026-05-05"


def test_record_descriptor_is_what_identifies_a_record():
    rec = {"recordId": "opaque==", "recordType": "statement",
           "title": "07/02/2026 - 08/05/2026",
           "startDate": "2026-07-02", "endDate": "2026-08-05"}
    assert site.record_descriptor(rec) == \
        ("statement", "07/02/2026 - 08/05/2026", "2026-07-02", "2026-08-05")
    assert "opaque" not in "".join(site.record_descriptor(rec))


def test_account_label_and_option_shapes():
    assert site.account_label("Mortgage", "5678") == "Mortgage (...5678)"
    assert site.account_label("Asterisk-Free Checking", "1234") == \
        "Asterisk-Free Checking (...1234)"

    assert site.parse_account_option("Asterisk-Free Checking…1234") == \
        ("Asterisk-Free Checking", "1234")
    assert site.parse_account_option("Mortgage…5678") == ("Mortgage", "5678")


def test_filename():
    storage.set_filename_owner("")
    assert build_pdf_filename("2026-04-15", "Escrow Analysis - Mortgage (...5678)", "") == \
        "2026-04-15 Huntington Bank Escrow Analysis - Mortgage (...5678).pdf"


def test_all_four_kinds_are_in_scope_by_default():
    cfg = {"document_types": storage.ALL_CATEGORIES}
    for cat in ["Statement", "Escrow Analysis", "Tax Document", "Correspondence"]:
        assert doc_types.wanted(cat, cfg), cat
    assert not doc_types.wanted("Other Document", cfg)


def test_paperwork_is_skipped():
    assert doc_types.should_skip("Get Balancing Worksheet", RULES)
    assert doc_types.should_skip("Electronic Statement Agreement", RULES)
    assert not doc_types.should_skip("07/02/2026 - 08/05/2026", RULES)


def test_a_date_range_files_on_its_closing_date():
    assert site.parse_period_date("07/02/2026 - 08/05/2026") == \
        ("2026-08-05", "07/02/2026 - 08/05/2026")


def test_month_year_files_on_last_day():
    assert site.parse_period_date("Statement December 2025")[0] == "2025-12-31"
    assert site.parse_period_date("February 2024 Statement")[0] == "2024-02-29"


def test_mmddyyyy_exact():
    assert site.parse_period_date("04/15/2026 Escrow Analysis")[0] == "2026-04-15"


def test_money_actions_are_never_safe():
    for label in ["Pay", "Make a payment", "Schedule payment", "Autopay",
                  "Pay Bills", "Transfer Money", "Send money with Zelle", "Zelle",
                  "Wire transfer", "Deposit", "Withdraw", "Stop a Check",
                  "Stop Multiple Checks", "View Requests & Activity"]:
        assert not site.is_safe_control(label), label
        assert site.FORBIDDEN_CONTROL_RE.search(label), label


def test_huntington_service_center_actions_are_never_safe():
    for label in ["Paperless Settings", "Research Bill Payments",
                  "Research Transactions", "Request Check or Deposit Copies",
                  "Lock or Unlock a Card", "Change PIN", "Activate Card",
                  "Report a Lost or Stolen Card", "Replace a Card",
                  "View Card Information", "Order Checks", "Stop a Check",
                  "Phone, Email & Address", "Change Password", "Change Username",
                  "Registered Devices", "Account Nicknames", "Overdraft Options",
                  "Manage Access Sharing Users", "Open an Account",
                  "Connected Accounts", "Add Payee", "Edit Payees", "Payee List",
                  "Request a statement copy", "Manage Hub", "Manage Dashboard",
                  "LOG OUT", "Submit", "Confirm", "Authorize", "Enroll"]:
        assert not site.is_safe_control(label), label
        assert site.FORBIDDEN_CONTROL_RE.search(label), label


def test_mortgage_servicing_actions_are_never_safe():
    for label in ["Make a mortgage payment", "Pay off my loan", "Payoff quote",
                  "Request payoff", "Escrow shortage payment", "Refinance",
                  "Loan modification", "Forbearance", "Apply now",
                  "Standby Cash", "Line of credit"]:
        assert not site.is_safe_control(label), label


def test_document_actions_are_safe():
    for label in ["View PDF", "Statements", "Tax Forms", "Correspondence",
                  "Download", "Download PDF", "View statement", "View 1098",
                  "2026 Statements", "2025 Tax Forms"]:
        assert site.is_safe_control(label), label


def test_empty_or_ambiguous_control_not_safe():
    assert not site.is_safe_control("")
    assert not site.is_safe_control("More")
    assert not site.is_safe_control("Give us a call")


def test_payment_widget_pickers_are_refused():
    for identity in [
            "fromAccount | From account | Transfer Money",
            "payFromAccount | Pay from | Make a payment",
            "amount | Amount | Payment",
            "payee | Select a payee | Bill Pay",
            "toAccount | To | Zelle"]:
        assert site.is_money_control(identity), identity


def test_the_real_statement_picker_is_allowed():
    for identity in ["base-ui-_r_8_ | Account | Select",
                     "base-ui-_r_15_ | Account | Account Asterisk-Free Checking…1234",
                     "base-ui-_r_15_ | Account | Account Mortgage…5678"]:
        assert not site.is_money_control(identity), identity


def test_unreadable_identity_fails_closed():
    assert site.is_money_control("")


def test_tabs_map_to_record_types():
    assert site.TAB_FOR_RECORD_TYPE["statement"].match("Statements")
    assert site.TAB_FOR_RECORD_TYPE["taxDocument"].match("Tax Forms")
    assert site.TAB_FOR_RECORD_TYPE["correspondence"].match("Correspondence")
    assert not site.TAB_FOR_RECORD_TYPE["statement"].match("Tax Forms")


def test_a_maintenance_notice_is_not_rate_limiting():
    notice = ("Transfers: Most new transfers can be submitted, but some features "
              "may be temporarily unavailable. Bill pay, Zelle, mobile check deposit")
    assert not any(rx.search(notice) for rx in site.RATE_LIMIT_MARKERS)


def test_real_throttling_is_still_detected():
    for text in ["Too many requests", "Our service is temporarily unavailable",
                 "The site is currently unavailable", "HTTP error 429",
                 "We're experiencing technical difficulties",
                 "unusual traffic from your network"]:
        assert any(rx.search(text) for rx in site.RATE_LIMIT_MARKERS), text


def test_the_documents_url_is_not_read_as_signed_out():
    class _P:
        url = site.URLS["documents"]
        def locator(self, _s):
            class _L:
                def count(self): return 0
            return _L()
    assert not site.looks_signed_out(_P())

    class _Q(_P):
        url = "https://onlinebanking.huntington.com/rol/Retail/Auth/Logout"
    assert site.looks_signed_out(_Q())
