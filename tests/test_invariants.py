"""Audit item 6: the arithmetic the report rests on is checked, not assumed. Synthetic data only.

(a) an identity metric1 = metric2 x metric3 holds in the slice the question asks about, not only overall;
(b) groups of an additive measure add up to the total;
(c) a distinct count cut by a dimension is not added across groups when the same id can sit in two groups.
"""

import shutil

import pandas as pd
import yaml

from aib.run import run
from aib.validate import data_problems
from aib.workspace import Workspace

import synth

WEEK = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}


def check(s, name):
    return next(c for c in s["checks"] if c["check"] == name)


def two_source_workspace(tmp_path):
    """Revenue comes from `orders`; the order count from `lines`, where 10% of the lines carry another channel label.
    Overall the identity revenue = orders x AOV holds; inside one channel it does not."""
    df = synth.orders(seed=11, per_day=40, start="2025-09-01", end="2026-10-25")
    root = synth.workspace(tmp_path, df, dims=["channel"])
    lines = df[["order_id", "order_date", "channel"]].copy()
    flip = lines.sample(frac=0.10, random_state=1).index
    lines.loc[flip, "channel"] = lines.loc[flip, "channel"].map({"a": "b", "b": "a", "c": "a"})
    lines.to_csv(root / "data" / "lines.csv", index=False)
    p = yaml.safe_load((root / "project.yaml").read_text(encoding="utf-8"))
    p["sources"]["lines"] = {"type": "csv", "path": "data/lines.csv", "date_columns": ["order_date"]}
    (root / "project.yaml").write_text(yaml.safe_dump(p), encoding="utf-8")
    m = yaml.safe_load((root / "model.yaml").read_text(encoding="utf-8"))
    m["measures"]["orders_m"] = {"source": "lines", "agg": "count", "date": "order_date", "dimensions": ["channel"]}
    # a factor that is its own measure (mean revenue per order), not revenue / orders, which would hold by construction
    m["measures"]["avg_rev_m"] = {"source": "orders", "agg": "mean", "column": "revenue", "date": "order_date",
                                  "dimensions": ["channel"], "additive_over": []}
    m["metrics"]["aov"] = {"label": "AOV", "measure": "avg_rev_m", "unit": "currency"}
    (root / "model.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    return root


def test_identity_holds_overall_in_the_two_source_workspace(tmp_path):
    ws = Workspace(two_source_workspace(tmp_path))
    w = (pd.Timestamp("2026-10-19").date(), pd.Timestamp("2026-10-25").date())
    assert data_problems(ws, w) == []


def test_identity_that_breaks_inside_the_asked_slice_blocks_the_report(tmp_path):
    ws = Workspace(two_source_workspace(tmp_path))
    s = run(ws, {**WEEK, "filters": {"channel": "a"}}, write=False)
    c = check(s, "identities_computable")
    assert not c["pass"] and "channel=a" in c["detail"]
    assert s["blocked"]


def test_identity_check_leaves_an_unfiltered_question_alone(tmp_path):
    s = run(Workspace(two_source_workspace(tmp_path)), WEEK, write=False)
    assert check(s, "identities_computable")["pass"]


def lines_workspace(tmp_path, split_orders):
    """Order lines; with split_orders, some orders have lines in two channels."""
    df = synth.orders(seed=12, per_day=30, start="2025-09-01", end="2026-10-25", dims={"channel": {"a": 0.5, "b": 0.5}})
    extra = df.sample(frac=0.2, random_state=2).copy() if split_orders else df.iloc[0:0].copy()
    extra["channel"] = extra["channel"].map({"a": "b", "b": "a"})
    extra["revenue"] = 0.0
    df = pd.concat([df, extra], ignore_index=True)
    df["line_no"] = df.groupby("order_id").cumcount() + 1
    root = synth.workspace(tmp_path, df, dims=["channel"], key=["order_id", "line_no"])
    return root


def test_a_distinct_count_that_does_not_add_across_groups_is_blocked_and_explained(tmp_path):
    ws = Workspace(lines_workspace(tmp_path, split_orders=True))
    s = run(ws, {"metric": "orders", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "dimensions": ["channel"]},
            write=False)
    c = check(s, "segments_add_up_to_total")
    assert not c["pass"]
    assert "distinct" in c["detail"] and "order_id" in c["detail"]


def test_a_distinct_count_that_does_add_up_is_not_blocked(tmp_path):
    ws = Workspace(lines_workspace(tmp_path, split_orders=False))
    s = run(ws, {"metric": "orders", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "dimensions": ["channel"]},
            write=False)
    assert check(s, "segments_add_up_to_total")["pass"]


def test_summed_groups_add_up_to_the_total(tmp_path):
    ws = Workspace(lines_workspace(tmp_path, split_orders=True))
    s = run(ws, {**WEEK, "dimensions": ["channel"]}, write=False)
    assert check(s, "segments_add_up_to_total")["pass"]
    r = s["cuts"][0]["result"]
    assert abs(sum(x["cur"] for x in r["segments"]) - ws.total("revenue", s["current"])) < 1e-6
