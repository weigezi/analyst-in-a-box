"""Command line. Every command prints JSON so the AI tool driving it can read the result.

  init      <data...> --workspace W       profile a table, or a folder / several tables, and write the confirmation questions
  confirm   --workspace W --answers A     turn the answers into a workspace and suggest a first run
  propose   --workspace W --doc D (--quote Q --json E | --file P)   record causes an AI tool read in a document
  formation --workspace W                 where every part of the workspace came from
  check     --workspace W                 list every problem in the workspace
  run       --workspace W --metric M --current START END [--base yoy|pop|START END] [...]
  followup  --workspace W --from RUN_DIR --slot ID [--dimensions D1,D2]   ask inside one cause of an earlier run
  correct   --workspace W --json C        record a correction and create its regression case
  regress   --workspace W                 replay every regression case
  docs      --workspace W                 rebuild the readable Markdown pages
  coverage  --workspace W                 how many explanations could cite a record, run by run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import docs_gen, draft, evolve, followup, intake
from .run import run
from .validate import all_problems
from .workspace import Workspace


def _out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def _load_json_or_yaml(arg: str):
    """A file path, or the JSON/YAML text itself."""
    looks_inline = arg.lstrip().startswith(("{", "[")) or "\n" in arg
    text = arg if looks_inline else Path(arg).read_text(encoding="utf-8")
    return yaml.safe_load(text)


def cmd_init(a):
    # One table is a folder of one table: it gets every question that several tables get (reversed rows, exact copies,
    # composite dates). `confirm` below still reads drafts that `draft.init` wrote (they have no "kind"), so a workspace
    # started before this change can still be confirmed.
    d = intake.init(a.data, a.workspace, a.lang, main=a.main)
    _out({"main": d["main"], "tables": {n: {"rows": t["rows"], "suggested_kind": t["suggested_kind"]} for n, t in d["tables"].items()},
          "links": d["links"], "questions": d["questions"],
          "next": "ask every question as multiple choice (show the suggested answer and its evidence), then run confirm"})


def cmd_confirm(a):
    d = json.loads((Path(a.workspace) / "draft.json").read_text(encoding="utf-8"))
    fn = intake.confirm if d.get("kind") == "tables" else draft.confirm
    _out({**fn(a.workspace, _load_json_or_yaml(a.answers)), "problems": all_problems(Workspace(a.workspace))})


def cmd_propose(a):
    if a.file:
        spec = _load_json_or_yaml(a.file)
        items, doc = spec["items"], a.doc or str(Path(a.file).parent / spec["doc"])
    else:
        if not (a.quote and a.json and a.type):
            raise SystemExit("give --file, or --type, --quote and --json")
        items, doc = [{"type": a.type, "quote": a.quote, "entry": _load_json_or_yaml(a.json)}], a.doc
    r = intake.propose(a.workspace, doc, items)
    _out(r)
    return 1 if r["rejected"] else 0


def cmd_formation(a):
    _out(intake.formation(a.workspace))


def cmd_check(a):
    p = all_problems(Workspace(a.workspace))
    _out({"ok": not p, "problems": p})
    return 0 if not p else 1


def cmd_run(a):
    cfg = _load_json_or_yaml(a.config) if a.config else {}
    if a.metric:
        cfg["metric"] = a.metric
    if a.current:
        cfg["current"] = a.current
    if a.base:
        cfg["base"] = a.base[0] if len(a.base) == 1 else a.base
    if a.compare:
        cfg["compare"] = a.compare
    if a.previous:
        cfg["previous"] = True
    if a.dimensions:
        cfg["dimensions"] = a.dimensions.split(",")
    if a.filter:
        cfg["filters"] = dict(x.split("=", 1) for x in a.filter)
    if a.question:
        cfg["question"] = a.question
    s = run(a.workspace, cfg, out_dir=a.out)
    _out({"run_id": s["run_id"], "out_dir": s["out_dir"], "blocked": s["blocked"], "coverage": s["coverage"],
          "gaps": s["gaps"], "to_confirm": s["to_confirm"],
          "reports": [str(Path(s["out_dir"]) / f"report.{x}.md") for x in ("zh", "en")]})
    return 1 if s["blocked"] else 0


def cmd_followup(a):
    cfg = followup.config(a.from_dir, a.slot, a.dimensions.split(",") if a.dimensions else None)
    s = run(a.workspace, cfg, out_dir=a.out)
    _out({"run_id": s["run_id"], "followed": cfg["parent_run"], "slot": cfg["parent_slot"], "filters": cfg["filters"],
          "out_dir": s["out_dir"], "blocked": s["blocked"], "coverage": s["coverage"], "gaps": s["gaps"],
          "reports": [str(Path(s["out_dir"]) / f"report.{x}.md") for x in ("zh", "en")]})
    return 1 if s["blocked"] else 0


def cmd_correct(a):
    _out(evolve.apply(a.workspace, _load_json_or_yaml(a.json)))


def cmd_regress(a):
    rows = evolve.regress(a.workspace)
    _out({"passed": sum(r["pass"] for r in rows), "total": len(rows), "rows": rows})
    return 0 if all(r["pass"] for r in rows) else 1


def cmd_docs(a):
    _out({"docs": str(docs_gen.build(Workspace(a.workspace), a.out))})


def cmd_coverage(a):
    rows = []
    for rec in sorted(Path(a.workspace, "runs").glob("*/record.json")):
        s = json.loads(rec.read_text(encoding="utf-8"))
        rows.append({"run": s["run_id"], "created_at": s.get("created_at"), **s["coverage"]})
    rows.sort(key=lambda r: r["created_at"] or "")
    _out({"runs": rows})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aib", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = ap.add_subparsers(dest="cmd", required=True)
    p = commands.add_parser("init")
    p.add_argument("data", nargs="+", help="a table, several tables, or a folder of tables")
    p.add_argument("--workspace", required=True)
    p.add_argument("--lang", default="zh", choices=["zh", "en"])
    p.add_argument("--main", help="name the main table yourself (file name without extension)")
    p.set_defaults(fn=cmd_init)
    p = commands.add_parser("propose", help="record mechanisms or events an AI tool read in a document")
    p.add_argument("--workspace", required=True)
    p.add_argument("--doc", help="the document the quotes come from")
    p.add_argument("--file", help="a YAML/JSON file: {doc, items: [{type, quote, entry}]}")
    p.add_argument("--type", choices=["mechanism", "event"])
    p.add_argument("--quote", help="the sentence, exactly as it is in the document")
    p.add_argument("--json", help="the entry (entities, start, what / claim, ...)")
    p.set_defaults(fn=cmd_propose)
    p = commands.add_parser("formation")
    p.add_argument("--workspace", required=True)
    p.set_defaults(fn=cmd_formation)
    p = commands.add_parser("confirm")
    p.add_argument("--workspace", required=True)
    p.add_argument("--answers", required=True, help="a JSON/YAML file or string")
    p.set_defaults(fn=cmd_confirm)
    for name, fn in (("check", cmd_check), ("regress", cmd_regress), ("coverage", cmd_coverage)):
        p = commands.add_parser(name)
        p.add_argument("--workspace", required=True)
        p.set_defaults(fn=fn)
    p = commands.add_parser("docs")
    p.add_argument("--workspace", required=True)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_docs)
    p = commands.add_parser("run")
    p.add_argument("--workspace", required=True)
    p.add_argument("--config", help="a JSON/YAML file or string with the whole run config")
    p.add_argument("--metric")
    p.add_argument("--current", nargs=2, metavar=("START", "END"))
    p.add_argument("--base", nargs="+", help="yoy, pop, or START END")
    p.add_argument("--compare", help="a comparison id from model.yaml (second order, two sides)")
    p.add_argument("--previous", action="store_true", help="second order: compare with the previous window's change")
    p.add_argument("--dimensions", help="comma-separated cut order for this run")
    p.add_argument("--filter", action="append", help="dimension=value, repeatable")
    p.add_argument("--question")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_run)
    p = commands.add_parser("followup", help="ask inside one cause of an earlier run")
    p.add_argument("--workspace", required=True)
    p.add_argument("--from", dest="from_dir", required=True, help="the earlier run's folder (it holds record.json)")
    p.add_argument("--slot", required=True, help="a slot id from that run, e.g. channel=marketplace")
    p.add_argument("--dimensions", help="comma-separated dimensions to cut next")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_followup)
    p = commands.add_parser("correct")
    p.add_argument("--workspace", required=True)
    p.add_argument("--json", required=True, help="a JSON/YAML file or string describing the correction")
    p.set_defaults(fn=cmd_correct)
    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
