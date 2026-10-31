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
    "holiday_misaligned", "z_method", "z_missing_reason", "verdict",
    "usual_gap", "expected_growth", "expected_part", "own_part_usual", "own_share_usual",
)

# 1.4826 makes the median absolute deviation comparable with a standard deviation for normal data.
# Source: B. Iglewicz & D. Hoaglin (1993), "How to Detect and Handle Outliers", ASQC.
MAD_SCALE = 1.4826


# When more than half of the history is identical the MAD is zero. The same authors fall back on the mean
# absolute deviation, scaled by 1.253314 to match a standard deviation for normal data (IBM SPSS documents
# the same fallback for its modified z-score).
MEANAD_SCALE = 1.253314


def unusualness(history: list[float], current: float) -> dict:
    """history: past period-over-period changes of the same kind (e.g. weekly year-on-year growth)."""
    h = [float(x) for x in history if x is not None and math.isfinite(x)]
    out = {"current_change": current, "history_n": len(h), "robust_z": None, "percentile": None,
           "history_median": None, "history_mad": None, "z_method": None, "z_missing_reason": None}
    if len(h) < 2 or current is None or not math.isfinite(current):
        out["z_missing_reason"] = "short_history" if len(h) < 2 else "no_current_value"
        return out
    med = statistics.median(h)
    mad = statistics.median(abs(x - med) for x in h)
    out["history_median"], out["history_mad"] = med, mad
    if mad > 0:
        out["robust_z"], out["z_method"] = (current - med) / (MAD_SCALE * mad), "median_absolute_deviation"
    else:
        meanad = statistics.fmean(abs(x - med) for x in h)
        if meanad > 0:
            out["robust_z"], out["z_method"] = (current - med) / (MEANAD_SCALE * meanad), "mean_absolute_deviation"
        else:
            out["z_missing_reason"] = "flat_history"
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


def versus_market_usual(own_base: float, own_cur: float, market_growth: float | None, past: list[tuple]) -> dict:
    """Expected change = the market's growth plus this business's usual gap to the market.

    past: [(own_growth, market_growth)] over the same past pairs the whole number is judged against.
    The plain split (versus_market) credits every gap to 'our own'. A business that always grows a few points
    below or above its market would then show a large 'own part' every period. Shift-share analysis separates a
    region's lasting difference from the market (its mix) from what is competitive; J. M. Esteban-Marquillas (1972),
    "A reinterpretation of shift-share analysis", Regional and Urban Economics 2(3), takes the expected, structural
    part out before calling the rest competitive. Here the business's median gap over its own history stands in
    for that lasting part: it is an estimate, not an accounting identity, and the report says so."""
    gaps = [o - m for o, m in past if o is not None and m is not None and math.isfinite(o) and math.isfinite(m)]
    out = {"usual_gap": None, "usual_gap_n": len(gaps), "expected_growth": None, "expected_part": None,
           "own_part_usual": None, "own_share_usual": None}
    if market_growth is None or len(gaps) < 3 or not own_base:
        return out
    gap = statistics.median(gaps)
    delta = own_cur - own_base
    expected = own_base * (market_growth + gap)
    out.update(usual_gap=gap, expected_growth=market_growth + gap, expected_part=expected,
               own_part_usual=delta - expected, own_share_usual=share(delta - expected, delta))
    return out


def ranges(history: list[float], q: dict, z_hi, z_lo, floor=None) -> dict:
    """Two separate things a chart must not mix up: the usual range (middle half of past changes) and the lines
    at which a change would be called unusual (median +/- threshold x robust scale)."""
    h = sorted(float(x) for x in history if x is not None and math.isfinite(x))
    out = {"usual_range": None, "unusual_below": None, "unusual_above": None, "scale": None}
    if len(h) >= 4:
        qs = statistics.quantiles(h, n=4, method="inclusive")
        out["usual_range"] = [qs[0], qs[2]]
    med = q.get("history_median")
    if med is None:
        return out
    if q.get("z_method") == "median_absolute_deviation":
        scale = MAD_SCALE * q["history_mad"]
    elif q.get("z_method") == "mean_absolute_deviation":
        scale = MEANAD_SCALE * statistics.fmean(abs(x - med) for x in h)
    else:
        return out
    out.update(scale=scale, unusual_below=med + z_lo * scale if z_lo is not None else None,
               unusual_above=med + z_hi * scale if z_hi is not None else None)
    if floor is not None and out["unusual_below"] is not None and out["unusual_below"] < floor:
        # a growth rate cannot go below -100%: a line further down means "no fall can be called unusual"
        out["unusual_below"], out["unusual_below_clipped"] = floor, True
    return out


def _days(a: dt.date, b: dt.date) -> set:
    return {a + dt.timedelta(days=i) for i in range((b - a).days + 1)}


def d(x):
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x))


def calendar_alignment(holidays: list[dict], base: tuple, current: tuple) -> dict:
    """holidays: [{'name', 'start', 'end'}] with ISO dates; base/current: (start, end) ISO dates inclusive.

    Holidays with the same name are matched across years; a different count of holiday days inside
    the two windows means a year-on-year comparison is distorted by the calendar."""
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
    misaligned_names = {r["name"] for r in items if r["difference"]}
    off = set()
    for h in holidays:
        if h["name"] in misaligned_names:
            off |= _days(d(h["start"]), d(h["end"])) & (bw | cw)
    return {"holidays": items, "holiday_misaligned": any(r["difference"] != 0 for r in items),
            "misaligned_days": sorted(x.isoformat() for x in off)}


def holiday_days(holidays: list[dict]) -> set:
    out = set()
    for h in holidays:
        out |= _days(dt.date.fromisoformat(str(h["start"])), dt.date.fromisoformat(str(h["end"])))
    return out


def holiday_plans(holidays: list[dict], base: tuple, current: tuple) -> list[dict]:
    """Two ways out when the two periods hold different holidays.

    exclude: leave the misaligned holiday days out of both periods (the base loses its days, the current its own);
    shift_base: move the base by whole weeks (keeps weekdays) until the holiday days line up, if any shift within
    three weeks does it."""
    cal = calendar_alignment(holidays, base, current)
    if not cal["holiday_misaligned"]:
        return []
    # A day left out of one period takes the day at the same position in the other period with it,
    # so both periods keep the same number of days and the same weekdays.
    cd = sorted(_days(d(current[0]), d(current[1])))
    bd = sorted(_days(d(base[0]), d(base[1])))
    off = {d(x) for x in cal["misaligned_days"]}
    drop = set()
    for c, b in zip(cd, bd):
        if c in off or b in off:
            drop |= {c, b}
    plans = [{"kind": "exclude", "days": sorted(x.isoformat() for x in drop)}]
    for k in (1, -1, 2, -2, 3, -3):
        b = (base[0] + dt.timedelta(days=7 * k), base[1] + dt.timedelta(days=7 * k))
        if not calendar_alignment(holidays, b, current)["holiday_misaligned"]:
            plans.append({"kind": "shift_base", "weeks": k, "base": [b[0].isoformat(), b[1].isoformat()]})
            break
    else:
        plans.append({"kind": "shift_base", "weeks": None, "base": None})
    return plans
