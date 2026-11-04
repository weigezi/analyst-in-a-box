"""How many questions intake asks, and that a question is asked only when its answer can matter.

Every table is invented here (seed 21); the one test on a public dataset runs only when AIB_DATA_DIR points at it.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aib import cli, intake
from aib.workspace import Workspace


def _rng():
    return np.random.default_rng(21)


def _bookings(n=600):
    rng = _rng()
    return pd.DataFrame({"day": pd.date_range("2025-01-01", periods=n), "order_id": np.arange(n),
                         "amount": rng.normal(60, 9, n).round(2),
                         "status": rng.choice(["paid", "cancelled", "refunded"], n, p=[0.8, 0.1, 0.1]),
                         "channel": rng.choice(["web", "app", "phone"], n),
                         "meal": rng.choice(["bb", "hb", "fb", "sc"], n)})


def _init(tmp_path, frame, name="bookings"):
    folder = tmp_path / "t"
    folder.mkdir(exist_ok=True)
    frame.to_csv(folder / f"{name}.csv", index=False)
    return intake.init([folder / f"{name}.csv"], tmp_path / "ws", lang="en")


def _ids(d):
    return [q["id"] for q in d["questions"]]


# ---------- 1. the values of a reversal column are asked only for the column the user picks ----------

def test_init_asks_which_column_marks_reversals_but_not_the_values_of_every_candidate(tmp_path):
    d = _init(tmp_path, _bookings())
    q = {x["id"]: x for x in d["questions"]}
    opts = [o if isinstance(o, str) else o["value"] for o in q["reversal_column"]["options"]]
    assert {"status", "channel", "meal", "none"} <= set(opts)       # still offered by shape
    assert not [i for i in _ids(d) if i.startswith("reversal_values:")]


def test_the_values_are_asked_once_the_column_is_picked_and_only_for_that_column(tmp_path):
    d = _init(tmp_path, _bookings())
    ws = tmp_path / "ws"
    base = {"date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": [],
            "reversal_column": "status"}
    with pytest.raises(intake.NeedsAnswers) as e:
        intake.confirm(ws, base)
    assert e.value.ids == ["reversal_values:status"]
    q = e.value.questions[0]
    assert sorted(o["value"] for o in q["options"]) == ["cancelled", "paid", "refunded"] and q["multi"] is True
    saved = json.loads((ws / "draft.json").read_text(encoding="utf-8"))
    assert "reversal_values:status" in [x["id"] for x in saved["questions"]]       # the next confirm and the count see it
    assert not [x for x in saved["questions"] if x["id"].startswith("reversal_values:") and x["id"] != "reversal_values:status"]


def test_the_full_path_reaches_the_same_numbers_as_asking_every_column(tmp_path):
    frame = _bookings()
    d = _init(tmp_path, frame)
    ws = tmp_path / "ws"
    base = {"date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": ["channel"],
            "reversal_column": "status"}
    with pytest.raises(intake.NeedsAnswers):
        intake.confirm(ws, base)
    intake.confirm(ws, {**base, "reversal_values:status": ["cancelled", "refunded"]})
    kept = frame[frame.status == "paid"]
    W = Workspace(ws)
    w = (frame.day.min().date(), frame.day.max().date())
    assert W.total("amount", w) == pytest.approx(kept.amount.sum())
    assert W.total("id_count", w) == len(kept)


def test_choosing_none_or_nothing_needs_no_values(tmp_path):
    d = _init(tmp_path, _bookings())
    for i, extra in enumerate(({"reversal_column": "none"}, {})):
        r = intake.confirm(tmp_path / "ws", {"date_column": "day", "role:amount": "amount", "order_id": "order_id",
                                             "dimensions": [], **extra})
        assert r["problems"] == []


def test_the_command_line_prints_the_follow_up_question_instead_of_a_traceback(tmp_path, capsys):
    frame = _bookings()
    f = tmp_path / "bookings.csv"
    frame.to_csv(f, index=False)
    ws = tmp_path / "ws"
    cli.main(["init", str(f), "--workspace", str(ws), "--lang", "en"])
    capsys.readouterr()
    answers = tmp_path / "a.json"
    answers.write_text(json.dumps({"date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": [],
                                   "reversal_column": "status"}), encoding="utf-8")
    code = cli.main(["confirm", "--workspace", str(ws), "--answers", str(answers)])
    out = json.loads(capsys.readouterr().out)
    assert code == 3
    assert [q["id"] for q in out["needs_answers"]] == ["reversal_values:status"]
    assert "confirm" in out["next"]


# ---------- 2. one question for "which numbers do you want to analyse", not one per number column ----------

def _shop_like(n=500):
    rng = _rng()
    return pd.DataFrame({"day": pd.date_range("2025-01-01", periods=n), "order_id": np.arange(n),
                         "user_ref": rng.integers(0, 300, n),             # a whole-number id that repeats (so it is not the row key)
                         "is_gift": rng.integers(0, 2, n),                   # a flag
                         "revenue": rng.normal(60, 9, n).round(2), "cost": rng.normal(35, 5, n).round(2),
                         "pieces": rng.integers(1, 40, n), "channel": rng.choice(["web", "app", "phone"], n)})


def _plain_options(q):
    return [o if isinstance(o, str) else o["value"] for o in q["options"]]


def test_one_multi_select_replaces_the_question_for_every_number_column(tmp_path):
    d = _init(tmp_path, _shop_like(), name="shop")
    q = {x["id"]: x for x in d["questions"]}
    assert not [i for i in q if i.startswith("role:")]
    m = q["measure_columns"]
    assert m["multi"] is True
    assert sorted(_plain_options(m)) == ["cost", "pieces", "revenue"]            # not the id, not the 0/1 flag
    assert sorted(m["not_analysed"]) == ["is_gift", "user_ref"]                  # said, so nothing is dropped quietly


def test_the_number_that_matters_most_is_chosen_among_the_numbers_offered(tmp_path):
    d = _init(tmp_path, _shop_like(), name="shop")
    q = {x["id"]: x for x in d["questions"]}
    assert sorted(_plain_options(q["north_star"])) == ["cost", "pieces", "revenue"]


def test_the_role_follow_up_is_asked_for_the_selected_columns_only(tmp_path):
    frame = _shop_like()
    _init(tmp_path, frame, name="shop")
    ws = tmp_path / "ws"
    base = {"date_column": "day", "order_id": "order_id", "dimensions": ["channel"], "measure_columns": ["revenue", "pieces"]}
    with pytest.raises(intake.NeedsAnswers) as e:
        intake.confirm(ws, base)
    q = e.value.questions[0]
    assert e.value.ids == ["measure_roles"] and q["columns"] == ["revenue", "pieces"]
    assert {"amount", "quantity", "cost", "skip"} <= set(_plain_options(q))
    assert "measure_roles" in [x["id"] for x in json.loads((ws / "draft.json").read_text(encoding="utf-8"))["questions"]]
    intake.confirm(ws, {**base, "measure_roles": {"revenue": "amount", "pieces": "quantity"}})
    W = Workspace(ws)
    assert set(W.metrics) >= {"revenue", "pieces", "id_count", "per_id"} and "cost" not in W.metrics
    assert W.metrics["pieces"]["role"] == "quantity" and W.metrics["revenue"]["role"] == "amount"
    w = (frame.day.min().date(), frame.day.max().date())
    assert W.total("revenue", w) == pytest.approx(frame.revenue.sum())


def test_the_old_per_column_answers_still_write_the_same_model(tmp_path):
    frame = _shop_like()
    _init(tmp_path, frame, name="shop")
    ws = tmp_path / "ws"
    intake.confirm(ws, {"date_column": "day", "order_id": "order_id", "dimensions": [],
                        "role:revenue": "amount", "role:cost": "cost", "role:pieces": "skip",
                        "role:user_ref": "skip", "role:is_gift": "skip"})
    W = Workspace(ws)
    assert W.metrics["revenue"]["role"] == "amount" and W.metrics["cost"]["role"] == "cost" and "pieces" not in W.metrics


def test_a_unit_price_and_the_parts_of_a_sum_need_no_role_question(tmp_path):
    rng = _rng()
    n = 500
    df = pd.DataFrame({"day": pd.date_range("2025-01-01", periods=n), "rate": rng.uniform(40, 220, n).round(2),
                       "wk_nights": rng.integers(0, 6, n), "we_nights": rng.integers(0, 4, n)})
    d = _init(tmp_path, df, name="stays")
    assert "unit_price_times" not in _ids(d)                                     # asked only once a unit price is picked
    ws = tmp_path / "ws"
    r = intake.confirm(ws, {"date_column": "day", "order_id": "none", "dimensions": [], "unit_price": "rate",
                            "sum_columns": ["wk_nights", "we_nights"], "unit_price_times": "sum_columns",
                            "measure_columns": ["rate", "wk_nights", "we_nights"]})
    assert r["problems"] == []
    W = Workspace(ws)
    assert "rate" not in W.metrics and W.metrics["wk_nights"]["role"] == "quantity"


def test_a_unit_price_without_the_column_it_multiplies_is_asked_not_refused(tmp_path):
    rng = _rng()
    n = 300
    df = pd.DataFrame({"day": pd.date_range("2025-01-01", periods=n), "rate": rng.uniform(40, 220, n).round(2),
                       "nights": rng.integers(0, 6, n)})
    _init(tmp_path, df, name="stays")
    with pytest.raises(intake.NeedsAnswers) as e:
        intake.confirm(tmp_path / "ws", {"date_column": "day", "order_id": "none", "dimensions": [], "unit_price": "rate"})
    assert e.value.ids == ["unit_price_times"] and "nights" in _plain_options(e.value.questions[0])
