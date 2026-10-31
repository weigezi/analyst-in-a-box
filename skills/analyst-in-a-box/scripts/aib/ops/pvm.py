"""Price-volume-mix: split a revenue change into selling more, selling a different mix, and charging differently.

For items i with quantity q and value v (price p = v / q), base 0 and current 1, Q = sum of q, s_i = q_i / Q:
  volume  = sum_i (Q1 - Q0) * s_i,0 * p_i,0          everything scaled up or down, mix and prices as in the base
  mix     = sum_i Q1 * (s_i,1 - s_i,0) * p_i,0       the same total quantity spread differently across items
  price   = sum_i q_i,1 * (p_i,1 - p_i,0)            what each item charged differently
Items sold in both periods satisfy volume_i + mix_i + price_i = v_i,1 - v_i,0 exactly (volume_i + mix_i =
(q_i,1 - q_i,0) p_i,0). Items sold in one period only have no price there: their whole value is counted as
'new' or 'gone', and they are left out of the shares, which keeps the split exact.
Source: the sales-volume / sales-mix / price variance analysis of management accounting, e.g. C. T. Horngren,
S. M. Datar & M. V. Rajan, "Cost Accounting: A Managerial Emphasis" (Pearson), chapter on flexible budgets and
sales variances; applied there to contribution margin, here to revenue (price in place of unit margin).
"""

from __future__ import annotations

import math

from .common import closure_gap, is_closed, key_str, safe_div, share

OUTPUT_FIELDS = ("delta", "volume_total", "mix_total", "price_total", "new_total", "gone_total",
                 "larger_effect", "closure_gap", "closed")


def decompose(segments: dict, label: str = "") -> dict:
    """segments: {item: (qty_base, value_base, qty_cur, value_cur)}."""
    rows = [{"key": key_str(k), "q0": float(a or 0), "v0": float(b or 0), "q1": float(c or 0), "v1": float(d or 0)}
            for k, (a, b, c, d) in segments.items()]
    both = [r for r in rows if r["q0"] > 0 and r["q1"] > 0]
    Q0 = math.fsum(r["q0"] for r in both)
    Q1 = math.fsum(r["q1"] for r in both)
    for r in rows:
        r.update(volume=0.0, mix=0.0, price=0.0, new=0.0, gone=0.0)
        if r in both:
            p0, p1 = r["v0"] / r["q0"], r["v1"] / r["q1"]
            s0, s1 = r["q0"] / Q0, r["q1"] / Q1
            r.update(price_base=p0, price_cur=p1, share_base=s0, share_cur=s1,
                     volume=(Q1 - Q0) * s0 * p0, mix=Q1 * (s1 - s0) * p0, price=r["q1"] * (p1 - p0))
        elif r["q1"] > 0 or r["v1"]:
            r["new"] = r["v1"] - r["v0"]
        else:
            r["gone"] = r["v1"] - r["v0"]
        r["total"] = r["volume"] + r["mix"] + r["price"] + r["new"] + r["gone"]
    delta = math.fsum(r["v1"] for r in rows) - math.fsum(r["v0"] for r in rows)
    tot = {k: math.fsum(r[k] for r in rows) for k in ("volume", "mix", "price", "new", "gone")}
    for r in rows:
        r["share"] = share(r["total"], delta)
    rows.sort(key=lambda r: abs(r["total"]), reverse=True)
    lead = max(("volume", "mix", "price"), key=lambda k: abs(tot[k]))
    return {
        "operator": "pvm", "label": label, "delta": delta, "segments": rows,
        "volume_total": tot["volume"], "mix_total": tot["mix"], "price_total": tot["price"],
        "new_total": tot["new"], "gone_total": tot["gone"], "larger_effect": lead,
        "quantity_base": Q0, "quantity_cur": Q1, "quantity_growth": safe_div(Q1 - Q0, Q0),
        "top_price_key": max(rows, key=lambda r: abs(r["price"]))["key"] if rows else None,
        "closure_gap": closure_gap(delta, tot.values()), "closed": is_closed(delta, tot.values()),
    }
