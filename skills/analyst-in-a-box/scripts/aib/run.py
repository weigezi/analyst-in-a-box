"""The analysis as a state machine. Each step reads the state, adds to it, and names the next step.

frame -> qualify -> (horizontal -> vertical | second_sides | second_time) -> explain -> actions -> checks -> record

The model frames the question and talks to the user; every number below is computed here.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from . import judge, qualify
from .explain import World, external_checks
from .ops import additive, divisive, multiplicative, second_order
from .validate import all_problems, data_problems
from .workspace import Workspace, label, shift_window, window

TRANSITIONS = [
    ("frame", "qualify", "always"),
    ("qualify", "second_sides", "the question compares two sides of a dimension"),
    ("qualify", "second_time", "the question compares this window's change with the previous window's"),
    ("qualify", "horizontal", "otherwise (first order)"),
    ("horizontal", "vertical", "always"),
    ("vertical", "explain", "always"),
    ("second_sides", "explain", "always"),
    ("second_time", "explain", "always"),
    ("explain", "actions", "always"),
    ("actions", "checks", "always"),
    ("checks", "record", "always; failed checks block the report"),
]


def _change(ws, metric, w, b, filters=None):
    cur, base = ws.total(metric, w, filters), ws.total(metric, b, filters)
    if ws.metrics[metric].get("kind") == "ratio":
        return cur - base
    return cur / base - 1 if base else None


def _op(ws, metric):
    return divisive if ws.metrics[metric].get("kind") == "ratio" else additive


def _table(ws, tid):
    return ws.tables().get(tid)


def _decide(ws, tid, results, state):
    t = _table(ws, tid)
    if t is None:
        return None
    hit = judge.evaluate(t, results, ws.params)
    state["decisions"].append(hit)
    return hit


def step_frame(ws, s):
    c = s["config"]
    if c["metric"] not in ws.metrics:
        raise KeyError(f"unknown metric {c['metric']}")
    cur = window(*c["current"])
    base = window(*c["base"]) if isinstance(c.get("base"), (list, tuple)) else shift_window(cur, c.get("base", "yoy"))
    s.update(metric=c["metric"], current=cur, base=base, filters=dict(c.get("filters") or {}),
             order="second_sides" if c.get("compare") else "second_time" if c.get("previous") else "first")
    s["problems"] = all_problems(ws, cur)
    s["window_days"] = [(cur[1] - cur[0]).days + 1, (base[1] - base[0]).days + 1]
    return "qualify"


def step_qualify(ws, s):
    m, cur, base, f = s["metric"], s["current"], s["base"], s["filters"]
    n = (cur[1] - cur[0]).days + 1
    how = s["config"].get("base", "yoy") if isinstance(s["config"].get("base", "yoy"), str) else "yoy"
    history, w = [], cur
    for _ in range(s["config"].get("history_windows", 26)):
        w = (w[0] - dt.timedelta(days=n), w[1] - dt.timedelta(days=n))
        try:
            history.append(_change(ws, m, w, shift_window(w, how), f))
        except Exception:  # windows before the data starts have no base; they are simply not history
            break
    q = qualify.unusualness(history, _change(ws, m, cur, base, f))
    q["total_base"], q["total_cur"] = ws.total(m, base, f), ws.total(m, cur, f)
    for name, spec in ws.external.specs.items():
        if spec.get("role") == "market" and spec.get("compares_with") == m and not f:
            df = ws.external.frame(name)
            from .sources import aggregate
            mb = aggregate(df, "sum", spec["value"], spec.get("date", "date"), base)
            mc = aggregate(df, "sum", spec["value"], spec.get("date", "date"), cur)
            q.update(qualify.versus_market(q["total_base"], q["total_cur"], mb, mc), market_source=name)
        if spec.get("role") == "calendar":
            df = ws.external.frame(name)
            q["calendar"] = qualify.calendar_alignment(df.to_dict("records"), base, cur)
            q["holiday_misaligned"] = q["calendar"]["holiday_misaligned"]
    s["qualify"] = q
    s["verdict_unusual"] = _decide(ws, "qualify.unusual", {"qualify": q}, s)
    s["verdict_market"] = _decide(ws, "qualify.market", {"qualify": q}, s)
    return {"first": "horizontal", "second_sides": "second_sides", "second_time": "second_time"}[s["order"]]


def step_horizontal(ws, s):
    m, f = s["metric"], s["filters"]
    for ident in ws.model.get("identities", []):
        if ident["left"] != m or ident.get("operator") != "multiply":
            continue
        if not all(set(f) <= ws.metric_dimensions(x) for x in ident["factors"]):
            s["notes"].append({"skipped_identity": ident["id"], "reason": "a factor cannot be filtered this way"})
            continue
        b = {x: ws.total(x, s["base"], f) for x in ident["factors"]}
        c = {x: ws.total(x, s["current"], f) for x in ident["factors"]}
        res = multiplicative.decompose(b, c, label=ident["id"])
        res["identity"] = ident["id"]
        s["horizontal"].append(res)
    return "vertical"


def _slot(ws, s, dim, value, path, filters, cut_index, extra=()):
    return {"id": "/".join(f"{d}={v}" for d, v in [*path, (dim, value)]), "dimension": dim, "value": value,
            "path": [list(p) for p in path], "filters": dict(filters), "cut": cut_index, "extra": list(extra)}


def step_vertical(ws, s):
    m = s["metric"]
    pr = (ws.model.get("priorities") or {}).get(m, {})
    order = s["config"].get("dimensions") or pr.get("order") or sorted(ws.metric_dimensions(m))
    mode = s["config"].get("mode") or pr.get("mode", "drill")
    s["vertical_mode"] = mode
    allowed, op = ws.metric_dimensions(m), _op(ws, m)
    filters, path = dict(s["filters"]), []
    for dim in order:
        if dim not in allowed or dim in filters:
            s["notes"].append({"skipped_dimension": dim})
            continue
        scope = dict(filters) if mode == "drill" else dict(s["filters"])
        res = op.decompose(ws.segments(m, dim, s["base"], s["current"], scope), label=dim)
        hit = _decide(ws, "stop.cut", {"result": res}, s) or {"then": {"action": "stop", "reason": "no_table"}}
        s["cuts"].append({"dimension": dim, "path": [list(p) for p in path], "filters": scope, "result": res, "decision": hit})
        if hit["then"].get("action") != "drill":
            if mode == "drill":
                break
            continue
        s["slots"].append(_slot(ws, s, dim, res["top1_key"], path if mode == "drill" else [], scope, len(s["cuts"]) - 1))
        if mode == "drill":
            filters[dim] = res["top1_key"]
            path.append((dim, res["top1_key"]))
    return "explain"


def step_second_sides(ws, s):
    m = s["metric"]
    comp = next(c for c in ws.model.get("comparisons", []) if c["id"] == s["config"]["compare"])
    dim, (a, b) = comp["dimension"], comp["sides"]
    seg = (s["config"].get("dimensions") or [comp.get("segment_by")])[0]
    fa, fb = {**s["filters"], dim: a}, {**s["filters"], dim: b}
    sa = ws.segments(m, seg, s["base"], s["current"], fa)
    sb = ws.segments(m, seg, s["base"], s["current"], fb)
    if ws.metrics[m].get("kind") == "ratio":
        # gap = side A's rate change - side B's rate change, split by segment and by structure / rate.
        res = second_order.across_time_rate(sb, sa, label=comp["id"])
        res.update(operator="second_order_sides_rate", growth_a=res["growth_w2"], growth_b=res["growth_w1"], gap=res["growth_change"])
    else:
        res = second_order.across_sides(sa, sb, label=comp["id"], names=(a, b))
    res["comparison"] = comp["id"]
    hit = _decide(ws, "stop.cut", {"result": res}, s) or {"then": {"action": "stop"}}
    s["cuts"].append({"dimension": seg, "path": [], "filters": dict(s["filters"]), "sides": [a, b],
                      "side_dimension": dim, "result": res, "decision": hit})
    if hit["then"].get("action") == "drill":
        s["slots"].append(_slot(ws, s, seg, res["top1_key"], [], s["filters"], len(s["cuts"]) - 1,
                                extra=[(dim, a), (dim, b)]))
    return "explain"


def step_second_time(ws, s):
    m, how = s["metric"], s["config"].get("base", "yoy")
    w2, b2 = s["current"], s["base"]
    w1 = shift_window(w2, "pop")
    b1 = shift_window(w1, how) if isinstance(how, str) else shift_window(b2, "pop")
    pr = (ws.model.get("priorities") or {}).get(m, {})
    seg = (s["config"].get("dimensions") or pr.get("order") or sorted(ws.metric_dimensions(m)))[0]
    s1 = ws.segments(m, seg, b1, w1, s["filters"])
    s2 = ws.segments(m, seg, b2, w2, s["filters"])
    fn = second_order.across_time_rate if ws.metrics[m].get("kind") == "ratio" else second_order.across_time
    res = fn(s1, s2, label=seg)
    res["previous_window"], res["previous_base"] = [w1[0], w1[1]], [b1[0], b1[1]]
    hit = _decide(ws, "stop.cut", {"result": res}, s) or {"then": {"action": "stop"}}
    s["cuts"].append({"dimension": seg, "path": [], "filters": dict(s["filters"]), "result": res, "decision": hit})
    if hit["then"].get("action") == "drill":
        s["slots"].append(_slot(ws, s, seg, res["top1_key"], [], s["filters"], len(s["cuts"]) - 1))
    return "explain"


def step_explain(ws, s):
    world = World(ws)
    for slot in s["slots"]:
        pairs = [tuple(p) for p in slot["path"]] + [(slot["dimension"], slot["value"])] + \
                [tuple(p) for p in slot["extra"]] + list(slot["filters"].items())
        ctx = world.context(pairs)
        mech, events, actions = world.cite(s["metric"], ctx, s["current"])
        cites, external = [], []
        for e in mech:
            cites.append({"kind": "mechanism", "id": e["id"], "status": e["status"], "source": e.get("source")})
        for e in events:
            item = {"kind": "event", "id": e["id"], "status": e["status"], "source": e.get("source"),
                    "external": e.get("kind") == "external"}
            if item["external"]:
                if s["order"] == "first" and ws.metrics[s["metric"]].get("kind") != "ratio":
                    scope_delta = ws.total(s["metric"], s["current"], slot["filters"]) - ws.total(s["metric"], s["base"], slot["filters"])
                    item["checks"] = external_checks(ws, world, e, s["metric"], s["base"], s["current"], slot["filters"], scope_delta)
                else:
                    item["checks"] = {"status": "timing_only", "note": "slice and size checks need an additive first-order question"}
                external.append(item)
            cites.append(item)
        solid = [c for c in cites if not c.get("external") or c["checks"]["status"] == "supported"]
        slot["context"] = sorted(ctx)
        slot["citations"] = cites
        slot["actions"] = [a["id"] for a in actions]
        slot["status"] = "explained" if solid else "hypothesis" if external else "gap"
        if slot["status"] == "gap":
            s["gaps"].append({"slot": slot["id"], "metric": s["metric"], "dimension": slot["dimension"],
                              "value": slot["value"], "context": sorted(ctx)})
        for c in cites:
            if c["status"] == "proposed" or c.get("external"):
                s["to_confirm"].append({"slot": slot["id"], **{k: c[k] for k in ("kind", "id", "status")}})
    explained = sum(1 for x in s["slots"] if x["status"] == "explained")
    s["coverage"] = {"explained": explained, "slots": len(s["slots"]),
                     "share": explained / len(s["slots"]) if s["slots"] else None}
    return "actions"


def step_actions(ws, s):
    seen = []
    for slot in s["slots"]:
        if slot["status"] in ("explained", "hypothesis"):
            seen.extend(a for a in slot["actions"] if a not in seen)
    s["actions"] = seen
    return "checks"


def _results(s):
    yield from s["horizontal"]
    for c in s["cuts"]:
        yield c["result"]


def step_checks(ws, s):
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    add("workspace_valid", not s["problems"], "; ".join(s["problems"][:5]))
    n_cur, n_base = s["window_days"]
    add("windows_same_length", n_cur == n_base,
        f"current has {n_cur} days, base has {n_base}; a change between windows of different length is not comparable")
    if not s["problems"]:
        dp = data_problems(ws, s["current"]) + data_problems(ws, s["base"])
        add("identities_hold_on_data", not dp, "; ".join(dp[:5]))
    bad = [r.get("label") for r in _results(s) if not r.get("closed")]
    add("every_decomposition_closes", not bad, ", ".join(map(str, bad)))
    off = []
    for c in s["cuts"]:
        shares = [x.get("share") for x in c["result"].get("segments", [])]
        if shares and all(x is not None for x in shares) and not math.isclose(math.fsum(shares), 1.0, abs_tol=1e-9):
            off.append(c["dimension"])
    add("contribution_shares_sum_to_100pct", not off, ", ".join(off))
    add("every_slot_explained_or_flagged", all(x.get("status") in ("explained", "hypothesis", "gap") for x in s["slots"]))
    unproven = [x["id"] for x in s["slots"] if x["status"] == "explained"
                and all(c.get("external") and c["checks"]["status"] != "supported" for c in x["citations"])]
    add("outside_events_not_stated_as_fact", not unproven, ", ".join(unproven))
    add("every_cut_went_through_a_decision_table", all(c.get("decision", {}).get("table") for c in s["cuts"]))
    s["checks"] = checks
    s["blocked"] = not all(c["pass"] for c in checks)
    return "record"


STEPS = {"frame": step_frame, "qualify": step_qualify, "horizontal": step_horizontal, "vertical": step_vertical,
         "second_sides": step_second_sides, "second_time": step_second_time, "explain": step_explain,
         "actions": step_actions, "checks": step_checks}


def _hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else None


def run(ws: Workspace | str | Path, config: dict, out_dir: str | Path | None = None, write: bool = True) -> dict:
    ws = ws if isinstance(ws, Workspace) else Workspace(ws)
    s = {"config": dict(config), "steps": [], "decisions": [], "horizontal": [], "cuts": [], "slots": [],
         "gaps": [], "to_confirm": [], "notes": [], "actions": [], "checks": [], "blocked": False,
         "definitions": {f: _hash(ws.root / f) for f in ("project.yaml", "model.yaml", "rules.yaml", "world.yaml")}}
    step = "frame"
    while step != "record":
        nxt = STEPS[step](ws, s)
        s["steps"].append({"step": step, "next": nxt})
        step = nxt
    s["steps"].append({"step": "record", "next": None})
    s["run_id"] = config.get("id") or f"{s['metric']}-{s['current'][0]}-{s['current'][1]}"
    s["created_at"] = dt.datetime.now().isoformat(timespec="seconds")
    if write:
        from . import report
        out = Path(out_dir) if out_dir else ws.root / "runs" / s["run_id"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "record.json").write_text(json.dumps(s, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        for lang in ("zh", "en"):
            (out / f"report.{lang}.md").write_text(report.render(ws, s, lang, out), encoding="utf-8")
        s["out_dir"] = str(out)
    return s
