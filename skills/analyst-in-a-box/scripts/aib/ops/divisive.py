"""Rate decomposition: split the change of a ratio metric R = N / D across the values of a dimension.

R = sum_s w_s * r_s, where w_s = D_s / D (the segment's weight) and r_s = N_s / D_s (its rate).
The change splits exactly into three terms (three-term form):
  structure   = sum_s (w_s,1 - w_s,0) * r_s,0       mix moved
  rate        = sum_s  w_s,0 * (r_s,1 - r_s,0)      segments' own rates moved
  interaction = sum_s (w_s,1 - w_s,0) * (r_s,1 - r_s,0)
Two-term form splits the interaction symmetrically (average weights / average rates).
Source: E. M. Kitagawa (1955), "Components of a difference between two rates", Journal of the
American Statistical Association 50(272); P. Das Gupta (1978) for the symmetric two-term form.

"relative" structure uses (r_s,0 - R_0) instead of r_s,0. Because the weight changes sum to zero,
the structure total is identical; per segment it reads more naturally: gaining share helps only if
the segment is above the average rate.

Segments present in only one period have no rate in the other. Their whole effect is counted as
structure (their weight appeared or disappeared), which keeps the decomposition exact.
"""

from __future__ import annotations

import math

from .common import closure_gap, is_closed, key_str, safe_div, share, top_fields

OUTPUT_FIELDS = (
    "top1_key", "top1_abs_share", "top2_cum_abs_share",
    "rate_base", "rate_cur", "rate_delta", "mode",
    "structure_total", "rate_total", "interaction_total",
    "structure_share", "rate_share", "interaction_share",
    "larger_effect", "closure_gap", "closed",
)


def decompose(segments: dict, label: str = "", mode: str = "three_term", relative: bool = True) -> dict:
    """segments: {key: (num_base, den_base, num_cur, den_cur)}."""
    if mode not in ("three_term", "two_term"):
        raise ValueError("mode must be three_term or two_term")
    rows = []
    for key, (n0, d0, n1, d1) in segments.items():
        rows.append({"key": key_str(key), "num_base": float(n0 or 0), "den_base": float(d0 or 0),
                     "num_cur": float(n1 or 0), "den_cur": float(d1 or 0)})
    D0 = math.fsum(r["den_base"] for r in rows)
    D1 = math.fsum(r["den_cur"] for r in rows)
    if D0 == 0 or D1 == 0:
        raise ValueError("total denominator is zero in one period; the rate is undefined")
    R0 = math.fsum(r["num_base"] for r in rows) / D0
    R1 = math.fsum(r["num_cur"] for r in rows) / D1
    dR = R1 - R0

    for r in rows:
        w0, w1 = r["den_base"] / D0, r["den_cur"] / D1
        r0 = safe_div(r["num_base"], r["den_base"])
        r1 = safe_div(r["num_cur"], r["den_cur"])
        r.update(weight_base=w0, weight_cur=w1, rate_base=r0, rate_cur=r1)
        if r0 is None or r1 is None:
            # Present in one period only: contribution = w1*r1 - w0*r0, all of it structure.
            own = (w1 * (r1 or 0.0)) - (w0 * (r0 or 0.0))
            ref = R0 if relative else 0.0
            s, rt, ix = own - (w1 - w0) * ref, 0.0, 0.0
        elif mode == "three_term":
            ref = R0 if relative else 0.0
            s = (w1 - w0) * (r0 - ref)
            rt = w0 * (r1 - r0)
            ix = (w1 - w0) * (r1 - r0)
        else:
            ref = (R0 + R1) / 2 if relative else 0.0
            s = (w1 - w0) * ((r0 + r1) / 2 - ref)
            rt = (w0 + w1) / 2 * (r1 - r0)
            ix = 0.0
        r.update(structure=s, rate=rt, interaction=ix, total=s + rt + ix)

    for r in rows:
        r["share"] = share(r["total"], dR)
    rows.sort(key=lambda r: abs(r["total"]), reverse=True)

    S = math.fsum(r["structure"] for r in rows)
    RT = math.fsum(r["rate"] for r in rows)
    IX = math.fsum(r["interaction"] for r in rows)
    larger = "structure" if abs(S) > abs(RT) else "rate" if abs(RT) > abs(S) else "tie"
    terms = [S, RT, IX]
    top = top_fields(rows, "total")
    return {
        **top,
        "operator": "divisive",
        "label": label,
        "mode": mode,
        "rate_base": R0,
        "rate_cur": R1,
        "rate_delta": dR,
        "segments": rows,
        "structure_total": S,
        "rate_total": RT,
        "interaction_total": IX,
        "structure_share": share(S, dR),
        "rate_share": share(RT, dR),
        "interaction_share": share(IX, dR),
        "larger_effect": larger,
        "closure_gap": closure_gap(dR, terms),
        "closed": is_closed(dR, terms),
    }
