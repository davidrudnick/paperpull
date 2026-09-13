"""Replay the portal document-list form for each year and beneficiary.
Statement links contain session-scoped identifiers and are re-resolved by
descriptor and occurrence. Public plan inserts are downloaded separately from
the provider CDN and deduplicated. Tax-form downloads need live validation.

All requests and navigation must stay on explicitly allowed provider hosts.
"""

from __future__ import annotations

import base64
import logging
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from urllib.parse import urlsplit, urljoin
from paperpull_core.controls import SETTINGS_CONTROL_RE, AUTH_CONTROL_RE

ALLOWED_HOSTS = {'www.brightstart-529.com', 'cdn.unite529.com'}


def is_safe_url(url: str) -> bool:
    try:
        parts = urlsplit(url or "")
        return (parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS
                and parts.port in (None, 443) and not parts.username
                and not parts.password)
    except (TypeError, ValueError):
        return False


log = logging.getLogger("brightstart_docs.site")

BASE = "https://www.brightstart-529.com"
URLS = {
    "home": f"{BASE}/ildtpl/al/list.cs",
    "login": f"{BASE}/ildtpl/auth/ll.cs",
    "documents": f"{BASE}/ildtpl/confirm/confirms.cs",
    "submit": f"{BASE}/ildtpl/confirm/confirmsSubmit.cs",
    "logout": f"{BASE}/ildtpl/auth/lo.cs",
}
DOCUMENT_URL_CANDIDATES = [URLS["documents"]]


INSERT_CDN_BASE = "https://cdn.unite529.com/jcdn/files/ILD/pdfs/"

LOGIN_URL_MARKERS = ["/ildtpl/auth/", "__cookiecheck", "/login", "/logon",
                     "/signin", "/sign-in"]


DOC_TYPE_ALL = "ALL"
DOC_TYPE_STATEMENTS = "STATEMENTS"
DOC_TYPE_CONFIRMS = "CONFIRMS"
DOC_TYPE_TAX = "TAX"


FORBIDDEN_CONTROL_RE = re.compile(

    r"(contribut|withdraw|distribut|roll\s*over|transfer|move\s+money|"
    r"recurring|one.?time\s+(purchase|investment)|invest\s+now|buy\b|sell\b|"

    r"exchange|reallocat|change\s+investment|future\s+allocations?|"
    r"portfolio\s+change|"

    r"gift|ugift|enroll|open\s+(a|an|another|new)\b[\w\s]{0,24}\baccount\b|"
    r"get\s+started|apply|"

    r"bank\s+info|add\s+bank|payroll|direct\s+deposit|funding\s+instructions?\s+"
    r"(form|setup)|"
    r"delivery\s+preference|paperless|e-?delivery\s+settings?|"
    r"password|security\s+features?|username|"
    r"beneficiar|successor|authorized\s+agent|interested\s+part|"
    r"trusted\s+contact|"

    r"edit\s+|update\s+|change\s+|set\s+up|enable|disable|delete|remove|"
    r"add\s+(funds|payee|agent)|"

    r"send\b|submit|confirm\s*$|continue|next|agree|accept|sign\b|authorize|"
    r"view\s+details|log\s*off|log\s*out|logout)", re.I)


SAFE_DOC_CONTROL_RE = re.compile(
    r"(search|download|view|open|save|print|pdf|statement|document|"
    r"tax|1099|5498)", re.I)

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


KIND_CONFIRM = "confirm"
KIND_INSERT = "insert"

CATEGORY_STATEMENT = "Statement"
CATEGORY_CONFIRMATION = "Confirmation"
CATEGORY_TAX = "Tax Document"
CATEGORY_INSERT = "Plan Document"
CATEGORY_OTHER = "Other Document"

TAX_LABEL_RE = re.compile(r"(\b1099|\b5498\b|\btax\b)", re.I)
STATEMENT_LABEL_RE = re.compile(r"^\s*statement\s*$", re.I)


ACCOUNT_NUMBER_RE = re.compile(r"\b([A-Z]?\d{6,12})-(\d{2})\b")

ACCT_OPTION_RE = re.compile(r"^\s*(\d{2})\s*-\s*(.+?)\s*$")


TABLE_RE = re.compile(r'<table[^>]*class="[^"]*unite-table[^"]*"[^>]*>.*?</table>', re.S)
TR_RE = re.compile(r"<tr\b.*?</tr>", re.S)
LINK_RE = re.compile(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
HEADING_SPAN_RE = re.compile(r'<span[^>]*class="[^"]*unite-table-heading[^"]*"[^>]*>.*?</span>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
DATE_TEXT_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
CMS_PDF_RE = re.compile(r"[?&]cmsPDF=([^&\"']+)", re.I)
SELECT_RE = re.compile(r'<select[^>]*name="(\w+)"[^>]*>(.*?)</select>', re.S)
OPTION_RE = re.compile(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', re.S)


DATE_PATTERNS = [
    (re.compile(r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
                r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
                r"Dec(?:ember)?)\.?\s+(\d{1,2}),?\s+(\d{4})", re.I), "mdY"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), "mdy_slash"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
]
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


_QUARTER_END = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}


def statement_period(date: str) -> str:
    if not date or len(date) != 10:
        return ""
    q = _QUARTER_END.get(date[5:])
    return f"Q{q} {date[:4]}" if q else ""


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


def html_looks_signed_out(html: str) -> bool:
    if not html:
        return True
    if 'name="documentType"' in html or "unite-table" in html:
        return False
    lowered = html.lower()
    return ("password" in lowered or "/ildtpl/auth/" in lowered
            or "log in" in lowered or "login" in lowered)


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


def on_documents_page(page) -> bool:
    try:
        return bool(page.evaluate(
            """() => !!(document.querySelector('select[name=year]') &&
                        document.querySelector('select[name=documentType]'))"""))
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
            for _ in range(10):
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


def _read_select_options(page, name: str) -> List[Tuple[str, str]]:
    try:
        return [tuple(o) for o in page.evaluate(
            """(n) => {
                 const s = document.querySelector(`select[name=${n}]`);
                 if (!s) return [];
                 return [...s.options].map(o => [o.value, o.textContent.trim()]);
               }""", name)]
    except Exception as e:
        log.info("reading select %r failed: %s", name, e)
        return []


def list_years(page) -> List[str]:
    years = [v for v, _t in _read_select_options(page, "year")
             if re.fullmatch(r"\d{4}", v or "")]
    return sorted(set(years), reverse=True)


def account_label(name: str, ext: str) -> str:
    name = re.sub(r"\s+", " ", name or "").strip() or "Account"
    ext = (ext or "").strip()
    return f"{name} (...{ext})" if ext else name


def parse_account_option(text: str) -> Tuple[str, str]:
    m = ACCT_OPTION_RE.match(text or "")
    if not m:
        return "", (text or "").strip()
    return m.group(1), m.group(2)


def list_accounts(page) -> List[dict]:
    out = []
    for value, text in _read_select_options(page, "acctExt"):
        if value == "ALL" or not value:
            continue
        ext, name = parse_account_option(text)
        ext = ext or value
        out.append({"ext": ext, "name": name, "label": account_label(name, ext)})
    return out


def fetch_list_html(page, year: str, acct_ext: str = "ALL",
                    doc_type: str = DOC_TYPE_ALL) -> str:
    body = f"year={year}&acctExt={acct_ext}&documentType={doc_type}&ctype=0"
    res = page.evaluate(
        """async (body) => {
             const ppTarget = new URL('/ildtpl/confirm/confirmsSubmit.cs', location.href);
             if (ppTarget.protocol !== "https:" || !["www.brightstart-529.com", "cdn.unite529.com"].includes(ppTarget.hostname) || ppTarget.username || ppTarget.password || (ppTarget.port && ppTarget.port !== "443")) throw new Error("Refusing an off-host document request");
             const r = await fetch('/ildtpl/confirm/confirmsSubmit.cs', {
               method: 'POST',
               headers: {'Content-Type': 'application/x-www-form-urlencoded'},
               body: body,
               credentials: 'include'
             });
             return {status: r.status, text: await r.text()};
           }""", body)
    if not res or res.get("status") != 200:
        log.info("list POST (%s) answered %s", body, (res or {}).get("status"))
        return ""
    return res.get("text") or ""


def parse_rows(html: str) -> List[dict]:
    m = TABLE_RE.search(html or "")
    if not m:
        return []
    out = []
    for tr in TR_RE.findall(m.group(0)):
        link = LINK_RE.search(tr)
        if not link:
            continue
        href = link.group(1).replace("&amp;", "&").strip()
        label = re.sub(r"\s+", " ", TAG_RE.sub("", link.group(2))).strip()
        plain = TAG_RE.sub(" ", HEADING_SPAN_RE.sub("", tr))
        dm = DATE_TEXT_RE.search(plain)
        date = (f"{int(dm.group(3)):04d}-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
                if dm else "")
        am = ACCOUNT_NUMBER_RE.search(plain)
        account_number = f"{am.group(1)}-{am.group(2)}" if am else ""
        ext = am.group(2) if am else ""
        cm = CMS_PDF_RE.search(href)
        kind = KIND_INSERT if "/lit/getPDF.cs" in href else (
            KIND_CONFIRM if "/confirm/confirmPDF.cs" in href else "")
        if not kind:
            log.info("unrecognized document link ignored: %r %r", label, href[:80])
            continue
        out.append({"date": date, "account_number": account_number, "ext": ext,
                    "label": label, "href": href, "kind": kind,
                    "cms_pdf": cm.group(1) if cm else ""})
    return out


def classify_row(kind: str, label: str) -> str:
    if kind == KIND_INSERT:
        return CATEGORY_INSERT
    if STATEMENT_LABEL_RE.match(label or ""):
        return CATEGORY_STATEMENT
    if TAX_LABEL_RE.search(label or ""):
        return CATEGORY_TAX
    return CATEGORY_CONFIRMATION


def row_descriptor(row: dict) -> Tuple[str, str, str, str]:
    return (row.get("kind") or "", row.get("date") or "",
            row.get("account_number") or "",
            re.sub(r"\s+", " ", row.get("label") or "").strip())


def collect_documents(page, years: Optional[List[str]] = None,
                      delay=None) -> List[dict]:
    years = years if years is not None else list_years(page)
    out: List[dict] = []
    seen_inserts: Dict[str, bool] = {}
    for year in years:
        html = fetch_list_html(page, year)
        if html_looks_signed_out(html):
            log.info("year %s: listing looks signed out", year)
            continue
        rows = parse_rows(html)
        log.info("Bright Start: year %s -> %d row(s)", year, len(rows))
        occurrences: Dict[Tuple[str, str, str, str], int] = {}
        for row in rows:
            if row["kind"] == KIND_INSERT:
                if row["cms_pdf"] in seen_inserts:
                    continue
                seen_inserts[row["cms_pdf"]] = True
                out.append({**row, "category": CATEGORY_INSERT, "year": year,
                            "occurrence": 0, "account_number": "", "ext": ""})
                continue
            desc = row_descriptor(row)
            occ = occurrences.get(desc, 0)
            occurrences[desc] = occ + 1
            out.append({**row, "category": classify_row(row["kind"], row["label"]),
                        "year": year, "occurrence": occ})
        if delay is not None and year != years[-1]:
            delay()
    return out


def _write_if_pdf(data: bytes, out_path: Path) -> bool:
    if not data or not data[:5].startswith(b"%PDF-"):
        return False
    Path(out_path).write_bytes(data)
    return True


def resolve_row_href(page, year: str, date: str, account_number: str,
                     label: str, occurrence: int = 0) -> str:
    html = fetch_list_html(page, year)
    if html_looks_signed_out(html):
        return ""
    want = (KIND_CONFIRM, date, account_number,
            re.sub(r"\s+", " ", label or "").strip())
    n = 0
    for row in parse_rows(html):
        if row_descriptor(row) == want:
            if n == occurrence:
                return row["href"]
            n += 1
    return ""


def fetch_pdf(page, href: str) -> Tuple[int, bytes, str]:
    res = page.evaluate(
        """async (p) => {
             const ppTarget = new URL(p, location.href);
             if (ppTarget.protocol !== "https:" || !["www.brightstart-529.com", "cdn.unite529.com"].includes(ppTarget.hostname) || ppTarget.username || ppTarget.password || (ppTarget.port && ppTarget.port !== "443")) throw new Error("Refusing an off-host document request");
             const r = await fetch(p, {redirect: 'error', credentials: 'include'});
             const buf = await r.arrayBuffer();
             const bytes = new Uint8Array(buf);
             const chunks = [];
             for (let i = 0; i < bytes.length; i += 0x8000) {
               let s = '';
               const end = Math.min(i + 0x8000, bytes.length);
               for (let j = i; j < end; j++) s += String.fromCharCode(bytes[j]);
               chunks.push(btoa(s));
             }
             return {status: r.status, ct: r.headers.get('content-type') || '',
                     chunks: chunks};
           }""", href)
    if not res:
        return 0, b"", ""
    data = b"".join(base64.b64decode(c) for c in (res.get("chunks") or []))
    return int(res.get("status") or 0), data, res.get("ct") or ""


def download_confirm(page, year: str, date: str, account_number: str,
                     label: str, out_path: Path, occurrence: int = 0,
                     href_hint: str = "", attempts: int = 2) -> bool:
    for attempt in range(attempts):
        href = resolve_row_href(page, year, date, account_number, label,
                                occurrence) or href_hint
        if not href:
            log.info("row %r (%s %s) not in the fresh %s listing",
                     label, date, account_number, year)
            return False
        status, data, ct = fetch_pdf(page, href)
        if status == 200 and _write_if_pdf(data, out_path):
            return True
        log.info("confirm fetch answered %s (%s, %d bytes) attempt %d/%d",
                 status, ct[:40], len(data or b""), attempt + 1, attempts)
        href_hint = ""
        page.wait_for_timeout(1500)
    return False


def insert_cdn_url(cms_pdf: str) -> str:
    name = (cms_pdf or "").strip().lstrip("/")

    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return ""
    return INSERT_CDN_BASE + name


def download_insert(cms_pdf: str, out_path: Path, attempts: int = 2) -> bool:
    url = insert_cdn_url(cms_pdf)
    if not url:
        log.info("refusing odd cmsPDF name %r", cms_pdf)
        return False
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if _write_if_pdf(data, out_path):
                return True
            log.info("insert %s answered non-PDF (%d bytes) attempt %d/%d",
                     cms_pdf, len(data or b""), attempt + 1, attempts)
        except Exception as e:
            log.info("insert %s fetch failed (%s) attempt %d/%d",
                     cms_pdf, e, attempt + 1, attempts)
    return False


def read_rendered_rows(page) -> List[dict]:
    try:
        html = page.evaluate("() => document.documentElement.outerHTML")
    except Exception as e:
        log.info("rendered read failed: %s", e)
        return []
    return parse_rows(html)


def read_controls(page) -> List[str]:
    try:
        return page.evaluate(
            """() => [...new Set([...document.querySelectorAll(
                 'a, button, input[type=submit], input[type=button]')].map(el =>
                   (el.textContent || el.value || el.getAttribute('aria-label') || '')
                     .trim().replace(/\\s+/g, ' ').slice(0, 80)).filter(Boolean))]""")
    except Exception:
        return []


def redact_label(text: str) -> str:
    return re.sub(r"\d", "#", text or "")
