"""Synthetic fixtures for provider parsing, filing and control checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage
from paperpull_core import doc_types
import stp_site as site
from storage import build_pdf_filename

RULES = doc_types.load_rules()


def _row(**kw):
    base = {
        "Alerts": None, "Document_Name": "Capital Call Notice",
        "Document_Type_Name": "Capital Call Notice",
        "Document_Description": None,
        "Account_Id": "1234", "Account_Name": "Sample Investor",
        "Fund_Id": "100", "Fund_Name": "Example-A (Example Fund A)",
        "Class_Id": None, "Class_Name": "Example-A (Example Fund A)",
        "Effective_Date": "2024-06-15T00:00:00",
        "Publish_Date": "2025-03-01T00:00:00.0000000",
        "Creation_Date": "2025-03-01T00:00:00.0000000",
        "Document_Status": "Published", "Document_State_Name": "Firm External",
        "File_Type": "pdf", "Collections_Name": None,
        "Document_Folder_Name": "Investor",
        "Document_SubFolder_Name": "Investor Reporting",
        "Document_Id": "00000000-0000-4000-8000-000000000001",
        "Fund_Code": "Example Fund A", "TotalCount": None,
    }
    base.update(kw)
    return base


def test_a_capital_call_notice_is_an_investor_report_on_its_effective_date():
    cat, date, period, title = site.classify_document(_row())
    assert cat == "Investor Report"
    assert date == "2024-06-15"
    assert period == ""
    assert title == "Capital Call Notice"


def test_a_partner_capital_statement_is_an_investor_report():
    cat, date, _p, title = site.classify_document(_row(
        Document_Name="Partner Capital Statement",
        Document_Type_Name="Partner Capital Statement",
        Effective_Date="2025-06-30T00:00:00"))
    assert cat == "Investor Report"
    assert date == "2025-06-30"
    assert title == "Partner Capital Statement"


def test_a_k1_is_a_tax_document_whose_period_is_its_effective_year():
    cat, date, period, title = site.classify_document(_row(
        Document_Name="K-1", Document_Type_Name="K-1",
        Effective_Date="2024-12-31T00:00:00",
        Document_SubFolder_Name="Tax"))
    assert cat == "Tax Document"
    assert date == "2024-12-31"
    assert period == "2024"
    assert title == "K-1"


def test_a_w9_is_a_tax_document():
    cat, _d, _p, title = site.classify_document(_row(
        Document_Name="W-9", Document_Type_Name="W-9",
        Effective_Date="2023-05-01T00:00:00",
        Document_SubFolder_Name="Tax"))
    assert cat == "Tax Document"
    assert title == "W-9"


def test_a_subscription_agreement_is_onboarding_and_never_skipped():
    cat, _d, _p, title = site.classify_document(_row(
        Document_Name="Subscription Agreement",
        Document_Type_Name="Subscription Agreement",
        Document_SubFolder_Name="Onboarding"))
    assert cat == "Onboarding Document"
    assert not doc_types.should_skip("Subscription Agreement", RULES)
    assert not doc_types.should_skip("Operating Agreement", RULES)


def test_fund_level_documents_have_no_account():
    cat, _d, _p, _t = site.classify_document(_row(
        Document_Name="Annual Financials",
        Document_Type_Name="Annual Financials",
        Account_Id=None, Account_Name=None,
        Effective_Date="2024-12-31T00:00:00",
        Document_Folder_Name="Fund",
        Document_SubFolder_Name="Fund Materials"))
    assert cat == "Fund Material"
    assert site.document_descriptor(_row(Account_Id=None))[3] == ""


def test_a_blinded_allocation_is_an_xlsx_fund_material():
    row = _row(Document_Name="Blinded Capital Call Allocation",
               Document_Type_Name="Blinded Capital Call Allocation",
               Account_Id=None, File_Type="xlsx",
               Document_Folder_Name="Fund",
               Document_SubFolder_Name="Fund Materials")
    cat, _d, _p, title = site.classify_document(row)
    assert cat == "Fund Material"
    assert row["File_Type"] == "xlsx"
    assert site.FILE_MAGIC["xlsx"] == b"PK\x03\x04"
    assert site.FILE_MAGIC["pdf"] == b"%PDF-"


def test_an_unknown_subfolder_is_kept_not_dropped():
    cat, _d, _p, _t = site.classify_document(_row(
        Document_SubFolder_Name="Surprises"))
    assert cat == "Other Document"


def test_document_descriptor_is_what_identifies_a_document():
    row = _row()
    assert site.document_descriptor(row) == \
        ("Capital Call Notice", "Capital Call Notice", "2024-06-15",
         "1234", "Example-A (Example Fund A)")
    assert "00000000" not in "".join(site.document_descriptor(row))


def test_fund_name_not_the_drifting_fund_code_is_the_label():
    row = _row(Fund_Code="Example Fund B",
               Fund_Name="Example-B")
    assert site.fund_label(row) == "Example-B"
    assert site.document_descriptor(row)[4] == "Example-B"


def test_filename():
    storage.set_filename_owner("")
    assert build_pdf_filename(
        "2024-12-31", "K-1 - Example-B - 1234", "") == \
        "2024-12-31 STP Investment Services K-1 - Example-B - 1234.pdf"


def test_all_four_kinds_are_in_scope_by_default():
    cfg = {"document_types": storage.ALL_CATEGORIES}
    for cat in ["Investor Report", "Tax Document", "Onboarding Document",
                "Fund Material"]:
        assert doc_types.wanted(cat, cfg), cat
    assert not doc_types.wanted("Other Document", cfg)


def test_the_execute_body_asks_for_everything():
    body = site._execute_body(site.FALLBACK_PARAMETER_IDS)
    assert body["reportId"] == site.REPORT_ID
    assert len(body["parameters"]) == 6
    by_id = {p["id"]: p for p in body["parameters"]}
    assert by_id[site.FALLBACK_PARAMETER_IDS["Document_Type"]]["value"] is None
    assert by_id[site.FALLBACK_PARAMETER_IDS["Account_Code"]]["value"] is None
    assert by_id[site.FALLBACK_PARAMETER_IDS["Read_UnRead"]]["value"] == \
        site.READ_UNREAD_BOTH
    for k in ("Dynamic_Date_Start", "Dynamic_Date_End"):
        p = by_id[site.FALLBACK_PARAMETER_IDS[k]]
        assert p["value"] == "1900-01-01" and p["dataTypeCode"] == "DateTime"


def test_dates_parse():
    assert site.parse_date("2024-06-15T00:00:00") == "2024-06-15"
    assert site.parse_date("06/15/2024") == "2024-06-15"
    assert site.parse_date("") is None


def test_investing_actions_are_never_safe():
    for label in ["Invest", "Subscribe", "Make a new investment",
                  "View investments", "Commit", "Fund now",
                  "Add investment", "Pay capital call"]:
        assert not site.is_safe_control(label), label


def test_money_actions_are_never_safe():
    for label in ["Transfer Funds", "Wire instructions setup", "Move Money",
                  "Deposit", "Withdraw", "Send money", "Make a payment",
                  "Bank details", "Redeem", "Distribution request",
                  "ACH", "Update banking information"]:
        assert not site.is_safe_control(label), label
        assert site.FORBIDDEN_CONTROL_RE.search(label), label


def test_esignature_actions_are_never_safe():
    for label in ["Sign", "Sign here", "E-Sign", "DocuSign",
                  "Adopt signature", "Initial here", "Execute agreement",
                  "Countersign"]:
        assert not site.is_safe_control(label), label


def test_settings_actions_are_never_safe():
    for label in ["View settings", "Update profile", "Change password",
                  "Notification preferences", "Invite user", "Add member",
                  "Submit", "Confirm", "Continue", "Next", "I Agree",
                  "Accept", "Authorize", "Approve", "Log Out", "Sign out",
                  "Enroll", "Apply"]:
        assert not site.is_safe_control(label), label


def test_document_actions_are_safe():
    for label in ["Get documents", "Show filters", "Open Filter Menu",
                  "Download", "View PDF", "Unread indicator",
                  "All Documents", "Investor Reporting", "Onboarding",
                  "Tax", "Fund Materials", "Search"]:
        assert site.is_safe_control(label), label


def test_document_names_are_safe_but_their_verbs_are_not():
    for doc in ["Subscription Agreement", "Commitment Letter",
                "Commitment Confirmation", "Capital Call Notice",
                "Distribution Notice", "Blinded Capital Call Allocation",
                "Partner Capital Statement", "K-1", "W-9", "W-8",
                "Annual Financials", "Operating Agreement",
                "Offering Memorandum", "Side Letter", "Sponsor Materials",
                "Membership Transfer", "Agent Authorization"]:
        assert site.is_safe_control(doc), doc
    assert not site.is_safe_control("Subscribe")
    assert not site.is_safe_control("Commit")
    assert not site.is_safe_control("Pay capital call")
    assert not site.is_safe_control("Distribution request")
    assert not site.is_safe_control("Sign")


def test_empty_or_ambiguous_control_not_safe():
    assert not site.is_safe_control("")
    assert not site.is_safe_control("More")
    assert not site.is_safe_control("See more")
    assert not site.is_safe_control("Open main menu")


def test_signed_out_is_the_b2c_login():
    class _P:
        url = site.URLS["documents"]
        def locator(self, _s):
            class _L:
                def count(self): return 0
            return _L()
    assert not site.looks_signed_out(_P())

    class _Q(_P):
        url = ("https://login.blueprintplatform.com/blueprintplatform"
               ".onmicrosoft.com/b2c_1_signin/oauth2/v2.0/authorize?x=y")
    assert site.looks_signed_out(_Q())


def test_real_throttling_is_still_detected():
    for text in ["Too many requests", "Our service is temporarily unavailable",
                 "HTTP error 429", "unusual traffic from your network"]:
        assert any(rx.search(text) for rx in site.RATE_LIMIT_MARKERS), text
