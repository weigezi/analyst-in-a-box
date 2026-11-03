"""Data access. Every source type turns into the same thing: a table of rows.

Adding a new kind of source (an online spreadsheet, a warehouse) means adding one loader here;
nothing else in the skill changes.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

LOADERS = {}


def loader(kind):
    def wrap(fn):
        LOADERS[kind] = fn
        return fn
    return wrap


# Words that mean "no value" to pandas by default but are real values in a business table ("None" as an offer type,
# "NULL" as an agent code). Only an empty cell is missing.
READ_AS_TEXT = {"keep_default_na": False, "na_values": [""]}
CURRENCY = re.compile(r"^\s*[-+]?\s*[$€£¥]?\s*[-+]?\d{1,3}(,\d{3})*(\.\d+)?\s*$|^\s*[-+]?\s*[$€£¥]?\s*[-+]?\d+(\.\d+)?\s*$")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})


def clean(df: pd.DataFrame, derive: list | None = None, exclude_rows: dict | None = None,
          drop_duplicates: bool = False) -> pd.DataFrame:
    """The one place a table is tidied, for intake and for every later run: header cells lose their outer spaces,
    a text column of amounts such as "$1,025.00 " becomes numbers, and the dates the workspace derived from
    several columns (see `derive_dates`) are added. Columns that are not clearly amounts are left alone."""
    stripped = {c: c.strip() for c in df.columns if isinstance(c, str) and c != c.strip()}
    taken = set(df.columns)
    # a header that would collide with another once its spaces are gone keeps its spaces
    df = df.rename(columns={c: n for c, n in stripped.items() if n not in taken and list(stripped.values()).count(n) == 1})
    for c in df.columns:
        s = df[c]
        if not (s.dtype == object or pd.api.types.is_string_dtype(s)):   # pandas 3 reads text as its own "str" type
            continue
        vals = s.dropna().astype(str)
        if len(vals) and vals.str.contains(r"[$€£¥,]", regex=True).any() and vals.map(lambda v: bool(CURRENCY.match(v))).all():
            df[c] = pd.to_numeric(s.astype(str).str.replace(r"[$€£¥,\s]", "", regex=True).replace({"nan": None, "": None}),
                                  errors="coerce")
    for d in derive or []:
        df[d["name"]] = derive_dates(df, d)
    # Cancelled, refunded or otherwise reversed rows, as named by the user at intake ({column: [values]}). They are
    # dropped here, once, so every number, every quality check and every group size sees the same table.
    for col, values in (exclude_rows or {}).items():
        if col in df.columns:
            df = df[~df[col].astype(str).isin([str(v) for v in values])]
    return df.drop_duplicates() if drop_duplicates else df


def derive_dates(df: pd.DataFrame, spec: dict) -> pd.Series:
    """A real date built from the columns of a composite date: year + month (the first of the month), year + month
    name + day, or a yyyymmdd whole number."""
    k, cols = spec["kind"], spec["columns"]
    if k == "year_month":
        y, m = pd.to_numeric(df[cols[0]], errors="coerce"), pd.to_numeric(df[cols[1]], errors="coerce")
        return pd.to_datetime(dict(year=y, month=m, day=1), errors="coerce")
    if k == "year_monthname_day":
        m = df[cols[1]].astype(str).str.strip().str.lower().map(MONTHS)
        return pd.to_datetime(dict(year=pd.to_numeric(df[cols[0]], errors="coerce"), month=m,
                                   day=pd.to_numeric(df[cols[2]], errors="coerce")), errors="coerce")
    if k == "year_month_day":
        return pd.to_datetime(dict(year=pd.to_numeric(df[cols[0]], errors="coerce"), month=pd.to_numeric(df[cols[1]], errors="coerce"),
                                   day=pd.to_numeric(df[cols[2]], errors="coerce")), errors="coerce")
    if k == "yyyymmdd":
        return pd.to_datetime(df[cols[0]].astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    raise ValueError(f"unknown composite date kind: {k}")


@loader("csv")
def _csv(spec, root):
    opts = {**READ_AS_TEXT, **spec.get("options", {})}
    return clean(pd.read_csv(root / spec["path"], **opts), spec.get("derive_dates"), spec.get("exclude_rows"),
                 spec.get("drop_duplicates", False))


@loader("excel")
def _excel(spec, root):
    opts = {**READ_AS_TEXT, **spec.get("options", {})}
    return clean(pd.read_excel(root / spec["path"], sheet_name=spec.get("sheet", 0), **opts), spec.get("derive_dates"),
                 spec.get("exclude_rows"), spec.get("drop_duplicates", False))


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
              window: tuple, by: list | None = None, filters: dict | None = None,
              where_filled: str | None = None) -> pd.Series | float:
    """Aggregate one measure over a date window [start, end] inclusive, optionally grouped."""
    start, end = pd.Timestamp(window[0]), pd.Timestamp(window[1])
    d = df[(df[date_col] >= start) & (df[date_col] <= end)]
    if where_filled:
        d = d[d[where_filled].notna()]
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
