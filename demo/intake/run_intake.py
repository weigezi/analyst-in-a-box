"""The whole intake on the demo shop's raw tables, and the formation report that compares it with the hand-written workspace.

    uv run python demo/intake/run_intake.py

1. build_tables.py splits the shop's data into system-shaped tables (demo/intake/tables/)
2. init     reads the folder and writes the questions                  (workspace/draft.json)
3. confirm  takes the owner's answers (answers.yaml)                   (workspace/*.yaml)
4. propose  records what an AI tool read in the weekly report (proposals.yaml); every quote is checked
5. run      the demo shop's questions on the formed workspace          (runs/)
6. formation.md / formation.zh.md   what was formed, from where, and how it differs from demo/store/workspace

demo/store/ is only read.
"""

from __future__ import annotations

import json
import shutil
import sys
import datetime as dt
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "skills" / "analyst-in-a-box" / "scripts"))
sys.path.insert(0, str(HERE))

from aib import intake  # noqa: E402
from aib.run import run  # noqa: E402
from aib.validate import all_problems  # noqa: E402
from aib.workspace import Workspace  # noqa: E402

import build_tables  # noqa: E402
import formation_report  # noqa: E402

WS = HERE / "workspace"
RUNS = HERE / "runs"

# The demo shop's questions, asked of the formed workspace. Metric names are the ones intake gave
# ("per_id" is average order value: the starter's name for amount per order id).
QUESTIONS = {
    "revenue_last_week": {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"},
    "east_last_week": {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy",
                       "filters": {"region": "east"}, "dimensions": ["delivery"]},
    "aov_last_week": {"metric": "per_id", "current": ["2026-10-19", "2026-10-25"], "base": "yoy",
                      "dimensions": ["category", "customer_type"]},
    "june_revenue": {"metric": "revenue", "current": ["2026-06-01", "2026-06-30"], "base": "yoy"},
}


# The demo is dated, so that rebuilding it gives the same files; a real intake uses today's date.
DEMO_DAY = dt.date(2026, 10, 31)


def main(ws: Path = WS, runs: Path = RUNS, tables: Path | None = None):
    tables = tables or HERE / "tables"
    build_tables.main(tables)
    if ws.exists():
        shutil.rmtree(ws)
    d = intake.init([tables], ws, lang="zh")
    answers = yaml.safe_load((HERE / "answers.yaml").read_text(encoding="utf-8"))
    out = intake.confirm(ws, answers, today=DEMO_DAY)
    problems = all_problems(Workspace(ws))
    spec = yaml.safe_load((HERE / "proposals.yaml").read_text(encoding="utf-8"))
    proposed = intake.propose(ws, HERE / spec["doc"], spec["items"], today=DEMO_DAY)
    states = {}
    for k, cfg in QUESTIONS.items():
        states[k] = run(ws, {**cfg, "id": k}, out_dir=runs / k)
    states["first_run"] = run(ws, {**out["first_run"], "id": "first_run"}, out_dir=runs / "first_run")
    summary = intake.formation(ws)
    facts = {"draft": d, "confirm": out, "problems": problems, "proposed": proposed, "formation": summary,
             "runs": {k: {"slots": [{"id": x["id"], "status": x["status"], "leaf": x.get("leaf", True),
                                     "citations": [{"id": c["id"], "status": c["status"], "explains": c.get("explains"),
                                                    "source": (c.get("source") or {}).get("kind"),
                                                    "checks": (c.get("checks") or {}).get("status")} for c in x["citations"]]}
                                    for x in s["slots"]],
                          "blocked": s["blocked"], "coverage": s["coverage"], "quality": s["quality"]["status"]}
                      for k, s in states.items()}}
    (HERE / "formation.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for lang in ("zh", "en"):
        name = "formation.zh.md" if lang == "zh" else "formation.md"
        (HERE / name).write_text(formation_report.render(ws, ROOT / "demo" / "store" / "workspace", facts, lang), encoding="utf-8")
    print(f"formed {ws}; {summary['counts']}; reports: formation.md, formation.zh.md")
    return facts


if __name__ == "__main__":
    main()
