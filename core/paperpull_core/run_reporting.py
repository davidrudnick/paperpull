"""Per-run file lists and a counts-only result for the local control panel."""
import json
from .storage import atomic_write_text

PREFIX = "PAPERPULL_RUN_RESULT "


def finish_run(root, stats):
    files = sorted(stats.get("new_files", []))
    # Always replace the list, including a zero-download run.
    atomic_write_text(root / "new-this-run.txt",
                      f"# {len(files)} file(s) downloaded on this run ({stats['ended']}):\n"
                      + "".join(f"{path}\n" for path in files))
    counts = {name: int(stats.get(name, 0)) for name in
              ("manual_review", "failed", "validation_failures")}
    counts["new_files"] = len(files)
    print(f"\n{len(files)} NEW file(s) downloaded this run (listed in new-this-run.txt).")
    # Never include file paths, account labels or provider response text here.
    print(PREFIX + json.dumps(counts), flush=True)
