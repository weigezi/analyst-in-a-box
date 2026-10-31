"""A small order generator for tests: a plain shop whose only causes are the ones a test plants.

Every test that needs dirty or tricky data builds it here, so the planted truth is in the test itself.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

DIMS = {"channel": {"a": 0.5, "b": 0.3, "c": 0.2}, "region": {"x": 0.5, "y": 0.3, "z": 0.2},
        "customer_type": {"new": 0.3, "returning": 0.7}}
PRICE = {"a": 100.0, "b": 100.0, "c": 100.0}


def orders(seed=1, start="2025-01-01", end="2026-10-25", per_day=300, dims=None, price=None, effects=(),
           price_by=None, customers=0, sigma=0.4) -> pd.DataFrame:
    """effects: [{where: {dim: value}, start, end, orders: x, price: y}] multiply volume or price in a slice.
    price_by: (dimension, {value: mean price}); default every row has mean price 100.
    customers: when > 0, each row gets a customer_id drawn from that many customers."""
    rng = np.random.default_rng(seed)
    dims = dims or DIMS
    days = pd.date_range(start, end, freq="D")
    names = list(dims)
    cells = list(itertools.product(*[list(dims[d]) for d in names]))
    share = np.array([np.prod([dims[d][v] for d, v in zip(names, c)]) for c in cells])
    lam = per_day * np.ones((len(days), 1)) * share[None, :]
    pmult = np.ones_like(lam)
    for e in effects:
        dm = np.ones(len(days), dtype=bool)
        if e.get("start"):
            dm &= days >= pd.Timestamp(e["start"])
        if e.get("end"):
            dm &= days <= pd.Timestamp(e["end"])
        cm = np.array([all(c[names.index(k)] == v for k, v in (e.get("where") or {}).items()) for c in cells])
        lam[np.ix_(dm, cm)] *= e.get("orders", 1.0)
        pmult[np.ix_(dm, cm)] *= e.get("price", 1.0)
    counts = rng.poisson(lam)
    di, ci = np.nonzero(counts)
    reps = counts[di, ci]
    di, ci = np.repeat(di, reps), np.repeat(ci, reps)
    df = pd.DataFrame([cells[i] for i in ci], columns=names)
    df.insert(0, "order_date", days[di].strftime("%Y-%m-%d"))
    if price_by:
        dim, means = price_by
        mean = df[dim].map(means).to_numpy(dtype=float)
    else:
        mean = np.full(len(df), 100.0)
    df["revenue"] = (mean * pmult[di, ci] * rng.lognormal(-sigma ** 2 / 2, sigma, len(df))).round(2)
    df.insert(0, "order_id", [f"o{i}" for i in range(len(df))])
    if customers:
        df["customer_id"] = [f"c{x}" for x in rng.integers(0, customers, len(df))]
    return df


def workspace(root: Path, df: pd.DataFrame, dims=None, priorities=None, key="order_id", project_extra=None,
              rules_extra=None, world=None, calendar=None) -> Path:
    """Write a minimal workspace around one orders table, with the skill's default rules."""
    from aib import defaults
    root = Path(root)
    (root / "data").mkdir(parents=True, exist_ok=True)
    df.to_csv(root / "data" / "orders.csv", index=False)
    dims = dims or [d for d in DIMS if d in df.columns]
    src = {"type": "csv", "path": "data/orders.csv", "date_columns": ["order_date"]}
    if key:
        src["key"] = key
    project = {"name": "synthetic", "language": "en", "sources": {"orders": src}}
    if calendar is not None:
        (root / "external").mkdir(exist_ok=True)
        pd.DataFrame(calendar).to_csv(root / "external" / "calendar.csv", index=False)
        project["external"] = {"calendar": {"type": "csv", "path": "external/calendar.csv", "role": "calendar"}}
    project.update(project_extra or {})
    model = {
        "measures": {
            "revenue_m": {"source": "orders", "agg": "sum", "column": "revenue", "date": "order_date", "dimensions": dims},
            "orders_m": {"source": "orders", "agg": "count_distinct", "column": "order_id", "date": "order_date",
                         "dimensions": dims, "additive_over": dims},
        },
        "metrics": {
            "revenue": {"label": "Revenue", "measure": "revenue_m", "unit": "currency"},
            "orders": {"label": "Orders", "measure": "orders_m", "unit": "count"},
            "aov": {"label": "AOV", "kind": "ratio", "numerator": "revenue", "denominator": "orders", "unit": "currency"},
        },
        "identities": [{"id": "revenue_by_orders", "left": "revenue", "factors": ["orders", "aov"], "operator": "multiply",
                        "source": {"kind": "formula"}, "status": "confirmed"}],
        "dimensions": {d: {"label": d, "column": d} for d in dims},
        "priorities": priorities or {},
        "comparisons": [],
    }
    rules = defaults.rules()
    for k, v in (rules_extra or {}).items():
        rules["params"][k] = {"value": v, "source": {"kind": "demo_setting", "note": "test setting"}, "status": "confirmed"}
    ents = [{"id": f"{d}:{v}", "type": d, "dimension": d, "key": str(v), "label": str(v), "source": {"kind": "data"},
             "status": "confirmed"} for d in dims for v in sorted(map(str, df[d].unique()))]
    w = {"entities": ents, "relations": [], "mechanisms": [], "events": [], "actions": []}
    for k, v in (world or {}).items():
        w[k] = v
    for name, data in (("project", project), ("model", model), ("rules", rules), ("world", w)):
        (root / f"{name}.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return root
