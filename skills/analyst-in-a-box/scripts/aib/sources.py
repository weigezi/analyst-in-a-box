"""Data access. Every source type turns into the same thing: a table of rows.

Adding a new kind of source (an online spreadsheet, a warehouse) means adding one loader here;
nothing else in the skill changes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

LOADERS = {}


def loader(kind):
    def wrap(fn):
        LOADERS[kind] = fn
        return fn
    return wrap


@loader("csv")
def _csv(spec, root):
    return pd.read_csv(root / spec["path"], **spec.get("options", {}))


@loader("excel")
def _excel(spec, root):
    return pd.read_excel(root / spec["path"], sheet_name=spec.get("sheet", 0), **spec.get("options", {}))


@loader("sqlite")
def _sqlite(spec, root):
    con = sqlite3.connect(root / spec["path"])
    try:
        sql = spec.get("query") or f'SELECT * FROM "{spec["table"]}"'
        return pd.read_sql_query(sql, con)
    finally:
        con.close()


@loader("duckdb")
def _duckdb(spec, root):
    import duckdb  # optional dependency, only needed for this source type
    con = duckdb.connect(str(root / spec["path"]), read_only=True)
    try:
        sql = spec.get("query") or f'SELECT * FROM "{spec["table"]}"'
        return con.execute(sql).df()
    finally:
        con.close()


class Sources:
    """Loads each named source once and caches it."""

    def __init__(self, specs: dict, root: Path):
        self.specs = specs or {}
        self.root = Path(root)
        self._cache: dict = {}

    def names(self):
        return list(self.specs)

    def frame(self, name: str) -> pd.DataFrame:
        if name not in self._cache:
            spec = self.specs.get(name)
            if spec is None:
                raise KeyError(f"unknown source '{name}'")
            kind = spec.get("type")
            if kind == "join":
                df = self._join(name, spec)
            elif kind not in LOADERS:
                raise ValueError(f"source '{name}': unsupported type '{kind}' (supported: {', '.join([*LOADERS, 'join'])})")
            else:
                df = LOADERS[kind](spec, self.root)
            if spec.get("rename"):
                df = df.rename(columns=spec["rename"])
            for col in spec.get("date_columns", []):
                df[col] = pd.to_datetime(df[col]).dt.normalize()
            self._cache[name] = df
        return self._cache[name]

    def _join(self, name, spec):
        """A base table with attribute columns looked up from other tables by a key.

        spec: {type: join, base: <source>, joins: [{source: <source>, on: {base_col: key_col}, columns: [...]}]}.
        Each lookup key must be unique in its table, so every base row stays exactly one row; a base value with no
        match gets empty attributes (the data-quality step's reconciliation then shows it)."""
        df = self.frame(spec["base"]).copy()
        n = len(df)
        for j in spec.get("joins", []):
            (left, right), = j["on"].items()
            other = self.frame(j["source"])
            if not other[right].is_unique:
                raise ValueError(f"source '{name}': key '{right}' repeats in '{j['source']}'; a lookup needs one row per key")
            cols = [c for c in j.get("columns", []) if c != right]
            look = other[[right, *cols]]
            if left != right:
                look = look.rename(columns={right: left})
            df = df.merge(look, on=left, how="left", validate="many_to_one")
        if len(df) != n:
            raise ValueError(f"source '{name}': the lookups changed the number of rows ({n} -> {len(df)})")
        return df


AGGS = {"sum", "count", "count_distinct", "mean", "min", "max"}


def aggregate(df: pd.DataFrame, agg: str, column: str | None, date_col: str,
              window: tuple, by: list | None = None, filters: dict | None = None) -> pd.Series | float:
    """Aggregate one measure over a date window [start, end] inclusive, optionally grouped."""
    start, end = pd.Timestamp(window[0]), pd.Timestamp(window[1])
    d = df[(df[date_col] >= start) & (df[date_col] <= end)]
    for col, val in (filters or {}).items():
        d = d[d[col].isin(val if isinstance(val, (list, tuple, set)) else [val])]
    by = list(by or [])

    def agg_fn(frame):
        if agg == "count":
            return len(frame)
        series = frame[column]
        return {"sum": series.sum, "count_distinct": series.nunique, "mean": series.mean,
                "min": series.min, "max": series.max}[agg]()

    if not by:
        return float(agg_fn(d)) if len(d) or agg in ("sum", "count", "count_distinct") else float("nan")
    if agg == "count":
        return d.groupby(by).size().astype(float)
    g = d.groupby(by)[column]
    return {"sum": g.sum, "count_distinct": g.nunique, "mean": g.mean, "min": g.min, "max": g.max}[agg]().astype(float)
