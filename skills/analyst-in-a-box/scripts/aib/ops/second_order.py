"""Second-order decompositions: compare two first-order results.

1) Across two time windows ("why is growth this window different from last window?")
   Each segment's contribution to growth in window k is c_s,k = (y_s,1 - y_s,0) / Y_0 (window k).
   Contributions sum exactly to the window's growth, so the change in growth splits exactly into
   the change of each segment's contribution: dg = sum_s (c_s,2 - c_s,1).
   Source: contributions to percent change, U.S. Bureau of Economic Analysis (NIPA methodology).

2) Across the two sides of a dimension ("why did side A grow faster than side B?")
   On each side, growth g = sum_s w_s * g_s with w_s = base weight of segment s on that side.
   The gap g_A - g_B splits exactly (for segments present on both sides) into
     mix          = sum_s (w_s,A - w_s,B) * (g_s,A + g_s,B) / 2    the sides sell a different mix
     performance  = sum_s (g_s,A - g_s,B) * (w_s,A + w_s,B) / 2    the same segment grew differently
   plus an "unmatched" term for segments with no base on one side.
   Source: E. M. Kitagawa (1955), symmetric form; the mix / competitive split is the core of
   shift-share analysis (E. S. Dunn, 1960, "A statistical and analytical technique for regional analysis").
"""

from __future__ import annotations

import math

from .common import closure_gap, is_closed, key_str, safe_div, share, top_fields

OUTPUT_FIELDS_TIME = ("growth_w1", "growth_w2", "growth_change", "top1_key", "top1_share",
                      "top1_abs_share", "top2_cum_abs_share", "closure_gap", "closed")
OUTPUT_FIELDS_SIDES = (
    "top1_key", "top1_abs_share", "top2_cum_abs_share",
    "growth_a", "growth_b", "gap", "mix_total", "performance_total", "unmatched_total",
    "mix_share", "performance_share", "larger_effect", "closure_gap", "closed",
)


def _contributions(segments: dict) -> tuple[float, dict]:
    base_total = math.fsum(float(b or 0) for b, _ in segments.values())
    if base_total == 0:
        raise ValueError("base total is zero; growth is undefined")
    return base_total, {key_str(k): (float(c or 0) - float(b or 0)) / base_total for k, (b, c) in segments.items()}


def across_time(window1: dict, window2: dict, label: str = "") -> dict:
    """window1, window2: {key: (base_value, current_value)} for the earlier and later window."""
    _, c1 = _contributions(window1)
    _, c2 = _contributions(window2)
    g1, g2 = math.fsum(c1.values()), math.fsum(c2.values())
    dg = g2 - g1
    rows = []
    for k in sorted(set(c1) | set(c2)):
        a, b = c1.get(k, 0.0), c2.get(k, 0.0)
        rows.append({"key": k, "contrib_w1": a, "contrib_w2": b, "change": b - a, "share": share(b - a, dg)})
    rows.sort(key=lambda r: abs(r["change"]), reverse=True)
    return {
        **top_fields(rows, "change"),
        "operator": "second_order_time",
        "label": label,
        "growth_w1": g1,
        "growth_w2": g2,
        "growth_change": dg,
        "segments": rows,
        "top1_key": rows[0]["key"] if rows else None,
        "top1_share": rows[0]["share"] if rows else None,
        "closure_gap": closure_gap(dg, (r["change"] for r in rows)),
        "closed": is_closed(dg, (r["change"] for r in rows)),
    }


def across_time_rate(window1: dict, window2: dict, label: str = "", mode: str = "three_term") -> dict:
    """Ratio metric across two windows: run the rate decomposition in each window and subtract term by term.
    window1, window2: {key: (num_base, den_base, num_cur, den_cur)}. Exact because each window is exact."""
    from . import divisive
    d1 = divisive.decompose(window1, mode=mode)
    d2 = divisive.decompose(window2, mode=mode)
    t1 = {s["key"]: s for s in d1["segments"]}
    t2 = {s["key"]: s for s in d2["segments"]}
    dg = d2["rate_delta"] - d1["rate_delta"]
    rows = []
    for k in sorted(set(t1) | set(t2)):
        a, b = t1.get(k, {}), t2.get(k, {})
        row = {"key": k}
        for term in ("structure", "rate", "interaction", "total"):
            row[term] = b.get(term, 0.0) - a.get(term, 0.0)
        row["change"] = row["total"]
        row["share"] = share(row["total"], dg)
        rows.append(row)
    rows.sort(key=lambda r: abs(r["change"]), reverse=True)
    return {
        **top_fields(rows, "change"),
        "operator": "second_order_time",
        "label": label,
        "growth_w1": d1["rate_delta"],
        "growth_w2": d2["rate_delta"],
        "growth_change": dg,
        "structure_change": d2["structure_total"] - d1["structure_total"],
        "rate_change": d2["rate_total"] - d1["rate_total"],
        "segments": rows,
        "top1_share": rows[0]["share"] if rows else None,
        "closure_gap": closure_gap(dg, (r["change"] for r in rows)),
        "closed": is_closed(dg, (r["change"] for r in rows)),
    }


def across_sides(side_a: dict, side_b: dict, label: str = "", names: tuple = ("A", "B")) -> dict:
    """side_a, side_b: {segment_key: (base_value, current_value)} for each side of the dimension."""
    ta, ca = _contributions(side_a)
    tb, cb = _contributions(side_b)
    ga, gb = math.fsum(ca.values()), math.fsum(cb.values())
    gap = ga - gb
    a = {key_str(k): (float(b or 0), float(c or 0)) for k, (b, c) in side_a.items()}
    b = {key_str(k): (float(x or 0), float(y or 0)) for k, (x, y) in side_b.items()}
    rows, mix, perf, unmatched = [], 0.0, 0.0, 0.0
    for k in sorted(set(a) | set(b)):
        a0, a1 = a.get(k, (0.0, 0.0))
        b0, b1 = b.get(k, (0.0, 0.0))
        diff = ca.get(k, 0.0) - cb.get(k, 0.0)
        if a0 > 0 and b0 > 0:
            wa, wb = a0 / ta, b0 / tb
            gsa, gsb = (a1 - a0) / a0, (b1 - b0) / b0
            m = (wa - wb) * (gsa + gsb) / 2
            p = (gsa - gsb) * (wa + wb) / 2
            u = 0.0
        else:
            wa, wb, gsa, gsb = a0 / ta, b0 / tb, safe_div(a1 - a0, a0), safe_div(b1 - b0, b0)
            m, p, u = 0.0, 0.0, diff
        mix += m
        perf += p
        unmatched += u
        rows.append({"key": k, "weight_a": wa, "weight_b": wb, "growth_a": gsa, "growth_b": gsb,
                     "mix": m, "performance": p, "unmatched": u, "total": m + p + u, "share": share(m + p + u, gap)})
    rows.sort(key=lambda r: abs(r["total"]), reverse=True)
    larger = "mix" if abs(mix) > abs(perf) else "performance" if abs(perf) > abs(mix) else "tie"
    terms = [mix, perf, unmatched]
    return {
        **top_fields(rows, "total"),
        "operator": "second_order_sides",
        "label": label,
        "sides": list(names),
        "growth_a": ga,
        "growth_b": gb,
        "gap": gap,
        "segments": rows,
        "mix_total": mix,
        "performance_total": perf,
        "unmatched_total": unmatched,
        "mix_share": share(mix, gap),
        "performance_share": share(perf, gap),
        "larger_effect": larger,
        "closure_gap": closure_gap(gap, terms),
        "closed": is_closed(gap, terms),
    }
