"""Real data the project has never shaped: the getting-started flow must run end to end and pass its checks.
There is no answer key here, so this tests that it loads and runs, not that the answer is right."""

import shutil
from pathlib import Path

import yaml

from aib import draft
from aib.run import run
from aib.validate import all_problems
from aib.workspace import Workspace

PUBLIC = Path(__file__).resolve().parent.parent / "demo" / "public"


def test_public_data_runs_through_first_use(tmp_path):
    data = tmp_path / "invoices.csv.gz"
    shutil.copy(PUBLIC / "data" / "invoices.csv.gz", data)
    ws_dir = tmp_path / "ws"
    d = draft.init(data, ws_dir, lang="en")
    answers = yaml.safe_load((PUBLIC / "answers.yaml").read_text(encoding="utf-8"))
    asked = {q["id"] for q in d["questions"]}
    assert {"date_column", "order_id", "dimensions"} <= asked
    out = draft.confirm(ws_dir, answers)
    ws = Workspace(ws_dir)
    assert all_problems(ws) == []
    s = run(ws, out["first_run"], out_dir=tmp_path / "first")
    assert not s["blocked"], [c for c in s["checks"] if not c["pass"]]
    assert s["cuts"] and all(c["result"]["closed"] for c in s["cuts"])
    assert (tmp_path / "first" / "report.en.md").exists()
