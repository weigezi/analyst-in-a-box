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


# ---------- the suggestion ----------

def test_a_child_that_adds_up_to_its_parent_makes_the_parent_the_suggested_main_table(tmp_path):
    d = _init(tmp_path, _shop())
    assert d["main"] == "orders"
    assert _q(d, "main_table")["suggested"] == "orders"


def test_the_detail_table_is_not_offered_as_more_business_data_once_the_parent_holds_its_totals(tmp_path):
    d = _init(tmp_path, _shop())
    assert d["tables"]["items"]["suggested_kind"] == "ignore"
    assert "orders" in _q(d, "kind:items")["evidence"] and "add up" in _q(d, "kind:items")["evidence"]


def test_the_main_table_question_shows_both_options_with_rows_what_one_row_is_and_sums(tmp_path):
    frames = _shop()
    d = _init(tmp_path, frames)
    q = _q(d, "main_table")
    assert {"orders", "items"} <= set(q["options"])
    cand = {c["table"]: c for c in q["candidates"]}
    assert cand["orders"]["rows"] == len(frames["orders"]) and cand["items"]["rows"] == len(frames["items"])
    assert "order_id" in cand["orders"]["one_row"] and "item_id" in cand["items"]["one_row"]
    assert "order_id" in cand["items"]["one_row"]                      # the column that repeats, and how often
    assert cand["orders"]["sums"]["amount"] == pytest.approx(frames["orders"].amount.sum())
    assert cand["items"]["sums"]["price"] == pytest.approx(frames["items"].price.sum())
    assert cand["orders"]["sums"]["amount"] == pytest.approx(cand["items"]["sums"]["price"])
    assert "orders" in q["evidence"] and "items" in q["evidence"]


def test_the_draft_records_which_columns_add_up_and_on_how_many_parent_rows(tmp_path):
    frames = _shop()
    d = _init(tmp_path, frames)
    (g,) = d["grain"]
    assert (g["child"], g["parent"], g["child_link"], g["parent_link"]) == ("items", "orders", "order_id", "order_id")
    assert g["child_rows"] == len(frames["items"]) and g["parent_rows"] == len(frames["orders"])
    (p,) = g["sums"]
    assert (p["child_column"], p["parent_column"], p["parent_rows_matching"]) == ("price", "amount", 1.0)


# ---------- when the parent must not be preferred ----------

def test_a_child_whose_rows_do_not_add_up_leaves_the_biggest_table_as_main(tmp_path):
    d = _init(tmp_path, _shop(honest=False))
    assert d["main"] == "items"
    assert d["grain"] == []
    assert d["tables"]["orders"]["suggested_kind"] == "lookup"


@pytest.mark.parametrize("rows", ["same", "fewer"])
def test_a_table_with_as_many_or_fewer_rows_than_the_other_is_not_a_detail_table(tmp_path, rows):
    frames = _shop(one_to_one=(rows == "same"))
    if rows == "fewer":
        frames["items"] = frames["items"].groupby("order_id", as_index=False).first().head(300)
        frames["items"]["price"] = frames["orders"].set_index("order_id").amount.reindex(frames["items"].order_id).values
    d = _init(tmp_path, frames)
    assert d["grain"] == []


# ---------- an answer that differs from the suggestion ----------

def test_the_suggested_main_table_confirms_in_one_step(tmp_path):
    d = _init(tmp_path, _shop())
    r = intake.confirm(tmp_path / "ws", _answer_all(d, {"amount"}, ["channel"], "order_id"))
    assert r["intake"]["main"] == "orders"


def test_another_main_table_is_derived_by_confirm_without_running_init_again(tmp_path):
    frames = _shop()
    d = _init(tmp_path, frames)
    ws = tmp_path / "ws"
    first = _answer_all(d, {"amount"}, ["channel"], "order_id")
    first["main_table"] = "items"
    with pytest.raises(intake.NeedsAnswers) as e:
        intake.confirm(ws, first)
    assert "role:price" in e.value.ids and "kind:orders" in e.value.ids
    d2 = _draft(tmp_path)
    assert d2["main"] == "items" and d2["main_changed_from"] == "orders"
    second = _answer_all(d2, {"price"}, ["channel"], "item_id")
    r = intake.confirm(ws, second)
    assert r["intake"]["main"] == "items"
    W = Workspace(ws)
    w = (frames["items"].placed_at.min().date(), frames["items"].placed_at.max().date())
    assert W.total("price", w) == pytest.approx(frames["items"].price.sum())


def test_an_answer_for_a_table_that_does_not_exist_names_the_tables(tmp_path):
    d = _init(tmp_path, _shop())
    bad = _answer_all(d, {"amount"}, ["channel"], "order_id")
    bad["main_table"] = "nothing"
    with pytest.raises(ValueError, match="orders"):
        intake.confirm(tmp_path / "ws", bad)


# ---------- how many links the channel needs ----------

def _by_channel(frames, value, via_orders):
    m = frames["items"].merge(frames["orders"][["order_id", "session_id"]], on="order_id") if via_orders else frames["orders"]
    return m.merge(frames["sessions"][["session_id", "channel"]], on="session_id").groupby("channel")[value].sum()


def test_revenue_by_channel_from_the_parent_needs_one_link(tmp_path):
    frames = _shop()
    d = _init(tmp_path, frames)
    ws = tmp_path / "ws"
    r = intake.confirm(ws, _answer_all(d, {"amount"}, ["channel"], "order_id"))
    assert [j["source"] for j in r["intake"]["joins"]] == ["sessions"]
    W = Workspace(ws)
    w = (frames["orders"].placed_at.min().date(), frames["orders"].placed_at.max().date())
    got = {c: W.total("amount", w, {"channel": c}) for c in ("search", "social", "direct")}
    assert got == pytest.approx(_by_channel(frames, "amount", False).to_dict())
    assert sum(got.values()) == pytest.approx(frames["orders"].amount.sum())


def test_revenue_by_channel_from_the_detail_table_needs_two_links_and_still_adds_up(tmp_path):
    frames = _shop()
    d = _init(tmp_path, frames)
    ws = tmp_path / "ws"
    first = _answer_all(d, {"amount"}, ["channel"], "order_id")
    first["main_table"] = "items"
    with pytest.raises(intake.NeedsAnswers):
        intake.confirm(ws, first)
    d2 = _draft(tmp_path)
    r = intake.confirm(ws, _answer_all(d2, {"price"}, ["channel"], "item_id"))
    assert [j["source"] for j in r["intake"]["joins"]] == ["orders", "sessions"]
    W = Workspace(ws)
    w = (frames["items"].placed_at.min().date(), frames["items"].placed_at.max().date())
    got = {c: W.total("price", w, {"channel": c}) for c in ("search", "social", "direct")}
    assert got == pytest.approx(_by_channel(frames, "price", True).to_dict())
    assert sum(got.values()) == pytest.approx(frames["items"].price.sum())


# ---------- a chosen dimension is never dropped without saying so ----------

def test_a_dimension_that_no_link_reaches_comes_back_as_a_problem_in_plain_words(tmp_path):
    frames = _shop()
    d = _init(tmp_path, frames)
    ans = _answer_all(d, {"amount"}, ["channel"], "order_id")
    ans["link:orders.session_id>sessions.session_id"] = "no"
    r = intake.confirm(tmp_path / "ws", ans)
    assert r["dimensions"] == []
    assert len(r["problems"]) == 1 and "channel" in r["problems"][0] and "orders" in r["problems"][0]


def test_the_command_line_shows_the_dropped_dimension_next_to_the_workspace_problems(tmp_path, capsys):
    from aib import cli
    frames = _shop()
    d = _init(tmp_path, frames)
    ans = _answer_all(d, {"amount"}, ["channel"], "order_id")
    ans["link:orders.session_id>sessions.session_id"] = "no"
    (tmp_path / "answers.json").write_text(json.dumps(ans), encoding="utf-8")
    assert cli.main(["confirm", "--workspace", str(tmp_path / "ws"), "--answers", str(tmp_path / "answers.json")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert any("channel" in p for p in out["problems"])


def test_a_reachable_dimension_is_not_reported(tmp_path):
    d = _init(tmp_path, _shop())
    r = intake.confirm(tmp_path / "ws", _answer_all(d, {"amount"}, ["channel"], "order_id"))
    assert r["problems"] == [] and r["dimensions"] == ["channel"]
