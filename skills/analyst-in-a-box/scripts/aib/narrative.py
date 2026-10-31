"""What the report says, computed: main cause, what offset it, what was ruled out, when it started, and chart data.

Every number here comes from the run state or the workspace; report.py only formats it. The structured parts
(`narrative`, `charts`) are also what a page draws from, so they are plain JSON with stable field names.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics

from .defaults import param
from .windows import days

DAY = dt.timedelta(days=1)


def _ratio(ws, m):
    return ws.metrics[m].get("kind") == "ratio"


def leaf(s):
    return next((x for x in s["slots"] if x.get("leaf", True)), None)


def slot_filters(slot):
    f = dict(slot["filters"])
    f.update({d: v for d, v in slot["path"]})
    f[slot["dimension"]] = slot["value"]
    return f


def parent_filters(slot):
    f = dict(slot["filters"])
    f.update({d: v for d, v in slot["path"]})
    return f


# ---------- the rest of the total, against its usual growth ----------

def _part(ws, m, w, scope, top):
    """(value of the scope without the top group, value of the top group) in window w."""
    if _ratio(ws, m):
        mm = ws.metrics[m]
        n_all, d_all = ws.total(mm["numerator"], w, scope), ws.total(mm["denominator"], w, scope)
        n_top, d_top = ws.total(mm["numerator"], w, top), ws.total(mm["denominator"], w, top)
        rest = (n_all - n_top) / (d_all - d_top) if d_all - d_top else None
        return rest, (n_top / d_top if d_top else None)
    t = ws.total(m, w, top)
    return ws.total(m, w, scope) - t, t


def _change(ws, m, b, c):
    if b is None or c is None:
        return None
    if _ratio(ws, m):
        return c - b
    return c / b - 1 if b else None


def rest_of_total(ws, s, slot):
    """Without the main group, how much did the rest change, and is that normal for it?"""
    m = s["metric"]
    scope, top = parent_filters(slot), slot_filters(slot)
    rb, tb = _part(ws, m, s["base"], scope, top)
    rc, tc = _part(ws, m, s["current"], scope, top)
    hist = []
    for w, b in s.get("history_pairs") or []:
        try:
            pb, _ = _part(ws, m, b, scope, top)
            pc, _ = _part(ws, m, w, scope, top)
            g = _change(ws, m, pb, pc)
            if g is not None and math.isfinite(g):
                hist.append(g)
        except (ValueError, ZeroDivisionError):
            continue
    usual = statistics.median(hist) if len(hist) >= 3 else None
    scale = 1.4826 * statistics.median(abs(x - usual) for x in hist) if usual is not None else None
    rc_ = _change(ws, m, rb, rc)
    verdict = None
    if usual is not None and scale and rc_ is not None:
        # same bar a group's own change has to clear to count (segment_z_min_when_unusual)
        z = (rc_ - usual) / scale
        lim = param(ws, "segment_z_min_when_unusual")
        verdict = "as_usual" if abs(z) < lim else "better" if z > 0 else "worse"
    return {"scope": scope, "rest_base": rb, "rest_cur": rc, "rest_change": rc_, "rest_verdict": verdict,
            "rest_usual_change": usual, "rest_usual_scale": scale, "rest_history_n": len(hist),
            "top_base": tb, "top_cur": tc, "top_change": _change(ws, m, tb, tc),
            "kind": "rate_difference" if _ratio(ws, m) else "growth"}


# ---------- when it started ----------

def _series_value(ws, s, slot, day):
    """One day's value of what moved in the slot: an amount for amounts; for a ratio slot led by mix, the group's
    weight in its parent; led by rate, the group's own rate."""
    m = s["metric"]
    w = (day, day)
    if not _ratio(ws, m):
        return ws.total(m, w, slot_filters(slot))
    mm = ws.metrics[m]
    if slot.get("dominant_term") == "structure":
        d_all = ws.total(mm["denominator"], w, parent_filters(slot))
        return ws.total(mm["denominator"], w, slot_filters(slot)) / d_all if d_all else None
    v = ws.total(m, w, slot_filters(slot))
    return v if math.isfinite(v) else None


def onset(ws, s, slot, weeks=None):
    """The day the slot's year-on-year gap shifted, by a single mean-shift change point (least squares).

    Series: day by day, the slot's value minus its value on the paired base day, over the last `weeks` weeks up to
    the end of the current window. The split minimising the within-segment sum of squares is the maximum-likelihood
    single change point for a shift in mean under normal errors. Source: D. V. Hinkley (1970), "Inference about the
    change-point in a sequence of random variables", Biometrika 57(1); the binary-segmentation use of it in
    R. Killick, P. Fearnhead & I. A. Eckley (2012), JASA 107(500)."""
    weeks = weeks or int(param(ws, "onset_lookback_weeks"))
    shift = s["current"][0] - s["base"][0]
    end = s["current"][1]
    start = end - (7 * weeks - 1) * DAY
    xs, ds = [], []
    for day in days((start, end)):
        a, b = _series_value(ws, s, slot, day), _series_value(ws, s, slot, day - shift)
        if a is None or b is None:
            continue
        xs.append(a - b)
        ds.append(day)
    n = len(xs)
    if n < 14:
        return None
    best = None
    for k in range(7, n - 2):
        L, R = xs[:k], xs[k:]
        ml, mr = statistics.fmean(L), statistics.fmean(R)
        sse = math.fsum((x - ml) ** 2 for x in L) + math.fsum((x - mr) ** 2 for x in R)
        if best is None or sse < best[0]:
            best = (sse, k, ml, mr)
    _, k, ml, mr = best
    sd = math.sqrt(best[0] / max(n - 2, 1))
    size = (mr - ml) / sd if sd else None
    found = size is not None and abs(size) >= param(ws, "onset_min_shift_sd")
    out = {"method": "single_mean_shift_least_squares", "series": "slot_minus_paired_base_day",
           "lookback_days": n, "start": ds[k].isoformat() if found else None, "candidate": ds[k].isoformat(),
           "mean_before": ml, "mean_after": mr, "shift_in_sd": size, "found": found,
           "daily": [{"day": d.isoformat(), "gap": x} for d, x in zip(ds, xs)]}
    events = []
    for c in slot.get("citations", []):
        e = next((x for x in ws.world.get("events", []) if x["id"] == c["id"]), None)
        if e and e.get("start") and found:
            gap = (dt.date.fromisoformat(str(e["start"])) - ds[k]).days
            events.append({"event": e["id"], "event_start": str(e["start"]), "days_from_onset": gap})
    out["events"] = events
    return out


def _weight(ws, m, w, slot):
    mm = ws.metrics[m]
    d = ws.total(mm["denominator"], w, parent_filters(slot))
    return ws.total(mm["denominator"], w, slot_filters(slot)) / d if d else None


def recent_weeks(ws, s, slot, n=4):
    """Week by week for the last n weeks ending with the current window (same base rule): the whole number's change
    and the slot's. For a ratio slot led by mix, the slot's change is its weight's change (what moved), not its rate."""
    m = s["metric"]
    f = slot_filters(slot)
    shift = s["current"][0] - s["base"][0]
    mix = _ratio(ws, m) and slot.get("dominant_term") == "structure"
    out = []
    for i in range(n - 1, -1, -1):
        w = (s["current"][0] - 7 * i * DAY, s["current"][1] - 7 * i * DAY)
        b = (w[0] - shift, w[1] - shift)
        try:
            row = {"window": [w[0].isoformat(), w[1].isoformat()],
                   "whole_change": _change(ws, m, ws.total(m, b, s["filters"]), ws.total(m, w, s["filters"]))}
            if mix:
                wb, wc = _weight(ws, m, b, slot), _weight(ws, m, w, slot)
                row.update(measure="weight", base=wb, current=wc, change=(wc - wb) if wb is not None and wc is not None else None)
            else:
                row.update(measure="value", change=_change(ws, m, ws.total(m, b, f), ws.total(m, w, f)))
            out.append(row)
        except (ValueError, ZeroDivisionError):
            continue
    return out


# ---------- the whole story ----------

def _value_field(r):
    return {"additive": "delta", "divisive": "total"}.get(r["operator"], "total" if "sides" in r["operator"] else "change")


def _total_of(r):
    return r.get({"additive": "total_delta", "divisive": "rate_delta"}.get(r["operator"],
                 "gap" if "sides" in r["operator"] else "growth_change"))


def build(ws, s) -> dict:
    out = {"main": None, "secondary": None, "offsets": [], "ruled_out": [], "rest": None, "onset": None,
           "recent_weeks": [], "estimate_notes": []}
    q = s["qualify"]
    if q.get("own_part_usual") is not None:
        out["market"] = {"plain_own_part": q.get("own_part"), "usual_gap": q["usual_gap"], "expected_growth": q["expected_growth"],
                         "expected_part": q["expected_part"], "own_part": q["own_part_usual"], "is_estimate": True}
        out["estimate_notes"].append("market_usual_gap")
    first = next((c for c in s["cuts"] if c.get("role") in ("layer", "each", None)), None)
    if first:
        r = first["result"]
        vf, tot = _value_field(r), _total_of(r)
        segs = sorted(r["segments"], key=lambda x: abs(x[vf]), reverse=True)
        sign = 1 if (tot or 0) >= 0 else -1
        same = [x for x in segs if x[vf] * sign > 0]
        out["offsets"] = [{"dimension": first["dimension"], "key": x["key"], "value": x[vf]} for x in segs
                          if x[vf] * sign < 0 and abs(x[vf]) > 0.05 * abs(tot or 1)][:3]
        if len(same) > 1 and abs(same[1][vf]) >= 0.1 * abs(tot or 1):
            out["secondary"] = {"dimension": first["dimension"], "key": same[1]["key"], "value": same[1][vf]}
    sl = leaf(s)
    if sl:
        cut = s["cuts"][sl["cut"]]
        row = next((x for x in cut["result"]["segments"] if x["key"] == sl["value"]), {})
        vf = _value_field(cut["result"])
        out["main"] = {"slot": sl["id"], "dimension": sl["dimension"], "key": sl["value"], "path": sl["path"],
                       "value": row.get(vf), "term": sl.get("dominant_term"), "status": sl["status"]}
        if s["order"] == "first":
            out["rest"] = rest_of_total(ws, s, sl)
            out["onset"] = onset(ws, s, sl)
            out["recent_weeks"] = recent_weeks(ws, s, sl)
        for c in sl["citations"]:
            if c.get("explains") and c["explains"] != "change":
                out["ruled_out"].append({"kind": "record_cannot_explain", "id": c["id"], "why": c["explains"]})
            elif c.get("external") and c["checks"]["status"] != "supported":
                out["ruled_out"].append({"kind": "outside_event_not_proven", "id": c["id"], "why": c["checks"]["status"]})
    if out.get("market") and out["market"]["own_part"] is not None:
        d = q["total_cur"] - q["total_base"]
        if d and abs(out["market"]["expected_part"]) < abs(d):
            out["ruled_out"].append({"kind": "market", "why": "market_explains_little", "expected_part": out["market"]["expected_part"]})
    for c in s["cuts"]:
        if c.get("role") == "layer" and c["decision"]["then"].get("action") == "stop" and c is not first:
            out["ruled_out"].append({"kind": "cut_spread", "dimension": c["dimension"], "filters": c["filters"],
                                     "why": c["decision"]["then"].get("reason")})
    if first and first["decision"]["then"].get("action") == "stop":
        out["ruled_out"].append({"kind": "cut_spread", "dimension": first["dimension"], "filters": first["filters"],
                                 "why": first["decision"]["then"].get("reason")})
    return out


def charts(ws, s) -> dict:
    """Data for the waterfall (base -> contributions -> current) and the two periods' daily series."""
    out = {}
    m, q = s["metric"], s["qualify"]
    first = next((c for c in s["cuts"] if c.get("role") in ("layer", "each", None)
                  and c["result"]["operator"] in ("additive", "divisive")), None)
    if first:
        r = first["result"]
        vf = _value_field(r)
        segs = sorted(r["segments"], key=lambda x: abs(x[vf]), reverse=True)
        top, rest = segs[:4], segs[4:]
        steps = [{"label_key": x["key"], "dimension": first["dimension"], "value": x[vf]} for x in top]
        if rest:
            steps.append({"label_key": None, "dimension": first["dimension"], "value": math.fsum(x[vf] for x in rest), "others": len(rest)})
        base = r["total_base"] if r["operator"] == "additive" else r["rate_base"]
        cur = r["total_cur"] if r["operator"] == "additive" else r["rate_cur"]
        out["waterfall"] = {"unit": ws.metrics[m].get("unit"), "dimension": first["dimension"], "filters": first["filters"],
                            "base": base, "steps": steps, "current": cur,
                            "base_window": [str(x) for x in s["base"]], "current_window": [str(x) for x in s["current"]]}
    cd, bd = days(s["current"]), days(s["base"])
    if len(cd) == len(bd) and len(cd) <= 92:
        def val(d):
            v = ws.total(m, (d, d), s["filters"])
            return v if math.isfinite(v) else None
        out["daily"] = {"unit": ws.metrics[m].get("unit"),
                        "current": [{"day": d.isoformat(), "value": val(d)} for d in cd],
                        "base": [{"day": d.isoformat(), "value": val(d)} for d in bd],
                        "excluded_days": sorted(s.get("excluded_days") or [])}
    out["range"] = {"current_change": q.get("current_change"), "usual_range": q.get("usual_range"),
                    "unusual_below": q.get("unusual_below"), "unusual_above": q.get("unusual_above"),
                    "history": q.get("history", [])}
    return out
