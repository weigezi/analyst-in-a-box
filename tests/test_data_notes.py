"""Audit items 2 to 5 and the stranger test: what the data looks like is said in the report, never guessed away.

Synthetic data only. Each test plants one defect and checks that it is named with its count or share.
"""

import numpy as np
import pandas as pd
import yaml

from aib.run import run
from aib.workspace import Workspace

import synth

WEEK = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}


def make(tmp_path, df, **kw):
    return Workspace(synth.workspace(tmp_path, df, **kw))


def base_orders(seed=7, per_day=40, **kw):
    return synth.orders(seed=seed, per_day=per_day, start="2025-06-01", end="2026-10-25", **kw)


def check(s, name):
    return next(c for c in s["quality"]["checks"] if c["check"] == name)


def note(s, kind):
    return next((n for n in s["quality"].get("notes", []) if n["note"] == kind), None)


# ---------- item 2: monthly data, weekly window ----------

def monthly_workspace(tmp_path, identity=True):
    df = base_orders(per_day=3)
    df["order_date"] = pd.to_datetime(df["order_date"]).dt.strftime("%Y-%m-01")
    root = synth.workspace(tmp_path, df)
    if not identity:
        m = yaml.safe_load((root / "model.yaml").read_text(encoding="utf-8"))
        m["identities"] = []
        (root / "model.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    return Workspace(root)


def test_monthly_source_with_a_weekly_window_and_an_identity_says_so_instead_of_nan(tmp_path):
    s = run(monthly_workspace(tmp_path), WEEK, write=False)
    assert "monthly" in s["problems"][0] and "whole months" in s["problems"][0]


def test_monthly_source_with_a_weekly_window_says_it_is_monthly(tmp_path):
    out = tmp_path / "out"
    s = run(monthly_workspace(tmp_path, identity=False), WEEK, out_dir=out)
    c = check(s, "row_ratio")
    assert c["status"] == "fail" and c["sources"][0]["monthly"] is True and c["sources"][0]["whole_months"] is False
    assert s["quality"]["suspect"]
    en = (out / "report.en.md").read_text(encoding="utf-8")
    zh = (out / "report.zh.md").read_text(encoding="utf-8")
    assert "monthly" in en and "whole months" in en
    assert "按月" in zh and "整月" in zh


def test_monthly_source_with_whole_months_is_not_flagged_as_monthly_mismatch(tmp_path):
    s = run(monthly_workspace(tmp_path, identity=False), {"metric": "revenue", "current": ["2026-09-01", "2026-09-30"], "base": "yoy"}, write=False)
    src = check(s, "row_ratio")["sources"][0]
    assert src["monthly"] is True and src["whole_months"] is True


# ---------- item 3: a blank dimension value ----------

def test_blank_dimension_rows_are_named_when_segments_fall_short(tmp_path):
    df = base_orders()
    rng = np.random.default_rng(1)
    cur = (df["order_date"] >= "2026-10-19") & (df["order_date"] <= "2026-10-25")
    blank = cur & (rng.random(len(df)) < 0.15)
    df.loc[blank, "channel"] = None
    share = blank.sum() / cur.sum()
    out = tmp_path / "out"
    s = run(make(tmp_path, df), {**WEEK, "dimensions": ["channel"]}, out_dir=out)
    c = next(x for x in s["checks"] if x["check"] == "segments_add_up_to_total")
    assert not c["pass"]
    assert "channel" in c["detail"] and "blank" in c["detail"] and f"{share:.1%}" in c["detail"]
    assert "channel" in (out / "report.en.md").read_text(encoding="utf-8").split("Pre-delivery checks failed")[1][:600]


# ---------- item 4: blank cells in a summed amount ----------

def test_blank_amounts_behind_the_headline_are_stated(tmp_path):
    df = base_orders()
    rng = np.random.default_rng(2)
    cur = (df["order_date"] >= "2026-10-19") & (df["order_date"] <= "2026-10-25")
    gone = cur & (rng.random(len(df)) < 0.10)
    df.loc[gone, "revenue"] = None
    out = tmp_path / "out"
    s = run(make(tmp_path, df), WEEK, out_dir=out)
    n = note(s, "blank_amounts")
    assert n and n["column"] == "revenue" and n["blank"] == int(gone.sum()) and n["rows"] == int(cur.sum())
    assert not s["quality"]["suspect"] and not s["blocked"]
    en = (out / "report.en.md").read_text(encoding="utf-8")
    assert "blank" in en.split("Data note")[1][:300] and f"{gone.sum() / cur.sum():.1%}" in en
    assert "空" in (out / "report.zh.md").read_text(encoding="utf-8")


def test_no_blank_amounts_means_no_note(tmp_path):
    s = run(make(tmp_path, base_orders()), WEEK, write=False)
    assert note(s, "blank_amounts") is None


# ---------- item 5: a summed column that looks like a rate or a stock ----------

def test_a_summed_column_of_rates_is_noted_with_its_evidence(tmp_path):
    df = base_orders()
    df["revenue"] = np.random.default_rng(3).uniform(0.05, 0.95, len(df)).round(3)
    s = run(make(tmp_path, df), WEEK, write=False)
    n = note(s, "looks_like_rate")
    assert n and n["column"] == "revenue" and n["max"] < 1 and n["min"] > 0
    assert not s["quality"]["suspect"]


def test_a_summed_column_that_repeats_per_entity_is_noted_as_a_possible_stock(tmp_path):
    df = base_orders(per_day=10, customers=50)
    level = {f"c{i}": 100.0 + 7 * i for i in range(50)}
    df["revenue"] = df["customer_id"].map(level)
    s = run(make(tmp_path, df), WEEK, write=False)
    n = note(s, "repeats_per_entity")
    assert n and n["column"] == "revenue" and n["entity"] == "customer_id" and n["share_constant"] >= 0.9


def test_an_ordinary_amount_gets_neither_note(tmp_path):
    s = run(make(tmp_path, base_orders(customers=50)), WEEK, write=False)
    assert note(s, "looks_like_rate") is None and note(s, "repeats_per_entity") is None


# ---------- stranger test: zero-night and zero-rate rows ----------

def test_rows_with_a_zero_amount_are_counted_and_named_without_blocking(tmp_path):
    df = base_orders()
    cur = (df["order_date"] >= "2026-10-19") & (df["order_date"] <= "2026-10-25")
    idx = df.index[cur][:12]
    df.loc[idx, "revenue"] = 0.0
    s = run(make(tmp_path, df), WEEK, write=False)
    n = note(s, "zero_amounts")
    assert n and n["column"] == "revenue" and n["zero"] == 12 and n["rows"] == int(cur.sum())
    assert not s["quality"]["suspect"] and not s["blocked"]
