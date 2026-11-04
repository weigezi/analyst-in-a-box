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
