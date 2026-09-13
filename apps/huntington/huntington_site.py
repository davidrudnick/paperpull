"""The statements interface is a web component backed by account and record
endpoints. Re-resolve records by descriptor before downloading; never use
opaque record IDs as durable document identity. Escrow analyses and
correspondence have separate categories. A guarded row capture is the fallback.

All requests and navigation must stay on explicitly allowed provider hosts.
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from urllib.parse import urlsplit, urljoin
from paperpull_core.controls import SETTINGS_CONTROL_RE, AUTH_CONTROL_RE

ALLOWED_HOSTS = {'onlinebanking.huntington.com', 'www.huntington.com'}


def is_safe_url(url: str) -> bool:
    try:
        parts = urlsplit(url or "")
        return (parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
                and parts.port in (None, 443) and not parts.username
                and not parts.password)
    except (TypeError, ValueError):
        return False


log = logging.getLogger("huntington_docs.site")

BASE = "https://onlinebanking.huntington.com"
PUBLIC = "https://www.huntington.com"
URLS = {
    "home": f"{BASE}/rol/Retail/AccountServices/Hub",
    "login": f"{PUBLIC}/",
    "documents": f"{BASE}/rol/Retail/AccountServices/ViewStatements",
    "logout": f"{BASE}/rol/Retail/Auth/Logout",
}
API = {
    "accounts": "/rol/Retail/api/documents/1.0/statements/accounts",
    "records": "/rol/Retail/api/documents/1.0/statements/accounts/{account_id}/records",
    "view": ("/rol/Retail/api/documents/1.0/statements/accounts/{account_id}"
             "/records/{record_id}/view?type={record_type}"),
}
DOCUMENT_URL_CANDIDATES = [URLS["documents"]]


LOGIN_URL_MARKERS = ["/rol/retail/auth/", "/login", "/logon", "/signin",
                     "/sign-in", "/mfa", "/verify-identity", "www.huntington.com/"]


HOST = "olb-feat-viewstatements"


FORBIDDEN_CONTROL_RE = re.compile(

    r"(transfer|deposit|withdraw|wire\b|move\s+money|send\s+money|zelle|"
    r"pay\b|payment|pay\s+bills?|bill\s*pay|autopay|auto-?pay|schedule\s+payment|"
    r"make\s+a\s+payment|stop\s+(a\s+|multiple\s+)?(payment|check)|real.?time\s+payments?|"
    r"requests?\s*(&|and)\s*activity|"
    r"payoff|pay\s*off|principal\s+payment|extra\s+payment|"

    r"escrow\s+(shortage|payment|deposit)|refinanc|modif|forbearance|"
    r"overdraft|standby\s+cash|line\s+of\s+credit|credit\s+line|credit\s+limit|"
    r"loan\s+(application|request)|apply|"

    r"order\s+checks?|check\s+order|lock\s+(or\s+unlock\s+)?(a\s+)?card|unlock|"
    r"freeze|activate|replace\s+(a\s+)?card|report\s+(a\s+)?(problem|fraud|lost|stolen)|"
    r"change\s+pin|card\s+information|"

    r"open\s+(a|an|another|new)\b[\w\s]{0,24}\baccount\b|"
    r"open\s+\w{0,12}\s*account\b|get\s+(a\s+)?(quote|started|loan|card)|"
    r"add\s+(funds|card|authorized|payee)|authorized\s+user|payee|"
    r"dispute|research\s+(a\s+)?(transaction|bill|payment)|close\s+account|"
    r"request\b|increase\b|"
    r"connected\s+accounts?|link(ed)?\s+accounts?|external\s+accounts?|"

    r"change\s+|edit\s+|update\s+|set\s+up|enroll|enable|disable|delete|remove|"
    r"beneficiar|contact\s+info|phone,?\s+email|\baddress\b|password|username|"
    r"registered\s+devices?|"
    r"paperless|delivery\s+(preference|option)|alerts?\b|nicknames?|"
    r"access\s+sharing|manage\s+(hub|dashboard|access)|"

    r"send\b|submit|confirm|continue|next|agree|accept|sign\b|authorize|"
    r"log\s*out|logout)", re.I)

SAFE_DOC_CONTROL_RE = re.compile(
    r"(download|view|open|save|print|pdf|statement|document|1099|1098|5498|"
    r"tax|e-?statement|year.?end|escrow\s+analysis|correspondence)", re.I)


MONEY_CONTROL_RE = re.compile(
    r"(pay|payment|payee|transfer|from\s*account|to\s*account|amount|"
    r"zelle|deposit|withdraw|wire|loan\s+amount|term\b|redeem)", re.I)

SECURITY_CHALLENGE_MARKERS = [
    "enter the code we sent", "enter your verification code", "verification code",
    "one-time", "one time passcode", "security code", "we sent a code",
    "two-factor", "two-step", "authenticator", "confirm your identity",
    "verify your identity", "we need to verify", "unusual activity",
    "are you a robot", "captcha", "unable to verify", "trouble verifying",
    "your session has expired", "please log in again", "you've been logged out",
    "for your security, we signed you out", "for your security we've signed",
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


RECORD_TYPE_STATEMENT = "statement"
RECORD_TYPE_TAX = "taxDocument"
RECORD_TYPE_CORRESPONDENCE = "correspondence"

CATEGORY_STATEMENT = "Statement"
CATEGORY_ESCROW = "Escrow Analysis"
CATEGORY_TAX = "Tax Document"
CATEGORY_CORRESPONDENCE = "Correspondence"
CATEGORY_OTHER = "Other Document"

ESCROW_TITLE_RE = re.compile(r"escrow\s+analysis", re.I)
PERIOD_TITLE_RE = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})\s*$")
TAX_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


ACCOUNT_OPTION_RE = re.compile(r"^\s*(.+?)\s*(?:…|\.\.\.|\*+|x+)\s*(\d{4})\s*$", re.I)


DATE_PATTERNS = [
    (re.compile(r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
                r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
                r"Dec(?:ember)?)\.?\s+(\d{1,2}),?\s+(\d{4})", re.I), "mdY"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), "mdy_slash"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
]
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MONTH_YEAR_RE = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(\d{4})", re.I)
QUARTER_RE = re.compile(r"\bQ([1-4])\s*[' ]?\s*(\d{4})\b", re.I)
YEAR_RE = re.compile(r"\b(19|20)(\d{2})\b")
_LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
             7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _last_day(year: int, month: int) -> int:
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        return 29
    return _LAST_DAY[month]


def parse_date(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern, kind in DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            if kind == "mdY":
                return f"{int(m.group(3)):04d}-{_MONTHS[m.group(1)[:3].lower()]:02d}-{int(m.group(2)):02d}"
            if kind == "mdy_slash":
                return f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            if kind == "iso":
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except (KeyError, ValueError):
            continue
    return None


def parse_period_date(text: str) -> Tuple[Optional[str], str]:
    text = text or ""
    m = PERIOD_TITLE_RE.match(text)
    if m:
        return parse_date(m.group(2)), text.strip()
    exact = parse_date(text)
    if exact:
        return exact, ""
    m = MONTH_YEAR_RE.search(text)
    if m:
        month = _MONTHS[m.group(1)[:3].lower()]
        year = int(m.group(2))
        return f"{year:04d}-{month:02d}-{_last_day(year, month):02d}", m.group(0)
    m = QUARTER_RE.search(text)
    if m:
        q, year = int(m.group(1)), int(m.group(2))
        month = q * 3
        return f"{year:04d}-{month:02d}-{_last_day(year, month):02d}", f"Q{q} {year}"
    m = YEAR_RE.search(text)
    if m:
        year = int(m.group(1) + m.group(2))
        return f"{year:04d}-12-31", str(year)
    return None, ""


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
    if (FORBIDDEN_CONTROL_RE.search(name) or SETTINGS_CONTROL_RE.search(name)
            or AUTH_CONTROL_RE.search(name)):
        return False
    return bool(SAFE_DOC_CONTROL_RE.search(name))


def is_money_control(identity: str) -> bool:
    identity = (identity or "").strip()
    if not identity:
        return True
    return bool(MONEY_CONTROL_RE.search(identity))


def dismiss_timeout(page) -> None:
    for pattern in (r"i'?m still here", r"stay (signed|logged) in",
                    r"continue session", r"keep me (signed|logged) in",
                    r"extend (my )?session", r"still (there|here)\?"):
        try:
            c = page.get_by_role("button", name=re.compile(pattern, re.I))
            if c.count() and c.first.is_visible():
                c.first.click()
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass


_HOST_READY_JS = """() => {
  const h = document.querySelector('%s');
  if (!h || !h.shadowRoot) return false;
  return !!h.shadowRoot.querySelector('[role=combobox]');
}""" % HOST


def on_documents_page(page) -> bool:
    try:
        return bool(page.evaluate(_HOST_READY_JS))
    except Exception:
        return False


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


def ensure_statements(page) -> bool:
    dismiss_timeout(page)
    if on_documents_page(page):
        return True
    return goto_documents(page)


def account_label(nickname: str, last4: str) -> str:
    nickname = re.sub(r"\s+", " ", nickname or "").strip() or "Account"
    last4 = (last4 or "").strip()
    return f"{nickname} (...{last4})" if last4 else nickname


def parse_account_option(text: str) -> Tuple[str, str]:
    m = ACCOUNT_OPTION_RE.match(text or "")
    if not m:
        return (text or "").strip(), ""
    return m.group(1).strip(), m.group(2)


def _fetch_json(page, path: str):
    return page.evaluate(
        """async (p) => {
             const ppTarget = new URL(p, location.href);
             if (ppTarget.protocol !== "https:" || !["onlinebanking.huntington.com", "www.huntington.com"].includes(ppTarget.hostname) || ppTarget.username || ppTarget.password || (ppTarget.port && ppTarget.port !== "443")) throw new Error("Refusing an off-host document request");
             const r = await fetch(p, {redirect: 'error', credentials: 'include',
                                       headers: {'Accept': 'application/json'}});
             const text = await r.text();
             let body = null;
             try { body = JSON.parse(text); } catch (e) { body = null; }
             return {status: r.status, body: body, text: body ? '' : text.slice(0, 300)};
           }""", path)


def list_accounts(page) -> List[dict]:
    res = _fetch_json(page, API["accounts"])
    if res.get("status") != 200 or not isinstance(res.get("body"), dict):
        log.info("accounts API answered %s %r", res.get("status"), (res.get("text") or "")[:120])
        return []
    out = []
    for a in res["body"].get("statementAccounts") or []:
        nick = a.get("nickname") or a.get("productType") or "Account"
        last4 = str(a.get("accountNumberLastFour") or "")
        out.append({
            "account_id": str(a.get("accountId") or ""),
            "label": account_label(nick, last4),
            "nickname": nick,
            "last4": last4,
            "product_type": a.get("productType") or "",
            "status": a.get("status") or "",
            "enrolled": bool((a.get("preference") or {}).get("onlineStatementsEnrolled", True)),
        })
    return [a for a in out if a["account_id"]]


def list_records(page, account_id: str) -> List[dict]:
    res = _fetch_json(page, API["records"].format(account_id=account_id))
    if res.get("status") != 200 or not isinstance(res.get("body"), dict):
        log.info("records API (%s) answered %s %r", account_id, res.get("status"),
                 (res.get("text") or "")[:120])
        return []
    return [r for r in (res["body"].get("records") or []) if isinstance(r, dict)]


def classify_record(rec: dict) -> Tuple[str, str, str, str]:
    rtype = (rec.get("recordType") or "").strip()
    title = re.sub(r"\s+", " ", rec.get("title") or "").strip()
    start = (rec.get("startDate") or "").strip()[:10]
    end = (rec.get("endDate") or "").strip()[:10]
    if rtype == RECORD_TYPE_STATEMENT:
        if ESCROW_TITLE_RE.search(title):
            date = parse_date(title) or start or end
            return CATEGORY_ESCROW, date, "", title or "Escrow Analysis"
        m = PERIOD_TITLE_RE.match(title)
        if m:
            return CATEGORY_STATEMENT, end or parse_date(m.group(2)) or "", title, title
        return CATEGORY_STATEMENT, end or parse_date(title) or start, "", title or "Statement"
    if rtype == RECORD_TYPE_TAX:
        year = ""
        m = TAX_YEAR_RE.search(title)
        if m:
            year = m.group(1)
        elif end:
            year = end[:4]
        date = end or (f"{year}-12-31" if year else "")
        return CATEGORY_TAX, date, year, title or "Tax Form"
    if rtype == RECORD_TYPE_CORRESPONDENCE:
        date = parse_date(title) or start or end
        return CATEGORY_CORRESPONDENCE, date, "", title or "Correspondence"

    date = parse_date(title) or end or start
    return CATEGORY_OTHER, date, "", title or (rtype or "Document")


def record_descriptor(rec: dict) -> Tuple[str, str, str, str]:
    return ((rec.get("recordType") or "").strip(),
            re.sub(r"\s+", " ", rec.get("title") or "").strip(),
            (rec.get("startDate") or "").strip()[:10],
            (rec.get("endDate") or "").strip()[:10])


def collect_documents(page) -> List[dict]:
    out = []
    for acct in list_accounts(page):
        recs = list_records(page, acct["account_id"])
        log.info("Huntington: %s -> %d record(s)", acct["label"], len(recs))
        seen: Dict[Tuple[str, str, str, str], int] = {}
        for rec in recs:
            category, date, period, title = classify_record(rec)
            desc = record_descriptor(rec)
            occ = seen.get(desc, 0)
            seen[desc] = occ + 1
            out.append({
                "account": acct["label"], "account_id": acct["account_id"],
                "product_type": acct["product_type"],
                "record_type": desc[0], "record_id": rec.get("recordId") or "",
                "title": title, "category": category, "date": date,
                "period": period, "start": desc[2], "end": desc[3],
                "occurrence": occ,
            })
    return out


def _write_if_pdf(data: bytes, out_path: Path) -> bool:
    if not data or not data[:5].startswith(b"%PDF-"):
        return False
    Path(out_path).write_bytes(data)
    return True


def resolve_record_id(page, account_id: str, record_type: str, title: str,
                      start: str, end: str, occurrence: int = 0,
                      hint: str = "") -> str:
    recs = list_records(page, account_id)
    if hint and any((r.get("recordId") or "") == hint for r in recs):
        return hint
    want = (record_type, re.sub(r"\s+", " ", title or "").strip(), start, end)
    n = 0
    for r in recs:
        if record_descriptor(r) == want:
            if n == occurrence:
                return r.get("recordId") or ""
            n += 1
    return ""


def fetch_pdf(page, account_id: str, record_id: str, record_type: str) -> Tuple[int, bytes]:
    path = API["view"].format(account_id=account_id, record_id=record_id,
                              record_type=record_type)
    res = page.evaluate(
        """async (p) => {
             const ppTarget = new URL(p, location.href);
             if (ppTarget.protocol !== "https:" || !["onlinebanking.huntington.com", "www.huntington.com"].includes(ppTarget.hostname) || ppTarget.username || ppTarget.password || (ppTarget.port && ppTarget.port !== "443")) throw new Error("Refusing an off-host document request");
             const r = await fetch(p, {redirect: 'error', credentials: 'include'});
             const buf = await r.arrayBuffer();
             let s = '';
             const bytes = new Uint8Array(buf);
             const chunk = 0x8000;
             for (let i = 0; i < bytes.length; i += chunk)
               s += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
             return {status: r.status, ct: r.headers.get('content-type') || '',
                     b64: btoa(s)};
           }""", path)
    data = base64.b64decode(res.get("b64") or "") if res else b""
    return int(res.get("status") or 0), data


def download_record(page, account_id: str, last4: str, record_type: str,
                    title: str, start: str, end: str, date: str,
                    out_path: Path, occurrence: int = 0,
                    record_id_hint: str = "") -> bool:
    record_id = resolve_record_id(page, account_id, record_type, title, start,
                                  end, occurrence, hint=record_id_hint)
    if record_id:
        status, data = fetch_pdf(page, account_id, record_id, record_type)
        if status == 200 and _write_if_pdf(data, out_path):
            return True
        log.info("direct fetch answered %s (%d bytes) - trying the row's own button",
                 status, len(data or b""))
    else:
        log.info("record %r (%s %s..%s) not in the fresh list - trying the row's own button",
                 title, record_type, start, end)
    return click_row_and_capture(page, last4, record_type, title, date, out_path)


_SHADOW_READ_JS = """() => {
  const h = document.querySelector('%s');
  if (!h || !h.shadowRoot) return null;
  const sr = h.shadowRoot;
  const txt = el => (el && (el.textContent || '').replace(/\\s+/g, ' ').trim()) || '';
  const combo = sr.querySelector('[role=combobox]');
  // the combobox's textContent includes its floating "Account" legend;
  // the chosen value is the span outside the <fieldset>
  const valueSpans = combo ? [...combo.querySelectorAll('span')].filter(s => !s.closest('fieldset')) : [];
  const out = {account: valueSpans.map(txt).filter(Boolean).join(' '), tabs: [], years: [], rows: [], controls: []};
  for (const t of sr.querySelectorAll('[role=tab]'))
    out.tabs.push({text: txt(t), selected: t.getAttribute('aria-selected') === 'true'});
  for (const a of sr.querySelectorAll('[id^=accordion-summary-]'))
    out.years.push({id: a.id, text: txt(a), expanded: a.getAttribute('aria-expanded') === 'true'});
  for (const b of sr.querySelectorAll('button')) {
    const label = txt(b) || b.getAttribute('aria-label') || '';
    if (!label) continue;
    out.controls.push(label);
    if (/view\\s+pdf/i.test(label)) {
      const row = b.closest('div') && b.closest('div').parentElement;
      const span = row ? row.querySelector('span') : null;
      out.rows.push({title: txt(span), control: label});
    }
  }
  return out;
}""" % HOST


def read_component(page) -> Optional[dict]:
    try:
        return page.evaluate(_SHADOW_READ_JS)
    except Exception as e:
        log.info("component read failed: %s", e)
        return None


def _combobox(page):
    return page.locator(HOST).locator("[role=combobox]").first


def combobox_identity(page) -> str:
    try:
        c = _combobox(page)
        if c.count() == 0:
            return ""
        return c.evaluate(
            """el => {
                 const lab = el.getAttribute('aria-labelledby');
                 const labEl = lab && el.getRootNode().getElementById(lab);
                 return [el.id || '', labEl ? labEl.textContent : '',
                         el.textContent || ''].join(' | ').replace(/\\s+/g, ' ').trim();
               }""")
    except Exception:
        return ""


def account_options(page) -> List[str]:
    ident = combobox_identity(page)
    if is_money_control(ident):
        log.info("account picker refused as a money control: %r", ident)
        return []
    try:
        _combobox(page).click()
        page.wait_for_timeout(800)
        opts = page.locator("[role=option]")
        labels = [re.sub(r"\s+", " ", opts.nth(i).inner_text()).strip()
                  for i in range(opts.count())]
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        return labels
    except Exception as e:
        log.info("account options failed: %s", e)
        return []


def select_account(page, last4: str) -> bool:
    ident = combobox_identity(page)
    if is_money_control(ident):
        log.info("account picker refused as a money control: %r", ident)
        return False
    try:
        current = read_component(page) or {}
        if last4 and last4 in (current.get("account") or ""):
            return True
        _combobox(page).click()
        page.wait_for_timeout(800)
        opt = page.locator("[role=option]").filter(has_text=last4)
        if opt.count() == 0:
            page.keyboard.press("Escape")
            return False
        opt.first.click()
        for _ in range(20):
            page.wait_for_timeout(400)
            comp = read_component(page) or {}
            if comp.get("rows") or comp.get("tabs") or comp.get("years"):
                return True
        return True
    except Exception as e:
        log.info("select account %s failed: %s", last4, e)
        return False


TAB_FOR_RECORD_TYPE = {
    RECORD_TYPE_STATEMENT: re.compile(r"^\s*statements?\s*$", re.I),
    RECORD_TYPE_TAX: re.compile(r"^\s*tax\s+forms?\s*$", re.I),
    RECORD_TYPE_CORRESPONDENCE: re.compile(r"^\s*correspondence\s*$", re.I),
}


def select_tab(page, record_type: str) -> bool:
    rx = TAB_FOR_RECORD_TYPE.get(record_type)
    host = page.locator(HOST)
    tabs = host.get_by_role("tab")
    if tabs.count() == 0:
        return True
    if rx is None:
        return False
    for i in range(tabs.count()):
        label = (tabs.nth(i).inner_text() or "").strip()
        if rx.match(label) and is_safe_control(label):
            tabs.nth(i).click()
            page.wait_for_timeout(1200)
            return True
    return False


def expand_year(page, year: str) -> None:
    try:
        summ = page.locator(HOST).locator(f"#accordion-summary-{year}")
        if summ.count() and summ.first.get_attribute("aria-expanded") != "true":
            label = (summ.first.inner_text() or "").strip()
            if not FORBIDDEN_CONTROL_RE.search(label):
                summ.first.click()
                page.wait_for_timeout(800)
    except Exception:
        pass


def click_row_and_capture(page, last4: str, record_type: str, title: str,
                          date: str, out_path: Path) -> bool:
    if not select_account(page, last4):
        return False
    if not select_tab(page, record_type):
        return False
    if date:
        expand_year(page, date[:4])
    host = page.locator(HOST)
    title_rx = re.compile(r"^\s*" + re.escape(title.strip()) + r"\s*$")
    rows = host.locator("span", has_text=title_rx)
    if rows.count() == 0:
        log.info("no rendered row titled %r", title)
        return False
    container = rows.first.locator("xpath=..")
    btn = container.get_by_role("button", name=re.compile(r"view\s+pdf", re.I))
    if btn.count() == 0:
        btn = container.locator("xpath=..").get_by_role("button", name=re.compile(r"view\s+pdf", re.I))
    if btn.count() == 0:
        return False
    label = (btn.first.inner_text() or "").strip()
    if not is_safe_control(label):
        return False
    ctx = page.context
    before = {id(p) for p in ctx.pages}
    try:
        with page.expect_response(lambda r: is_safe_url(r.url) and "/records/" in r.url and "/view" in r.url,
                                  timeout=30000) as resp_info:
            btn.first.click()
        resp = resp_info.value
        data = resp.body()
    except Exception as e:
        log.info("row click capture failed: %s", e)
        data = b""

    for p in list(ctx.pages):
        try:
            if (id(p) not in before and (p.url or "").startswith("blob:")
                    and is_safe_url(p.url[5:])):
                p.close()
        except Exception:
            pass
    return _write_if_pdf(data, out_path)


def redact_label(text: str) -> str:
    return re.sub(r"\d", "#", text or "")
