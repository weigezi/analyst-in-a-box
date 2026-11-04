"""A workspace is one company's knowledge. The skill is generic; everything specific lives here.

<workspace>/
  project.yaml   name, language, data sources, external sources
  model.yaml     method layer: measures, metrics, identities, dimensions, priorities, comparisons
  rules.yaml     named params (with sources) and decision tables
  world.yaml     the part of the world that explains the numbers
  corrections.jsonl, regressions/, runs/   written by the skill as it is used
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from . import defaults
from .sources import AGGS, Sources, aggregate

STATUSES = ("confirmed", "proposed", "retired")
SOURCE_KINDS = ("user", "document", "data", "system_record", "general_knowledge", "demo_setting", "formula")


def _read(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or default


def label(x, lang: str = "en") -> str:
    if isinstance(x, dict):
        return str(x.get(lang) or x.get("en") or x.get("zh") or next(iter(x.values()), ""))
    return "" if x is None else str(x)


def window(start, end) -> tuple:
    return (dt.date.fromisoformat(str(start)), dt.date.fromisoformat(str(end)))


def shift_window(w: tuple, how: str) -> tuple:
    """The base for a window. Rules and their names live in windows.base; this keeps the 0.1 call signature."""
    from .windows import base
    return base(w, how)[0]


class Workspace:
    def __init__(self, root):
        self.root = Path(root)
        self.project = _read(self.root / "project.yaml", {})
        self.model = _read(self.root / "model.yaml", {})
        self.rules = _read(self.root / "rules.yaml", {})
        self.world = _read(self.root / "world.yaml", {})
        self.sources = Sources(self.project.get("sources", {}), self.root)
        self.external = Sources(self.project.get("external", {}), self.root)
        # Set by run for the length of one run, then reset: days left out of every window, and per-day scaling.
        self.exclude_days: frozenset = frozenset()
        self.per_day = False
        self._daily: dict = {}
        self._unique: dict = {}

    # ---------- lookups ----------
    @property
    def lang(self):
        return self.project.get("language", "en")

    @property
    def measures(self):
        return self.model.get("measures", {})

    @property
    def metrics(self):
        return self.model.get("metrics", {})

    @property
    def dimensions(self):
        return self.model.get("dimensions", {})

    @property
    def params(self):
        return self.rules.get("params", {})

    def tables(self):
        return {t["id"]: t for t in self.rules.get("tables", [])}

    def column(self, measure: str, dim: str) -> str:
        m = self.measures[measure]
        return (m.get("columns") or {}).get(dim) or self.dimensions[dim].get("column", dim)

    def metric_measures(self, metric: str) -> list:
        m = self.metrics[metric]
        if m.get("kind") == "ratio":
            return [self.metrics[m["numerator"]]["measure"], self.metrics[m["denominator"]]["measure"]]
        return [m["measure"]]

    def metric_dimensions(self, metric: str) -> set:
        """Dimensions every measure of this metric can be cut by."""
        sets = [set(self.measures[x].get("dimensions", [])) for x in self.metric_measures(metric)]
        return set.intersection(*sets) if sets else set()

    # ---------- numbers ----------
    def _row_unique(self, source, column) -> bool:
        """True when a column never repeats in the source: a distinct count over it is then a plain row count."""
        k = (source, column)
        if k not in self._unique:
            s = self.sources.frame(source)[column]
            self._unique[k] = bool(s.notna().all() and s.is_unique)
        return self._unique[k]

    def _additive_by_day(self, name) -> bool:
        m = self.measures[name]
        return m["agg"] in ("sum", "count") or (m["agg"] == "count_distinct" and self._row_unique(m["source"], m["column"]))

    # ---------- exact copies of a row ----------
    def _exact_copies(self, source):
        """The user's answer about exact copies for a source (follows a join to its base table), or None."""
        seen = set()
        while source in self.sources.specs and source not in seen:
            seen.add(source)
            spec = self.sources.specs[source]
            if spec.get("exact_copies"):
                return spec["exact_copies"]
            source = spec.get("base")
        return None

    def measure_policy(self, name) -> str:
        """'every': the number counts every row whether or not copies are real (a sum, a distinct count, min, max).
        'depends': it changes with the answer (a count of rows, a mean)."""
        return "depends" if self.measures[name]["agg"] in ("count", "mean") else "every"

    def copies_policy(self, metric) -> str:
        m = self.metrics[metric]
        if m.get("kind") == "ratio":
            return "depends" if "depends" in (self.copies_policy(m["numerator"]), self.copies_policy(m["denominator"])) else "every"
        return self.measure_policy(m["measure"])

    def _reading(self, name, copies):
        """'each' or 'once': an explicit request wins; else the user's answer, for a measure that depends on it."""
        if copies:
            return copies
        if self.measure_policy(name) == "depends" and self._exact_copies(self.measures[name]["source"]) == "once":
            return "once"
        return "each"

    def copies_readings(self, metric, w, filters=None) -> "dict | None":
        """Both readings of a metric that depends on exact copies, or None for one that does not.
        {each, once, relative_difference, differ, param, reason, headline}: `differ` is true when the two differ by more
        than the `copies_second_number_min_diff` param (a second number is then worth showing)."""
        if self.copies_policy(metric) != "depends":
            return None
        each, once = self.total(metric, w, filters, copies="each"), self.total(metric, w, filters, copies="once")
        rel = abs(each - once) / abs(once) if once else float("nan")
        limit = defaults.param(self, "copies_second_number_min_diff")
        answer = next((self._exact_copies(self.measures[x]["source"]) for x in self.metric_measures(metric)), None)
        return {"each": each, "once": once, "relative_difference": rel, "differ": bool(rel > limit), "param": "copies_second_number_min_diff",
                "limit": limit, "headline": "once" if answer == "once" else "each", "answer": answer,
                "reason": defaults.PARAMS["copies_second_number_min_diff"]["source"]["note"]}

    def _daily_frame(self, name, cols, fcols, once=False):
        """Day x group table of one measure, cached: window totals become slices of it."""
        key = (name, tuple(cols), tuple(sorted((k, str(v)) for k, v in fcols.items())), once)
        if key not in self._daily:
            m = self.measures[name]
            d = self.sources.frame_once(m["source"]) if once else self.sources.frame(m["source"])
            for col, val in fcols.items():
                d = d[d[col].isin(val if isinstance(val, (list, tuple, set)) else [val])]
            if m.get("where_filled"):
                d = d[d[m["where_filled"]].notna()]
            g = d.groupby([m["date"], *cols], dropna=True)
            s = g.size() if m["agg"] != "sum" else g[m["column"]].sum()
            s = s.astype(float)
            self._daily[key] = s.unstack(cols) if cols else s.to_frame("_all")
        return self._daily[key]

    def _measure(self, name, w, by=None, filters=None, copies=None):
        m = self.measures[name]
        once = self._reading(name, copies) == "once"
        cols = [self.column(name, d) for d in (by or [])]
        fcols = {self.column(name, k): v for k, v in (filters or {}).items()}
        if self._additive_by_day(name):
            import pandas as pd
            f = self._daily_frame(name, cols, fcols, once)
            part = f.loc[(f.index >= pd.Timestamp(w[0])) & (f.index <= pd.Timestamp(w[1]))]
            if self.exclude_days:
                part = part.loc[~part.index.isin([pd.Timestamp(x) for x in self.exclude_days])]
            if not cols:
                return float(part["_all"].sum()) if len(part) else 0.0
            present = part.notna().any(axis=0)
            return part.loc[:, present].sum(axis=0)
        df = self.sources.frame_once(m["source"]) if once else self.sources.frame(m["source"])
        if self.exclude_days:
            import pandas as pd
            df = df[~df[m["date"]].isin([pd.Timestamp(x) for x in self.exclude_days])]
        return aggregate(df, m["agg"], m.get("column"), m["date"], w, cols, fcols, m.get("where_filled"))

    def excluding(self, days):
        """Context manager: leave these days out of every window until the block ends."""
        import contextlib

        @contextlib.contextmanager
        def cm():
            old = self.exclude_days
            self.exclude_days = frozenset(old | set(days))
            try:
                yield self
            finally:
                self.exclude_days = old
        return cm()

    def days_in(self, w: tuple) -> int:
        n = (w[1] - w[0]).days + 1
        return n - sum(1 for d in self.exclude_days if w[0] <= d <= w[1])

    def total(self, metric: str, w: tuple, filters=None, copies=None) -> float:
        """`copies`: 'each' counts every row, 'once' counts exact copies once; None follows the user's answer."""
        m = self.metrics[metric]
        if m.get("kind") == "ratio":
            n = self.total(m["numerator"], w, filters, copies)
            d = self.total(m["denominator"], w, filters, copies)
            return n / d if d else float("nan")
        v = float(self._measure(m["measure"], w, None, filters, copies))
        return v / max(self.days_in(w), 1) if self.per_day else v

    def rows(self, source: str, w: tuple, by=None, filters=None) -> "dict | float":
        """Row counts of a source in a window (for sample sizes and data-quality checks); never scaled per day."""
        spec = self.sources.specs[source]
        date = (spec.get("date_columns") or [None])[0]
        df = self.sources.frame(source)
        return aggregate(df, "count", None, date, w, list(by or []), filters or {})

    def source_of(self, metric: str) -> tuple:
        """(source name, date column) of a metric's first measure."""
        m = self.measures[self.metric_measures(metric)[0]]
        return m["source"], m["date"]

    def data_range(self, metric: str) -> tuple:
        src, date = self.source_of(metric)
        d = self.sources.frame(src)[date]
        return d.min().date(), d.max().date()

    def segments(self, metric: str, dim: str, base: tuple, cur: tuple, filters=None) -> dict:
        """Data shape the operators expect. Base metric: {value: (b, c)}; ratio: {value: (nb, db, nc, dc)}."""
        m = self.metrics[metric]
        if m.get("kind") == "ratio":
            num, den = m["numerator"], m["denominator"]
            parts = [self._grouped(num, dim, base, filters), self._grouped(den, dim, base, filters),
                     self._grouped(num, dim, cur, filters), self._grouped(den, dim, cur, filters)]
            keys = sorted(set().union(*[p.keys() for p in parts]), key=str)
            return {k: tuple(p.get(k, 0.0) for p in parts) for k in keys}
        b = self._grouped(metric, dim, base, filters)
        c = self._grouped(metric, dim, cur, filters)
        return {k: (b.get(k, 0.0), c.get(k, 0.0)) for k in sorted(set(b) | set(c), key=str)}

    def _grouped(self, metric, dim, w, filters):
        """dim may be a list: the keys are then the values joined with ' / ' (one cell per combination)."""
        dims = list(dim) if isinstance(dim, (list, tuple)) else [dim]
        s = self._measure(self.metrics[metric]["measure"], w, dims, filters)
        k = max(self.days_in(w), 1) if self.per_day else 1
        key = (lambda x: " / ".join(map(str, x)) if isinstance(x, tuple) else str(x))
        return {key(i): float(v) / k for i, v in s.items()}

    def series(self, metric: str, start, end, freq_days: int = 7, filters=None) -> list:
        """Consecutive non-overlapping windows ending at `end`, oldest first: [(window, value)]."""
        out = []
        b = end
        while b - dt.timedelta(days=freq_days - 1) >= start:
            a = b - dt.timedelta(days=freq_days - 1)
            out.append(((a, b), self.total(metric, (a, b), filters)))
            b = a - dt.timedelta(days=1)
        return list(reversed(out))
