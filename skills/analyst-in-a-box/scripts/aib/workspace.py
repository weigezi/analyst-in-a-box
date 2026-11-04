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

    def _daily_frame(self, name, cols, fcols):
        """Day x group table of one measure, cached: window totals become slices of it."""
        key = (name, tuple(cols), tuple(sorted((k, str(v)) for k, v in fcols.items())))
        if key not in self._daily:
            m = self.measures[name]
            d = self.sources.frame(m["source"])
            for col, val in fcols.items():
                d = d[d[col].isin(val if isinstance(val, (list, tuple, set)) else [val])]
            if m.get("where_filled"):
                d = d[d[m["where_filled"]].notna()]
            g = d.groupby([m["date"], *cols], dropna=True)
            s = g.size() if m["agg"] != "sum" else g[m["column"]].sum()
            s = s.astype(float)
            self._daily[key] = s.unstack(cols) if cols else s.to_frame("_all")
        return self._daily[key]

    def _measure(self, name, w, by=None, filters=None):
        m = self.measures[name]
        cols = [self.column(name, d) for d in (by or [])]
        fcols = {self.column(name, k): v for k, v in (filters or {}).items()}
        if self._additive_by_day(name):
            import pandas as pd
            f = self._daily_frame(name, cols, fcols)
            part = f.loc[(f.index >= pd.Timestamp(w[0])) & (f.index <= pd.Timestamp(w[1]))]
            if self.exclude_days:
                part = part.loc[~part.index.isin([pd.Timestamp(x) for x in self.exclude_days])]
            if not cols:
                return float(part["_all"].sum()) if len(part) else 0.0
            present = part.notna().any(axis=0)
            return part.loc[:, present].sum(axis=0)
        df = self.sources.frame(m["source"])
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

    def total(self, metric: str, w: tuple, filters=None) -> float:
        m = self.metrics[metric]
        if m.get("kind") == "ratio":
            n = self.total(m["numerator"], w, filters)
            d = self.total(m["denominator"], w, filters)
            return n / d if d else float("nan")
        v = float(self._measure(m["measure"], w, None, filters))
        return v / max(self.days_in(w), 1) if self.per_day else v

    def rows(self, source: str, w: tuple, by=None, filters=None) -> "dict | float":
        """Row counts of a source in a window (for sample sizes and data-quality checks); never scaled per day."""
        spec = self.sources.specs[source]
        date = (spec.get("date_columns") or [None])[0]
        df = self.sources.frame(source)
        return aggregate(df, "count", None, date, w, list(by or []), filters or {})

    def group_size(self, measure: str, w: tuple, by=None, filters=None) -> tuple:
        """(size per group, unit) behind a measure in a window: how many of the things it is about, not how many rows.

        The unit is, in order: the measure's own counted column; else the finest counted column of another measure on
        the same source (an orders measure over an order-lines table); else the source's declared key; else 'rows'.
        Same window, filters, blank handling and excluded days as the measure itself."""
        import pandas as pd
        m = self.measures[measure]
        d = self.sources.frame(m["source"])
        d = d[(d[m["date"]] >= pd.Timestamp(w[0])) & (d[m["date"]] <= pd.Timestamp(w[1]))]
        if m.get("where_filled"):
            d = d[d[m["where_filled"]].notna()]
        if self.exclude_days:
            d = d[~d[m["date"]].isin([pd.Timestamp(x) for x in self.exclude_days])]
        for k, v in (filters or {}).items():
            d = d[d[self.column(measure, k)].isin(v if isinstance(v, (list, tuple, set)) else [v])]
        cols = [self.column(measure, x) for x in (by or [])]
        unit = self._count_unit(m)
        if unit is None:
            return (d.groupby(cols).size().astype(float) if cols else float(len(d))), "rows"
        if cols:
            return d.drop_duplicates([*unit, *cols]).groupby(cols).size().astype(float), "+".join(unit)
        return float(len(d.drop_duplicates(unit))), "+".join(unit)

    def _count_unit(self, m: dict):
        """Columns whose distinct values a group's size counts, or None for plain rows."""
        if m["agg"] == "count_distinct":
            return [m["column"]]
        frame = self.sources.frame(m["source"])
        cands = [x["column"] for x in self.measures.values()
                 if x["source"] == m["source"] and x["agg"] == "count_distinct" and x["column"] in frame.columns]
        key = self.sources.specs[m["source"]].get("key")
        key = [key] if isinstance(key, str) else list(key or [])
        if len(key) == 1 and key[0] in frame.columns:
            cands.append(key[0])
        if cands:
            return [max(dict.fromkeys(cands), key=lambda c: frame[c].nunique())]
        return key if key and all(k in frame.columns for k in key) else None

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
