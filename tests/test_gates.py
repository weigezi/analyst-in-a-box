"""Audit item 1: a group's size is the number of things the metric is about (orders), not the number of rows.

A seller with 63 order lines but 28 orders must not pass a 30-order gate. Synthetic data only.
"""

import pandas as pd

from aib.run import run
from aib.workspace import Workspace

import synth

WEEK = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "dimensions": ["channel"],
        "drill_when_usual": True}


def lines_workspace(tmp_path, lines_per_c_order=3):
    """A small shop where every channel-c order has several lines, so c has 3x more rows than orders."""
    df = synth.orders(seed=3, per_day=40, effects=[{"where": {"channel": "c"}, "start": "2026-10-19", "end": "2026-10-25", "orders": 0.3}])
    df["line_no"] = 1
    extra = []
    for k in range(2, lines_per_c_order + 1):
        c = df[df["channel"] == "c"].copy()
        c["line_no"] = k
        extra.append(c)
    df = pd.concat([df, *extra], ignore_index=True)
    df["revenue"] = df["revenue"] / df.groupby("order_id")["line_no"].transform("count")
    root = synth.workspace(tmp_path, df, key=["order_id", "line_no"])
    return root, df


def test_group_size_counts_orders_not_lines(tmp_path):
    root, df = lines_workspace(tmp_path)
    ws = Workspace(root)
    w = (pd.Timestamp("2026-10-19").date(), pd.Timestamp("2026-10-25").date())
    size, unit = ws.group_size("revenue_m", w, ["channel"])
    cur = df[(df["order_date"] >= "2026-10-19") & (df["order_date"] <= "2026-10-25") & (df["channel"] == "c")]
    assert unit == "order_id"
    assert size["c"] == cur["order_id"].nunique()
    assert len(cur) > 2.5 * size["c"]          # the rows would have said three times as many


def test_a_group_with_many_lines_but_few_orders_is_too_small_to_name(tmp_path):
    root, df = lines_workspace(tmp_path)
    s = run(Workspace(root), WEEK, write=False)
    cut = s["cuts"][0]
    cur = df[(df["order_date"] >= "2026-10-19") & (df["order_date"] <= "2026-10-25") & (df["channel"] == "c")]
    assert cut["result"]["top1_key"] == "c"
    assert cut["gate"]["top1_n"] == cur["order_id"].nunique() < 30 <= len(cur)
    assert cut["decision"]["then"]["reason"] == "top_group_too_small"
    assert cut["gate"]["size_unit"] == "order_id"


def test_the_report_says_what_the_size_counts(tmp_path):
    root, _ = lines_workspace(tmp_path)
    out = tmp_path / "out"
    run(Workspace(root), WEEK, out_dir=out)
    assert "order_id" in (out / "report.en.md").read_text(encoding="utf-8").split("too small to name")[1][:120]
    assert "order_id" in (out / "report.zh.md").read_text(encoding="utf-8").split("样本太少")[1][:120]


def test_without_a_counted_entity_or_key_the_size_is_rows(tmp_path):
    df = synth.orders(seed=4, per_day=20, start="2026-09-01", end="2026-10-25")
    root = synth.workspace(tmp_path, df, key=None)
    import yaml
    m = yaml.safe_load((root / "model.yaml").read_text(encoding="utf-8"))
    m["measures"].pop("orders_m")
    m["metrics"] = {"revenue": m["metrics"]["revenue"]}
    m["identities"] = []
    (root / "model.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    ws = Workspace(root)
    w = (pd.Timestamp("2026-10-19").date(), pd.Timestamp("2026-10-25").date())
    size, unit = ws.group_size("revenue_m", w, ["channel"])
    assert unit == "rows" and float(size.sum()) == len(df[df["order_date"] >= "2026-10-19"])


# ---------- findings from the stranger test: a short history is not a quiet number ----------

SHORT = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "pop", "dimensions": ["channel"]}


def short_history_workspace(tmp_path):
    df = synth.orders(seed=5, per_day=60, start="2026-10-05", end="2026-10-25",
                      effects=[{"where": {"channel": "a"}, "start": "2026-10-19", "end": "2026-10-25", "orders": 3.0}])
    return synth.workspace(tmp_path, df)


def test_a_history_of_one_period_does_not_call_the_number_quiet(tmp_path):
    s = run(Workspace(short_history_workspace(tmp_path)), SHORT, write=False)
    assert s["qualify"]["history_n"] == 1 and s["qualify"]["robust_z"] is None
    assert s["cuts"][0]["decision"]["then"]["reason"] != "whole_number_within_usual_range"
    assert s["cuts"][0]["gate"]["overall_quiet"] is False


def test_the_report_makes_one_statement_about_unusualness(tmp_path):
    out = tmp_path / "out"
    run(Workspace(short_history_workspace(tmp_path)), SHORT, out_dir=out)
    en = (out / "report.en.md").read_text(encoding="utf-8")
    assert "Not enough history" in en
    assert "within its usual range" not in en
    zh = (out / "report.zh.md").read_text(encoding="utf-8")
    assert "历史太短" in zh and "整体在通常范围内" not in zh


def test_a_segment_carrying_most_of_the_movement_is_named_even_without_history(tmp_path):
    s = run(Workspace(short_history_workspace(tmp_path)), SHORT, write=False)
    cut = s["cuts"][0]
    assert cut["result"]["top1_key"] == "a" and cut["gate"]["top1_excess"] > 0.6
    assert cut["decision"]["then"]["action"] == "drill"
