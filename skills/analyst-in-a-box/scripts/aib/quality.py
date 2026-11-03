"""Data quality, checked before anything is attributed. A change in the data is not a change in the business.

Checks (each 'ok', 'warn' or 'fail', always with the numbers behind it):
  calendar_complete         every expected day of both periods has rows (closed weekdays / dates come from project.yaml)
  key_unique                a declared key (project.yaml sources.<name>.key) never repeats in the two periods
  daily_volume_steady       no day has far more or far fewer rows than the same weekday's recent median
  daily_value_steady        no day's total is many times the usual (a unit or definition change)
  row_ratio                 the two periods have a comparable number of rows
  no_single_row_dominates   leave-one-out: no single row carries a large part of the change
  dimension_values_stable   no value vanished while another of similar size appeared from nothing (a rename)

Any 'fail' marks the data suspect: the report says so first, and nothing is marked explained.
Thresholds are params in rules.yaml (defaults in defaults.py, each with its source).
"""

from __future__ import annotations

import datetime as dt
import math
import statistics

import pandas as pd

from .defaults import param
from .windows import days

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _cfg(ws):
    return ws.project.get("quality") or {}


def closed_weekdays(ws) -> set:
    out = set()
    for x in _cfg(ws).get("closed_weekdays", []) or []:
        out.add(x if isinstance(x, int) else WEEKDAYS.index(str(x).lower()))
    return out


def closed_dates(ws) -> set:
    return {dt.date.fromisoformat(str(x)) for x in _cfg(ws).get("closed_dates", []) or []}


def expected_days(ws, w) -> list:
    cw, cd = closed_weekdays(ws), closed_dates(ws)
    return [x for x in days(w) if x.weekday() not in cw and x not in cd and x not in ws.exclude_days]


def _sources_for(ws, metrics):
    """{source: (date column, [(measure name, measure spec)])} for the measures behind these metrics."""
    out = {}
    for m in metrics:
        for name in ws.metric_measures(m):
            spec = ws.measures[name]
            out.setdefault(spec["source"], (spec["date"], []))[1].append((name, spec))
    return out


def _daily_rows(df, date):
    return df.groupby(date).size()


def is_monthly(df, date) -> bool:
    """Every date is the first of a month: the source was dated by year + month, so there are no days to check."""
    d = pd.to_datetime(df[date]).dropna()
    return d.nunique() >= 2 and bool((d.dt.day == 1).all())


def expected_months(w) -> list:
    """The first of each calendar month a window touches."""
    return [m.date() for m in pd.date_range(pd.Timestamp(w[0]).replace(day=1), pd.Timestamp(w[1]), freq="MS")]


def _status(items):
    return "fail" if any(x == "fail" for x in items) else "warn" if any(x == "warn" for x in items) else "ok"


def _jump(series_by_day: pd.Series, check_days, holidays, weeks, hi, lo):
    """Ratio of each day to the median of the same weekday in the previous `weeks` weeks."""
    hits = []
    for day in check_days:
        if day in holidays:
            continue
        v = float(series_by_day.get(pd.Timestamp(day), 0.0))
        ref = []
        for k in range(1, weeks + 1):
            past = day - dt.timedelta(days=7 * k)
            x = float(series_by_day.get(pd.Timestamp(past), float("nan")))
            if past not in holidays and math.isfinite(x) and x > 0:
                ref.append(x)
        if len(ref) < 3 or v == 0:
            continue
        r = v / statistics.median(ref)
        if r >= hi or r <= lo:
            hits.append({"day": day.isoformat(), "value": v, "usual": statistics.median(ref), "ratio": r})
    return hits


def typical_change(ws, metric, pairs, filters) -> float | None:
    """Usual size of this question's change, in the metric's own unit: 1.4826 x MAD of past changes.
    Computed on the same past (window, base) pairs the whole number is judged against."""
    vals = []
    for w, b in pairs:
        try:
            vals.append(ws.total(metric, w, filters) - ws.total(metric, b, filters))
        except Exception:  # a past window that cannot be computed is simply not history
            continue
    vals = [v for v in vals if math.isfinite(v)]
    if len(vals) < 3:
        return None
    med = statistics.median(vals)
    return 1.4826 * statistics.median(abs(v - med) for v in vals)


def assess(ws, metric, base, cur, filters, holidays=frozenset(), metrics=None, pairs=()) -> dict:
    metrics = metrics or [metric]
    checks = []
    srcs = _sources_for(ws, metrics)

    def add(name, status, **detail):
        checks.append({"check": name, "status": status, **detail})

    # 1. calendar
    missing = {"base": [], "current": []}
    for src, (date, _) in srcs.items():
        df = ws.sources.frame(src)
        seen = set(pd.to_datetime(df[date]).dt.date.unique())
        monthly = is_monthly(df, date)
        for tag, w in (("base", base), ("current", cur)):
            expect = expected_months(w) if monthly else expected_days(ws, w)
            missing[tag] += [x.isoformat() for x in expect if x not in seen and x.isoformat() not in missing[tag]]
    n_missing = len(missing["base"]) + len(missing["current"])
    add("calendar_complete", "fail" if n_missing > param(ws, "quality_missing_days_max") else "ok", missing=missing,
        closed_weekdays=sorted(closed_weekdays(ws)), closed_dates=sorted(x.isoformat() for x in closed_dates(ws)))

    # 2. declared keys
    dups = []
    for src, (date, _) in srcs.items():
        key = ws.sources.specs[src].get("key")
        if not key:
            continue
        cols = [key] if isinstance(key, str) else list(key)
        df = ws.sources.frame(src)
        part = df[(df[date] >= pd.Timestamp(base[0]) - pd.Timedelta(days=0)) & (df[date] <= pd.Timestamp(cur[1]))]
        part = part[((part[date] >= pd.Timestamp(base[0])) & (part[date] <= pd.Timestamp(base[1]))) |
                    ((part[date] >= pd.Timestamp(cur[0])) & (part[date] <= pd.Timestamp(cur[1])))]
        n = len(part)
        d = int(part.duplicated(cols).sum()) if n else 0
        share = d / n if n else 0.0
        if d:
            dups.append({"source": src, "key": cols, "rows": n, "duplicates": d, "share": share,
                         "examples": [str(x) for x in part[part.duplicated(cols, keep=False)][cols[0]].head(3)]})
    no_key = [s for s in srcs if not ws.sources.specs[s].get("key")]
    add("key_unique", "fail" if any(x["share"] > param(ws, "quality_duplicate_key_max_share") for x in dups) else "ok",
        duplicates=dups, sources_without_key=no_key)

    # 3. daily volume and value
    weeks, hi, lo = int(param(ws, "quality_jump_lookback_weeks")), param(ws, "quality_jump_high"), param(ws, "quality_jump_low")
    vj = param(ws, "quality_value_jump")
    check_days = [x for x in days(base) + days(cur) if x not in ws.exclude_days]
    vol, val = [], []
    for src, (date, measures) in srcs.items():
        df = ws.sources.frame(src)
        if is_monthly(df, date):
            continue   # a month is one row-set; there are no days to compare with their usual weekday
        lo_day = pd.Timestamp(min(base[0], cur[0]) - dt.timedelta(days=7 * weeks))
        part = df[(df[date] >= lo_day) & (df[date] <= pd.Timestamp(cur[1]))]
        for h in _jump(_daily_rows(part, date), check_days, holidays, weeks, hi, lo):
            vol.append({"source": src, **h})
        for name, spec in measures:
            if spec["agg"] != "sum":
                continue
            s = part.groupby(date)[spec["column"]].sum()
            for h in _jump(s, check_days, holidays, weeks, vj, 1 / vj):
                val.append({"source": src, "measure": name, **h})
    add("daily_volume_steady", "fail" if vol else "ok", days=vol[:10], thresholds=[lo, hi])
    add("daily_value_steady", "fail" if val else "ok", days=val[:10], thresholds=[1 / vj, vj])

    # 4. row ratio
    rr = []
    for src in srcs:
        nb, nc = ws.rows(src, base), ws.rows(src, cur)
        r = nc / nb if nb else None
        rr.append({"source": src, "base_rows": nb, "current_rows": nc, "ratio": r})
    mx, bx = param(ws, "quality_row_ratio_max"), param(ws, "quality_row_ratio_block")
    broken = [x for x in rr if not x["base_rows"] or not x["current_rows"] or x["ratio"] > bx or x["ratio"] < 1 / bx]
    bad = [x for x in rr if x["ratio"] is None or x["ratio"] > mx or x["ratio"] < 1 / mx]
    add("row_ratio", "fail" if broken else "warn" if bad else "ok", sources=rr, thresholds=[mx, bx])

    # 5. leave one out
    st, detail = _single_rows(ws, metric, base, cur, filters, typical_change(ws, metric, pairs, filters))
    add("no_single_row_dominates", st, **detail)

    # 6. renamed values
    st, detail = _values(ws, metric, base, cur, filters)
    add("dimension_values_stable", st, **detail)

    # Two levels (rules.yaml params.quality_check_levels): a failed 'block' check would make the numbers wrong, so the
    # data is in doubt and the report stops; a failed 'warn' check is named at the top and the conclusions are given.
    levels = param(ws, "quality_check_levels") or {}
    for c in checks:
        c["level"] = levels.get(c["check"], "warn")
    blocking = [c["check"] for c in checks if c["status"] == "fail" and c["level"] == "block"]
    warned = [c["check"] for c in checks if c["status"] == "warn" or (c["status"] == "fail" and c["level"] != "block")]
    status = "suspect" if blocking else "warn" if warned else "ok"
    return {"status": status, "suspect": bool(blocking), "checks": checks, "failed": blocking, "warned": warned,
            "failed_any": [c["check"] for c in checks if c["status"] == "fail"]}


def _frame(ws, measure, w, filters):
    spec = ws.measures[measure]
    df = ws.sources.frame(spec["source"])
    d = df[(df[spec["date"]] >= pd.Timestamp(w[0])) & (df[spec["date"]] <= pd.Timestamp(w[1]))]
    for k, v in (filters or {}).items():
        d = d[d[ws.column(measure, k)].isin(v if isinstance(v, (list, tuple, set)) else [v])]
    if ws.exclude_days:
        d = d[~d[spec["date"]].isin([pd.Timestamp(x) for x in ws.exclude_days])]
    return d


def _single_rows(ws, metric, base, cur, filters, typical_change=None):
    """Rows of the current period whose removal would move the change the most.

    Additive sum: a row's effect is its own value. Ratio N/D (both counted on the same rows): removing row i
    moves the ratio from N/D to (N - n_i)/(D - d_i)."""
    m = ws.metrics[metric]
    top = int(param(ws, "quality_top_rows"))
    if m.get("kind") == "ratio":
        num, den = ws.metrics[m["numerator"]], ws.metrics[m["denominator"]]
        if "measure" not in num or "measure" not in den:
            return "ok", {"rows": [], "note": "not computed: the ratio is not built from two plain measures"}
        mn, md = ws.measures[num["measure"]], ws.measures[den["measure"]]
        if mn["source"] != md["source"] or mn["agg"] != "sum" or md["agg"] not in ("count", "count_distinct", "sum"):
            return "ok", {"rows": [], "note": "not computed: numerator and denominator come from different tables"}
        d = _frame(ws, num["measure"], cur, filters)
        if len(d) < 2:
            return "ok", {"rows": []}
        n = d[mn["column"]].astype(float)
        dd = d[md["column"]].astype(float) if md["agg"] == "sum" else pd.Series(1.0, index=d.index)
        N, D = n.sum(), dd.sum()
        effect = N / D - (N - n) / (D - dd).where((D - dd) != 0)
        key_src = mn
    else:
        if "measure" not in m or ws.measures[m["measure"]]["agg"] != "sum":
            return "ok", {"rows": [], "note": "not computed: only for summed metrics and ratios of sums"}
        key_src = ws.measures[m["measure"]]
        d = _frame(ws, m["measure"], cur, filters)
        if not len(d):
            return "ok", {"rows": []}
        effect = d[key_src["column"]].astype(float)
    if ws.per_day:
        effect = effect / max(ws.days_in(cur), 1)
    delta = ws.total(metric, cur, filters) - ws.total(metric, base, filters)
    # Judge a row against the larger of this change and the usual size of a change (set by run from history),
    # so an ordinary large order does not "dominate" a week that barely moved.
    scale = max(abs(delta), float(typical_change or 0.0))
    typical = float(effect.abs().median()) or 0.0
    key = ws.sources.specs[key_src["source"]].get("key")
    kcol = key if isinstance(key, str) else None
    order = effect.abs().sort_values(ascending=False).index[:top]
    rows = []
    for i in order:
        e = float(effect.loc[i])
        rows.append({"key": str(d.loc[i, kcol]) if kcol else str(i), "date": str(d.loc[i, key_src["date"]])[:10], "effect": e,
                     "share_of_change": e / delta if delta else None, "share_of_scale": e / scale if scale else None,
                     "times_typical": abs(e) / typical if typical else None})
    if not rows or not scale:
        return "ok", {"rows": rows, "change": delta, "scale": scale}
    lead = rows[0]
    extreme = (lead["times_typical"] or 0) >= param(ws, "quality_extreme_row_times")
    sh = abs(lead["share_of_scale"] or 0)
    st = "fail" if extreme and sh >= param(ws, "quality_single_row_fail_share") else \
        "warn" if extreme and sh >= param(ws, "quality_single_row_max_share") else "ok"
    return st, {"rows": rows, "change": delta, "scale": scale, "typical_change": typical_change, "typical_row_effect": typical}


def _values(ws, metric, base, cur, filters):
    measure = ws.metric_measures(metric)[-1]
    spec = ws.measures[measure]
    mn = param(ws, "quality_new_value_min_share")
    found = []
    for dim in sorted(ws.metric_dimensions(metric) - set(filters or {})):
        col = ws.column(measure, dim)
        b = _frame(ws, measure, base, filters)[col].value_counts()
        c = _frame(ws, measure, cur, filters)[col].value_counts()
        nb, nc = b.sum() or 1, c.sum() or 1
        gone = [str(k) for k, v in b.items() if k not in c.index and v / nb >= mn]
        new = [str(k) for k, v in c.items() if k not in b.index and v / nc >= mn]
        if gone or new:
            found.append({"dimension": dim, "gone": gone, "new": new, "looks_renamed": bool(gone and new)})
    st = "fail" if any(x["looks_renamed"] for x in found) else "warn" if found else "ok"
    return st, {"dimensions": found, "column_source": spec["source"]}
