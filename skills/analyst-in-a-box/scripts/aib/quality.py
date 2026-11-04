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


def whole_months(w) -> bool:
    """The window starts on the 1st and ends on the last day of a month."""
    return w[0].day == 1 and (w[1] + dt.timedelta(days=1)).day == 1


def monthly_mismatch(ws, metric, cur, base) -> str | None:
    """One plain sentence when the metric's source is dated by month and a window is not whole months, else None."""
    for src, (date, _) in _sources_for(ws, [metric]).items():
        if is_monthly(ws.sources.frame(src), date) and not (whole_months(cur) and whole_months(base)):
            return (f"source '{src}' is monthly data (every date is the 1st of a month) and the window is not whole months, "
                    "so the window holds no records; ask for whole calendar months")
    return None


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
    for src, (date, measures) in srcs.items():
        # Counted in the unit the measure is about (orders, not order lines) when the workspace says what that is.
        nb, unit = ws.group_size(measures[0][0], base)
        nc, _ = ws.group_size(measures[0][0], cur)
        r = nc / nb if nb else None
        rr.append({"source": src, "base_rows": nb, "current_rows": nc, "ratio": r, "unit": unit,
                   "monthly": is_monthly(ws.sources.frame(src), date), "whole_months": whole_months(base) and whole_months(cur)})
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
    notes = data_notes(ws, metrics, base, cur, filters)
    blocking = [c["check"] for c in checks if c["status"] == "fail" and c["level"] == "block"]
    warned = [c["check"] for c in checks if c["status"] == "warn" or (c["status"] == "fail" and c["level"] != "block")]
    status = "suspect" if blocking else "warn" if warned else "ok"
    return {"status": status, "suspect": bool(blocking), "checks": checks, "notes": notes, "failed": blocking, "warned": warned,
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


# ---------- data notes: what the summed columns look like (never a block) ----------

def _summed(ws, metrics):
    """{(source, column): [measure names]} for the summed measures behind these metrics."""
    out: dict = {}
    for m in metrics:
        for name in ws.metric_measures(m):
            spec = ws.measures[name]
            if spec["agg"] == "sum":
                out.setdefault((spec["source"], spec["column"]), []).append(name)
    return out


def blank_share(ws, measure, dims, w, filters=None) -> tuple:
    """(rows with a blank in any of these dimensions, rows) of the measure's source in a window, same filters as the numbers."""
    d = _frame(ws, measure, w, filters)
    cols = [ws.column(measure, x) for x in dims]
    return int(d[cols].isna().any(axis=1).sum()), len(d)


def data_notes(ws, metrics, base, cur, filters) -> list:
    """Facts about the summed columns behind the headline that a reader should know, each with its count and share.
    They are shown in the report and never stop it; the shape tests only say what the numbers look like."""
    notes = []
    mn_blank, mn_zero = param(ws, "quality_blank_note_min_share"), param(ws, "quality_zero_note_min_share")
    for (src, col), names in _summed(ws, metrics).items():
        name = names[0]
        spec = ws.measures[name]
        d_cur, d_base = _frame(ws, name, cur, filters), _frame(ws, name, base, filters)
        n, nb = len(d_cur), len(d_base)
        if not n:
            continue
        v = d_cur[col]
        blank, blank_b = int(v.isna().sum()), int(d_base[col].isna().sum())
        if blank / n > mn_blank and blank or (nb and blank_b / nb > mn_blank and blank_b):
            notes.append({"note": "blank_amounts", "source": src, "column": col, "rows": n, "blank": blank, "share": blank / n,
                          "base_rows": nb, "base_blank": blank_b, "base_share": blank_b / nb if nb else None})
        zero = int((v == 0).sum())
        if zero and zero / n >= mn_zero:
            notes.append({"note": "zero_amounts", "source": src, "column": col, "rows": n, "zero": zero, "share": zero / n})
        both = pd.concat([d_cur, d_base])
        x = pd.to_numeric(both[col], errors="coerce").dropna()
        if len(x) >= 20 and x.min() >= 0 and x.max() <= 1 and x.nunique() > 2 and ((x > 0) & (x < 1)).any():
            notes.append({"note": "looks_like_rate", "source": src, "column": col, "n": len(x), "min": float(x.min()),
                          "max": float(x.max())})
        notes += _repeats_per_entity(ws, spec, both, col)
    return notes


def _repeats_per_entity(ws, spec, df, col) -> list:
    """A value that stays the same for the same customer or product across dates is a level (a balance, a price list),
    not an amount that happens each time; adding it up over dates counts it again every period."""
    date = spec["date"]
    key = ws.sources.specs[spec["source"]].get("key")
    skip = {col, date, *( [key] if isinstance(key, str) else list(key or []))}
    min_entities, min_share = int(param(ws, "quality_stock_min_entities")), param(ws, "quality_stock_min_share")
    d = df[df[col].notna()]
    if d[col].nunique() < 2:
        return []
    out = []
    for c in d.columns:
        if c in skip or pd.api.types.is_float_dtype(d[c]) or pd.api.types.is_datetime64_any_dtype(d[c]):
            continue
        if not 2 <= d[c].nunique() < len(d):
            continue
        g = d.groupby(c)
        dates, levels = g[date].nunique(), g[col].nunique()
        multi = dates[dates >= 2].index
        if len(multi) < min_entities:
            continue
        same = float((levels.loc[multi] == 1).mean())
        if same >= min_share:
            out.append({"note": "repeats_per_entity", "source": spec["source"], "column": col, "entity": c,
                        "entities": int(len(multi)), "share_constant": same})
        if len(out) >= 2:
            break
    return out
