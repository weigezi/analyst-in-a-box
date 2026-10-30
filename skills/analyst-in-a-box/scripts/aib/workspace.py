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
    """yoy: same weekdays one year earlier (364 days); pop: the window right before, same length."""
    a, b = w
    if how == "yoy":
        return (a - dt.timedelta(days=364), b - dt.timedelta(days=364))
    if how == "pop":
        n = (b - a).days + 1
        return (a - dt.timedelta(days=n), b - dt.timedelta(days=n))
    raise ValueError(f"unknown base '{how}'")


class Workspace:
    def __init__(self, root):
        self.root = Path(root)
        self.project = _read(self.root / "project.yaml", {})
        self.model = _read(self.root / "model.yaml", {})
        self.rules = _read(self.root / "rules.yaml", {})
        self.world = _read(self.root / "world.yaml", {})
        self.sources = Sources(self.project.get("sources", {}), self.root)
        self.external = Sources(self.project.get("external", {}), self.root)

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
    def _measure(self, name, w, by=None, filters=None):
        m = self.measures[name]
        df = self.sources.frame(m["source"])
        cols = [self.column(name, d) for d in (by or [])]
        fcols = {self.column(name, k): v for k, v in (filters or {}).items()}
        return aggregate(df, m["agg"], m.get("column"), m["date"], w, cols, fcols)

    def total(self, metric: str, w: tuple, filters=None) -> float:
        m = self.metrics[metric]
        if m.get("kind") == "ratio":
            n = self.total(m["numerator"], w, filters)
            d = self.total(m["denominator"], w, filters)
            return n / d if d else float("nan")
        return float(self._measure(m["measure"], w, None, filters))

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
        s = self._measure(self.metrics[metric]["measure"], w, [dim], filters)
        return {str(k): float(v) for k, v in s.items()}

    def series(self, metric: str, start, end, freq_days: int = 7, filters=None) -> list:
        """Consecutive non-overlapping windows ending at `end`, oldest first: [(window, value)]."""
        out = []
        b = end
        while b - dt.timedelta(days=freq_days - 1) >= start:
            a = b - dt.timedelta(days=freq_days - 1)
            out.append(((a, b), self.total(metric, (a, b), filters)))
            b = a - dt.timedelta(days=1)
        return list(reversed(out))
