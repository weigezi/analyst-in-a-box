"""Parent and child tables: when the rows of one table add up to the totals of another that it points at, the
parent is the table to analyse, and the user sees both options with the evidence.

Every table is invented here (seed 11); nothing is read from outside tmp_path.
"""

import json

import numpy as np
import pandas as pd
import pytest

from aib import intake
from aib.workspace import Workspace


def _rng():
    return np.random.default_rng(11)


def _shop(honest=True, n_sessions=2000, n_orders=600, one_to_one=False):
    """sessions (channel) <- orders (one amount per order) <- items (one price per item).
    honest: the item prices of an order add up to the order's amount. Otherwise the two are unrelated."""
    rng = _rng()
    sid = np.arange(1, n_sessions + 1)
    started = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 90 * 24 * 60, n_sessions), unit="m")
    sessions = pd.DataFrame({"session_id": sid, "started_at": started,
                             "channel": rng.choice(["search", "social", "direct"], n_sessions)})
    pick = rng.choice(sid, n_orders, replace=False)
    placed = sessions.set_index("session_id").loc[pick, "started_at"].values + pd.to_timedelta(rng.integers(1, 30, n_orders), unit="m")
    oid = np.arange(1, n_orders + 1)
    per = np.ones(n_orders, dtype=int) if one_to_one else rng.choice([1, 2, 3], n_orders, p=[0.7, 0.25, 0.05])
    items = pd.DataFrame({"item_id": np.arange(1, per.sum() + 1), "order_id": np.repeat(oid, per),
                          "placed_at": np.repeat(placed, per), "price": rng.uniform(5, 90, per.sum()).round(2),
                          "sku": rng.choice(list("ABCD"), per.sum())})
    amount = items.groupby("order_id").price.sum().round(2).reindex(oid).values if honest else rng.uniform(5, 200, n_orders).round(2)
    orders = pd.DataFrame({"order_id": oid, "session_id": pick, "placed_at": placed, "amount": amount})
    return {"sessions": sessions, "orders": orders, "items": items}


def _init(tmp_path, frames, main=None):
    folder = tmp_path / "tables"
    folder.mkdir(exist_ok=True)
    for name, df in frames.items():
        df.to_csv(folder / f"{name}.csv", index=False)
    return intake.init([folder], tmp_path / "ws", lang="en", main=main)


def _q(d, qid):
    return next(q for q in d["questions"] if q["id"] == qid)


def _answer_all(d, amounts, dims, order_id):
    """Answer every question of a draft: the suggestion for kinds and links, 'amount' for the named columns."""
    ans = {}
    for q in d["questions"]:
        i = q["id"]
        if i.startswith(("kind:", "link:")):
            ans[i] = q["suggested"]
        elif i.startswith("role:"):
            ans[i] = "amount" if q["column"] in amounts else "skip"
    ans.update({"main_table": d["main"], "dimensions": dims, "order_id": order_id})
    return ans


def _draft(tmp_path):
    return json.loads((tmp_path / "ws" / "draft.json").read_text(encoding="utf-8"))


# ---------- one table goes through the same intake as many ----------

def _one_table():
    rng = _rng()
    n = 400
    return pd.DataFrame({"day": (pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 120, n), unit="D")).strftime("%Y-%m-%d"),
                         "order_id": np.arange(n), "amount": rng.uniform(5, 90, n).round(2),
                         "state": rng.choice(["done", "void"], n, p=[0.8, 0.2])})


def test_a_single_file_gets_the_same_questions_as_a_folder(tmp_path, capsys):
    from aib import cli
    f = tmp_path / "sales.csv"
    _one_table().to_csv(f, index=False)
    assert cli.main(["init", str(f), "--workspace", str(tmp_path / "ws"), "--lang", "en"]) == 0
    capsys.readouterr()
    d = _draft(tmp_path)
    ids = [q["id"] for q in d["questions"]]
    assert d["kind"] == "tables" and d["main"] == "sales"
    assert "reversal_column" in ids and "main_table" in ids


def test_a_single_file_is_confirmed_with_the_cancelled_rows_left_out(tmp_path, capsys):
    from aib import cli
    frame = _one_table()
    f = tmp_path / "sales.csv"
    frame.to_csv(f, index=False)
    ws = tmp_path / "ws"
    cli.main(["init", str(f), "--workspace", str(ws), "--lang", "en"])
    capsys.readouterr()
    d = _draft(tmp_path)
    ans = _answer_all(d, {"amount"}, [], "order_id")
    ans.update({"reversal_column": "state", "reversal_values:state": ["void"]})
    (tmp_path / "answers.json").write_text(json.dumps(ans), encoding="utf-8")
    assert cli.main(["confirm", "--workspace", str(ws), "--answers", str(tmp_path / "answers.json")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["problems"] == []
    kept = frame[frame.state != "void"]
    W = Workspace(ws)
    assert W.total("amount", (pd.Timestamp(kept.day.min()).date(), pd.Timestamp(kept.day.max()).date())) == pytest.approx(kept.amount.sum())


