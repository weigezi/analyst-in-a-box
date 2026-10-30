"""Before attributing a change, decide what kind of change it is.

Three questions, all answered with numbers and no hard-coded verdict:
1. Is this period unusual compared with its own history?  (robust z-score + percentile rank)
2. Did the market move the same way?  (shift-share at total level)
3. Do the two periods hold the same holidays?  (calendar alignment)
"""

from __future__ import annotations

import datetime as dt
import math
import statistics

from .ops.common import safe_div, share

OUTPUT_FIELDS = (
    "current_change", "robust_z", "percentile", "history_n",
    "market_growth", "own_growth", "market_part", "own_part", "market_share", "own_share",
    "holiday_misaligned",
)

# 1.4826 makes the median absolute deviation comparable with a standard deviation for normal data.
# Source: B. Iglewicz & D. Hoaglin (1993), "How to Detect and Handle Outliers", ASQC.
MAD_SCALE = 1.4826


def unusualness(history: list[float], current: float) -> dict:
    """history: past period-over-period changes of the same kind (e.g. weekly year-on-year growth)."""
    h = [float(x) for x in history if x is not None and math.isfinite(x)]
    out = {"current_change": current, "history_n": len(h), "robust_z": None, "percentile": None,
           "history_median": None, "history_mad": None}
    if len(h) < 2:
        return out
    med = statistics.median(h)
    mad = statistics.median(abs(x - med) for x in h)
    out["history_median"], out["history_mad"] = med, mad
    if mad > 0:
        out["robust_z"] = (current - med) / (MAD_SCALE * mad)
    out["percentile"] = sum(1 for x in h if x <= current) / len(h)
    return out


def versus_market(own_base: float, own_cur: float, market_base: float, market_cur: float) -> dict:
    """Split the own change into 'moved with the market' and 'own'. Exact by construction."""
    own_delta = own_cur - own_base
    mg = safe_div(market_cur - market_base, market_base)
    if mg is None:
        return {"market_growth": None, "own_growth": safe_div(own_delta, own_base), "market_part": None,
                "own_part": None, "market_share": None, "own_share": None}
    market_part = own_base * mg
    own_part = own_delta - market_part
    return {
        "market_growth": mg,
        "own_growth": safe_div(own_delta, own_base),
        "market_part": market_part,
        "own_part": own_part,
        "market_share": share(market_part, own_delta),
        "own_share": share(own_part, own_delta),
    }


def _days(a: dt.date, b: dt.date) -> set:
    return {a + dt.timedelta(days=i) for i in range((b - a).days + 1)}


def calendar_alignment(holidays: list[dict], base: tuple, current: tuple) -> dict:
    """holidays: [{'name', 'start', 'end'}] with ISO dates; base/current: (start, end) ISO dates inclusive.

    Holidays with the same name are matched across years; a different count of holiday days inside
    the two windows means a year-on-year comparison is distorted by the calendar."""
    def d(x):
        return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x))
    bw, cw = _days(d(base[0]), d(base[1])), _days(d(current[0]), d(current[1]))
    per_name: dict = {}
    for h in holidays:
        days = _days(d(h["start"]), d(h["end"]))
        rec = per_name.setdefault(h["name"], {"name": h["name"], "base_days": 0, "current_days": 0,
                                              **{k: h[k] for k in h if str(k).startswith("label_")}})
        rec["base_days"] += len(days & bw)
        rec["current_days"] += len(days & cw)
    items = [r for r in per_name.values() if r["base_days"] or r["current_days"]]
    for r in items:
        r["difference"] = r["current_days"] - r["base_days"]
    return {"holidays": items, "holiday_misaligned": any(r["difference"] != 0 for r in items)}
