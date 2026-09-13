"""Documents are listed through the BluePrint report API and downloaded as a
base64 envelope. Tokens are read from the signed-in tab and kept in memory.
Document identity uses kind/name/date/account/fund and occurrence. PDF and
XLSX are distinct supported formats. The portal report schema and identifiers
are provider integration constants; broader firm layouts remain unverified.

All requests and navigation must stay on explicitly allowed provider hosts.
"""

from __future__ import annotations

import base64
import logging
import re
import time as _time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from urllib.parse import urlsplit, urljoin
from paperpull_core.controls import SETTINGS_CONTROL_RE, AUTH_CONTROL_RE

ALLOWED_HOSTS = {'api.blueprintplatform.com', 'app.blueprintplatform.com'}


def is_safe_url(url: str) -> bool:
    try:
        parts = urlsplit(url or "")
        return (parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
                and parts.port in (None, 443) and not parts.username
                and not parts.password)
    except (TypeError, ValueError):
        return False


log = logging.getLogger("stp_docs.site")

BASE = "https://app.blueprintplatform.com"
API_BASE = "https://api.blueprintplatform.com"
URLS = {
    "home": f"{BASE}/",
    "login": f"{BASE}/",
    "documents": f"{BASE}/investor-portal/documents",
}
API = {
    "metadata": f"{API_BASE}/api/flat/v1/user/metadata",
    "parameters": f"{API_BASE}/report-definition/api/flat/v1/report/parameters",
    "execute": f"{API_BASE}/report-data/api/flat/v1/report/execute",
    "doc_view": f"{API_BASE}/docvault/api/flat/v1/doc/view/",
}
DOCUMENT_URL_CANDIDATES = [URLS["documents"]]


APPLICATION_ID = "7E6515E4-0585-4BAD-9BAE-EAC9D468C50F"


REPORT_ID = "DD26C787-1C6D-431E-B180-6BB878FE7B21"
READ_UNREAD_BOTH = ("D2BEC775-B596-4647-AA29-0659CDD330FF,"
                    "67479880-0680-4D3E-93AA-1B3D595C4060")

FALLBACK_PARAMETER_IDS = {
    "Document_Type": "c0cc0d56-1b47-4607-ad3b-a37febd75c84",
    "Product_Code": "eecc450d-0ba9-405c-b90e-ba7a2cdf53cf",
    "Account_Code": "f22646f3-732b-465e-8064-287fb523a39a",
    "Read_UnRead": "c223155f-5e8e-4ae2-927f-a220669c025e",
    "Dynamic_Date_Start": "d7157eee-3cdd-460d-ae8c-e6cc2ff13049",
    "Dynamic_Date_End": "f25b84e9-1f2f-45a8-be99-f3e6223caeae",
}


LOGIN_URL_MARKERS = ["login.blueprintplatform.com", "b2c_1_signin",
                     "b2clogin.com", "/authorize", "/login", "/signin",
                     "/sign-in"]


FILE_MAGIC = {"pdf": b"%PDF-", "xlsx": b"PK\x03\x04"}


FORBIDDEN_CONTROL_RE = re.compile(

    r"(\binvest\b|\bsubscribe\b|make\s+(a|an|another|new)\s+investment|"
    r"new\s+investment|add\s+investment|\bcommit\b(?!ment)|fund\s+(now|your)|"
    r"view\s+investments|capital\s+call\s+payment|pay\s+capital|"


    r"(?<!membership )transfer|wire\b|\bach\b|move\s+money|send\s+money|deposit|withdraw|"
    r"\bpay\b|payment|banking|bank\s+(details|info|account)|redeem|"
    r"distribut(e|ion)\s+(request|instruction|election)|"

    r"\bsign\b(?!ed|\s+out)|e-?sign|docu\s*sign|adopt\s+signature|"
    r"initial\s+here|sign\s+here|counter-?sign|execute\b|"

    r"open\s+(a|an|another|new)\b[\w\s]{0,24}\baccount\b|apply|enroll|"
    r"invite|add\s+(user|member|agent|payee|bank)|"
    r"change\s+|edit\s+|update\s+|set\s+up|enable|disable|delete|remove|"
    r"beneficiar|contact\s+info|\baddress\b|password|username|"
    r"view\s+settings|settings\b|preferences|notification|"


    r"submit|\bconfirm\b(?!ation)|continue(?!\s+session)|next\b|\bagree\b|"
    r"\baccept\b|authorize|i\s+agree|approve|log\s*out|logout|sign\s+out)", re.I)

SAFE_DOC_CONTROL_RE = re.compile(
    r"(download|\bview\b(?!\s+(settings|investments))|save|print|"
    r"pdf|get\s+documents|show\s+filters|open\s+filter\s+menu|"
    r"filter|search|read/unread|unread\s+indicator|"
    r"document|statement|notice|capital\s+call|distribution\s+notice|"
    r"allocation|k-1\b|w-[89]\b|tax\b|annual\s+financials|"
    r"commitment\s+(letter|confirmation)|subscription\s+agreement|"
    r"operating\s+agreement|offering\s+memorandum|side\s+letter|"
    r"sponsor\s+materials|membership\s+transfer|agent\s+authorization|"
    r"investor\s+reporting|onboarding|fund\s+materials|"
    r"still\s+here|continue\s+session)", re.I)

SECURITY_CHALLENGE_MARKERS = [
    "enter the code we sent", "enter your verification code", "verification code",
    "one-time", "one time passcode", "security code", "we sent a code",
    "two-factor", "two-step", "authenticator", "confirm your identity",
    "verify your identity", "we need to verify", "unusual activity",
    "are you a robot", "captcha", "unable to verify", "trouble verifying",
    "your session has expired", "please log in again", "you've been logged out",
    "for your security", "session timed out",
]

RATE_LIMIT_MARKERS = [
    re.compile(r"too many requests", re.I),
    re.compile(r"rate limit(ed|ing)?\b", re.I),
    re.compile(r"unusual traffic", re.I),
    re.compile(r"\b(http\s*)?(error\s*)?429\b", re.I),
    re.compile(r"(site|service|page|system|application)\s+(is\s+)?"
               r"(currently\s+|temporarily\s+)*unavailable", re.I),
    re.compile(r"we'?re\s+(currently\s+)?(experiencing|having)\s+"
               r"(technical\s+)?(difficulties|issues)", re.I),
]


CATEGORY_INVESTOR_REPORT = "Investor Report"
CATEGORY_TAX = "Tax Document"
CATEGORY_ONBOARDING = "Onboarding Document"
CATEGORY_FUND_MATERIAL = "Fund Material"
CATEGORY_OTHER = "Other Document"

CATEGORY_FOR_SUBFOLDER = {
    "Investor Reporting": CATEGORY_INVESTOR_REPORT,
    "Tax": CATEGORY_TAX,
    "Onboarding": CATEGORY_ONBOARDING,
    "Fund Materials": CATEGORY_FUND_MATERIAL,
}

TAX_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?!\d)")
MDY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def parse_date(text: str) -> Optional[str]:
    if not text:
        return None
    m = ISO_RE.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = MDY_RE.search(text)
    if m:
        return f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None


def looks_signed_out(page) -> bool:
    url = (page.url or "").lower()
    if any(m in url for m in LOGIN_URL_MARKERS):
        return True
    try:
        if page.locator("input[type='password']").count() > 0:
            return True
    except Exception:
        pass
    return False


def on_documents_page(page) -> bool:
    try:
        url = (page.url or "").lower()
        if "/investor-portal/documents" not in url:
            return False
        return not looks_signed_out(page)
    except Exception:
        return False


def detect_security_challenge(page) -> Optional[str]:
    try:
        if on_documents_page(page):
            return None
    except Exception:
        pass
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    try:
        body = page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        body = ""
    hay = title + "\n" + body[:1500]
    for m in SECURITY_CHALLENGE_MARKERS:
        if m in hay:
            return f"Security challenge detected: '{m}'"
    for rx in RATE_LIMIT_MARKERS:
        m = rx.search(hay)
        if m:
            return f"Possible rate limiting detected: '{m.group(0)}'"
    return None


def is_safe_control(name: str) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    if name == "Agent Authorization":
        return True
    if (FORBIDDEN_CONTROL_RE.search(name) or SETTINGS_CONTROL_RE.search(name)
            or AUTH_CONTROL_RE.search(name)):
        return False
    return bool(SAFE_DOC_CONTROL_RE.search(name))


def dismiss_timeout(page) -> None:
    for pattern in (r"continue session", r"i'?m still here",
                    r"stay (signed|logged) in", r"keep me (signed|logged) in",
                    r"extend (my )?session", r"still (there|here)\?"):
        try:
            c = page.get_by_role("button", name=re.compile(pattern, re.I))
            if c.count() and c.first.is_visible():
                c.first.click()
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass


def goto_documents(page) -> bool:
    dismiss_timeout(page)
    if on_documents_page(page):
        return True
    for url in DOCUMENT_URL_CANDIDATES:
        try:
            if not is_safe_url(url):
                continue
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            dismiss_timeout(page)
            if looks_signed_out(page):
                return False
            for _ in range(20):
                if on_documents_page(page):
                    log.info("documents area reached at %s", page.url)
                    return True
                page.wait_for_timeout(500)
        except Exception as e:
            log.info("documents URL %s failed: %s", url, e)
    return on_documents_page(page)


def ensure_documents(page) -> bool:
    dismiss_timeout(page)
    if on_documents_page(page):
        return True
    return goto_documents(page)


_READ_TOKEN_JS = """() => {
  for (const store of [sessionStorage, localStorage]) {
    for (let i = 0; i < store.length; i++) {
      const k = store.key(i);
      if (/accesstoken/i.test(k)) {
        try {
          const v = JSON.parse(store.getItem(k));
          if (v && v.secret) return v.secret;
        } catch (e) {}
      }
    }
  }
  return '';
}"""

_FETCH_JSON_JS = """async ({url, headers, body}) => {
  const opts = {headers: headers};
  if (body !== null) {
    opts.method = 'POST';
    opts.headers = {...headers, 'content-type': 'application/json'};
    opts.body = JSON.stringify(body);
  }
  const ppTarget = new URL(url, location.href);
  if (ppTarget.protocol !== "https:" || !["app.blueprintplatform.com", "api.blueprintplatform.com"].includes(ppTarget.hostname) || ppTarget.username || ppTarget.password || (ppTarget.port && ppTarget.port !== "443")) throw new Error("Refusing an off-host document request");
  const r = await fetch(url, opts);
  const text = await r.text();
  let j = null;
  try { j = JSON.parse(text); } catch (e) {}
  return {status: r.status, body: j, text: j ? '' : text.slice(0, 300)};
}"""


def _evaluate_with_retry(page, js: str, arg, attempts: int = 2):
    last = None
    for i in range(attempts):
        try:
            return page.evaluate(js, arg)
        except Exception as e:
            last = e
            log.info("page fetch attempt %d failed: %s", i + 1, e)
            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass
    raise last


def _read_token(page) -> str:
    try:
        return page.evaluate(_READ_TOKEN_JS) or ""
    except Exception as e:
        log.info("token read failed: %s", e)
        return ""


_identity_cache: Dict[int, Tuple[dict, float]] = {}
_IDENTITY_TTL_SECONDS = 20 * 60


def _base_headers(token: str) -> dict:
    import uuid
    return {
        "authorization": f"Bearer {token}",
        "application-id": APPLICATION_ID,
        "accept": "application/json, text/plain, */*",
        "request-tracking-id": str(uuid.uuid4()),
        "correlation-id": str(uuid.uuid4()),
    }


def get_identity(page, force: bool = False) -> Optional[dict]:
    key = id(page)
    if not force:
        ident, when = _identity_cache.get(key, (None, 0.0))
        if ident and (_time.time() - when) < _IDENTITY_TTL_SECONDS:
            return ident
    token = _read_token(page)
    if not token:
        log.info("no access token in the tab's storage")
        return None
    res = _evaluate_with_retry(page, _FETCH_JSON_JS, {
        "url": API["metadata"], "headers": _base_headers(token), "body": None})
    body = (res or {}).get("body")
    if (res or {}).get("status") != 200 or not isinstance(body, dict):
        log.info("metadata answered %s %r", (res or {}).get("status"),
                 ((res or {}).get("text") or "")[:120])
        return None
    profiles = body.get("profiles") or []
    profile = next((p for p in profiles if p.get("isDefault")), profiles[0] if profiles else None)
    if not profile:
        return None
    firms = profile.get("firms") or []
    firm = next((f for f in firms if f.get("isDefault")), firms[0] if firms else None)
    if not firm:
        return None
    ident = {
        "profile_id": profile.get("userProfileId") or "",
        "firm_id": str(firm.get("firmId") or ""),
        "firm_name": firm.get("displayName") or "",
        "timeout_minutes": firm.get("timeoutMinute") or 0,
    }
    _identity_cache[key] = (ident, _time.time())
    return ident


def _api_headers(page, ident: dict) -> Optional[dict]:
    token = _read_token(page)
    if not token:
        return None
    h = _base_headers(token)
    h["user-profile-id"] = ident["profile_id"]
    h["firm-id"] = ident["firm_id"]
    h["lob-code"] = "FundManagement"
    return h


def _api_call(page, url: str, post_body: Optional[dict] = None):
    ident = get_identity(page)
    if not ident:
        return {"status": 0, "body": None, "text": "no identity (signed out?)"}
    headers = _api_headers(page, ident)
    if not headers:
        return {"status": 0, "body": None, "text": "no access token"}
    res = _evaluate_with_retry(page, _FETCH_JSON_JS,
                               {"url": url, "headers": headers, "body": post_body})
    if (res or {}).get("status") in (401, 403):
        log.info("API answered %s - reloading the tab to renew the token",
                 res.get("status"))
        try:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
        except Exception:
            pass
        ident = get_identity(page, force=True)
        headers = _api_headers(page, ident) if ident else None
        if headers:
            res = _evaluate_with_retry(page, _FETCH_JSON_JS,
                                       {"url": url, "headers": headers,
                                        "body": post_body})
    return res


_parameter_cache: Dict[int, Dict[str, str]] = {}


def report_parameter_ids(page) -> Dict[str, str]:
    key = id(page)
    if key in _parameter_cache:
        return _parameter_cache[key]
    res = _api_call(page, API["parameters"], {"reportid": REPORT_ID.lower()})
    rows = (res or {}).get("body")
    ids: Dict[str, str] = {}
    if isinstance(rows, list):
        for r in rows:
            src = (r or {}).get("dataSourceCode")
            pid = (r or {}).get("reportParameterId")
            if src and pid:
                ids[src] = pid
    if not all(k in ids for k in FALLBACK_PARAMETER_IDS):
        log.info("parameters call incomplete (%s) - using recorded ids",
                 sorted(ids))
        ids = {**FALLBACK_PARAMETER_IDS, **ids}
    _parameter_cache[key] = ids
    return ids


def _execute_body(param_ids: Dict[str, str]) -> dict:
    return {"reportId": REPORT_ID, "parameters": [
        {"id": param_ids["Document_Type"], "dataTypeCode": "String",
         "type": None, "value": None},
        {"id": param_ids["Product_Code"], "dataTypeCode": "String",
         "type": None, "value": None},
        {"id": param_ids["Account_Code"], "dataTypeCode": "String",
         "type": None, "value": None},
        {"id": param_ids["Read_UnRead"], "dataTypeCode": "String",
         "type": None, "value": READ_UNREAD_BOTH},
        {"id": param_ids["Dynamic_Date_Start"], "dataTypeCode": "DateTime",
         "value": "1900-01-01", "type": None},
        {"id": param_ids["Dynamic_Date_End"], "dataTypeCode": "DateTime",
         "value": "1900-01-01", "type": None},
    ]}


def list_documents(page) -> List[dict]:
    body = _execute_body(report_parameter_ids(page))
    res = _api_call(page, API["execute"], body)
    data = (res or {}).get("body")
    if (res or {}).get("status") != 200 or not isinstance(data, dict):
        log.info("execute answered %s %r", (res or {}).get("status"),
                 ((res or {}).get("text") or "")[:120])
        return []
    return [r for r in (data.get("reportData") or []) if isinstance(r, dict)]


def fund_label(row: dict) -> str:
    return re.sub(r"\s+", " ", row.get("Fund_Name") or "").strip()


def classify_document(row: dict) -> Tuple[str, str, str, str]:
    sub = (row.get("Document_SubFolder_Name") or "").strip()
    category = CATEGORY_FOR_SUBFOLDER.get(sub, CATEGORY_OTHER)
    title = re.sub(r"\s+", " ", row.get("Document_Name") or "").strip()
    date = parse_date(row.get("Effective_Date") or "") or ""
    period = ""
    if category == CATEGORY_TAX:
        m = TAX_YEAR_RE.search(title)
        period = m.group(1) if m else (date[:4] if date else "")
    if not title:
        title = (row.get("Document_Type_Name") or "").strip() or "Document"
    return category, date, period, title


def document_descriptor(row: dict) -> Tuple[str, str, str, str, str]:
    return ((row.get("Document_Type_Name") or "").strip(),
            re.sub(r"\s+", " ", row.get("Document_Name") or "").strip(),
            parse_date(row.get("Effective_Date") or "") or "",
            (row.get("Account_Id") or "").strip(),
            fund_label(row))


def collect_documents(page) -> List[dict]:
    rows = list_documents(page)
    log.info("STP/BluePrint: %d document row(s)", len(rows))
    out = []
    seen: Dict[Tuple[str, str, str, str, str], int] = {}
    for row in rows:
        category, date, period, title = classify_document(row)
        desc = document_descriptor(row)
        occ = seen.get(desc, 0)
        seen[desc] = occ + 1
        out.append({
            "account_id": desc[3],
            "account_name": re.sub(r"\s+", " ", row.get("Account_Name") or "").strip(),
            "fund": desc[4],
            "fund_id": (row.get("Fund_Id") or "").strip(),
            "doc_type": desc[0],
            "file_type": (row.get("File_Type") or "pdf").strip().lower(),
            "document_id": (row.get("Document_Id") or "").strip(),
            "title": title, "category": category, "date": date,
            "period": period, "occurrence": occ,
        })
    return out


def resolve_document(page, doc_type: str, title: str, date: str,
                     account_id: str, fund: str,
                     occurrence: int = 0) -> Optional[dict]:
    want = (doc_type, re.sub(r"\s+", " ", title or "").strip(), date,
            (account_id or "").strip(), (fund or "").strip())
    n = 0
    for row in list_documents(page):
        if document_descriptor(row) == want:
            if n == occurrence:
                return row
            n += 1
    return None


def fetch_document(page, document_id: str) -> Tuple[int, str, bytes]:
    res = _api_call(page, API["doc_view"] + document_id)
    body = (res or {}).get("body")
    status = int((res or {}).get("status") or 0)
    if status != 200 or not isinstance(body, dict):
        log.info("doc view answered %s %r", status,
                 ((res or {}).get("text") or "")[:120])
        return status, "", b""
    try:
        data = base64.b64decode(body.get("documentFile") or "")
    except Exception:
        data = b""
    return status, (body.get("fileType") or "").lower(), data


def download_document(page, doc_type: str, title: str, date: str,
                      account_id: str, fund: str, file_type: str,
                      out_path: Path, occurrence: int = 0,
                      document_id_hint: str = "") -> bool:
    row = resolve_document(page, doc_type, title, date, account_id, fund,
                           occurrence)
    document_id = (row or {}).get("Document_Id") or ""
    if not document_id and document_id_hint:
        log.info("document %r (%s %s) not in the fresh list - trying the stored id",
                 title, doc_type, date)
        document_id = document_id_hint
    if not document_id:
        log.info("document %r (%s %s) could not be resolved", title, doc_type, date)
        return False
    status, env_type, data = fetch_document(page, document_id)
    if status != 200 or not data:
        log.info("download answered %s (%d bytes) for %r", status,
                 len(data or b""), title)
        return False
    expect = FILE_MAGIC.get((env_type or file_type or "pdf").lower(),
                            FILE_MAGIC["pdf"])
    if not data.startswith(expect):
        log.info("download for %r did not start with %r (got %r)",
                 title, expect, data[:8])
        return False
    Path(out_path).write_bytes(data)
    return True


_READ_UI_JS = """() => {
  const out = {menu: [], buttons: [], total: '', rows: 0};
  const clean = (s) => (s || '').trim().replace(/\\s+/g, ' ');
  for (const el of document.querySelectorAll('button')) {
    const t = clean(el.textContent).slice(0, 60);
    if (t) out.buttons.push(t);
  }
  const text = clean(document.body.innerText);
  const m = text.match(/Total Documents:\\s*(\\d+)/i);
  if (m) out.total = m[1];
  out.rows = document.querySelectorAll('[role="row"]').length;
  for (const t of ['All Documents', 'Investor Reporting', 'Onboarding',
                   'Tax', 'Fund Materials'])
    if (text.includes(t)) out.menu.push(t);
  out.buttons = [...new Set(out.buttons)].slice(0, 40);
  return out;
}"""


def read_page_ui(page) -> Optional[dict]:
    try:
        return page.evaluate(_READ_UI_JS)
    except Exception as e:
        log.info("page UI read failed: %s", e)
        return None


def redact_label(text: str) -> str:
    return re.sub(r"\d", "#", text or "")
