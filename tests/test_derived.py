"""Derived columns (a unit price times a quantity, a sum of two columns) and the guard against joins that bring in a
column the table already has.

Every table is invented here (seed 5); nothing is read from outside tmp_path.
"""

import json

import numpy as np
import pandas as pd
import pytest

from aib import intake, sources
from aib.workspace import Workspace


def _rng():
    return np.random.default_rng(5)


# ---------- the loader step ----------

def _frame():
    return pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10, 20, 30], "c": [0.5, 0.5, np.nan]})


def test_add_mul_and_sub_make_new_columns_and_leave_the_old_ones():
    out = sources.clean(_frame(), derive_columns=[{"name": "ab", "op": "add", "columns": ["a", "b"]},
                                                  {"name": "a_b", "op": "mul", "columns": ["a", "b"]},
                                                  {"name": "b_a", "op": "sub", "columns": ["b", "a"]}])
    assert out["ab"].tolist() == [11, 22, 33] and out["a_b"].tolist() == [10, 40, 90] and out["b_a"].tolist() == [9, 18, 27]
    assert out["a"].tolist() == [1.0, 2.0, 3.0]


def test_a_derived_column_can_use_an_earlier_derived_column():
    out = sources.clean(_frame(), derive_columns=[{"name": "ab", "op": "add", "columns": ["a", "b"]},
                                                  {"name": "x", "op": "mul", "columns": ["c", "ab"]}])
    assert out["x"].tolist()[:2] == [5.5, 11.0] and np.isnan(out["x"].iloc[2])


@pytest.mark.parametrize("spec,word", [
    ({"name": "x", "op": "__import__('os').system('true')", "columns": ["a", "b"]}, "op"),
    ({"name": "x", "op": "mul", "columns": ["a", "nope"]}, "nope"),
    ({"name": "a", "op": "add", "columns": ["a", "b"]}, "already"),
    ({"name": "x", "op": "sub", "columns": ["a", "b", "c"]}, "two"),
])
def test_a_derived_column_that_cannot_be_built_stops_with_a_message(spec, word):
    with pytest.raises(ValueError, match=word):
        sources.clean(_frame(), derive_columns=[spec])


def test_a_text_column_cannot_be_derived_from():
    f = _frame()
    f["t"] = ["x", "y", "z"]
    with pytest.raises(ValueError, match="t"):
        sources.clean(f, derive_columns=[{"name": "x", "op": "add", "columns": ["a", "t"]}])


def test_the_csv_loader_applies_derive_columns(tmp_path):
    _frame().to_csv(tmp_path / "t.csv", index=False)
    s = sources.Sources({"t": {"type": "csv", "path": "t.csv", "derive_columns": [{"name": "ab", "op": "mul", "columns": ["a", "b"]}]}}, tmp_path)
    assert s.frame("t")["ab"].tolist() == [10, 40, 90]


# ---------- the join guard ----------

def test_a_join_that_would_bring_in_a_column_the_table_already_has_stops(tmp_path):
    pd.DataFrame({"order_id": [1, 2, 3], "d": ["2025-01-01"] * 3, "price": [10.0, 20.0, 30.0]}).to_csv(tmp_path / "orders.csv", index=False)
    pd.DataFrame({"item_id": [1, 2, 3, 4], "order_id": [1, 1, 2, 3], "price": [4.0, 6.0, 20.0, 30.0]}).to_csv(tmp_path / "items.csv", index=False)
    specs = {"items": {"type": "csv", "path": "items.csv"}, "orders": {"type": "csv", "path": "orders.csv", "key": "order_id"},
             "both": {"type": "join", "base": "items", "joins": [{"source": "orders", "on": {"order_id": "order_id"}, "columns": ["d", "price"]}]}}
    with pytest.raises(ValueError, match="price"):
        sources.Sources(specs, tmp_path).frame("both")


def test_a_join_without_a_clash_still_works(tmp_path):
    pd.DataFrame({"order_id": [1, 2, 3], "d": ["2025-01-01"] * 3}).to_csv(tmp_path / "orders.csv", index=False)
    pd.DataFrame({"item_id": [1, 2, 3, 4], "order_id": [1, 1, 2, 3], "price": [4.0, 6.0, 20.0, 30.0]}).to_csv(tmp_path / "items.csv", index=False)
    specs = {"items": {"type": "csv", "path": "items.csv"}, "orders": {"type": "csv", "path": "orders.csv", "key": "order_id"},
             "both": {"type": "join", "base": "items", "joins": [{"source": "orders", "on": {"order_id": "order_id"}, "columns": ["d"]}]}}
    out = sources.Sources(specs, tmp_path).frame("both")
    assert len(out) == 4 and "d" in out.columns


# ---------- intake: a unit price and a sum of two columns ----------

def _stays(n=700):
    rng = _rng()
    day = rng.integers(1, 29, n)
    arrive = pd.DataFrame({"hotel": rng.choice(["City", "Resort"], n, p=[0.6, 0.4]),
                           "arrival_year": rng.choice([2015, 2016], n), "arrival_month": rng.choice(["January", "February", "March"], n),
                           "arrival_day": np.where(day < 13, day + 13, day),
                           "weekend_nights": rng.integers(0, 3, n), "week_nights": rng.integers(0, 6, n),
                           "rate": rng.uniform(40, 220, n).round(2), "status": rng.choice(["Check-Out", "Canceled", "No-Show"], n, p=[0.7, 0.25, 0.05])})
    return arrive


def _init(tmp_path, frame):
    folder = tmp_path / "t"
    folder.mkdir(exist_ok=True)
    frame.to_csv(folder / "stays.csv", index=False)
    return intake.init([folder / "stays.csv"], tmp_path / "ws", lang="en")


def _q(d, qid):
    return next(q for q in d["questions"] if q["id"] == qid)


def _answers(d, **extra):
    ans = {q["id"]: "skip" for q in d["questions"] if q["id"].startswith("role:")}
    ans.update(date_column="composite:arrival_year+arrival_month+arrival_day", dimensions=["hotel"],
               reversal_column="status", **{"reversal_values:status": ["Canceled", "No-Show"]})
    ans.update(extra)
    return ans


def _kept(frame):
    k = frame[frame.status == "Check-Out"]
    return k, k.weekend_nights + k.week_nights


def test_the_unit_price_questions_are_asked_for_a_table_with_a_decimal_and_a_whole_number_column(tmp_path):
    d = _init(tmp_path, _stays())
    assert _q(d, "unit_price")["options"][:1] == ["rate"] and "none" in _q(d, "unit_price")["options"]
    assert set(_q(d, "sum_columns")["options"]) == {"weekend_nights", "week_nights"}
    times = [o["value"] if isinstance(o, dict) else o for o in _q(d, "unit_price_times")["options"]]
    assert "sum_columns" in times and "week_nights" in times


def test_the_role_question_of_a_decimal_column_offers_unit_price_first(tmp_path):
    d = _init(tmp_path, _stays())
    opts = [o["value"] for o in _q(d, "role:rate")["options"]]
    assert opts[0] == "unit_price" and "amount" in opts
    assert "unit_price" not in [o["value"] for o in _q(d, "role:week_nights")["options"]]


def test_room_revenue_is_the_rate_times_the_nights_and_the_average_rate_is_weighted(tmp_path):
    frame = _stays()
    d = _init(tmp_path, frame)
    ws = tmp_path / "ws"
    r = intake.confirm(ws, _answers(d, sum_columns=["weekend_nights", "week_nights"], unit_price="rate", unit_price_times="sum_columns"))
    assert r["problems"] == []
    k, nights = _kept(frame)
    W = Workspace(ws)
    w = (pd.Timestamp("2015-01-01").date(), pd.Timestamp("2016-12-31").date())
    assert W.total("weekend_nights_plus_week_nights", w) == nights.sum()
    assert W.total("rate_times_weekend_nights_plus_week_nights", w) == pytest.approx((k.rate * nights).sum())
    assert W.total("per_unit", w) == pytest.approx((k.rate * nights).sum() / nights.sum())
    assert "rate" not in W.metrics
    by = {h: W.total("rate_times_weekend_nights_plus_week_nights", w, {"hotel": h}) for h in ("City", "Resort")}
    assert sum(by.values()) == pytest.approx((k.rate * nights).sum())


def test_a_unit_price_cannot_also_be_money_in(tmp_path):
    d = _init(tmp_path, _stays())
    bad = _answers(d, sum_columns=["weekend_nights", "week_nights"], unit_price="rate", unit_price_times="sum_columns", **{"role:rate": "amount"})
    with pytest.raises(ValueError, match="rate"):
        intake.confirm(tmp_path / "ws", bad)


def test_a_unit_price_without_the_column_it_multiplies_is_refused(tmp_path):
    d = _init(tmp_path, _stays())
    with pytest.raises(ValueError, match="multipl"):
        intake.confirm(tmp_path / "ws", _answers(d, unit_price="rate"))


def test_the_derived_columns_are_recorded_in_the_source(tmp_path):
    d = _init(tmp_path, _stays())
    intake.confirm(tmp_path / "ws", _answers(d, sum_columns=["weekend_nights", "week_nights"], unit_price="rate", unit_price_times="sum_columns"))
    spec = Workspace(tmp_path / "ws").project["sources"]["stays"]
    assert [x["op"] for x in spec["derive_columns"]] == ["add", "mul"]
    assert spec["derive_columns"][1]["columns"] == ["rate", "weekend_nights_plus_week_nights"]
