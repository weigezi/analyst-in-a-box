"""A table of visits: each row is one visit, so a visit count is the number of rows (or distinct keys), never a sum of ids.

The tables below are made up with the shape of a shop's sessions and orders: a sessions table (one row per session, a
key, a channel) and an orders table that points at it. Conversion = orders / sessions must come out as a rate, a
sessions table must be both the lookup of the order (its channel) and the source of the visit count, and a ratio that
displays as 0.00% in both periods must stop instead of printing "fell from 0.00% to 0.00%"."""

import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from aib import cli, draft, intake
from aib.run import run
from aib.validate import all_problems
from aib.workspace import Workspace

BASE = ("2012-11-01", "2012-11-30")
CUR = ("2013-01-01", "2013-01-30")
SESSIONS_LINK = "link:orders.website_session_id>website_sessions.website_session_id"
USER_LINK = "link:orders.user_id>website_sessions.website_session_id"


def build_tables(folder):
    """sessions (one row per session) and orders (one per order, pointing at its session). Conversion is about 5% in
    the base month and 7% in the current month, differently by channel."""
    rng = np.random.default_rng(7)
    rows, orders, sid, oid = [], [], 0, 0
    for day in pd.date_range("2012-09-01", "2013-03-31"):
        rate = {"gsearch": 0.044, "bsearch": 0.058} if day < pd.Timestamp("2013-01-01") else {"gsearch": 0.062, "bsearch": 0.082}
        for k in range(160):
            sid += 1
            src = "gsearch" if k % 5 < 3 else "bsearch"
            t = day + pd.Timedelta(hours=8, minutes=k)
            rows.append({"website_session_id": sid, "created_at": t, "user_id": sid // 2 + 1,
                         "is_repeat_session": int(k % 7 == 0), "utm_source": src, "device_type": "mobile" if k % 2 else "desktop"})
            if rng.random() < rate[src]:
                oid += 1
                price = [49.99, 59.99, 29.99][oid % 3]
                orders.append({"order_id": oid, "created_at": t + pd.Timedelta(minutes=1), "website_session_id": sid,
                               "user_id": sid // 2 + 1, "price_usd": price, "cogs_usd": round(price * 0.4, 2)})
    folder.mkdir(parents=True, exist_ok=True)
    s, o = pd.DataFrame(rows), pd.DataFrame(orders)
    s.to_csv(folder / "website_sessions.csv", index=False)
    o.to_csv(folder / "orders.csv", index=False)
    return s, o


def truth(s, o, w, by=None):
    """Orders, sessions and conversion in a window, straight from the raw tables with pandas."""
    lo, hi = pd.Timestamp(w[0]), pd.Timestamp(w[1])
    ss = s[(s.created_at >= lo) & (s.created_at < hi + pd.Timedelta(days=1))]
    oo = o[(o.created_at >= lo) & (o.created_at < hi + pd.Timedelta(days=1))].merge(
        s[["website_session_id", "utm_source"]], on="website_session_id", how="left")
    if by:
        n, d = oo.groupby(by).size(), ss.groupby(by).size()
        return n, d, n / d
    return len(oo), len(ss), len(oo) / len(ss)


def answers(role="records", **extra):
    a = {"main_table": "orders", "kind:website_sessions": "business", SESSIONS_LINK: "yes",
         "date_column": "created_at", "unit_price": "none", "sum_columns": [], "measure_columns": ["price_usd", "cogs_usd"],
         "order_id": "order_id", "template": "orders", "north_star": "price_usd",
         "dimensions": ["utm_source", "device_type"], "single_point_share": 0.5, "reversal_column": "none",
         "measure_roles": {"price_usd": "amount", "cogs_usd": "cost"},
         "role:website_sessions.website_session_id": role, "role:website_sessions.user_id": "skip",
         "role:website_sessions.is_repeat_session": "skip"}
    a.update(extra)
    return a


@pytest.fixture(scope="module")
def shop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("visits")
    s, o = build_tables(tmp / "tables")
    return {"tmp": tmp, "tables": tmp / "tables", "s": s, "o": o}


def formed(shop, name, a):
    ws = shop["tmp"] / name
    intake.init([shop["tables"]], ws, lang="en")
    out = intake.confirm(ws, a)
    return ws, out


CONV = {"metric": "conversion", "current": list(CUR), "base": list(BASE)}


# ---------- the role ----------

def test_the_role_question_offers_records_and_says_ids_are_not_added(shop):
    ws = shop["tmp"] / "q"
    intake.init([shop["tables"]], ws, lang="en")
    a = answers()
    for k in [k for k in a if k.startswith("role:website_sessions")]:
        del a[k]
    with pytest.raises(intake.NeedsAnswers) as need:
        intake.confirm(ws, a)
    q = {x["id"]: x for x in need.value.questions}["role:website_sessions.website_session_id"]
    assert {"visits", "records"} <= {o["value"] for o in q["options"]}
    assert "never added up" in q["ask"]


def test_the_measure_roles_question_says_ids_are_not_added(shop):
    ws = shop["tmp"] / "mr"
    intake.init([shop["tables"]], ws, lang="en")
    a = answers()
    del a["measure_roles"]
    with pytest.raises(intake.NeedsAnswers) as need:
        intake.confirm(ws, a)
    q = need.value.questions[0]
    assert q["id"] == "measure_roles" and "records" in {o["value"] for o in q["options"]} and "never added up" in q["ask"]


# ---------- a table of visits ----------

@pytest.mark.parametrize("role", ["records", "visits"])
def test_conversion_is_orders_over_sessions_counted(shop, role):
    ws_dir, out = formed(shop, f"c_{role}", answers(role))
    ws = Workspace(ws_dir)
    assert all_problems(ws) == []
    m = ws.measures[ws.metrics["conversion"]["denominator"] and ws.metrics[ws.metrics["conversion"]["denominator"]]["measure"]]
    assert m["agg"] == "count_distinct" and m["column"] == "website_session_id" and m["source"] == "website_sessions"
    assert m["date"] == "created_at"
    n0, d0, c0 = truth(shop["s"], shop["o"], BASE)
    n1, d1, c1 = truth(shop["s"], shop["o"], CUR)
    s = run(ws_dir, CONV, out_dir=shop["tmp"] / f"run_{role}")
    assert not s["blocked"], [c for c in s["checks"] if not c["pass"]]
    q = s["qualify"]
    assert q["total_base"] == pytest.approx(c0) and q["total_cur"] == pytest.approx(c1)
    assert ws.total("id_count", (dt.date(2013, 1, 1), dt.date(2013, 1, 30))) == n1
    assert ws.total(ws.metrics["conversion"]["denominator"], (dt.date(2013, 1, 1), dt.date(2013, 1, 30))) == d1
    assert 0.03 < c0 < 0.08 and 0.03 < c1 < 0.09


def test_the_report_does_not_say_zero(shop):
    ws_dir, _ = formed(shop, "rep", answers())
    s = run(ws_dir, CONV, out_dir=shop["tmp"] / "run_rep")
    text = (shop["tmp"] / "run_rep" / "report.en.md").read_text(encoding="utf-8")
    n0, d0, c0 = truth(shop["s"], shop["o"], BASE)
    n1, d1, c1 = truth(shop["s"], shop["o"], CUR)
    assert f"{c0:.2%}" in text and f"{c1:.2%}" in text
    assert "from 0.00% to 0.00%" not in text


def test_conversion_can_be_cut_by_channel(shop):
    ws_dir, _ = formed(shop, "cut", answers())
    ws = Workspace(ws_dir)
    assert {"utm_source", "device_type"} <= ws.metric_dimensions("conversion")
    seg = ws.segments("conversion", "utm_source", (dt.date(2012, 11, 1), dt.date(2012, 11, 30)), (dt.date(2013, 1, 1), dt.date(2013, 1, 30)))
    n0, d0, c0 = truth(shop["s"], shop["o"], BASE, "utm_source")
    n1, d1, c1 = truth(shop["s"], shop["o"], CUR, "utm_source")
    for src in ("gsearch", "bsearch"):
        nb, db, nc, dc = seg[src]
        assert (nb, db, nc, dc) == (n0[src], d0[src], n1[src], d1[src])
        assert nc / dc == pytest.approx(c1[src])
    s = run(ws_dir, {**CONV, "dimensions": ["utm_source"]}, out_dir=shop["tmp"] / "run_cut")
    assert any(c["dimension"] == "utm_source" for c in s["cuts"])


def test_the_sessions_table_is_also_the_lookup_of_the_order(shop):
    """Answering "business" and the link "yes" used to raise a ValueError; the channel of an order comes from the session."""
    ws_dir, out = formed(shop, "both", answers())
    project = yaml.safe_load((ws_dir / "project.yaml").read_text(encoding="utf-8"))
    assert project["sources"]["orders"]["type"] == "join"
    assert project["sources"]["orders"]["joins"][0]["source"] == "website_sessions"
    assert project["sources"]["website_sessions"]["key"] == "website_session_id"
    assert project["sources"]["website_sessions"]["date_columns"] == ["created_at"]
    ws = Workspace(ws_dir)
    seg = ws.segments("price_usd", "utm_source", (dt.date(2012, 11, 1), dt.date(2012, 11, 30)), (dt.date(2013, 1, 1), dt.date(2013, 1, 30)))
    assert set(seg) == {"gsearch", "bsearch"}


def test_a_false_link_stays_off(shop):
    """user_id of an order is found among the session ids, but spreads over a third of their range: not suggested."""
    d = intake.init([shop["tables"]], shop["tmp"] / "fl", lang="en")
    lk = {intake._link_id(x): x for x in d["links"]}
    assert lk[SESSIONS_LINK]["suggested"] == "yes"
    assert USER_LINK not in {q["id"] for q in d["questions"]}
    assert lk[USER_LINK]["suggested"] == "no"


def test_other_kinds_with_a_key_link_ask_instead_of_crashing(shop):
    ws = shop["tmp"] / "series"
    intake.init([shop["tables"]], ws, lang="en")
    with pytest.raises(intake.NeedsAnswers) as need:
        intake.confirm(ws, answers(**{"kind:website_sessions": "events"}))
    q = need.value.questions[0]
    assert q["id"] == "kind:website_sessions"
    assert {o["value"] for o in q["options"]} == {"lookup", "business"}
    # answering it goes on
    intake.confirm(ws, answers(**{"kind:website_sessions": "business"}))


# ---------- a whole table ----------

def test_a_table_without_numbers_is_counted_by_its_rows(tmp_path):
    s, o = build_tables(tmp_path / "t")
    (tmp_path / "t" / "website_sessions.csv").unlink()
    hits = s[["created_at", "utm_source"]].copy()
    hits.to_csv(tmp_path / "t" / "page_hits.csv", index=False)
    ws_dir = tmp_path / "ws"
    d = intake.init([tmp_path / "t"], ws_dir, lang="en")
    a = {"main_table": "orders", "kind:page_hits": "business", "date_column": "created_at", "unit_price": "none", "sum_columns": [],
         "measure_columns": ["price_usd", "cogs_usd"], "order_id": "order_id", "template": "orders", "north_star": "price_usd",
         "dimensions": ["utm_source"] if False else [], "single_point_share": 0.5, "reversal_column": "none",
         "measure_roles": {"price_usd": "amount", "cogs_usd": "cost"}}
    with pytest.raises(intake.NeedsAnswers) as need:
        intake.confirm(ws_dir, a)
    q = {x["id"]: x for x in need.value.questions}["records:page_hits"]
    assert "count the rows" in q["ask"] and q["options"] == ["yes", "no"]
    out = intake.confirm(ws_dir, {**a, "records:page_hits": "yes"})
    ws = Workspace(ws_dir)
    m = ws.measures["m_page_hits_records"]
    assert m["agg"] == "count" and m["source"] == "page_hits" and m["date"] == "created_at"
    assert ws.total("page_hits_records", (dt.date(2013, 1, 1), dt.date(2013, 1, 30))) == float(
        ((hits.created_at >= "2013-01-01") & (hits.created_at < "2013-01-31")).sum())
    assert ws.metrics["conversion"]["denominator"] == "page_hits_records"
