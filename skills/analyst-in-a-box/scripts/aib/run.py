"""The analysis as a state machine. Each step reads the state, adds to it, and names the next step.

frame -> quality -> qualify -> (horizontal -> vertical | second_sides | second_time) -> explain -> actions -> checks -> record

The model frames the question and talks to the user; every number below is computed here.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from . import judge, narrative, qualify, quality, search, windows
from .defaults import param
from .explain import World, dominant_term, external_checks, fit
from .ops import additive, divisive, growth_accounting, multiplicative, pvm, second_order
from .validate import all_problems, data_problems
from .workspace import Workspace, label, shift_window, window

TRANSITIONS = [
    ("frame", "quality", "always"),
    ("quality", "qualify", "always; failed checks mark the data in doubt"),
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
    how = c.get("base", "yoy")
    if isinstance(how, (list, tuple)):
        base, rule = window(*how), None
    else:
        base, rule = windows.base(cur, how)
    s.update(metric=c["metric"], current=cur, base=base, filters=dict(c.get("filters") or {}),
             order="second_sides" if c.get("compare") else "second_time" if c.get("previous") else "first")
    if rule:
        s["notes"].append({"window": rule})
    s["problems"] = all_problems(ws, cur)
    if s["problems"]:
        mon = quality.monthly_mismatch(ws, s["metric"], cur, base)
        if mon:
            s["problems"].insert(0, mon)
    # Holidays in one period only: the run can leave those days out (with their paired days) or move the base.
    cal = _calendar(ws)
    plan = c.get("holiday")
    if cal and plan in ("exclude", "shift_base"):
        plans = {p["kind"]: p for p in qualify.holiday_plans(cal, base, cur)}
        if plan == "exclude" and "exclude" in plans:
            s["excluded_days"] = plans["exclude"]["days"]
            ws.exclude_days = frozenset(dt.date.fromisoformat(x) for x in s["excluded_days"])
        elif plan == "shift_base" and (plans.get("shift_base") or {}).get("base"):
            base = window(*plans["shift_base"]["base"])
            s["base"] = base
            s["notes"].append({"holiday": "base moved", "weeks": plans["shift_base"]["weeks"]})
    s["window_days"] = [(cur[1] - cur[0]).days + 1, (base[1] - base[0]).days + 1]
    s["days_compared"] = [ws.days_in(cur), ws.days_in(base)]
    # Unequal lengths: compare daily averages. Automatic when the rule chose the windows (calendar months differ
    # in length); for windows the user typed, only when asked (per_day: true), so a typo is not silently rescaled.
    auto = rule in ("calendar_month", "calendar_month_last_year") and s["days_compared"][0] != s["days_compared"][1]
    s["per_day"] = bool(c.get("per_day") or auto)
    ws.per_day = s["per_day"]
    if auto:
        s["notes"].append({"per_day": "automatic: the two calendar months have different lengths"})
    return "quality"


def _calendar(ws):
    for spec_name, spec in ws.external.specs.items():
        if spec.get("role") == "calendar":
            return ws.external.frame(spec_name).to_dict("records")
    return []


def step_quality(ws, s):
    if s["problems"]:
        s["quality"] = {"status": "not_checked", "suspect": False, "checks": [], "failed": [], "warned": [],
                        "note": "the workspace has problems; data quality was not checked"}
        return "qualify"
    hol = qualify.holiday_days(_calendar(ws))
    metrics = [s["metric"]] + [f for i in ws.model.get("identities", []) if i.get("left") == s["metric"] for f in i["factors"]]
    metrics = [x for x in dict.fromkeys(metrics) if ws.metrics.get(x, {}).get("kind") != "ratio" or x == s["metric"]]
    s["history_pairs"], s["history_kind"] = _history_pairs(ws, s)
    s["quality"] = quality.assess(ws, s["metric"], s["base"], s["current"], s["filters"], holidays=hol, metrics=metrics,
                                  pairs=s["history_pairs"])
    return "qualify"


def _history_pairs(ws, s):
    """Past (window, base) pairs of the same kind as this question, inside the data's range."""
    c, cur, base = s["config"], s["current"], s["base"]
    how = c.get("base", "yoy")
    if isinstance(how, (list, tuple)):
        how, rule = windows.explicit_kind(cur, base)
    else:
        rule = windows.base(cur, how)[1]
    try:
        lo, hi = ws.data_range(s["metric"])
    except Exception:  # an empty or unreadable source has no history; the quality step reports why
        return [], rule
    pairs = [(w, b) for w, b in windows.history(cur, base, how, c.get("history_windows", 26)) if b[0] >= lo and w[1] <= hi]
    # A past pair whose two windows hold different holidays is distorted by the calendar, not by the business:
    # it is left out of the history and named, so the z-score is not judged against it.
    cal = _calendar(ws)
    if cal and c.get("history_skip_holidays", param(ws, "history_skip_misaligned_holidays")):
        keep, out = [], []
        for w, b in pairs:
            al = qualify.calendar_alignment(cal, b, w)
            if al["holiday_misaligned"]:
                out.append({"window": [str(w[0]), str(w[1])], "base": [str(b[0]), str(b[1])],
                            "holidays": [h["name"] for h in al["holidays"] if h["difference"]]})
            else:
                keep.append((w, b))
        pairs = keep
        s["history_left_out"] = out
    return pairs, rule


def step_qualify(ws, s):
    m, cur, base, f = s["metric"], s["current"], s["base"], s["filters"]
    if "history_pairs" not in s:
        s["history_pairs"], s["history_kind"] = _history_pairs(ws, s)
    pairs, kind = s["history_pairs"], s["history_kind"]
    history, used = [], []
    for w, b in pairs:
        try:
            history.append(_change(ws, m, w, b, f))
            used.append((w, b))
        except Exception:  # a past window with no base is not history
            continue
    q = qualify.unusualness(history, _change(ws, m, cur, base, f))
    q["history_basis"] = {"kind": kind, "pairs": len(pairs),
                          "newest": [[str(x) for x in pairs[0][0]], [str(x) for x in pairs[0][1]]] if pairs else None,
                          "left_out_for_holidays": s.get("history_left_out", [])}
    q["history"] = [{"window": [str(w[0]), str(w[1])], "base": [str(b[0]), str(b[1])], "change": v}
                    for (w, b), v in zip(used, history)]
    q.update(qualify.ranges(history, q, (ws.params.get("unusual_z") or {}).get("value"),
                            (ws.params.get("unusual_z_low") or {}).get("value"),
                            floor=None if ws.metrics[m].get("kind") == "ratio" else -1.0))
    q["total_base"], q["total_cur"] = ws.total(m, base, f), ws.total(m, cur, f)
    for name, spec in ws.external.specs.items():
        if spec.get("role") == "market" and spec.get("compares_with") == m and not f:
            df = ws.external.frame(name)
            from .sources import aggregate
            dcol = spec.get("date", "date")

            def mk(w):
                return aggregate(df, "sum", spec["value"], dcol, w)
            mb, mc = mk(base), mk(cur)
            q.update(qualify.versus_market(q["total_base"], q["total_cur"], mb, mc), market_source=name)
            past = []
            for w, b in used:
                ob, oc, xb, xc = ws.total(m, b), ws.total(m, w), mk(b), mk(w)
                past.append((oc / ob - 1 if ob else None, xc / xb - 1 if xb else None))
            q.update(qualify.versus_market_usual(q["total_base"], q["total_cur"], q.get("market_growth"), past))
        if spec.get("role") == "calendar":
            df = ws.external.frame(name)
            q["calendar"] = qualify.calendar_alignment(df.to_dict("records"), base, cur)
            q["holiday_misaligned"] = q["calendar"]["holiday_misaligned"]
            q["holiday_plans"] = qualify.holiday_plans(df.to_dict("records"), base, cur)
    s["qualify"] = q
    s["verdict_unusual"] = _decide(ws, "qualify.unusual", {"qualify": q}, s)
    s["verdict_market"] = _decide(ws, "qualify.market", {"qualify": q}, s)
    return {"first": "horizontal", "second_sides": "second_sides", "second_time": "second_time"}[s["order"]]


def _expand(ws, metric, f, seen, used):
    """Leaves of the metric tree under `metric`: follow multiply identities down while every factor can be filtered."""
    for ident in ws.model.get("identities", []):
        if ident["left"] != metric or ident.get("operator") != "multiply" or ident["id"] in seen:
            continue
        if not all(set(f) <= ws.metric_dimensions(x) for x in ident["factors"]):
            return [metric], f"{ident['id']}: a factor cannot be filtered by {', '.join(sorted(f))}"
        seen.add(ident["id"])
        used.append(ident)
        leaves, stops = [], []
        for x in ident["factors"]:
            got, why = _expand(ws, x, f, seen, used)
            leaves += got
            if why:
                stops.append(why)
        return leaves, "; ".join(stops) or None
    return [metric], None


def step_horizontal(ws, s):
    """Break the metric down by its formulas, to the leaves (gross profit = revenue x margin; revenue = orders x AOV; ...).

    Each identity is decomposed on its own (LMDI), and the whole tree once more over its leaves. LMDI-I is
    consistent in aggregation: a leaf's contribution is the same whether the tree is taken in one step or level by
    level (Ang 2004), so the leaves add up to the change at the top. Ratio leaves are then split by their first
    dimension into mix and rate (Kitagawa)."""
    m, f = s["metric"], s["filters"]
    _extras(ws, s)
    used, stops = [], []
    leaves, why = _expand(ws, m, f, set(), used)
    if why:
        s["notes"].append({"tree_stops": why})
    for ident in used:
        b = {x: ws.total(x, s["base"], f) for x in ident["factors"]}
        c = {x: ws.total(x, s["current"], f) for x in ident["factors"]}
        try:
            res = multiplicative.decompose(b, c, label=ident["id"])
        except ValueError as exc:
            s["notes"].append({"skipped_identity": ident["id"], "reason": str(exc)})
            continue
        res["identity"] = ident["id"]
        res["parent"] = ident["left"]
        s["horizontal"].append(res)
    if len(leaves) < 2:
        return "vertical"
    b = {x: ws.total(x, s["base"], f) for x in leaves}
    c = {x: ws.total(x, s["current"], f) for x in leaves}
    try:
        tree = multiplicative.decompose(b, c, label=f"{m}_tree")
    except ValueError as exc:
        s["notes"].append({"tree": str(exc)})
        return "vertical"
    tree["metric"] = m
    tree["leaves"] = tree.pop("factors")
    tree["identities"] = [i["id"] for i in used]
    tree["stopped_at"] = why
    splits = {}
    pr = ws.model.get("priorities") or {}
    for x in leaves:
        if ws.metrics[x].get("kind") != "ratio":
            continue
        dims = [d for d in ((pr.get(x) or {}).get("order") or sorted(ws.metric_dimensions(x))) if d in ws.metric_dimensions(x) and d not in f]
        if not dims:
            continue
        try:
            r = divisive.decompose(ws.segments(x, dims[0], s["base"], s["current"], f), label=dims[0])
        except ValueError:
            continue
        splits[x] = {"dimension": dims[0], "rate_delta": r["rate_delta"], "structure_total": r["structure_total"],
                     "rate_total": r["rate_total"], "interaction_total": r["interaction_total"],
                     "larger_effect": r["larger_effect"], "closed": r["closed"], "top1_key": r["top1_key"]}
    tree["ratio_splits"] = splits
    s["tree"] = tree
    return "vertical"


def _extras(ws, s):
    """Optional breakdowns that answer a different shape of question: who (growth accounting) and how (price-volume-mix)."""
    m, f = s["metric"], s["filters"]
    ga = s["config"].get("growth_accounting")
    if ga and s["order"] == "first" and ws.metrics[m].get("kind") != "ratio":
        spec = ws.measures[ws.metrics[m]["measure"]]
        if spec["agg"] != "sum":
            s["notes"].append({"growth_accounting": "needs a summed metric"})
        else:
            import pandas as pd
            df = ws.sources.frame(spec["source"])
            for k, v in f.items():
                df = df[df[ws.column(spec_name(ws, m), k)].isin(v if isinstance(v, (list, tuple)) else [v])]
            col, dcol = ga["customer_column"], spec["date"]

            def per(w):
                d = df[(df[dcol] >= pd.Timestamp(w[0])) & (df[dcol] <= pd.Timestamp(w[1])) & df[col].notna()]
                return d.groupby(col)[spec["column"]].sum().to_dict()
            earlier = set(df[(df[dcol] < pd.Timestamp(s["base"][0])) & df[col].notna()][col].unique())
            r = growth_accounting.decompose(per(s["base"]), per(s["current"]), earlier, label=col)
            whole = ws.total(m, s["current"], f) - ws.total(m, s["base"], f)
            r["no_customer_delta"] = whole - r["total_delta"]
            r["customer_column"] = col
            s["growth_accounting"] = r
    for p in ws.model.get("pvm", []) or []:
        if p.get("metric") != m or s["order"] != "first" or p["dimension"] in f:
            continue
        qs = ws.segments(p["quantity"], p["dimension"], s["base"], s["current"], f)
        vs = ws.segments(m, p["dimension"], s["base"], s["current"], f)
        seg = {k: (qs.get(k, (0, 0))[0], vs.get(k, (0, 0))[0], qs.get(k, (0, 0))[1], vs.get(k, (0, 0))[1]) for k in set(qs) | set(vs)}
        r = pvm.decompose(seg, label=p["dimension"])
        r.update(dimension=p["dimension"], quantity=p["quantity"])
        s["pvm"] = r


def spec_name(ws, metric):
    return ws.metrics[metric]["measure"]


def _slot(ws, s, dim, value, path, filters, cut_index, extra=()):
    return {"id": "/".join(f"{d}={v}" for d, v in [*path, (dim, value)]), "dimension": dim, "value": value,
            "path": [list(p) for p in path], "filters": dict(filters), "cut": cut_index, "extra": list(extra)}


def _cut(ws, s, dim, scope, path, role, cand=None, candidates=None):
    """Cut once: exact decomposition, small-group ranking for ratios, each group's z and size, then the gate."""
    m = s["metric"]
    try:
        res = (cand or {}).get("_res") or search.decompose(ws, m, dim, s["base"], s["current"], scope)[1]
    except ValueError as exc:
        s["errors"].append({"dimension": dim, "filters": dict(scope), "error": str(exc)})
        return None
    if search.is_ratio(ws, m) and s["config"].get("shrink", param(ws, "shrink_ratio_segments")):
        search.shrink_ranking(ws, m, dim, s["base"], s["current"], scope, res)
    search.annotate(ws, m, dim, s["base"], s["current"], scope, res, s.get("history_pairs") or [])
    g = search.gate(ws, s, res, "first", layer=len(path))
    hit = _decide(ws, "stop.cut", {"result": res, "cut": g}, s) or {"then": {"action": "stop", "reason": "no_table"}}
    cut = {"dimension": dim, "path": [list(p) for p in path], "filters": dict(scope), "result": res, "decision": hit,
           "gate": g, "role": role}
    if candidates is not None:
        cut["candidates"] = [search.public(c) for c in candidates]
    s["cuts"].append(cut)
    return cut


def _order(ws, s):
    m = s["metric"]
    pr = (ws.model.get("priorities") or {}).get(m, {})
    allowed = ws.metric_dimensions(m)
    order = s["config"].get("dimensions") or pr.get("order") or sorted(allowed)
    for d in order:
        if d not in allowed:
            s["notes"].append({"skipped_dimension": d, "reason": "this metric cannot be cut by it"})
    # Only an order the user gave (in this run, or confirmed in model.yaml) fixes the first cut;
    # a proposed order is just the list of candidates.
    stated = bool(s["config"].get("dimensions") or (pr.get("order") and pr.get("status") == "confirmed"))
    return [d for d in order if d in allowed], stated, pr


def step_vertical(ws, s):
    """Modes: drill (default) scores the candidates at every layer, except that a stated first dimension is
    cut first; each cuts every dimension from the top and then merges slots that are one cause; fixed cuts the
    given order without scoring (the 0.1 behaviour)."""
    m = s["metric"]
    order, stated, pr = _order(ws, s)
    mode = s["config"].get("mode") or pr.get("mode", "drill")
    mode = "drill" if mode == "auto" else mode
    depth = int(s["config"].get("max_depth", param(ws, "search_max_depth")))
    top_k = int(param(ws, "search_top_k"))
    s["vertical_mode"] = mode
    s["config_used"] = {"mode": mode, "max_depth": depth, "top_k": top_k}
    if mode == "each":
        _each(ws, s, order)
        return "explain"
    filters, path = dict(s["filters"]), []
    for layer in range(depth):
        left = [d for d in order if d not in filters]
        if not left:
            break
        if mode == "fixed" or (layer == 0 and stated):
            dim, cands = left[0], None
        else:
            cands = sorted((search.candidate(ws, m, d, s["base"], s["current"], filters) for d in left),
                           key=lambda c: c["score"], reverse=True)
            cands = [c for c in cands if "error" not in c] or cands
            dim = cands[0]["dimension"]
        cand = next((c for c in cands or [] if c["dimension"] == dim), None)
        cut = _cut(ws, s, dim, filters, path, "layer", cand, (cands or [])[:top_k] if cands else None)
        if cut is None or cut["decision"]["then"].get("action") != "drill":
            break
        key = cut["result"]["top1_key"]
        s["slots"].append(_slot(ws, s, dim, key, path, filters, len(s["cuts"]) - 1))
        filters[dim] = key
        path.append((dim, key))
    for x in s["slots"]:
        x["leaf"] = False
    if s["slots"]:
        s["slots"][-1]["leaf"] = True
    if len(path) >= 2:
        _cross_check(ws, s, path)
    return "explain"


def _cross_check(ws, s, path):
    """Cut the second-to-last dimension inside the last value: if it points back to the same value, the two
    layers describe one cell, and the report can say so from both sides."""
    (d1, v1), (d2, v2) = path[-2], path[-1]
    scope = {**s["filters"], **{d: v for d, v in path[:-2]}, d2: v2}
    cut = _cut(ws, s, d1, scope, path[-1:], "cross_check")
    if cut is not None:
        cut["confirms"] = cut["result"]["top1_key"] == v1
        s["slots"][-1]["cross_check"] = {"cut": len(s["cuts"]) - 1, "confirms": cut["confirms"]}


def _cell_share(ws, s, a, b):
    """How much of each slot's contribution sits in their shared cell (a, b slots cut from the top)."""
    m = s["metric"]
    try:
        seg = ws.segments(m, [a["dimension"], b["dimension"]], s["base"], s["current"], s["filters"])
        r = search.op_for(ws, m).decompose(seg)
    except ValueError:
        return None, None
    vf = search.value_field(ws, m)
    cell = next((x[vf] for x in r["segments"] if x["key"] == f"{a['value']} / {b['value']}"), 0.0)
    va = next(x[vf] for x in s["cuts"][a["cut"]]["result"]["segments"] if x["key"] == a["value"])
    vb = next(x[vf] for x in s["cuts"][b["cut"]]["result"]["segments"] if x["key"] == b["value"])
    return (cell / va if va else None), (cell / vb if vb else None)


def _each(ws, s, order):
    for dim in order:
        if dim in s["filters"]:
            continue
        cut = _cut(ws, s, dim, s["filters"], [], "each")
        if cut and cut["decision"]["then"].get("action") == "drill":
            s["slots"].append(_slot(ws, s, dim, cut["result"]["top1_key"], [], s["filters"], len(s["cuts"]) - 1))
    for x in s["slots"]:
        x["leaf"] = True
    need = param(ws, "same_cause_min_share")
    merged = []
    for i, a in enumerate(s["slots"]):
        for b in s["slots"][i + 1:]:
            if not (a["leaf"] and b["leaf"]):
                continue
            sa, sb = _cell_share(ws, s, a, b)
            s["notes"].append({"same_cause_test": [a["id"], b["id"]], "cell_share_of_each": [sa, sb]})
            if sa is not None and sb is not None and sa >= need and sb >= need:
                a["leaf"] = b["leaf"] = False
                new = _slot(ws, s, b["dimension"], b["value"], [(a["dimension"], a["value"])], s["filters"], b["cut"])
                new.update(leaf=True, merged_from=[a["id"], b["id"]], cell_share_of_each=[sa, sb])
                merged.append(new)
    s["slots"].extend(merged)


def step_second_sides(ws, s):
    m = s["metric"]
    comp = next(c for c in ws.model.get("comparisons", []) if c["id"] == s["config"]["compare"])
    dim, (a, b) = comp["dimension"], comp["sides"]
    seg = (s["config"].get("dimensions") or [comp.get("segment_by")])[0]
    fa, fb = {**s["filters"], dim: a}, {**s["filters"], dim: b}
    sa = ws.segments(m, seg, s["base"], s["current"], fa)
    sb = ws.segments(m, seg, s["base"], s["current"], fb)
    try:
        if ws.metrics[m].get("kind") == "ratio":
            # gap = side A's rate change - side B's rate change, split by segment and by structure / rate.
            res = second_order.across_time_rate(sb, sa, label=comp["id"])
            res.update(operator="second_order_sides_rate", growth_a=res["growth_w2"], growth_b=res["growth_w1"], gap=res["growth_change"])
        else:
            res = second_order.across_sides(sa, sb, label=comp["id"], names=(a, b))
    except ValueError as exc:
        s["errors"].append({"dimension": seg, "filters": dict(s["filters"]), "error": str(exc)})
        return "explain"
    res["comparison"] = comp["id"]
    g = search.gate(ws, s, res, "second")
    hit = _decide(ws, "stop.cut", {"result": res, "cut": g}, s) or {"then": {"action": "stop"}}
    s["cuts"].append({"dimension": seg, "path": [], "filters": dict(s["filters"]), "sides": [a, b],
                      "side_dimension": dim, "result": res, "decision": hit, "gate": g, "role": "layer"})
    if hit["then"].get("action") == "drill":
        s["slots"].append({**_slot(ws, s, seg, res["top1_key"], [], s["filters"], len(s["cuts"]) - 1,
                                   extra=[(dim, a), (dim, b)]), "leaf": True})
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
    try:
        res = fn(s1, s2, label=seg)
    except ValueError as exc:
        s["errors"].append({"dimension": seg, "filters": dict(s["filters"]), "error": str(exc)})
        return "explain"
    res["previous_window"], res["previous_base"] = [w1[0], w1[1]], [b1[0], b1[1]]
    g = search.gate(ws, s, res, "second")
    hit = _decide(ws, "stop.cut", {"result": res, "cut": g}, s) or {"then": {"action": "stop"}}
    s["cuts"].append({"dimension": seg, "path": [], "filters": dict(s["filters"]), "result": res, "decision": hit,
                      "gate": g, "role": "layer"})
    if hit["then"].get("action") == "drill":
        s["slots"].append({**_slot(ws, s, seg, res["top1_key"], [], s["filters"], len(s["cuts"]) - 1), "leaf": True})
    return "explain"


def _anchor(ws, s, slot):
    """The decomposition row the slot stands for (for a merged slot, the shared cell)."""
    cut = s["cuts"][slot["cut"]]
    if slot.get("merged_from"):
        try:
            a = next(x for x in s["slots"] if x["id"] == slot["merged_from"][0])
            seg = ws.segments(s["metric"], [a["dimension"], slot["dimension"]], s["base"], s["current"], s["filters"])
            r = search.op_for(ws, s["metric"]).decompose(seg)
            return next((x for x in r["segments"] if x["key"] == f"{a['value']} / {slot['value']}"), None)
        except ValueError:
            return None
    return next((x for x in cut["result"].get("segments", []) if x["key"] == slot["value"]), None)


def step_explain(ws, s):
    world = World(ws)
    suspect = s["quality"].get("suspect")
    ratio = ws.metrics[s["metric"]].get("kind") == "ratio"
    for slot in s["slots"]:
        pairs = [tuple(p) for p in slot["path"]] + [(slot["dimension"], slot["value"])] + \
                [tuple(p) for p in slot["extra"]] + list(slot["filters"].items())
        ctx = world.context(pairs)
        mech, events, actions = world.cite(s["metric"], ctx, s["current"])
        anchor = _anchor(ws, s, slot)
        term = dominant_term(anchor) if s["order"] == "first" else "change"
        slot["dominant_term"] = term
        cites, external = [], []
        for e in mech:
            cites.append({"kind": "mechanism", "id": e["id"], "status": e["status"], "source": e.get("source"),
                          "explains": fit(e, s["base"], s["current"], term)})
        for e in events:
            item = {"kind": "event", "id": e["id"], "status": e["status"], "source": e.get("source"),
                    "external": e.get("kind") == "external", "explains": fit(e, s["base"], s["current"], term)}
            if item["external"]:
                if s["order"] == "first":
                    f = slot["filters"]
                    scope_delta = ws.total(s["metric"], s["current"], f) - ws.total(s["metric"], s["base"], f)
                    item["checks"] = external_checks(ws, world, e, s["metric"], s["base"], s["current"], f, scope_delta)
                else:
                    item["checks"] = {"status": "timing_only", "note": "slice and size checks need a first-order question"}
                external.append(item)
            cites.append(item)
        # A record explains a slot only if it fits the change and someone vouches for it: confirmed by the user, or
        # (for an outside event) passed the three checks. A proposed record from a document or a system table that
        # fits is a hypothesis "to confirm" until the user confirms it.
        explains = [c for c in cites if c["explains"] == "change"
                    and (c["checks"]["status"] == "supported" if c.get("external") else c["status"] == "confirmed")]
        pending = [c for c in cites if c["explains"] == "change" and not c.get("external") and c["status"] == "proposed"]
        slot["context"] = sorted(ctx)
        slot["citations"] = cites
        slot["actions"] = [a["id"] for a in actions]
        if suspect:
            slot["status"] = "data_suspect"
        else:
            slot["status"] = "explained" if explains else "hypothesis" if (external or pending) else "gap"
        slot["pending_confirmation"] = [c["id"] for c in pending]
        if not slot.get("leaf", True):
            continue
        if slot["status"] == "gap":
            s["gaps"].append({"slot": slot["id"], "metric": s["metric"], "dimension": slot["dimension"],
                              "value": slot["value"], "context": sorted(ctx), "dominant_term": term,
                              "cited_but_cannot_explain": [c["id"] for c in cites if c["explains"] != "change"]})
        for c in cites:
            if c["status"] == "proposed" or c.get("external"):
                s["to_confirm"].append({"slot": slot["id"], **{k: c[k] for k in ("kind", "id", "status")}})
    leaves = [x for x in s["slots"] if x.get("leaf", True)]
    explained = sum(1 for x in leaves if x["status"] == "explained")
    s["coverage"] = {"explained": explained, "slots": len(leaves),
                     "share": None if suspect or not leaves else explained / len(leaves),
                     "data_suspect": bool(suspect)}
    return "actions"


def step_actions(ws, s):
    seen = []
    for slot in s["slots"]:
        if slot["status"] in ("explained", "hypothesis"):
            seen.extend(a for a in slot["actions"] if a not in seen)
    s["actions"] = seen
    s["narrative"] = narrative.build(ws, s)
    s["charts"] = narrative.charts(ws, s)
    return "checks"


def _results(s):
    yield from s["horizontal"]
    for c in s["cuts"]:
        yield c["result"]


def _why_short(ws, s, cut) -> str:
    """What a shortfall of the groups is made of, when the data can show it: rows with a blank in the cut's dimension."""
    dims = [cut["dimension"]] if isinstance(cut["dimension"], str) else list(cut["dimension"])
    try:
        measure = ws.metric_measures(s["metric"])[0]
        spec = ws.measures[measure]
        if spec["agg"] == "count_distinct" and not ws._row_unique(spec["source"], spec["column"]):
            return (f"; {measure} counts distinct {spec['column']} and the same {spec['column']} appears in more than one "
                    f"{', '.join(dims)}, so it is counted in each group and the groups cannot be added up")
        usable = [d for d in dims if d in ws.dimensions]
        parts = []
        for tag, w in (("current", s["current"]), ("base", s["base"])):
            blank, rows = quality.blank_share(ws, measure, usable, w, cut["filters"])
            if blank:
                parts.append(f"{blank:,} of {rows:,} rows ({blank / rows:.1%}) in the {tag} period")
        if parts:
            return f"; blank {', '.join(usable)} on " + " and ".join(parts) + ", and rows with a blank value fall in no group"
    except (KeyError, ValueError):
        return ""
    return ""


def _reconcile(ws, s):
    """Independent check: the groups of every first-order cut add up to the total computed without grouping.
    Rows with no value on the dimension (or a measure that does not add across it) break this."""
    off = []
    for c in s["cuts"]:
        r = c["result"]
        if r.get("operator") not in ("additive", "divisive"):
            continue
        f = c["filters"]
        if r["operator"] == "additive":
            pairs = [(r["total_base"], ws.total(s["metric"], s["base"], f)), (r["total_cur"], ws.total(s["metric"], s["current"], f))]
        else:
            m = ws.metrics[s["metric"]]
            seg = r["segments"]
            pairs = [(math.fsum(x["num_base"] for x in seg), ws.total(m["numerator"], s["base"], f)),
                     (math.fsum(x["den_base"] for x in seg), ws.total(m["denominator"], s["base"], f)),
                     (math.fsum(x["num_cur"] for x in seg), ws.total(m["numerator"], s["current"], f)),
                     (math.fsum(x["den_cur"] for x in seg), ws.total(m["denominator"], s["current"], f))]
        for got, want in pairs:
            if not math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-6):
                off.append(f"{c['dimension']}: groups add to {got:,.2f}, total is {want:,.2f}" + _why_short(ws, s, c))
                break
    return not off, "; ".join(off)


def step_checks(ws, s):
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    add("workspace_valid", not s["problems"], "; ".join(s["problems"][:5]))
    q = s["quality"]
    add("data_quality", not q.get("suspect"),
        "data in doubt: " + ", ".join(q.get("failed", [])) if q.get("suspect") else "")
    n_cur, n_base = s["window_days"]
    add("windows_same_length", n_cur == n_base or s.get("per_day"),
        f"current has {n_cur} days, base has {n_base}; a change between windows of different length is not comparable "
        "(re-run with per_day: true to compare daily averages)")
    add("base_has_data", not s["errors"], "; ".join(f"{e['dimension']}: {e['error']}" for e in s["errors"]))
    if not s["problems"]:
        # Ratio metrics are defined as numerator / denominator, so an identity like revenue = orders x AOV holds by
        # construction. This only proves every factor can be computed (no zero denominator, no missing source).
        dp = data_problems(ws, s["current"]) + data_problems(ws, s["base"])
        if s["filters"]:
            dp += data_problems(ws, s["current"], s["filters"]) + data_problems(ws, s["base"], s["filters"])
        add("identities_computable", not dp, "; ".join(dp[:5]))
    add("segments_add_up_to_total", *_reconcile(ws, s))
    bad = [r.get("label") for r in _results(s) if not r.get("closed")]
    add("every_decomposition_closes", not bad, ", ".join(map(str, bad)))
    off = []
    for c in s["cuts"]:
        shares = [x.get("share") for x in c["result"].get("segments", [])]
        if shares and all(x is not None for x in shares) and not math.isclose(math.fsum(shares), 1.0, abs_tol=1e-9):
            off.append(c["dimension"])
    add("contribution_shares_sum_to_100pct", not off, ", ".join(off))
    add("every_slot_explained_or_flagged",
        all(x.get("status") in ("explained", "hypothesis", "gap", "data_suspect") for x in s["slots"]))
    claimed = [x["id"] for x in s["slots"] if x["status"] == "explained"
               and not any(c.get("explains") == "change" for c in x["citations"])]
    add("explanations_fit_the_change", not claimed, ", ".join(claimed))
    unproven = [x["id"] for x in s["slots"] if x["status"] == "explained"
                and all(c.get("external") and c["checks"]["status"] != "supported" for c in x["citations"])]
    add("outside_events_not_stated_as_fact", not unproven, ", ".join(unproven))
    add("every_cut_went_through_a_decision_table", all(c.get("decision", {}).get("table") for c in s["cuts"]))
    s["checks"] = checks
    s["blocked"] = not all(c["pass"] for c in checks)
    return "record"


STEPS = {"frame": step_frame, "quality": step_quality, "qualify": step_qualify, "horizontal": step_horizontal, "vertical": step_vertical,
         "second_sides": step_second_sides, "second_time": step_second_time, "explain": step_explain,
         "actions": step_actions, "checks": step_checks}


def _hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else None


def run(ws: Workspace | str | Path, config: dict, out_dir: str | Path | None = None, write: bool = True) -> dict:
    ws = ws if isinstance(ws, Workspace) else Workspace(ws)
    s = {"config": dict(config), "steps": [], "decisions": [], "horizontal": [], "cuts": [], "slots": [],
         "gaps": [], "to_confirm": [], "notes": [], "actions": [], "checks": [], "blocked": False, "errors": [],
         "definitions": {f: _hash(ws.root / f) for f in ("project.yaml", "model.yaml", "rules.yaml", "world.yaml")}}
    step = "frame"
    try:
        while step != "record":
            nxt = STEPS[step](ws, s)
            s["steps"].append({"step": step, "next": nxt})
            step = nxt
    finally:
        # one run's excluded days and per-day scaling must not leak into the next run on the same workspace
        ws.exclude_days, ws.per_day = frozenset(), False
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
