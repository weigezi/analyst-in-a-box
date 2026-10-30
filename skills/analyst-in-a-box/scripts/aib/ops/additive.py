"""Additive decomposition: split the change of a summable metric across the values of a dimension.

Method: for a metric Y = sum_s y_s, the change dY = sum_s (y_s,1 - y_s,0) exactly.
Each segment's contribution is its own change; its share is that change divided by dY.
This is the textbook "contribution to change" used for additive aggregates, e.g. the
contributions-to-percent-change tables published by national statistics offices
(U.S. Bureau of Economic Analysis, NIPA methodology).
"""

from __future__ import annotations

import math

from .common import closure_gap, is_closed, key_str, safe_div, share

OUTPUT_FIELDS = (
    "total_base", "total_cur", "total_delta", "total_growth",
    "top1_key", "top1_share", "top1_abs_share", "top2_cum_abs_share",
    "same_direction_share", "n_segments", "closure_gap", "closed",
)


def decompose(segments: dict, label: str = "") -> dict:
    """segments: {key: (base_value, current_value)}. Returns a JSON-friendly dict."""
    rows = []
    for key, (b, c) in segments.items():
        b = float(b or 0.0)
        c = float(c or 0.0)
        rows.append({"key": key_str(key), "base": b, "cur": c, "delta": c - b})

    total_base = math.fsum(r["base"] for r in rows)
    total_cur = math.fsum(r["cur"] for r in rows)
    total_delta = total_cur - total_base
    abs_sum = math.fsum(abs(r["delta"]) for r in rows)

    for r in rows:
        r["share"] = share(r["delta"], total_delta)
        r["abs_share"] = safe_div(abs(r["delta"]), abs_sum)
        r["growth"] = safe_div(r["delta"], r["base"])
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)

    direction = 1 if total_delta > 0 else -1 if total_delta < 0 else 0
    same_dir = math.fsum(abs(r["delta"]) for r in rows if direction and r["delta"] * direction > 0)

    top1 = rows[0] if rows else None
    top2_abs = math.fsum(r["abs_share"] or 0.0 for r in rows[:2])
    return {
        "operator": "additive",
        "label": label,
        "total_base": total_base,
        "total_cur": total_cur,
        "total_delta": total_delta,
        "total_growth": safe_div(total_delta, total_base),
        "segments": rows,
        "top1_key": top1["key"] if top1 else None,
        "top1_share": top1["share"] if top1 else None,
        "top1_abs_share": top1["abs_share"] if top1 else None,
        "top2_cum_abs_share": top2_abs if rows else None,
        "same_direction_share": safe_div(same_dir, abs_sum),
        "n_segments": len(rows),
        "closure_gap": closure_gap(total_delta, (r["delta"] for r in rows)),
        "closed": is_closed(total_delta, (r["delta"] for r in rows)),
    }
