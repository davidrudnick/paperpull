"""Synthetic fixtures for provider parsing, filing and control checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage
from paperpull_core import doc_types
import brightstart_site as site
from storage import build_pdf_filename

RULES = doc_types.load_rules()


LISTING_HTML = """
<form action="confirmsSubmit.cs" method="post">
<select name="year"><option value="2026">2026</option><option value="2025">2025</option></select>
<select name="acctExt"><option value="ALL">All Beneficiaries</option>
<option value="01">01 - Alex Sample</option><option value="02">02 - Bo Sample</option></select>
<select name="documentType"><option value="ALL">All Documents</option>
<option value="STATEMENTS">Statements</option><option value="CONFIRMS">Confirms</option>
<option value="TAX">Tax Forms</option></select>
</form>
<table class="unite-table">
  <caption class="unite-table-caption">Statements, Confirms &amp; Tax Forms</caption>
  <thead class="unite-table-header"></thead>
  <tr class="unite-table-row">
    <td class="unite-table-heading">Date</td>
    <td class="unite-table-heading">Account</td>
    <td class="unite-table-heading">Type</td>
  </tr>
  <tr class="unite-table-row">
    <td class="unite-table-cell"><span class="unite-table-heading">Date</span>
        12/31/2025</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Account</span>
        A1234567-01</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Type</span>
        <a href="/ildtpl/confirm/confirmPDF.cs?bId=X1AAA&pId=11111&mac=EAAAASYNTHETIC1" class="unite-link" target="_blank">Statement</a></td>
  </tr>
  <tr class="unite-table-row">
    <td class="unite-table-cell"><span class="unite-table-heading">Date</span>
        12/31/2025</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Account</span>
        A1234567-01</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Type</span>
        <a href="/ildtpl/lit/getPDF.cs?cmsPDF=statementinsert122025.pdf" class="unite-link" target="_blank">Important Plan Information</a></td>
  </tr>
  <tr class="unite-table-row">
    <td class="unite-table-cell"><span class="unite-table-heading">Date</span>
        09/27/2025</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Account</span>
        A1234567-01</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Type</span>
        <a href="/ildtpl/confirm/confirmPDF.cs?bId=111&pId=22222&mac=EAAAASYNTHETIC2" class="unite-link" target="_blank">Statement</a></td>
  </tr>
  <tr class="unite-table-row">
    <td class="unite-table-cell"><span class="unite-table-heading">Date</span>
        09/27/2025</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Account</span>
        A1234567-01</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Type</span>
        <a href="/ildtpl/confirm/confirmPDF.cs?bId=111&pId=33333&mac=EAAAASYNTHETIC3" class="unite-link" target="_blank">Statement</a></td>
  </tr>
  <tr class="unite-table-row">
    <td class="unite-table-cell"><span class="unite-table-heading">Date</span>
        11/29/2025</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Account</span>
        A1234567-02</td>
    <td class="unite-table-cell"><span class="unite-table-heading">Type</span>
        <a href="/ildtpl/confirm/confirmPDF.cs?bId=X1BBB&amp;pId=44444&amp;mac=EAAAASYNTHETIC4" class="unite-link" target="_blank">Financial Confirmation</a></td>
  </tr>
</table>
"""


def test_parse_rows_reads_the_recorded_markup():
    rows = site.parse_rows(LISTING_HTML)
    assert len(rows) == 5
    stmt = rows[0]
    assert stmt["date"] == "2025-12-31"
    assert stmt["account_number"] == "A1234567-01"
    assert stmt["ext"] == "01"
    assert stmt["label"] == "Statement"
    assert stmt["kind"] == site.KIND_CONFIRM
    assert stmt["href"].startswith("/ildtpl/confirm/confirmPDF.cs?bId=X1AAA")


def test_parse_rows_reads_the_insert_link():
    rows = site.parse_rows(LISTING_HTML)
    ins = rows[1]
    assert ins["kind"] == site.KIND_INSERT
    assert ins["label"] == "Important Plan Information"
    assert ins["cms_pdf"] == "statementinsert122025.pdf"


def test_parse_rows_decodes_entity_encoded_hrefs():
    conf = site.parse_rows(LISTING_HTML)[4]
    assert conf["label"] == "Financial Confirmation"
    assert "&amp;" not in conf["href"]
    assert "pId=44444" in conf["href"]


def test_duplicate_same_day_rows_share_a_descriptor():
    rows = site.parse_rows(LISTING_HTML)
    assert site.row_descriptor(rows[2]) == site.row_descriptor(rows[3])
    assert rows[2]["href"] != rows[3]["href"]


def test_row_descriptor_ignores_session_tokens():
    row = site.parse_rows(LISTING_HTML)[0]
    desc = site.row_descriptor(row)
    assert desc == (site.KIND_CONFIRM, "2025-12-31", "A1234567-01", "Statement")
    assert "X1AAA" not in "".join(desc) and "11111" not in "".join(desc)


def test_a_statement_is_a_statement():
    assert site.classify_row(site.KIND_CONFIRM, "Statement") == "Statement"


def test_an_insert_is_a_plan_document():
    assert site.classify_row(site.KIND_INSERT, "Important Plan Information") == \
        "Plan Document"


def test_every_confirmation_label_seen_live_files_as_a_confirmation():
    for label in ["Financial Confirmation", "Change Investment Allocations",
                  "Add Funding Instructions", "Delete Funding Instructions",
                  "New Account", "New Web Registration",
                  "E-Delivery changed to Paper"]:
        assert site.classify_row(site.KIND_CONFIRM, label) == "Confirmation", label


def test_a_tax_looking_label_files_as_a_tax_document():
    for label in ["1099-Q", "2026 Tax Form", "Form 5498"]:
        assert site.classify_row(site.KIND_CONFIRM, label) == "Tax Document", label
    assert doc_types.classify_document("1099-Q", RULES)[:2] == \
        (doc_types.TAX, "1099-Q Tax Form")


def test_an_unknown_label_is_kept_as_a_confirmation_not_dropped():
    assert site.classify_row(site.KIND_CONFIRM, "Address Change") == "Confirmation"


def test_account_option_and_label_shapes():
    assert site.parse_account_option("01 - Alex Sample") == ("01", "Alex Sample")
    assert site.account_label("Alex Sample", "01") == "Alex Sample (...01)"

    assert site.account_label("Bo Sample", "02") != site.account_label("Bo Sample", "03")


def test_quarter_end_statements_get_a_period_label():
    assert site.statement_period("2025-12-31") == "Q4 2025"
    assert site.statement_period("2026-06-30") == "Q2 2026"


def test_converted_history_odd_dates_get_no_period_label():
    assert site.statement_period("2024-09-27") == ""


def test_filename():
    storage.set_filename_owner("")
    assert build_pdf_filename("2025-12-31", "Important Plan Information", "") == \
        "2025-12-31 Bright Start 529 Important Plan Information.pdf"


def test_all_four_kinds_are_in_scope_by_default():
    cfg = {"document_types": storage.ALL_CATEGORIES}
    for cat in ["Statement", "Confirmation", "Tax Document", "Plan Document"]:
        assert doc_types.wanted(cat, cfg), cat
    assert not doc_types.wanted("Other Document", cfg)


def test_insert_cdn_url_is_the_public_pdf():
    assert site.insert_cdn_url("statementinsert122025.pdf") == \
        "https://cdn.unite529.com/jcdn/files/ILD/pdfs/statementinsert122025.pdf"


def test_path_like_insert_names_are_refused():
    for bad in ["../secrets.pdf", "a/b.pdf", "x?y=1", ""]:
        assert site.insert_cdn_url(bad) == "", bad


def test_a_signed_in_listing_is_not_read_as_signed_out():
    assert not site.html_looks_signed_out(LISTING_HTML)


def test_a_login_page_response_is_read_as_signed_out():
    login = '<html><form action="/ildtpl/auth/ll.cs">' \
            '<input type="password" name="pw"></form></html>'
    assert site.html_looks_signed_out(login)
    assert site.html_looks_signed_out("")


def test_the_documents_url_is_not_read_as_signed_out():
    class _P:
        url = site.URLS["documents"]
        def locator(self, _s):
            class _L:
                def count(self): return 0
            return _L()
    assert not site.looks_signed_out(_P())

    class _Q(_P):
        url = "https://www.brightstart-529.com/ildtpl/auth/ll.cs"
    assert site.looks_signed_out(_Q())

    class _R(_P):
        url = ("https://www.brightstart-529.com/ildtpl/confirm/confirmPDF.cs"
               "?pId=11111&__cookieCheck=true")
    assert site.looks_signed_out(_R())


def test_money_actions_are_never_safe():
    for label in ["Contribute Save money for college", "Contribute",
                  "Withdraw", "Take a Withdrawal", "Request a Distribution",
                  "Move Money", "Transfer", "Rollover", "Roll over funds",
                  "Exchange", "Change Investments", "Buy", "Sell",
                  "Invest Now", "Set up recurring contributions"]:
        assert not site.is_safe_control(label), label
        assert site.FORBIDDEN_CONTROL_RE.search(label), label


def test_brightstart_portal_actions_are_never_safe():
    for label in ["Enroll Open a New 529 account",
                  "Continue Enrollment Open a New 529 account",
                  "Share Ugift code and view history of gifts",
                  "Bank Information", "Payroll Direct Deposit",
                  "Delivery Preferences", "Password & Security Features",
                  "Beneficiaries", "Successors", "Authorized Agents",
                  "Interested Parties", "Trusted Contact",
                  "Edit Address", "Edit Contact", "View Details",
                  "Log Off", "Submit", "Confirm", "Continue", "Authorize"]:
        assert not site.is_safe_control(label), label
        assert site.FORBIDDEN_CONTROL_RE.search(label), label


def test_document_actions_are_safe():
    for label in ["Search", "View PDF", "Download", "Download PDF",
                  "View statement", "View 1099-Q"]:
        assert site.is_safe_control(label), label


def test_empty_or_ambiguous_control_not_safe():
    assert not site.is_safe_control("")
    assert not site.is_safe_control("More")
    assert not site.is_safe_control("Menu")
    assert not site.is_safe_control("Give us a call")


def test_a_maintenance_notice_is_not_rate_limiting():
    notice = ("Please note: Historical statements and tax forms may be "
              "temporarily unavailable. To view historical transactions "
              "please visit the Transactions section of your account.")
    assert not any(rx.search(notice) for rx in site.RATE_LIMIT_MARKERS)


def test_real_throttling_is_still_detected():
    for text in ["Too many requests", "Our service is temporarily unavailable",
                 "The site is currently unavailable", "HTTP error 429",
                 "We're experiencing technical difficulties",
                 "unusual traffic from your network"]:
        assert any(rx.search(text) for rx in site.RATE_LIMIT_MARKERS), text
