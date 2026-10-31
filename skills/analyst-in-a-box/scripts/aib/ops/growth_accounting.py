"""Growth accounting: split a change across customers by what each customer did between the two periods.

For customer i with base value b_i and current value c_i:
  new          c_i            not active in the base, never active before it
  resurrected  c_i            not active in the base, active at some time before it
  retained     min(b_i, c_i)  active in both (what was kept)
  expansion    c_i - b_i      active in both, spent more
  contraction  c_i - b_i      active in both, spent less (negative)
  churned      -b_i           active in the base, not in the current period (negative)
Identities (exact): current = retained + new + resurrected + expansion;
                    base    = retained - contraction - churned;
                    change  = new + resurrected + expansion + contraction + churned.
Source: J. Hsu, Tribe Capital (2019), "A Quantitative Approach to Product Market Fit",
https://tribecap.co/essays/a-quantitative-approach-to-product-market-fit (quick ratio and gross retention as defined there).
"""

from __future__ import annotations

import math

from .common import closure_gap, is_closed, safe_div

OUTPUT_FIELDS = ("total_delta", "new", "resurrected", "expansion", "contraction", "churned", "retained",
                 "quick_ratio", "gross_retention", "closure_gap", "closed")
BUCKETS = ("new", "resurrected", "retained", "expansion", "contraction", "churned")


def decompose(base: dict, cur: dict, earlier: set | None = None, label: str = "") -> dict:
    """base, cur: {customer: value} in the two periods (customers with no value are absent);
    earlier: customers active at some time before the base period."""
    earlier = set(earlier or ())
    b = {k: float(v) for k, v in base.items() if v}
    c = {k: float(v) for k, v in cur.items() if v}
    buckets = {k: 0.0 for k in BUCKETS}
    counts = {k: 0 for k in BUCKETS}
    for k in set(b) | set(c):
        x, y = b.get(k, 0.0), c.get(k, 0.0)
        if k not in b:
            kind = "resurrected" if k in earlier else "new"
            buckets[kind] += y
            counts[kind] += 1
        elif k not in c:
            buckets["churned"] -= x
            counts["churned"] += 1
        else:
            buckets["retained"] += min(x, y)
            counts["retained"] += 1
            if y > x:
                buckets["expansion"] += y - x
                counts["expansion"] += 1
            elif y < x:
                buckets["contraction"] += y - x
                counts["contraction"] += 1
    tb, tc = math.fsum(b.values()), math.fsum(c.values())
    delta = tc - tb
    moves = [buckets[k] for k in ("new", "resurrected", "expansion", "contraction", "churned")]
    gains = buckets["new"] + buckets["resurrected"] + buckets["expansion"]
    losses = -(buckets["churned"] + buckets["contraction"])
    return {
        "operator": "growth_accounting", "label": label, "total_base": tb, "total_cur": tc, "total_delta": delta,
        "buckets": buckets, "customers": counts, **buckets,
        "quick_ratio": safe_div(gains, losses), "gross_retention": safe_div(buckets["retained"], tb),
        "identity_current": closure_gap(tc, [buckets["retained"], buckets["new"], buckets["resurrected"], buckets["expansion"]]),
        "identity_base": closure_gap(tb, [buckets["retained"], -buckets["contraction"], -buckets["churned"]]),
        "closure_gap": closure_gap(delta, moves), "closed": is_closed(delta, moves),
    }
