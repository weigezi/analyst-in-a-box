"""Where to cut next, and whether what a cut shows is a cause or noise.

Noise gate. A cut's top group counts as a single point only if
  - it carries clearly more of the movement than an even split would (excess over 1/n, below), and
  - its own change is far from its own history (robust z of the group's contribution over the same past pairs
    the whole number was judged against), and it is not tiny.
With two groups the top one always carries at least half of the movement; measuring the excess over 1/n
removes that bias, so a two-value dimension in a quiet week does not read as a single point.

Choosing the dimension. Each candidate dimension is scored by explanatory power x surprise, after Adtributor:
  explanatory power  the top group's share of all movement, as an excess over an even split
  surprise           Jensen-Shannon divergence between the groups' shares in the base and in the current period
                     (for a ratio, the numerator's and the denominator's shares, added)
Source: R. Bhagwan et al. (2014), "Adtributor: Revenue Debugging in Advertising Systems", USENIX NSDI '14,
https://www.usenix.org/conference/nsdi14/technical-sessions/presentation/bhagwan
Adtributor ranks with surprise and keeps elements until they explain 2/3 of the change; here only the top group
is drilled, so its excess share stands in for explanatory power.
"""

from __future__ import annotations

import math

from . import qualify, windows
from .defaults import param
from .ops import additive, divisive, shrink
from .ops.common import top_fields


def excess(share, n):
    """How far the top group's share is above an even split: 0 = even, 1 = it carries everything."""
    if share is None or not n or n < 2:
        return None
    return (share - 1 / n) / (1 - 1 / n)


def excess_over(share, expected):
    """excess() with the expected share given: a group with 70% of the base carrying 70% of the change scores 0."""
    if share is None or expected is None or expected >= 1:
        return None
    return (share - expected) / (1 - expected)


def js(p, q) -> float:
    """Jensen-Shannon divergence with log base 2 (0 = same distribution, 1 = no overlap)."""
    sp, sq = math.fsum(p), math.fsum(q)
    if sp <= 0 or sq <= 0:
        return 0.0
    p = [x / sp for x in p]
    q = [x / sq for x in q]
    out = 0.0
    for a, b in zip(p, q):
        m = (a + b) / 2
        if a > 0:
            out += 0.5 * a * math.log2(a / m)
        if b > 0:
            out += 0.5 * b * math.log2(b / m)
    return max(out, 0.0)


def is_ratio(ws, metric):
    return ws.metrics[metric].get("kind") == "ratio"


def op_for(ws, metric):
    return divisive if is_ratio(ws, metric) else additive


def value_field(ws, metric):
    return "total" if is_ratio(ws, metric) else "delta"


def surprise(ws, metric, seg: dict) -> float:
    keys = list(seg)
    if is_ratio(ws, metric):
        return js([abs(seg[k][0]) for k in keys], [abs(seg[k][2]) for k in keys]) + \
            js([abs(seg[k][1]) for k in keys], [abs(seg[k][3]) for k in keys])
    return js([abs(seg[k][0]) for k in keys], [abs(seg[k][1]) for k in keys])


def decompose(ws, metric, dim, base, cur, filters):
    seg = ws.segments(metric, dim, base, cur, filters)
    return seg, op_for(ws, metric).decompose(seg, label=dim)


def candidate(ws, metric, dim, base, cur, filters) -> dict:
    """Score one dimension without the history work (that is done only for the dimension chosen)."""
    try:
        seg, res = decompose(ws, metric, dim, base, cur, filters)
    except ValueError as exc:
        return {"dimension": dim, "error": str(exc), "score": -1.0}
    n = len(res["segments"])
    ep = excess(res["top1_abs_share"], n)
    sp = surprise(ws, metric, seg)
    return {"dimension": dim, "top1_key": res["top1_key"], "n_groups": n, "top1_abs_share": res["top1_abs_share"],
            "explanatory_power": ep, "surprise": sp, "score": (ep or 0.0) * sp, "_seg": seg, "_res": res}


def public(c: dict) -> dict:
    return {k: v for k, v in c.items() if not k.startswith("_")}


# ---------- noise: each group against its own history ----------

def segment_history(ws, metric, dim, filters, pairs) -> dict:
    vf = value_field(ws, metric)
    out: dict = {}
    for w, b in pairs:
        try:
            _, r = decompose(ws, metric, dim, b, w, filters)
        except ValueError:
            continue
        for x in r["segments"]:
            out.setdefault(x["key"], []).append(x[vf])
    return out


def sizes(ws, metric, dim, cur, filters, res) -> tuple:
    """({group: size}, unit) in the current period: how many of the counted things (orders, or rows when nothing is
    counted) sit behind each group. For a ratio it is the size behind its denominator measure, so an amount
    denominator (margin = profit / revenue) is never mistaken for a count."""
    m = ws.metrics[metric]
    if is_ratio(ws, metric):
        den = ws.metrics[m["denominator"]]
        if "measure" not in den:
            return {x["key"]: x["den_cur"] for x in res["segments"]}, "denominator"
        name = den["measure"]
    else:
        name = m["measure"]
    s, unit = ws.group_size(name, cur, [dim], filters)
    return {str(k): float(v) for k, v in s.items()}, unit


def residuals(r: dict) -> dict:
    """An additive group's change beyond growing like all the other groups together:
    delta_s - base_s * (delta of the rest / base of the rest).
    Zero when every group moved by the same percentage, so a uniform drop is not a single point; and a shock in
    one group cannot hide itself by moving the yardstick it is compared with (leave-one-out)."""
    tb, td = r.get("total_base") or 0.0, r.get("total_delta") or 0.0
    out = {}
    for x in r["segments"]:
        rb, rd = tb - x["base"], td - x["delta"]
        g = rd / rb if rb else (td / tb if tb else 0.0)
        out[x["key"]] = x["delta"] - x["base"] * g
    return out


def segment_history(ws, metric, dim, filters, pairs) -> dict:
    """Past values of what the gate tests: residual change for an amount, contribution for a ratio."""
    out: dict = {}
    for w, b in pairs:
        try:
            _, r = decompose(ws, metric, dim, b, w, filters)
        except ValueError:
            continue
        vals = residuals(r) if not is_ratio(ws, metric) else {x["key"]: x["total"] for x in r["segments"]}
        for k, v in vals.items():
            out.setdefault(k, []).append(v)
    return out


SCAN_RUNS = (2, 3, 4)


def _daily_groups(ws, metric, dim, w, filters):
    """Day-by-day group values of an additive metric over a window, oldest first: [{group: value}]."""
    import pandas as pd
    name = ws.metrics[metric]["measure"]
    if not ws._additive_by_day(name):
        return None
    cols = [ws.column(name, dim)]
    fcols = {ws.column(name, k): v for k, v in (filters or {}).items()}
    f = ws._daily_frame(name, cols, fcols)
    out = []
    for i in range((w[1] - w[0]).days + 1):
        day = pd.Timestamp(w[0]) + pd.Timedelta(days=i)
        row = f.loc[day] if day in f.index else None
        out.append({str(k): (0.0 if row is None or pd.isna(row[k]) else float(row[k])) for k in f.columns})
    return out


def p_for_z(z: float) -> float:
    """Two-sided normal tail probability of a z score."""
    return math.erfc(abs(z) / math.sqrt(2))


def z_for_p(p: float, sign: float) -> float:
    """Inverse of p_for_z, with the sign of `sign`; bisection keeps it free of extra dependencies."""
    lo, hi = 0.0, 40.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if p_for_z(mid) > p else (lo, mid)
    return math.copysign((lo + hi) / 2, sign)


def scan(ws, metric, dim, w, b, filters) -> dict | None:
    """Strongest run of consecutive days in each group's residual change (leave-one-out, as residuals()).

    A three-day event inside a seven-day window is diluted by four ordinary days in a weekly test; scoring the
    strongest run of 2 to 4 days recovers it. The same statistic is computed on every past pair, so the max over
    runs is judged against maxima, not against single days. Sources: J. I. Naus (1965), "The distribution of the
    size of the maximum cluster of points on a line", JASA 60(310); M. Kulldorff (1997), "A spatial scan statistic",
    Communications in Statistics - Theory and Methods 26(6)."""
    cd, bd = _daily_groups(ws, metric, dim, w, filters), _daily_groups(ws, metric, dim, b, filters)
    if cd is None or bd is None or len(cd) != len(bd) or len(cd) < max(SCAN_RUNS) + 1:
        return None
    keys = sorted(set().union(*cd, *bd))
    tb = {k: math.fsum(x.get(k, 0.0) for x in bd) for k in keys}
    td = {k: math.fsum(x.get(k, 0.0) for x in cd) - tb[k] for k in keys}
    B, Dt = math.fsum(tb.values()), math.fsum(td.values())
    keep = [i for i, day in enumerate(windows.days(w)) if day not in ws.exclude_days]
    out = {}
    for k in keys:
        rb, rd = B - tb[k], Dt - td[k]
        g = rd / rb if rb else 0.0
        r = [cd[i].get(k, 0.0) - bd[i].get(k, 0.0) - bd[i].get(k, 0.0) * g for i in keep]
        best = 0.0
        for n in SCAN_RUNS:
            for i in range(len(r) - n + 1):
                v = math.fsum(r[i:i + n])
                if abs(v) > abs(best):
                    best = v
        out[k] = best
    return out


def annotate(ws, metric, dim, base, cur, filters, res, pairs) -> None:
    """Add z (against the group's own history), n and, for amounts, the residual change to every row, in place."""
    vf = value_field(ws, metric)
    hist = segment_history(ws, metric, dim, filters, pairs) if pairs else {}
    n, unit = sizes(ws, metric, dim, cur, filters, res)
    res_now = residuals(res) if not is_ratio(ws, metric) else None
    if res_now is not None:
        tb = res.get("total_base")
        for x in res["segments"]:
            x["residual"] = res_now[x["key"]]
            x["base_share"] = x["base"] / tb if tb else None
    now_scan = scan(ws, metric, dim, cur, base, filters) if res_now is not None else None
    hist_scan: dict = {}
    if now_scan is not None:
        for w, b in pairs:
            sc = scan(ws, metric, dim, w, b, filters)
            for k, v in (sc or {}).items():
                hist_scan.setdefault(k, []).append(v)
    for x in res["segments"]:
        q = qualify.unusualness(hist.get(x["key"], []), x["residual"] if res_now is not None else x[vf])
        x["z_week"], x["z_method"], x["history_n"] = q["robust_z"], q["z_method"], q["history_n"]
        x["z"] = x["z_week"]
        x["n"], x["n_unit"] = n.get(x["key"], 0.0), unit
        if now_scan is not None and x["key"] in now_scan:
            qs = qualify.unusualness(hist_scan.get(x["key"], []), now_scan[x["key"]])
            x["z_run"], x["run_change"] = qs["robust_z"], now_scan[x["key"]]
            if qs["robust_z"] is not None:
                # The weekly test stays the primary evidence, unchanged. The run-of-days test is a second look, so
                # it only replaces the weekly z when it is stronger even after a two-test (Bonferroni) correction.
                # Measured on ten pure-noise shops x 30 weeks: revenue drilled into 17/300 weeks without the
                # correction, 15/300 with it. Correcting the weekly test too gave 10/300 but lost a real cause
                # (one channel in one region losing 80% of orders, weekly z -2.19 -> -1.90), so it was not used.
                # Sources: C. E. Bonferroni (1936); O. J. Dunn (1961), "Multiple comparisons among means", JASA 56(293).
                zr = z_for_p(min(1.0, 2 * p_for_z(qs["robust_z"])), qs["robust_z"])
                x["z_run_corrected"] = zr
                if x["z"] is None or abs(zr) > abs(x["z"]):
                    x["z"], x["z_from"] = zr, "run_of_days"


# ---------- small groups in a ratio ----------

def _kind(ws, metric):
    m = ws.metrics[metric]
    num, den = ws.metrics[m["numerator"]], ws.metrics[m["denominator"]]
    if "measure" not in num or "measure" not in den:
        return None
    mn, md = ws.measures[num["measure"]], ws.measures[den["measure"]]
    if mn["agg"] in ("count", "count_distinct"):
        return "proportion", mn, md
    if mn["agg"] == "sum" and md["agg"] in ("count", "count_distinct") and mn["source"] == md["source"]:
        return "mean", mn, md
    return None


def _row_variance(ws, mn, w, filters, dim):
    """Pooled within-group variance of one row's numerator: the sampling noise of a mean over d rows is this / d."""
    import pandas as pd
    df = ws.sources.frame(mn["source"])
    d = df[(df[mn["date"]] >= pd.Timestamp(w[0])) & (df[mn["date"]] <= pd.Timestamp(w[1]))]
    for k, v in (filters or {}).items():
        col = (mn.get("columns") or {}).get(k) or ws.dimensions[k].get("column", k)
        d = d[d[col].isin(v if isinstance(v, (list, tuple, set)) else [v])]
    col = (mn.get("columns") or {}).get(dim) or ws.dimensions[dim].get("column", dim)
    g = d.groupby(col)[mn["column"]]
    var, cnt = g.var(ddof=1).fillna(0.0), g.size()
    dof = (cnt - 1).clip(lower=0)
    return float((var * dof).sum() / dof.sum()) if dof.sum() > 0 else 0.0


def shrink_ranking(ws, metric, dim, base, cur, filters, res) -> bool:
    """Re-rank a ratio cut by shrunk contributions. The exact numbers stay; 'total_shrunk' is added per row."""
    k = _kind(ws, metric)
    if k is None:
        return False
    kind, mn, _ = k
    rows = res["segments"]

    def var(period, w):
        if kind == "proportion":
            R = res["rate_base"] if period == "base" else res["rate_cur"]
            return [R * (1 - R) / x[f"den_{period}"] if x[f"den_{period}"] else float("inf") for x in rows]
        pooled = _row_variance(ws, mn, w, filters, dim)
        return [pooled / x[f"den_{period}"] if x[f"den_{period}"] else float("inf") for x in rows]

    tots = shrink.shrunk_totals(rows, res["rate_base"], var("base", base), var("cur", cur))
    for x, t in zip(rows, tots):
        x["total_shrunk"] = t
    rows.sort(key=lambda x: abs(x["total_shrunk"]), reverse=True)
    exact = top_fields(rows, "total")
    res["top1_key"], res["top1_abs_share"], res["top2_cum_abs_share"] = rows[0]["key"], exact["top1_abs_share"], exact["top2_cum_abs_share"]
    res["ranked_by"] = "shrunk_rates"
    return True


# ---------- the gate ----------

def overall_quiet(ws, s, order="first", layer=0) -> bool:
    """The whole number is within its usual range and was judged (there is a z-score): nothing moved."""
    verdict = ((s.get("verdict_unusual") or {}).get("then") or {}).get("verdict")
    drill_usual = s["config"].get("drill_when_usual", param(ws, "drill_when_usual"))
    # With no z-score (history too short or flat) the table's last row still says "within_usual_range"; that is the
    # absence of a verdict, not a finding, so it must not stop the search or be reported as a reason.
    judged = (s.get("qualify") or {}).get("robust_z") is not None
    return order == "first" and verdict == "within_usual_range" and judged and not drill_usual and layer == 0


def gate(ws, s, res, order="first", layer=0) -> dict:
    """Inputs of the stop.cut table. layer > 0 means a parent group was already drilled into, so the question
    is 'where inside it', and the context counts as unusual."""
    segs = res.get("segments") or []
    top = next((x for x in segs if x["key"] == res.get("top1_key")), {}) if segs else {}
    z = top.get("z")
    verdict = ((s.get("verdict_unusual") or {}).get("then") or {}).get("verdict")
    drill_usual = s["config"].get("drill_when_usual", param(ws, "drill_when_usual"))
    quiet = overall_quiet(ws, s, order, layer)
    # A group far outside its own history may override a quiet total: the total's noise is the sum of every group's,
    # so one group's real change can hide inside it (a level shift that started weeks ago, for instance).
    beats_quiet = bool(param(ws, "drill_quiet_total_when_group_stands_out")) and z is not None \
        and abs(z) >= param(ws, "group_stands_out_z")
    unusual = order == "first" and (layer > 0 or verdict in ("unusual_low", "unusual_high") or bool(drill_usual))
    if top.get("residual") is not None:
        # amounts: the share of all movement this group carries beyond moving in step with the other groups
        # (0 when every group moved by the same percentage, close to 1 when it alone moved)
        tot = math.fsum(abs(x["delta"]) for x in segs)
        ex = min(abs(top["residual"]) / tot, 1.0) if tot else None
    elif top.get("weight_base") is not None:
        # ratios: when nothing moved but noise, a group's share of the movement is about its weight, so compare
        # with the group's base weight (as amounts compare with their base share), not with an even split
        ex = excess_over(res.get("top1_abs_share"), top["weight_base"])
    else:
        ex = excess(res.get("top1_abs_share"), len(segs))
    return {"overall_quiet": quiet, "top1_beats_quiet": beats_quiet, "context_unusual": unusual, "layer": layer,
            "n_groups": len(segs), "top1_abs_share": res.get("top1_abs_share"),
            "top1_excess": ex,
            "top1_abs_z": abs(z) if z is not None else None, "top1_z": z, "top1_n": top.get("n"),
            "size_unit": top.get("n_unit"),
            "has_history": z is not None, "order": order}
