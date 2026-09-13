import ast
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from paperpull_core.run_reporting import finish_run, PREFIX
from paperpull_core.storage import atomic_write_text, now_iso

ROOT = Path(__file__).resolve().parents[2]
ENTRIES = sorted(p for base in (ROOT / "apps", ROOT / "apps" / "Removed")
                 for p in base.glob("*/*.py")
                 if p.name.endswith(("_docs.py", "_receipts.py")))


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda p: p.parent.name)
def test_each_provider_replaces_previous_list_on_empty_run(entry, tmp_path, capsys):
    # Execute the actual summary method, without loading browsers or private configs.
    tree = ast.parse(entry.read_text(encoding="utf-8-sig"))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == "write_run_summary")
    scope = {"atomic_write_text": atomic_write_text, "now_iso": now_iso,
             "finish_run": finish_run}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(entry), "exec"), scope)
    stats = defaultdict(int, started="2026-01-01T00:00:00", mode="all", dates=[], dates_processed=[],
                        new_files=["Statements/synthetic.pdf"], manual_review=2)
    app = SimpleNamespace(stats=stats, paths=SimpleNamespace(root=tmp_path,
                          run_summary=tmp_path / "run-summary.txt"))
    scope["write_run_summary"](app)
    assert "Statements/synthetic.pdf" in (tmp_path / "new-this-run.txt").read_text()
    stats.update(new_files=[], manual_review=0)
    scope["write_run_summary"](app)
    lines = (tmp_path / "new-this-run.txt").read_text().splitlines()
    assert lines and lines[0].startswith("# 0 file(s)")
    assert not [line for line in lines if line and not line.startswith("#")]
    reports = [json.loads(line[len(PREFIX):]) for line in capsys.readouterr().out.splitlines()
               if line.startswith(PREFIX)]
    assert reports[0]["manual_review"] == 2
    assert reports[1] == {"manual_review": 0, "failed": 0, "validation_failures": 0, "new_files": 0}
