"""Self-improvement for one person: each correction is written down and becomes a regression case.

A correction changes a workspace file (world.yaml, model.yaml or rules.yaml), is appended to
corrections.jsonl with the user's own words, and produces regressions/<id>.yaml: the run that prompted
it, plus what must be true from now on. `regress` re-runs every case; a failure means the skill
forgot something it was told.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import yaml

from .workspace import Workspace

KINDS = {"add_mechanism": "mechanisms", "add_event": "events", "add_action": "actions"}


def _load(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def _dump(p: Path, data):
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:32] or "item"


def _next_id(existing: set, prefix: str, hint: str) -> str:
    base = f"{prefix}_{_slug(hint)}"
    out, n = base, 2
    while out in existing:
        out, n = f"{base}_{n}", n + 1
    return out


def _hint(entry: dict) -> str:
    if entry.get("hint"):
        return entry["hint"]
    text = entry.get("claim") or entry.get("what") or entry.get("action") or "user"
    return text.get("en") or next(iter(text.values()), "user") if isinstance(text, dict) else str(text)


def apply(ws_root, correction: dict, today: dt.date | None = None) -> dict:
    """Apply one correction. Returns {'correction': ..., 'regression': path}."""
    root = Path(ws_root)
    today = today or dt.date.today()
    kind = correction["type"]
    source = {"kind": "user", "date": today.isoformat(), "quote": correction.get("quote", "")}
    world_p, model_p, rules_p = root / "world.yaml", root / "model.yaml", root / "rules.yaml"
    expect = []

    if kind in KINDS:
        world = _load(world_p)
        bucket = world.setdefault(KINDS[kind], [])
        entry = dict(correction["entry"])
        prefix = {"add_mechanism": "mech", "add_event": "ev", "add_action": "act"}[kind]
        entry["id"] = entry.get("id") or _next_id({x["id"] for x in bucket}, prefix, _hint(entry))
        entry.pop("hint", None)
        # The user's own words are confirmed at once. Anything found elsewhere (a news link, a document)
        # keeps the source and status the caller gives it, normally "proposed", until the user confirms.
        entry["source"] = entry.get("source") or source
        entry["status"] = entry.get("status") or ("confirmed" if entry["source"].get("kind") == "user" else "proposed")
        bucket.append(entry)
        _dump(world_p, world)
        target = entry["id"]
        if kind == "add_action":
            expect.append({"actions_include": target})
        elif correction.get("slot"):
            expect.append({"slot": correction["slot"], "cites": target})
    elif kind == "add_alias":
        world = _load(world_p)
        ent = next(e for e in world["entities"] if e["id"] == correction["entity"])
        ent.setdefault("aliases", []).append(correction["alias"])
        ent.setdefault("alias_sources", []).append({**source, "alias": correction["alias"]})
        _dump(world_p, world)
        target = correction["entity"]
        expect.append({"alias": correction["alias"], "dimension": ent.get("dimension"), "resolves_to": target})
    elif kind == "set_priority":
        model = _load(model_p)
        pr = model.setdefault("priorities", {}).setdefault(correction["metric"], {})
        pr["order"] = list(correction["order"])
        pr["source"], pr["status"] = source, "confirmed"
        _dump(model_p, model)
        target = correction["metric"]
        expect.append({"first_cut": correction["order"][0]})
    elif kind == "set_param":
        rules = _load(rules_p)
        prm = rules.setdefault("params", {}).setdefault(correction["name"], {})
        prm["value"], prm["source"], prm["status"] = correction["value"], source, "confirmed"
        _dump(rules_p, rules)
        target = correction["name"]
        expect.append({"param": correction["name"], "equals": correction["value"]})
    elif kind in ("confirm", "retire"):
        world = _load(world_p)
        bucket = world[correction["bucket"]]
        entry = next(x for x in bucket if x["id"] == correction["id"])
        entry["status"] = "confirmed" if kind == "confirm" else "retired"
        entry.setdefault("history", []).append({**source, "change": kind, "reason": correction.get("reason", "")})
        _dump(world_p, world)
        target = correction["id"]
        expect.append({"status_of": target, "equals": entry["status"]})
        if kind == "retire" and correction.get("slot"):
            expect.append({"slot": correction["slot"], "not_cites": target})
    else:
        raise ValueError(f"unknown correction type {kind}")

    record = {"at": dt.datetime.now().isoformat(timespec="seconds"), "date": today.isoformat(), "type": kind,
              "target": target, "quote": correction.get("quote", ""), "run": correction.get("run")}
    with open(root / "corrections.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    reg_dir = root / "regressions"
    reg_dir.mkdir(exist_ok=True)
    case_id = f"{today.isoformat()}_{_slug(target)}"
    case = {"id": case_id, "from_correction": {"type": kind, "target": target, "quote": correction.get("quote", "")},
            "run": correction.get("run"), "expect": expect}
    path = reg_dir / f"{case_id}.yaml"
    _dump(path, case)
    return {"correction": record, "regression": str(path), "target": target}


def check(ws: Workspace, state: dict | None, expectation: dict) -> tuple[bool, str]:
    e = expectation
    if "slot" in e:
        slot = next((x for x in state["slots"] if x["id"] == e["slot"]), None)
        if slot is None:
            return False, f"slot {e['slot']} not found in run"
        ids = [c["id"] for c in slot["citations"]]
        if "cites" in e:
            return (e["cites"] in ids), f"{e['slot']} cites {ids}"
        if "not_cites" in e:
            return (e["not_cites"] not in ids), f"{e['slot']} cites {ids}"
    if "first_cut" in e:
        got = state["cuts"][0]["dimension"] if state["cuts"] else None
        return got == e["first_cut"], f"first cut {got}"
    if "actions_include" in e:
        return e["actions_include"] in state["actions"], f"actions {state['actions']}"
    if "param" in e:
        got = ws.params.get(e["param"], {}).get("value")
        return got == e["equals"], f"{e['param']} = {got}"
    if "status_of" in e:
        got = next((x.get("status") for k in ("mechanisms", "events", "actions") for x in ws.world.get(k, [])
                    if x["id"] == e["status_of"]), None)
        return got == e["equals"], f"status {got}"
    if "alias" in e:
        from .explain import World
        got = World(ws).entity_for(e["dimension"], e["alias"])
        return got == e["resolves_to"], f"alias resolves to {got}"
    return False, f"unknown expectation {e}"


def regress(ws_root) -> list[dict]:
    """Re-run every regression case. Returns one row per expectation."""
    from .run import run
    ws = Workspace(ws_root)
    out = []
    for path in sorted((Path(ws_root) / "regressions").glob("*.yaml")):
        case = _load(path)
        state = run(ws, case["run"], write=False) if case.get("run") else None
        for e in case.get("expect", []):
            needs_run = any(k in e for k in ("slot", "first_cut", "actions_include"))
            if needs_run and state is None:
                out.append({"case": case["id"], "expect": e, "pass": False, "detail": "case has no run to replay"})
                continue
            ok, detail = check(ws, state, e)
            out.append({"case": case["id"], "expect": e, "pass": ok, "detail": detail})
    return out
