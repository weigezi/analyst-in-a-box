"""Empirical-Bayes shrinkage of group rates, so a group with three orders cannot rank first by luck.

Each group's observed rate r_i has sampling variance v_i. With a normal prior r_i ~ N(m, tau^2), the posterior mean
is m + B_i (r_i - m) with B_i = tau^2 / (tau^2 + v_i): small groups (large v_i) are pulled toward m.
Source: B. Efron & C. Morris (1975), "Data analysis using Stein's estimator and its generalizations", JASA 70(350);
the James-Stein idea in W. James & C. Stein (1961).

tau^2 is estimated robustly: (1.4826 * MAD of r_i around m)^2 minus the median v_i, floored at zero. The usual
method-of-moments estimate uses the mean square, which a single wild group inflates until it shrinks nothing,
exactly the case this exists for.

For a proportion (successes / trials), v_i = m (1 - m) / n_i, which is the normal approximation of the
Beta-Binomial model; beta_binomial() returns the equivalent Beta prior (a, b) as well.
Source for the Beta-Binomial form: R. E. Kass & D. Steffey (1989), JASA 84(407); D. Robinson (2017),
"Introduction to Empirical Bayes: Examples from Baseball Statistics".

Shrinkage is used only to rank groups. The decomposition itself stays exact on the observed numbers.
"""

from __future__ import annotations

import math
import statistics

MAD_SCALE = 1.4826


def normal_normal(rates, variances, prior_mean=None, weights=None) -> dict:
    r = [float(x) for x in rates]
    v = [max(float(x), 0.0) for x in variances]
    if prior_mean is None:
        w = weights or [1.0] * len(r)
        prior_mean = math.fsum(a * b for a, b in zip(r, w)) / (math.fsum(w) or 1.0)
    m = float(prior_mean)
    if len(r) < 2:
        return {"prior_mean": m, "tau2": None, "weights": [1.0] * len(r), "shrunk": r}
    mad = statistics.median(abs(x - m) for x in r)
    tau2 = max((MAD_SCALE * mad) ** 2 - statistics.median(v), 0.0)
    b = [tau2 / (tau2 + vi) if (tau2 + vi) > 0 else 1.0 for vi in v]
    return {"prior_mean": m, "tau2": tau2, "weights": b, "shrunk": [m + bi * (x - m) for bi, x in zip(b, r)]}


def beta_binomial(successes, trials) -> dict:
    s = [float(x) for x in successes]
    n = [float(x) for x in trials]
    m = math.fsum(s) / (math.fsum(n) or 1.0)
    rates = [a / b if b else m for a, b in zip(s, n)]
    var = [m * (1 - m) / b if b else float("inf") for b in n]
    est = normal_normal(rates, var, prior_mean=m)
    tau2 = est["tau2"] or 0.0
    strength = (m * (1 - m) / tau2 - 1) if tau2 > 0 else float("inf")
    est["prior_a"], est["prior_b"] = (m * strength, (1 - m) * strength) if math.isfinite(strength) else (None, None)
    return est


def shrunk_totals(rows: list, R0: float, var_base: list, var_cur: list) -> list[float]:
    """Per-row contribution recomputed with shrunk rates; rows as produced by divisive.decompose.

    total_i = w1 * r1 - w0 * r0 - (w1 - w0) * R0, the relative three-term total, with r0 / r1 replaced by their
    shrunk values (a row absent in one period keeps rate 0 there, as in the exact decomposition)."""
    def shrink(period, var):
        idx = [i for i, x in enumerate(rows) if x[f"rate_{period}"] is not None]
        if not idx:
            return {}
        rates = [rows[i][f"rate_{period}"] for i in idx]
        dens = [rows[i][f"den_{period}"] for i in idx]
        est = normal_normal(rates, [var[i] for i in idx], weights=dens)
        return dict(zip(idx, est["shrunk"]))
    s0, s1 = shrink("base", var_base), shrink("cur", var_cur)
    out = []
    for i, x in enumerate(rows):
        r0, r1 = s0.get(i, 0.0), s1.get(i, 0.0)
        out.append(x["weight_cur"] * r1 - x["weight_base"] * r0 - (x["weight_cur"] - x["weight_base"]) * R0)
    return out
