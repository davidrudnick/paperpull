"""STP / BluePrint investment documents."""
from __future__ import annotations

from paperpull_core.run_reporting import finish_run

import argparse
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from paperpull_core import doc_types, receipt_pdf
from paperpull_core import browser as browser_launcher
import stp_site as site
from paperpull_core.models import State
from storage import (CsvFile, DOCUMENT_INDEX_COLUMNS, JsonStore, Paths,
                     atomic_write_text, build_pdf_filename, load_config,
                     now_iso, sanitize_component, unique_path)

from storage import ensure_owner, PROJECT_DIR, set_filename_owner
from storage import (ALL_CATEGORIES, FUND_MATERIAL as CAT_FUND_MATERIAL,
                     INVESTOR_REPORT as CAT_INVESTOR_REPORT,
                     ONBOARDING as CAT_ONBOARDING, TAX as CAT_TAX)
log = logging.getLogger("stp_docs")

DONE_STATES = {State.COMPLETED.value, State.NO_RECEIPT_AVAILABLE.value}


def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        print("\nNo interactive console available to answer a required prompt.")
        print("Run this from a real console window (use the .bat files).")
        raise SystemExit(3)


class Document:

    def __init__(self, title="", category="", summary="", date="", period="",
                 href="", confidence="", account_id="", account_name="",
                 fund="", fund_id="", doc_type="", file_type="pdf",
                 document_id="", occurrence=0, **kw):
        self.title = title


        self.account_id = account_id
        self.account_name = account_name


        self.fund = fund
        self.fund_id = fund_id
        self.category = category
        self.summary = summary
        self.date = date
        self.period = period



        self.doc_type = doc_type
        self.file_type = file_type
        self.document_id = document_id

        self.occurrence = occurrence

        self.downloaded_ok = kw.get("downloaded_ok", False)
        self.href = href
        self.confidence = confidence
        self.state = kw.get("state", State.DISCOVERED.value)
        self.pdf_filename = kw.get("pdf_filename", "")
        self.pdf_path = kw.get("pdf_path", "")
        self.pdf_size = kw.get("pdf_size", "")
        self.pdf_pages = kw.get("pdf_pages", "")
        self.notes = kw.get("notes", "")
        self.discovered_at = kw.get("discovered_at", now_iso())

    @property
    def key(self) -> str:
        fund = sanitize_component(self.fund or "")[:40]
        base = (f"{fund}:{self.account_id}:{self.doc_type}:{self.date}:"
                f"{sanitize_component(self.title)[:60]}")
        return base if not self.occurrence else f"{base}#{self.occurrence}"

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(**d)


class App:
    def __init__(self, args):
        self.args = args
        cfg_path = Path(args.config) if getattr(args, "config", None) \
            else (PROJECT_DIR / "config.json")
        self.config = load_config(cfg_path)
        ensure_owner(self.config, cfg_path)
        set_filename_owner(self.config.get("owner", "") if self.config.get("owner_in_filename") else "")
        self.paths = Paths(Path(self.config["output_dir"]))
        self.paths.ensure()
        self._setup_logging()

        self.progress = JsonStore(self.paths.progress_json, self.paths.backups)
        self.discovery = JsonStore(self.paths.discovery_json, self.paths.backups)
        self.progress.load()
        self.discovery.load()
        self.index_csv = CsvFile(self.paths.document_index_csv,
                                 DOCUMENT_INDEX_COLUMNS, self.paths.backups)
        self.rules = doc_types.load_rules()

        self._pw = None
        self._browser = None
        self._context = None
        self._work_page = None
        self._cdp_mode = False
        self.stats = {
            "mode": "", "started": now_iso(), "ended": "",
            "discovered": 0, "investor_reports": 0, "tax_documents": 0,
            "onboarding": 0, "fund_materials": 0,
            "other": 0, "skipped_completed": 0, "skipped_out_of_scope": 0,
            "manual_review": 0, "failed": 0, "duplicate_filenames": 0,
            "validation_failures": 0, "dates": [], "new_files": [],
        }


    def _setup_logging(self):
        logfile = self.paths.logs / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            handlers=[logging.FileHandler(logfile, encoding="utf-8"),
                      logging.StreamHandler(sys.stdout)])
        logging.getLogger("pypdf").setLevel(logging.ERROR)

    def _delay(self, factor: float = 1.0):
        time.sleep(random.uniform(
            float(self.config["delay_min_seconds"]) * factor,
            float(self.config["delay_max_seconds"]) * factor))

    def browser(self):
        if self._context is not None:
            return self._context
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        cdp_url = self.config.get("cdp_url")
        if cdp_url:
            try:
                self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
            except Exception as e:
                self._pw.stop()
                self._pw = None
                raise SystemExit(
                    f"Could not connect to your signed-in browser at {cdp_url}.\n"
                    f"Run login.bat first and keep that browser window OPEN.\n({e})")
            if not self._browser.contexts:
                raise SystemExit("Connected browser has no context; open a tab and retry.")
            self._context = self._browser.contexts[0]
            self._cdp_mode = True
        else:
            profile = Path(self.config["profile_dir"])
            profile.mkdir(parents=True, exist_ok=True)
            self._context = self._pw.chromium.launch_persistent_context(
                str(profile), headless=False, accept_downloads=True,
                viewport={"width": 1400, "height": 950})
            self._cdp_mode = False
        self._context.set_default_timeout(30000)
        return self._context

    def page(self):
        ctx = self.browser()
        if self._work_page is not None and not self._work_page.is_closed():
            return self._work_page
        if self._cdp_mode:



            live = [p for p in ctx.pages if not p.is_closed()]
            bp = [p for p in live if site.is_safe_url(p.url or "")]
            bp = bp or [p for p in live if site.is_safe_url(p.url or "")]
            self._work_page = bp[0] if bp else ctx.new_page()
        else:
            self._work_page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return self._work_page

    def close(self):
        try:
            if self._cdp_mode:
                pass
            elif self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._context = self._work_page = None


    def check_session(self, page) -> None:
        challenge = site.detect_security_challenge(page)
        if challenge:
            self.progress.save(backup=True)
            print(f"\n!! {challenge}")
            print("Stopped. Please resolve it yourself in the browser window.")
            print("I will NOT attempt to bypass any security check.")
            ask("Press Enter once the page looks normal (or Ctrl+C to quit)... ")
        if site.looks_signed_out(page):
            self.progress.save(backup=True)
            print("\n!! The BluePrint portal appears to have signed you out.")
            print("Please sign in again in the open browser window.")
            ask("Press Enter after you are signed in... ")
            site.goto_documents(page)


    def cmd_open_browser(self):
        port = browser_launcher.port_from_cdp_url(self.config.get("cdp_url", ""), '9246')
        profile = self.config["profile_dir"]
        url = site.URLS.get("login") or site.URLS.get("documents") or site.URLS["home"]
        name = browser_launcher.open_signin_browser(profile, port, url, prefer_real=True,
            mode=self.config.get("browser", "auto"))
        if not name:
            return
        print(f"Opened a sign-in browser on port {port} ({name}).")
        print(f"Profile: {profile}")
        print("Sign in, keep the window OPEN, then run the pilot.")

    def cmd_login(self):
        print("Checking the connection to your signed-in BluePrint browser...\n")
        page = self.page()
        ok = site.goto_documents(page)
        challenge = site.detect_security_challenge(page)
        if challenge:
            print(f"!! {challenge}\nResolve it in the browser, then re-run --login.")
        elif site.looks_signed_out(page):
            print("Connected, but the portal shows a signed-out page.")
            print("Sign in in the open browser window (keep it OPEN), then re-run --login.")
        elif ok:
            print("Success: connected and the Documents page is visible.")
            print("Keep that browser window OPEN, then run run_pilot.")
        else:
            print("Connected and signed in, but the documents page did not render.")
            print("Open Documents in that browser, then run --diagnose.")
        self.close()

    def _in_scope(self, doc: Document) -> bool:
        a = self.args
        if not doc_types.wanted(doc.category, self.config):
            return False
        if a.type and doc.category.lower() != a.type.lower():
            return False
        if getattr(a, "account", None) and (doc.account_id or "") != str(a.account).strip():
            return False
        if getattr(a, "fund", None) and \
                str(a.fund).strip().lower() not in (doc.fund or "").lower():
            return False
        if a.year and not (doc.date or "").startswith(str(a.year)):
            return False
        floor = a.start_date or self.config.get("default_start_date")
        if floor and (not doc.date or doc.date < floor):
            return False
        if a.end_date and (not doc.date or doc.date > a.end_date):
            return False
        return True

    def _label(self, name: str) -> str:
        labels = self.config.get("account_labels") or {}
        return labels.get(name) or name

    def _record_stp_doc(self, d: dict) -> int:
        title = re.sub(r"\s+", " ", (d.get("title") or "")).strip()
        if doc_types.should_skip(title, self.rules):
            self.stats["skipped_out_of_scope"] += 1
            return 0
        category = d.get("category") or ""
        if not doc_types.wanted(category, self.config):
            self.stats["skipped_out_of_scope"] += 1
            return 0
        date = (d.get("date") or "").strip()
        floor = self.args.start_date or self.config.get("default_start_date")
        if floor and (not date or date < floor):
            self.stats["skipped_out_of_scope"] += 1
            return 0




        fund = d.get("fund") or ""
        account_id = d.get("account_id") or ""
        summary = f"{title} - {self._label(fund)}" if fund else title
        if account_id:
            summary = f"{summary} - {self._label(account_id)}"
        if d.get("occurrence"):
            summary = f"{summary} ({int(d['occurrence']) + 1})"
        self.stats.setdefault("funds", {})
        self.stats["funds"][fund] = self.stats["funds"].get(fund, 0) + 1
        doc = Document(title=title, category=category, summary=summary,
                       date=date, period=d.get("period") or "",
                       confidence=doc_types.HIGH,
                       account_id=account_id,
                       account_name=d.get("account_name") or "",
                       fund=fund, fund_id=d.get("fund_id") or "",
                       doc_type=d.get("doc_type") or "",
                       file_type=d.get("file_type") or "pdf",
                       document_id=d.get("document_id") or "",
                       occurrence=int(d.get("occurrence", 0) or 0),
                       href=site.URLS["documents"])
        existing = self.discovery.get(doc.key)
        if existing is None:
            rec = doc.to_dict()
            rec["state"] = State.DISCOVERED.value
            self.discovery.update(doc.key, rec, save=False)
            return 1

        if doc.document_id and existing.get("document_id") != doc.document_id:
            self.discovery.update(doc.key, {"document_id": doc.document_id},
                                  save=False)
        return 0

    def cmd_discover(self, quiet: bool = False) -> int:
        page = self.page()
        if not site.ensure_documents(page):
            self.check_session(page)
            if not site.ensure_documents(page):
                print("Could not open the BluePrint documents page. Sign in in the")
                print("browser, then try again.")
                return 0
        self.check_session(page)



        raw = site.collect_documents(page)
        log.info("STP: %d document(s)", len(raw))
        n_new = 0
        for d in raw:
            n_new += self._record_stp_doc(d)

        self.discovery.save()
        self.stats["discovered"] = len(self.discovery.data)

        if not quiet:
            docs = [Document.from_dict(v) for v in self.discovery.data.values()]
            print(f"\nDiscovery complete. Documents known: {len(docs)}")
            by_cat = {}
            for d in docs:
                by_cat.setdefault(d.category, []).append(d)
            for cat, group in sorted(by_cat.items()):
                years = {}
                for d in group:
                    y = (d.date or "?")[:4]
                    years[y] = years.get(y, 0) + 1
                spread = ", ".join(f"{y}: {c}" for y, c in sorted(years.items(), reverse=True))
                print(f"  {cat}: {len(group)}  ({spread})")
            dates = sorted(d.date for d in docs if d.date)
            if dates:
                print(f"  Date range: {dates[0]} .. {dates[-1]}")
            funds = self.stats.get("funds") or {}
            if funds:
                print(f"\n  Funds seen ({len(funds)}):")
                for name, n in sorted(funds.items(), key=lambda kv: -kv[1]):
                    print(f"    {n:4}  {name}")
            if self.stats["skipped_out_of_scope"]:
                print(f"  Skipped as out of scope: {self.stats['skipped_out_of_scope']}")
        return n_new

    def _select(self, limit: Optional[int] = None) -> List[Document]:
        docs = [Document.from_dict(v) for v in self.discovery.data.values()]
        docs = [d for d in docs if self._in_scope(d)]
        docs.sort(key=lambda d: d.date or "0000", reverse=True)
        limit = limit if limit is not None else self.args.max_docs
        return docs[:limit] if limit else docs

    def _already_done(self, doc: Document) -> bool:
        if getattr(self.args, "redownload", False):
            return False
        rec = self.progress.get(doc.key)
        if not rec:
            return False
        if rec.get("downloaded_ok"):
            return True
        state = rec.get("state")
        if state in (State.COMPLETED.value, State.PDF_VERIFIED.value,
                     State.NO_RECEIPT_AVAILABLE.value, State.CANCELED.value):
            return True
        if state == State.NEEDS_MANUAL_REVIEW.value:
            p = rec.get("pdf_path", "")
            if not (p and Path(p).exists()):
                return False
            if (rec.get("file_type") or "pdf") != "pdf":
                return True
            return receipt_pdf.validate_pdf(Path(p), self.config["min_pdf_bytes"]).ok
        return False


    def process(self, docs: List[Document], dry_run: bool = False):
        page = self.page()
        for i, doc in enumerate(docs, 1):
            print(f"\n[{i}/{len(docs)}] {doc.date or '(no date)'}  "
                  f"{doc.category}  {doc.summary}")
            if self._already_done(doc):
                print("  Already downloaded and verified - skipping.")
                self.stats["skipped_completed"] += 1
                continue
            filename = build_pdf_filename(doc.date, doc.summary, "")
            if doc.file_type and doc.file_type != "pdf":
                filename = filename[:-len(".pdf")] + f".{doc.file_type}"
            if dry_run:
                print(f"  DRY RUN - would save: {filename}")
                continue
            try:
                self.download_one(page, doc, filename)
            except KeyboardInterrupt:
                print("\nInterrupted. Progress saved; run --resume to continue.")
                raise
            except Exception as e:
                log.exception("Failed on %s", doc.key)
                self._record(doc, State.FAILED, notes=str(e))
                self.stats["failed"] += 1
            self._delay()

    def download_one(self, page, doc: Document, filename: str):
        self.check_session(page)
        folder = self.paths.folder_for(doc.category)
        out_path = unique_path(folder, filename, self.config["max_path_length"])
        if out_path.name != filename:
            self.stats["duplicate_filenames"] += 1

        if not site.ensure_documents(page):
            self.check_session(page)
            site.ensure_documents(page)
        saved = site.download_document(page, doc.doc_type, doc.title, doc.date,
                                       doc.account_id, doc.fund, doc.file_type,
                                       out_path, occurrence=doc.occurrence,
                                       document_id_hint=doc.document_id)
        if not saved:
            self._record(doc, State.NEEDS_MANUAL_REVIEW,
                         notes="Could not capture the document (see the log)")
            self._write_row(doc, "Capture failed", "Needs Manual Review")
            self.stats["manual_review"] += 1
            print("  Could not capture this document - marked for manual review.")
            return

        doc.pdf_path, doc.pdf_filename = str(out_path), out_path.name
        self._record(doc, State.PDF_SAVED)

        if doc.file_type == "pdf":
            result = receipt_pdf.validate_pdf(out_path, self.config["min_pdf_bytes"])
            if not result.ok:
                self.stats["validation_failures"] += 1
                quarantine = unique_path(self.paths.manual_review, out_path.name,
                                         self.config["max_path_length"])
                try:
                    out_path.replace(quarantine)
                except OSError:
                    quarantine = out_path
                doc.pdf_path, doc.pdf_filename = str(quarantine), quarantine.name
                self._record(doc, State.NEEDS_MANUAL_REVIEW,
                             notes=f"PDF validation failed: {result.reason}")
                self._write_row(doc, "Validation failed", "Needs Manual Review")
                self.stats["manual_review"] += 1
                print(f"  !! Validation failed ({result.reason}); moved to Manual Review.")
                return
            doc.pdf_size, doc.pdf_pages = result.size_bytes, result.page_count
        else:


            doc.pdf_size, doc.pdf_pages = out_path.stat().st_size, ""
        doc.downloaded_ok = True
        self._record(doc, State.COMPLETED)
        self._write_row(doc, "Downloaded", "Completed")
        self.stats["new_files"].append(str(out_path))
        if doc.date:
            self.stats["dates"].append(doc.date)
        if doc.category == CAT_TAX:
            self.stats["tax_documents"] += 1
        elif doc.category == CAT_INVESTOR_REPORT:
            self.stats["investor_reports"] += 1
        elif doc.category == CAT_ONBOARDING:
            self.stats["onboarding"] += 1
        elif doc.category == CAT_FUND_MATERIAL:
            self.stats["fund_materials"] += 1
        else:
            self.stats["other"] += 1
        print(f"  Saved: {out_path.name}")


    def _record(self, doc: Document, state: State, notes: str = ""):
        doc.state = state.value
        if notes:
            doc.notes = (doc.notes + "; " if doc.notes else "") + notes
        self.progress.update(doc.key, doc.to_dict())
        self.discovery.update(doc.key, {"state": state.value})

    def _write_row(self, doc: Document, status: str, processing: str):
        notes = "; ".join(x for x in (doc.notes, status) if x)
        self.index_csv.append_rows([{
            "Account Holder": self.config.get("owner", ""),
            "Document Date": doc.date,
            "Category": doc.category,
            "Document Summary": doc.summary,
            "Document Title": doc.title,
            "Account": doc.account_name or doc.account_id,
            "Fund": doc.fund,
            "Period": doc.period,
            "File Name": doc.pdf_filename,
            "Full Path": doc.pdf_path,
            "File Size": doc.pdf_size,
            "PDF Page Count": doc.pdf_pages,
            "Source URL": doc.href,
            "Classification Confidence": doc.confidence,
            "Downloaded At": now_iso() if doc.pdf_filename else "",
            "Verified At": now_iso() if doc.pdf_pages else "",
            "Processing Status": processing,
            "Notes": notes,
        }])


    def cmd_pilot(self):
        self.stats["mode"] = "pilot"
        print("PILOT MODE - limited supervised test run.\n")
        self.cmd_discover()
        docs = self._select(limit=self.config.get("pilot_count", 5))
        if not docs:
            print("\nNo documents in scope to pilot. Run --diagnose.")
            return
        print(f"\nDownloading {len(docs)} document(s)...")
        self.process(docs, dry_run=self.args.dry_run)
        self._pilot_report(docs)

    def _pilot_report(self, docs: List[Document]):
        print("\n" + "=" * 70)
        print("PILOT RESULTS - inspect these before approving a full run")
        print("=" * 70)
        problems = []
        for d in docs:
            rec = self.progress.get(d.key) or {}
            state = rec.get("state", "?")
            print(f"\n  {rec.get('date', d.date)}  {rec.get('category', d.category)}")
            print(f"    Title:  {rec.get('title', d.title)[:70]}")
            print(f"    State:  {state}   [{rec.get('confidence', '')}]")
            print(f"    File:   {rec.get('pdf_filename', '(none)')}"
                  f"  ({rec.get('pdf_size', '?')} bytes, {rec.get('pdf_pages', '?')} pages)")
            if state != State.COMPLETED.value:
                problems.append(f"{d.key}: {state} - {rec.get('notes', '')}")
        print("\n" + "-" * 70)
        if problems:
            print("Needs attention:")
            for p in problems:
                print(f"  ! {p}")
        else:
            print("No problems detected in the pilot.")
        print(f"\nFiles are in:\n  {self.paths.root}")
        print("Nothing further runs until you explicitly start a full command.")

    def cmd_run(self, mode_name: str):
        self.stats["mode"] = mode_name
        if mode_name == "all" and not self.args.yes:
            scope = ", ".join(self.config.get("document_types", []))
            print(f"This downloads ALL available STP Investment Services documents ({scope}).")
            print("Type YES to continue:")
            if ask("> ").strip().upper() != "YES":
                print("Aborted. (Run the pilot first if you haven't: --pilot)")
                return
        self.cmd_discover()
        docs = self._select()
        print(f"\nDownloading {len(docs)} document(s)...")
        self.process(docs, dry_run=self.args.dry_run)

    def cmd_resume(self):
        self.stats["mode"] = "resume"
        docs = [d for d in self._select() if not self._already_done(d)]
        if not docs:
            print("Nothing to resume - everything in scope is complete.")
            return
        print(f"Resuming: {len(docs)} document(s) remaining.")
        self.process(docs, dry_run=self.args.dry_run)

    def cmd_verify(self):
        self.stats["mode"] = "verify"
        rows = self.index_csv.read_all()
        if not rows:
            print("Document index is empty - nothing to verify.")
            return
        bad = 0
        for row in rows:
            p = row.get("Full Path", "")
            if not p:
                continue
            if not p.lower().endswith(".pdf"):
                if not Path(p).exists():
                    bad += 1
                    print(f"  BAD {row.get('File Name', '')}: file missing")
                else:
                    row["Verified At"] = now_iso()
                continue
            r = receipt_pdf.validate_pdf(Path(p), self.config["min_pdf_bytes"])
            if not r.ok:
                bad += 1
                print(f"  BAD {row.get('File Name', '')}: {r.reason}")
            else:
                row["Verified At"] = now_iso()
        self.index_csv.rewrite(rows)
        print(f"\nVerified {len(rows)} index rows; {bad} problem(s).")

    def cmd_diagnose(self):
        self.stats["mode"] = "diagnose"
        import json as _json
        page = self.page()
        info = {"timestamp": now_iso()}
        try:
            found = site.goto_documents(page)
            info["documents_page_found"] = found
            info["url"] = page.url
            info["title"] = page.title()
            info["signed_out"] = site.looks_signed_out(page)
            info["challenge"] = site.detect_security_challenge(page)
            ident = site.get_identity(page) or {}
            info["identity"] = {"firm": ident.get("firm_name"),
                                "timeout_minutes": ident.get("timeout_minutes")}

            rows = site.list_documents(page)
            kinds = {}
            by_fund = {}
            samples = []
            for r in rows:
                cat, date, period, title = site.classify_document(r)
                kinds[cat] = kinds.get(cat, 0) + 1
                fund = site.redact_label(site.fund_label(r))
                by_fund[fund] = by_fund.get(fund, 0) + 1
                if len(samples) < 8:
                    samples.append({"type": r.get("Document_Type_Name"),
                                    "title": title[:80], "category": cat,
                                    "date": date, "period": period,
                                    "file_type": r.get("File_Type"),
                                    "subfolder": r.get("Document_SubFolder_Name"),
                                    "fields": sorted(r.keys())})
            info["documents_total"] = len(rows)
            info["documents_by_category"] = kinds
            info["documents_by_fund"] = by_fund
            info["samples"] = samples

            ui = site.read_page_ui(page) or {}
            info["rendered"] = {"menu": ui.get("menu"),
                                "total_on_screen": ui.get("total"),
                                "rows_on_screen": ui.get("rows")}
            info["controls"] = [{"text": c[:60], "safe": site.is_safe_control(c)}
                                for c in (ui.get("buttons") or [])[:60]]
            page.screenshot(path=str(self.paths.diagnostics / "diagnose-documents.png"),
                            full_page=True)
        except Exception as e:
            info["error"] = str(e)
        out = self.paths.diagnostics / "diagnose-documents.json"
        atomic_write_text(out, _json.dumps(info, indent=2))
        print(f"Wrote {out}")
        print(f"Documents page found: {info.get('documents_page_found')}")
        print(f"Documents (API): {info.get('documents_total')}  "
              f"{info.get('documents_by_category')}")
        r = info.get("rendered") or {}
        print(f"Rendered: menu={r.get('menu')} total={r.get('total_on_screen')!r} "
              f"rows on screen={r.get('rows_on_screen')}")
        if info.get("error"):
            print(f"Error: {info['error']}")


    def write_run_summary(self):
        s = self.stats
        s["ended"] = now_iso()
        dates = sorted(d for d in s["dates"] if d)
        new_files = s.get("new_files", [])
        atomic_write_text(self.paths.run_summary, "\n".join([
            "STP Investment Services Documents - run summary",
            "=" * 40,
            f"Run start:                 {s['started']}",
            f"Run end:                   {s['ended']}",
            f"Mode:                      {s['mode'] or '(none)'}",
            f"Documents known:           {s['discovered']}",
            f"NEW files this run:        {len(new_files)}",
            f"Investor reports:          {s['investor_reports']}",
            f"Tax documents:             {s['tax_documents']}",
            f"Onboarding documents:      {s['onboarding']}",
            f"Fund materials:            {s['fund_materials']}",
            f"Other documents:           {s['other']}",
            f"Skipped (already done):    {s['skipped_completed']}",
            f"Skipped (out of scope):    {s['skipped_out_of_scope']}",
            f"Needs manual review:       {s['manual_review']}",
            f"Failed:                    {s['failed']}",
            f"Duplicate filenames (#'d): {s['duplicate_filenames']}",
            f"PDF validation failures:   {s['validation_failures']}",
            f"Earliest date processed:   {dates[0] if dates else '-'}",
            f"Latest date processed:     {dates[-1] if dates else '-'}",
            "",
        ]))
        finish_run(self.paths.root, s)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Local supervised STP Investment Services document downloader (read-only)")
    for name, help_text in [
            ("login", "verify connection to your signed-in browser"),
            ("discover", "list available documents; writes discovery.json"),
            ("pilot", "download the 5 newest in-scope documents, then stop"),
            ("all", "download everything in scope (asks for confirmation)"),
            ("resume", "continue an interrupted run"),
            ("verify", "re-validate every saved PDF"),
            ("diagnose", "dump the Documents page structure (no downloads)")]:
        ap.add_argument(f"--{name}", action="store_true", help=help_text)
    ap.add_argument("--dry-run", action="store_true",
                    help="plan filenames but download nothing")
    ap.add_argument("--year", type=int)
    ap.add_argument("--start-date")
    ap.add_argument("--end-date")
    ap.add_argument("--max-docs", type=int)
    ap.add_argument("--type", help="one of: " + ", ".join(ALL_CATEGORIES))
    ap.add_argument("--account", help="only this investor account id, e.g. 2294")
    ap.add_argument("--fund", help="only funds whose name contains this text")
    ap.add_argument("--yes", action="store_true", help="skip the --all confirmation")
    ap.add_argument("--redownload", action="store_true",
                    help="re-download everything in scope, ignoring the "
                         "'already downloaded' memory (rebuilds deleted files)")
    ap.add_argument("--config", help="use an alternate config file, e.g. "
                                     "config.spouse.json (separate account)")
    ap.add_argument("--open-browser", action="store_true",
                    help="launch a sign-in browser using this config's profile/port")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    for d in (args.start_date, args.end_date):
        if d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            print(f"Bad date '{d}': use YYYY-MM-DD")
            return 2
    app = App(args)
    try:
        if getattr(args, "open_browser", False):
            app.cmd_open_browser()
        elif args.login:
            app.cmd_login()
        elif args.discover:
            app.cmd_discover()
        elif args.pilot:
            app.cmd_pilot()
        elif args.all:
            app.cmd_run("all")
        elif args.resume:
            app.cmd_resume()
        elif args.verify:
            app.cmd_verify()
        elif args.diagnose:
            app.cmd_diagnose()
        elif args.dry_run:
            app.cmd_run("dry-run")
        else:
            build_parser().print_help()
            return 0
    except KeyboardInterrupt:
        print("\nStopped by user. Progress saved.")
        return 130
    finally:
        app.progress.save()
        app.discovery.save()
        if app.stats["mode"]:
            app.write_run_summary()
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
