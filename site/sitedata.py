"""The data layer of the site: run the engine and collect what the pages show. No wording, no layout.

Everything comes from engine runs on the demo shop, the public dataset and the adversarial test data.
Fields the engine returns are copied as they are (under `state`; field list in
skills/analyst-in-a-box/references/report.md section 5). The only numbers computed here are the two measurements
listed in DERIVED, which are about the engine rather than produced by it.

If the engine raises, this module raises: a site built from a half-failed run would show wrong numbers.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DEMO = ROOT / "demo" / "store"
PUBLIC = ROOT / "demo" / "public"
TESTS = ROOT / "tests"
for p in (ROOT / "skills" / "analyst-in-a-box" / "scripts", DEMO, TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import answer_key  # noqa: E402
from aib import draft, evolve  # noqa: E402
from aib.explain import World, entry_text  # noqa: E402
from aib.report import seg_label, slot_label  # noqa: E402
from aib.run import run  # noqa: E402
from aib.workspace import Workspace, label  # noqa: E402

LANGS = ("zh", "en")
# The four demo-shop questions the site reports on, and the kind of page each one needs.
CASES = {"revenue_last_week": "additive", "east_last_week": "external", "aov_last_week": "ratio",
         "june_price_volume": "pvm", "app_vs_web": "sides"}

DERIVED = {
    "unsure.noise_weeks": "The adversarial pure-noise data (tests/synth.py seed 23) asked week by week for 30 weeks, each "
                          "against the same weekdays a year earlier; count of weeks where the run drilled into a slice "
                          "(state.slots non-empty). tests/test_adversarial.py asks only one week of it.",
    "learning.forget": "After the learning correction, the world entry it added is deleted from world.yaml and "
                       "evolve.regress is run again; `caught` is True when at least one regression case fails.",
}


# ---------------------------------------------------------------- helpers

def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [jsonable(v) for v in x]
    if isinstance(x, (dt.date, dt.datetime)):
        return x.isoformat()
    if isinstance(x, Path):
        return x.name
    return x


def win(w):
    return (dt.date.fromisoformat(str(w[0])), dt.date.fromisoformat(str(w[1])))


def copy_ws(dst: Path) -> Path:
    shutil.copytree(DEMO / "workspace", dst, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    return dst


def lab(x):
    return {lg: label(x, lg) for lg in LANGS}


def slice_filters(slot):
    f = dict(slot["filters"])
    f.update({d: v for d, v in slot["path"]})
    f[slot["dimension"]] = slot["value"]
    return f


def find_entry(ws, eid):
    for bucket in ("mechanisms", "events", "actions", "entities"):
        for x in ws.world.get(bucket, []):
            if x.get("id") == eid:
                return bucket, x
    return None, None


def labels_for(ws, world, s):
    """Every label a page of this run can need, in both languages."""
    dims = {c["dimension"] for c in s.get("cuts", [])} | set(s.get("filters", {})) | {d for x in s.get("slots", []) for d, _ in x["path"]}
    dims |= {x["dimension"] for x in s.get("slots", [])}
    out = {"dimensions": {d: lab(ws.dimensions[d].get("label", d)) for d in dims if d in ws.dimensions},
           "metrics": {m: lab(spec.get("label", m)) for m, spec in ws.metrics.items()},
           "values": {}}
    pairs = set()
    for c in s.get("cuts", []):
        pairs |= {(c["dimension"], seg["key"]) for seg in c["result"]["segments"]}
        pairs |= set((d, v) for d, v in c.get("filters", {}).items())
    for x in s.get("slots", []):
        pairs |= {(x["dimension"], x["value"])} | {(d, v) for d, v in x["path"]} | {(d, v) for d, v in x.get("extra", [])}
    pairs |= set(s.get("filters", {}).items())
    if s.get("pvm"):
        out["dimensions"].setdefault(s["pvm"]["dimension"], lab(ws.dimensions[s["pvm"]["dimension"]].get("label", s["pvm"]["dimension"])))
        pairs |= {(s["pvm"]["dimension"], g["key"]) for g in s["pvm"]["segments"]}
    for d, v in pairs:
        out["values"].setdefault(d, {})[str(v)] = {lg: seg_label(ws, world, d, v, lg) for lg in LANGS}
    out["slots"] = {x["id"]: {lg: slot_label(ws, world, x, lg) for lg in LANGS} for x in s.get("slots", [])}
    return out


def entries_for(ws, s):
    """Text of every world entry the run cites or proposes, in both languages."""
    ids = {c["id"] for x in s.get("slots", []) for c in x["citations"]} | set(s.get("actions", []))
    ids |= {r["id"] for r in (s.get("narrative") or {}).get("ruled_out", []) if r.get("id")}
    out = {}
    for eid in sorted(ids):
        bucket, e = find_entry(ws, eid)
        if e is None:
            raise KeyError(f"run cites {eid}, which is not in world.yaml")
        row = {"bucket": bucket, "text": {lg: entry_text(e, lg) for lg in LANGS}, "start": jsonable(e.get("start")),
               "end": jsonable(e.get("end")), "status": e.get("status"), "source": e.get("source"), "kind": e.get("kind"),
               "refuted_by": lab(e["refuted_by"]) if e.get("refuted_by") else None}
        if bucket == "actions":
            row["owner"] = lab(e.get("owner", ""))
            row["action"] = lab(e.get("action", ""))
        out[eid] = row
    return out
# ---------------------------------------------------------------- runs

def store_cases(tmp: Path) -> dict:
    out = {}
    for k, kind in CASES.items():
        c = answer_key.CASES[k]
        ws = Workspace(copy_ws(tmp / f"ws_{k}"))
        s = run(ws, {**c["run"], "id": k, "question": c["question"]}, out_dir=tmp / "runs" / k)
        if s.get("errors"):
            raise RuntimeError(f"{k}: engine errors {s['errors']}")
        world = World(ws)
        state = jsonable({key: v for key, v in s.items() if key not in ("out_dir",)})
        out[k] = {"id": k, "kind": kind, "question": c["question"], "state": state,
                  "labels": labels_for(ws, world, s), "entries": entries_for(ws, s),
                  "unit": ws.metrics[s["metric"]].get("unit")}
    return out


def adversarial() -> dict:
    import synth
    import test_adversarial as T
    out = {}
    for name in ("pure_noise_week", "missing_two_days", "week_loaded_twice"):
        t = Path(tempfile.mkdtemp())
        ws, cfg, expect, want = T.CASES[name](t)
        s = run(ws, cfg, write=False)
        out[name] = {"expect": expect, "ok": T.judge(s, expect, want), "blocked": s["blocked"],
                     "drilled": bool(s["slots"]), "verdict": s["verdict_unusual"]["then"]["verdict"] if s.get("verdict_unusual") else None,
                     "z": s["qualify"].get("robust_z"), "quality": jsonable(s["quality"]), "window": jsonable(s["current"])}
    t = Path(tempfile.mkdtemp())
    ws = Workspace(synth.workspace(t, synth.orders(seed=23)))
    end, drilled = dt.date.fromisoformat(T.WEEK[1]), []
    for k in range(30):
        e = end - dt.timedelta(days=7 * k)
        s = run(ws, {"metric": "revenue", "current": [str(e - dt.timedelta(days=6)), str(e)], "base": "yoy"}, write=False)
        drilled.append(bool(s["slots"]))
    out["noise_weeks"] = {"weeks": 30, "drilled": sum(drilled), "seed": 23}
    return out


def public(tmp: Path) -> dict:
    src = PUBLIC / "data" / "invoices.csv.gz"
    if not src.exists():
        raise SystemExit(f"{src} is missing; build it with demo/public/prepare.py (see demo/public/README.md)")
    answers = yaml.safe_load((PUBLIC / "answers.yaml").read_text(encoding="utf-8"))
    out = {"source": json.loads((PUBLIC / "data" / "source.json").read_text(encoding="utf-8")), "answers": jsonable(answers), "init": {}}
    for lg in LANGS:
        d = tmp / "public" / lg
        d.mkdir(parents=True)
        shutil.copy(src, d / src.name)
        init = draft.init(d / src.name, d / "ws", lang=lg)
        out["init"][lg] = jsonable({k: init[k] for k in ("rows", "profile", "belongs_to", "quiet_weekdays", "questions")})
        if lg == "zh":
            first = draft.confirm(d / "ws", answers)["first_run"]
            ws = Workspace(d / "ws")
            s = run(ws, first, out_dir=tmp / "public" / "run")
            if s.get("errors"):
                raise RuntimeError(f"public: engine errors {s['errors']}")
            out["first_run"] = jsonable(first)
            out["state"] = jsonable({k: v for k, v in s.items() if k != "out_dir"})
            out["labels"] = labels_for(ws, World(ws), s)
    return out


def learning(tmp: Path) -> dict:
    root = copy_ws(tmp / "learn")
    spec = yaml.safe_load((DEMO / "correction.yaml").read_text(encoding="utf-8"))
    case = answer_key.CASES[spec["after_case"]]
    cfg = {**case["run"], "id": case["case"], "question": case["question"]}
    before = run(root, cfg, out_dir=tmp / "learn_before")
    applied = evolve.apply(root, {**spec["correction"], "run": cfg})
    after = run(root, cfg, out_dir=tmp / "learn_after")
    rows = evolve.regress(root)
    ws_after = Workspace(root)
    entries = {**entries_for(Workspace(copy_ws(tmp / "learn_view")), before), **entries_for(ws_after, after)}
    labels = labels_for(ws_after, World(ws_after), after)
    world = yaml.safe_load((root / "world.yaml").read_text(encoding="utf-8"))
    target, removed = applied["target"], False
    for bucket in ("mechanisms", "events", "actions"):
        keep = [x for x in world.get(bucket, []) if x.get("id") != target]
        removed |= len(keep) != len(world.get(bucket, []))
        world[bucket] = keep
    if not removed:
        raise AssertionError(f"learning target {target} not found in world.yaml")
    (root / "world.yaml").write_text(yaml.safe_dump(world, allow_unicode=True, sort_keys=False), encoding="utf-8")
    forgot = evolve.regress(root)
    pick = lambda s: jsonable({k: s[k] for k in ("slots", "coverage", "narrative", "qualify", "cuts", "metric")})  # noqa: E731
    return {"spec": jsonable(spec), "question": case["question"], "before": pick(before), "after": pick(after),
            "applied": jsonable({k: applied[k] for k in ("target", "correction")}), "regress": jsonable(rows),
            "forget": {"caught": not all(r["pass"] for r in forgot), "rows": jsonable(forgot)},
            "entries": entries, "labels": labels}


def world_stats() -> dict:
    ws = Workspace(DEMO / "workspace")
    params = []
    for k, v in (ws.rules.get("params") or {}).items():
        if isinstance(v, dict):
            params.append({"id": k, "value": v.get("value"), "source": v.get("source"), "status": v.get("status")})
    return {"metrics": len(ws.metrics), "dimensions": len(ws.dimensions),
            "entities": len(ws.world.get("entities", [])), "mechanisms": len(ws.world.get("mechanisms", [])),
            "events": len(ws.world.get("events", [])), "actions": len(ws.world.get("actions", [])),
            "tables": len(ws.tables()), "params": jsonable(params)}


def meta() -> dict:
    import subprocess
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "skills", "demo"], capture_output=True, text=True).stdout.strip())
    skill = (ROOT / "skills" / "analyst-in-a-box" / "SKILL.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(skill.split("---")[1])
    return {"built_at": dt.datetime.now().isoformat(timespec="seconds"), "git_head": head, "engine_has_uncommitted_changes": dirty,
            "skill_version": (fm.get("metadata") or {}).get("version"),
            "shop": yaml.safe_load((DEMO / "planted.yaml").read_text(encoding="utf-8"))["shop"]}


def intake() -> dict:
    """Run the intake demo (demo/intake/run_intake.py) fresh, then read the formation.json it just wrote.
    run_intake rewrites its own outputs under demo/intake/ (tables, workspace, formation.*); nothing else."""
    sys.path.insert(0, str(ROOT / "demo" / "intake"))
    import run_intake
    run_intake.main()
    return json.loads((ROOT / "demo" / "intake" / "formation.json").read_text(encoding="utf-8"))


def collect() -> dict:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        data = {"meta": meta(), "derived_fields": DERIVED, "intake": intake(), "cases": store_cases(tmp),
                "unsure": adversarial(), "public": public(tmp), "learning": learning(tmp), "world": world_stats()}
    return data
