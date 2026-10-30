"""Multiplicative decomposition: split the change of Y = x1 * x2 * ... * xn across its factors.

Default method: LMDI-I (logarithmic mean Divisia index), exact for products of positive factors.
  contribution_k = L(Y1, Y0) * ln(x_k,1 / x_k,0),  L(a, b) = (a - b) / (ln a - ln b),  L(a, a) = a
  Source: B. W. Ang (2004), "Decomposition analysis for policymaking in energy: which is the
  preferred method?", Energy Policy; B. W. Ang (2005), "The LMDI approach to decomposition
  analysis: a practical guide", Energy Policy.

Fallback when any factor is zero or negative (logs undefined): Shapley decomposition, which
averages each factor's marginal effect over every order of switching factors from base to current.
It is also exact. Source: L. S. Shapley (1953), "A value for n-person games"; applied to index
decomposition by J. W. Sun (1998), "Changes in energy consumption and energy intensity: a
complete decomposition model", Energy Economics.
"""

from __future__ import annotations

import itertools
import math

from .common import closure_gap, is_closed, safe_div, share

OUTPUT_FIELDS = (
    "y_base", "y_cur", "y_delta", "y_growth", "method",
    "dominant_factor", "dominant_share", "closure_gap", "closed",
)


def _logmean(a: float, b: float) -> float:
    if a == b:
        return a
    return (a - b) / (math.log(a) - math.log(b))


def _product(values) -> float:
    out = 1.0
    for v in values:
        out *= v
    return out


def _lmdi(base: dict, cur: dict) -> dict:
    y0 = _product(base.values())
    y1 = _product(cur.values())
    w = _logmean(y1, y0)
    return {k: w * math.log(cur[k] / base[k]) for k in base}


def _shapley(base: dict, cur: dict) -> dict:
    names = list(base)
    n = len(names)
    contrib = {k: 0.0 for k in names}
    for k in names:
        others = [x for x in names if x != k]
        for r in range(n):
            for subset in itertools.combinations(others, r):
                weight = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
                with_k = _product(cur[x] if (x in subset or x == k) else base[x] for x in names)
                without_k = _product(cur[x] if x in subset else base[x] for x in names)
                contrib[k] += weight * (with_k - without_k)
    return contrib


def decompose(base: dict, cur: dict, label: str = "", method: str = "auto") -> dict:
    """base, cur: {factor_name: value}, same keys. Y is the product of the factors."""
    if set(base) != set(cur):
        raise ValueError("base and current must have the same factors")
    base = {k: float(v) for k, v in base.items()}
    cur = {k: float(cur[k]) for k in base}
    positive = all(v > 0 for v in base.values()) and all(v > 0 for v in cur.values())
    if method == "auto":
        method = "lmdi" if positive else "shapley"
    if method == "lmdi" and not positive:
        raise ValueError("LMDI needs positive factors; use method='shapley'")
    contrib = _lmdi(base, cur) if method == "lmdi" else _shapley(base, cur)

    y0, y1 = _product(base.values()), _product(cur.values())
    dy = y1 - y0
    factors = [
        {
            "factor": k,
            "base": base[k],
            "cur": cur[k],
            "growth": safe_div(cur[k] - base[k], base[k]),
            "contribution": contrib[k],
            "share": share(contrib[k], dy),
        }
        for k in base
    ]
    factors.sort(key=lambda f: abs(f["contribution"]), reverse=True)
    return {
        "operator": "multiplicative",
        "label": label,
        "method": method,
        "y_base": y0,
        "y_cur": y1,
        "y_delta": dy,
        "y_growth": safe_div(dy, y0),
        "factors": factors,
        "dominant_factor": factors[0]["factor"] if factors else None,
        "dominant_share": factors[0]["share"] if factors else None,
        "closure_gap": closure_gap(dy, contrib.values()),
        "closed": is_closed(dy, contrib.values()),
    }
