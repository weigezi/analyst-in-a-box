"""Intake on tables of other shapes: which table is the main one, two dates in one table, dates spread over
sibling columns, data with no time axis, and files that need cleaning on the way in.

Every table is invented here (seed 7); nothing is read from outside tmp_path.
"""

import numpy as np
import pandas as pd
import pytest
import yaml

from aib import draft, intake
from aib.run import run
from aib.workspace import Workspace, window


def _rng():
    return np.random.default_rng(7)


def _iso(ts):
    return list(pd.DatetimeIndex(ts).strftime("%Y-%m-%d"))


def _days(rng, n, start="2025-01-01", span=365):
    return _iso(pd.Timestamp(start) + pd.to_timedelta(rng.integers(0, span, n), unit="D"))


def _init(tmp_path, frames, main=None):
    folder = tmp_path / "tables"
    folder.mkdir(exist_ok=True)
    for name, df in frames.items():
        df.to_csv(folder / f"{name}.csv", index=False)
    return intake.init([folder], tmp_path / "ws", lang="en", main=main)


def _question(d, qid):
    return next(q for q in d["questions"] if q["id"] == qid)


def _values(q):
    return [o["value"] if isinstance(o, dict) else o for o in q["options"]]


def _answers(d, roles, **extra):
    """Answer every role question (skip, unless the column is named in roles) so confirm has what it needs."""
    asked = {q["id"]: roles.get(q["column"], "skip") for q in d["questions"] if q["id"].startswith("role:")}
    offered = [o["value"] for q in d["questions"] if q["id"] == "measure_columns" for o in q["options"]]
    picked = [c for c in offered if roles.get(c, "skip") != "skip"]
    return {**asked, "measure_columns": picked, "measure_roles": {c: roles[c] for c in picked}, **extra}


# ---------- 1. which table is the main one ----------

def _visits_orders_products():
    rng = _rng()
    visits = pd.DataFrame({"date": _days(rng, 2000), "visit_id": np.arange(2000),
                           "user_id": rng.integers(0, 1500, 2000)})
    orders = pd.DataFrame({"date": _days(rng, 300), "order_id": np.arange(300), "visit_id": rng.choice(2000, 300, replace=False),
                           "amount": rng.uniform(5, 500, 300).round(2), "units": rng.integers(1, 6, 300)})
    products = pd.DataFrame({"product_code": [f"P{i}" for i in range(12)], "label": [f"item {i}" for i in range(12)]})
    return {"visits": visits, "orders": orders, "products": products}


def test_main_is_the_largest_table_that_has_a_measure_not_the_largest_table(tmp_path):
    d = _init(tmp_path, _visits_orders_products())
    assert d["main"] == "orders"
    assert d["tables"]["orders"]["suggested_kind"] == "main"
    assert d["tables"]["visits"]["suggested_kind"] != "main"


def test_main_override_still_picks_a_table_without_a_measure(tmp_path):
    d = _init(tmp_path, _visits_orders_products(), main="visits")
    assert d["main"] == "visits"
    assert d["tables"]["visits"]["suggested_kind"] == "main"


def _ints(rng, n, distinct):
    """n integers with exactly `distinct` different values."""
    vals = np.concatenate([np.arange(distinct), rng.integers(0, distinct, n - distinct)])
    return rng.permutation(vals)


@pytest.mark.parametrize("session_share", [0.3, 0.5, 1.0])
def test_an_event_log_with_only_identifier_numbers_is_never_main(tmp_path, session_share):
    rng = _rng()
    log = pd.DataFrame({"date": _days(rng, 5000), "view_id": np.arange(5000),
                        "session_id": _ints(rng, 5000, int(5000 * session_share))})
    sales = pd.DataFrame({"date": _days(rng, 400), "amount": rng.uniform(1, 90, 400).round(2)})
    d = _init(tmp_path, {"page_views": log, "sales": sales})
    assert d["main"] == "sales"
    assert d["tables"]["page_views"]["suggested_kind"] != "main"


@pytest.mark.parametrize("distinct,main", [(300, "other"), (299, "tally")])
def test_integer_column_is_an_identifier_from_a_third_of_rows_distinct(tmp_path, distinct, main):
    # 1000 rows in 'tally' (the larger table): its only number is an identifier at 300/1000 = 0.3, a measure at 299/1000
    rng = _rng()
    tally = pd.DataFrame({"date": _days(rng, 1000), "code": _ints(rng, 1000, distinct)})
    other = pd.DataFrame({"date": _days(rng, 900), "amount": rng.uniform(1, 9, 900).round(2)})
    assert _init(tmp_path, {"tally": tally, "other": other})["main"] == main



# ---------- 2. two dates in one table ----------

def _two_dates(n, measure, first="opened_on", second="closed_on"):
    rng = _rng()
    start = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 300, n), unit="D")
    df = pd.DataFrame({first: _iso(start), second: _iso(start + pd.to_timedelta(rng.integers(0, 10, n), unit="D")),
                       "ref_no": np.arange(n), "team": rng.choice(["north", "south", "east"], n)})
    if measure:
        df["fee"] = rng.uniform(10, 400, n).round(2)
    return df


def _big_sales():
    rng = _rng()
    return pd.DataFrame({"day": _days(rng, 3000), "amount": rng.uniform(1, 90, 3000).round(2)})


@pytest.mark.parametrize("rows,measure,start_end", [(1000, False, True), (1000, True, False), (200, True, True), (201, True, False)])
def test_two_ordered_dates_are_a_start_end_pair_only_without_a_measure_or_when_short(tmp_path, rows, measure, start_end):
    d = _init(tmp_path, {"jobs": _two_dates(rows, measure), "sales": _big_sales()})
    t = d["tables"]["jobs"]
    assert ("start_end" in t) is start_end
    assert t["date_columns"] == ["opened_on", "closed_on"]
    assert (t["suggested_kind"] in ("events", "calendar")) is start_end


def test_an_orders_table_with_ordered_and_shipped_dates_can_be_the_main_table(tmp_path):
    orders = _two_dates(1000, True, "ordered_on", "shipped_on").rename(columns={"fee": "amount"})
    d = _init(tmp_path, {"orders": orders, "regions": pd.DataFrame({"team": ["north", "south", "east"], "boss": ["a", "b", "c"]})})
    t = d["tables"]["orders"]
    assert d["main"] == "orders" and t["suggested_kind"] == "main"
    assert "start_end" not in t and t["date_columns"] == ["ordered_on", "shipped_on"]


def test_a_three_row_campaign_table_is_still_events(tmp_path):
    rng = _rng()
    sales = pd.DataFrame({"day": _days(rng, 400), "item": rng.choice(["P1", "P2", "P3"], 400),
                          "amount": rng.uniform(1, 90, 400).round(2)})
    camp = pd.DataFrame({"begin": ["2025-03-01", "2025-05-10", "2025-08-01"], "finish": ["2025-03-07", "2025-05-12", "2025-08-09"],
                         "title": ["spring push", "clearance", "back to school"], "product": ["P1", "P2", "P3"]})
    t = _init(tmp_path, {"sales": sales, "camp": camp})["tables"]["camp"]
    assert t["suggested_kind"] == "events" and t["start_end"] == ["begin", "finish"]



# ---------- 3. dates spread over sibling columns ----------

def _monthly_activity():
    rng = _rng()
    months = pd.period_range("2022-01", "2025-12", freq="M")
    df = pd.DataFrame({"Year": months.year, "Month": months.month, "flights": rng.integers(80, 400, len(months)),
                       "points": rng.uniform(1e3, 9e3, len(months)).round(2)})
    comp = {"name": "year+month", "kind": "year_month", "columns": ["Year", "Month"]}
    return {"table": df, "composite": comp, "periods": months, "freq": "M", "roles": {"points": "amount", "flights": "quantity"},
            "metric": "points", "run": (("2025-03-01", "2025-03-31"), "2025-03")}


def _bookings():
    rng = _rng()
    # every day of the two years has bookings (3 a day, plus a few extra days of spread): a daily table with holes would
    # be stopped by the missing-days check, which is not what this fixture is for
    days = pd.date_range("2024-01-01", periods=731, freq="D")
    when = pd.DatetimeIndex(days.repeat(3))
    df = pd.DataFrame({"arrival_year": when.year, "arrival_month": list(when.month_name()), "arrival_day": when.day,
                       "price": rng.uniform(40, 900, len(when)).round(2)})
    comp = {"name": "arrival_year+arrival_month+arrival_day", "kind": "year_monthname_day",
            "columns": ["arrival_year", "arrival_month", "arrival_day"]}
    return {"table": df, "composite": comp, "periods": when.to_period("D"), "freq": "D", "roles": {"price": "amount"},
            "metric": "price", "run": (("2025-06-01", "2025-06-30"), "2025-06")}


COMPOSITES = {"monthly_activity": _monthly_activity, "bookings": _bookings}


def _confirmed(tmp_path, case):
    d = _init(tmp_path, {"t": case["table"]})
    answers = _answers(d, case["roles"], date_column=f"composite:{case['composite']['name']}")
    intake.confirm(tmp_path / "ws", answers)
    return d, Workspace(tmp_path / "ws")


@pytest.mark.parametrize("case", COMPOSITES)
def test_sibling_date_columns_are_reported_and_the_table_can_be_main(tmp_path, case):
    c = COMPOSITES[case]()
    d = _init(tmp_path, {"t": c["table"]})
    assert d["tables"]["t"]["composite_dates"] == [c["composite"]]
    assert d["main"] == "t"


@pytest.mark.parametrize("case", COMPOSITES)
def test_the_date_column_question_offers_the_composite_date(tmp_path, case):
    c = COMPOSITES[case]()
    d = _init(tmp_path, {"t": c["table"]})
    assert f"composite:{c['composite']['name']}" in _values(_question(d, "date_column"))


def test_a_composite_is_offered_next_to_an_ordinary_date_column(tmp_path):
    rng = _rng()
    df = pd.DataFrame({"day": _days(rng, 500), "fy": rng.integers(2023, 2026, 500), "fm": rng.integers(1, 13, 500),
                       "amount": rng.uniform(1, 90, 500).round(2)})
    d = _init(tmp_path, {"t": df})
    assert d["tables"]["t"]["composite_dates"] == [{"name": "fy+fm", "kind": "year_month", "columns": ["fy", "fm"]}]
    assert {"day", "composite:fy+fm"} <= set(_values(_question(d, "date_column")))


NOT_COMPOSITE = {
    "year_without_month": lambda rng, n: {"Year": rng.integers(2023, 2026, n)},
    "month_without_year": lambda rng, n: {"Month": rng.integers(1, 13, n)},
    "year_before_1900": lambda rng, n: {"Year": rng.integers(1800, 1803, n), "Month": rng.integers(1, 13, n)},
    "month_up_to_13": lambda rng, n: {"Year": rng.integers(2023, 2026, n), "Month": rng.integers(1, 14, n)},
    "month_names_not_english": lambda rng, n: {"Year": rng.integers(2023, 2026, n),
                                               "Month": rng.choice(["janvier", "fevrier", "mars", "avril"], n)},
}


@pytest.mark.parametrize("case", NOT_COMPOSITE)
def test_columns_that_only_look_like_a_year_and_month_are_not_a_composite(tmp_path, case):
    rng = _rng()
    df = pd.DataFrame({"day": _days(rng, 300), **NOT_COMPOSITE[case](rng, 300), "amount": rng.uniform(1, 90, 300).round(2)})
    assert _init(tmp_path, {"t": df})["tables"]["t"].get("composite_dates", []) == []


@pytest.mark.parametrize("case", COMPOSITES)
def test_confirming_a_composite_date_derives_a_real_date_column(tmp_path, case):
    c = COMPOSITES[case]()
    _, ws = _confirmed(tmp_path, c)
    m = next(iter(ws.measures.values()))
    frame = ws.sources.frame(m["source"])
    assert m["date"] in frame.columns and m["date"] not in c["table"].columns
    assert pd.api.types.is_datetime64_any_dtype(frame[m["date"]])
    assert list(frame[m["date"]].dt.to_period(c["freq"])) == list(c["periods"])


@pytest.mark.parametrize("case", COMPOSITES)
def test_a_month_can_be_run_on_a_composite_date(tmp_path, case):
    c = COMPOSITES[case]()
    _, ws = _confirmed(tmp_path, c)
    (a, b), month = c["run"]
    s = run(ws, {"metric": c["metric"], "current": [a, b], "base": "pop"}, write=False)
    mask = pd.Series(c["periods"].strftime("%Y-%m")) == month
    assert not s["errors"] and not s["blocked"]
    assert ws.total(c["metric"], window(a, b)) == pytest.approx(c["table"][c["metric"]][mask].sum())


# hour_offset (a single integer column counting up from 0) is not tested: the contract leaves open what the
# offset is relative to, so there is no date to compare the result against.



# ---------- 4. nothing usable ----------

def _snapshot():
    rng = _rng()
    return {"customers": pd.DataFrame({"customer": [f"c{i}" for i in range(500)],
                                       "contract": rng.choice(["monthly", "yearly", "two-year"], 500),
                                       "tenure": rng.integers(1, 72, 500), "charges": rng.uniform(20, 120, 500).round(2)})}


def _ids_only_log():
    rng = _rng()
    return {"page_views": pd.DataFrame({"date": _days(rng, 3000), "view_id": np.arange(3000), "session_id": _ints(rng, 3000, 1500)})}


def _dates_but_no_numbers():
    rng = _rng()
    return {"notes": pd.DataFrame({"date": _days(rng, 300), "author": rng.choice(["ann", "bo", "cy"], 300),
                                   "body": [f"remark {i}" for i in range(300)]})}


NO_AXIS = {"snapshot": _snapshot, "dates_but_no_numbers": _dates_but_no_numbers}


@pytest.mark.parametrize("case", NO_AXIS)
def test_without_a_date_and_a_measure_init_raises_no_time_axis_without_pointing_at_main(tmp_path, case):
    with pytest.raises(intake.NoTimeAxis) as e:
        _init(tmp_path, NO_AXIS[case]())
    assert isinstance(e.value, ValueError) and "--main" not in str(e.value)


def test_the_message_says_in_plain_words_that_there_are_no_dates_to_compare_periods(tmp_path):
    with pytest.raises(intake.NoTimeAxis) as e:
        _init(tmp_path, _snapshot())
    msg = str(e.value).lower()
    assert "date" in msg and "period" in msg
    assert any(w in msg for w in ("no ", "none", "without", "has not", "lack"))


# ---------- 5. reading ----------

def _write_sales(tmp_path, **cols):
    rng = _rng()
    df = pd.DataFrame({"day": _days(rng, 200), "order_id": np.arange(200), **cols})
    df.to_csv(tmp_path / "sales.csv", index=False)
    return df


def test_the_words_none_and_null_stay_text(tmp_path):
    rng = _rng()
    note = rng.choice(["None", "NULL", "late", "gift wrap", "fragile"], 200)
    _write_sales(tmp_path, note=note, amount=rng.uniform(1, 90, 200).round(2))
    df, _ = draft.load_table(tmp_path / "sales.csv")
    assert df["note"].isna().sum() == 0
    assert set(df["note"]) == {"None", "NULL", "late", "gift wrap", "fragile"}


def _dollar_prices(n=200):
    rng = _rng()
    values = rng.uniform(1, 2500, n).round(2)
    text = [f"${v:,.2f}" + (" " if i % 3 == 0 else "") for i, v in enumerate(values)]
    return values, text


def test_dollar_strings_in_a_table_with_real_numbers_are_profiled_as_a_number(tmp_path):
    values, text = _dollar_prices()
    _write_sales(tmp_path, price=text, units=_rng().integers(1, 6, 200))
    df, _ = draft.load_table(tmp_path / "sales.csv")
    assert next(p for p in draft.profile(df) if p["column"] == "price")["shape"] == "number"
    assert df["price"].dtype.kind == "f" and df["price"].to_numpy() == pytest.approx(values)


def test_dollar_strings_reach_the_workspace_as_floats(tmp_path):
    values, text = _dollar_prices()
    _write_sales(tmp_path, price=text, units=_rng().integers(1, 6, 200))
    d = intake.init([tmp_path / "sales.csv"], tmp_path / "ws", lang="en")
    assert "price" in d["tables"]["sales"]["number_columns"]
    intake.confirm(tmp_path / "ws", _answers(d, {"price": "amount", "units": "quantity"}))
    ws = Workspace(tmp_path / "ws")
    assert ws.total("price", window("2025-01-01", "2025-12-31")) == pytest.approx(values.sum())


def test_header_cells_lose_their_leading_and_trailing_spaces(tmp_path):
    (tmp_path / "sales.csv").write_text(" day ,order_id , amount\n2025-03-01,1,9.5\n2025-03-02,2,7.25\n", encoding="utf-8")
    df, _ = draft.load_table(tmp_path / "sales.csv")
    assert list(df.columns) == ["day", "order_id", "amount"]


# ---------- 6. rows are counted through a key (decided with the owner, 2026-11-03) ----------
# A table with a date and an identifier column but no amount can still be analysed: the metric is the number of
# distinct keys (orders, subscriptions, sessions), never the number of rows, so duplicated rows are not counted twice.
# This replaces the earlier contract that an identifier-only log raises NoTimeAxis.

def test_an_identifier_only_log_is_the_main_table_when_nothing_has_amounts(tmp_path):
    d = _init(tmp_path, _ids_only_log())
    assert d["main"] == "page_views"
    ids = {q["id"]: q for q in d["questions"]}["order_id"]["options"]
    assert "view_id" in [o["value"] if isinstance(o, dict) else o for o in ids]


def test_a_table_with_amounts_beats_a_bigger_log_of_keys(tmp_path):
    rng = _rng()
    tables = {"views": pd.DataFrame({"day": _days(rng, 5000), "view_id": np.arange(5000), "visit_id": _ints(rng, 5000, 2000)}),
              "orders": pd.DataFrame({"day": _days(rng, 400), "order_id": np.arange(400), "visit_id": rng.integers(0, 2000, 400),
                                      "amount": rng.normal(60, 9, 400).round(2)})}
    assert _init(tmp_path, tables)["main"] == "orders"


def test_year_month_day_in_three_whole_number_columns_is_one_daily_date():
    rng = _rng()
    df = pd.DataFrame({"yr": 2024 + rng.integers(0, 2, 200), "mo": rng.integers(1, 13, 200), "dy": rng.integers(13, 29, 200),
                       "v": rng.normal(10, 2, 200).round(2)})
    found = draft.composite_dates(df)
    assert [(c["kind"], c["columns"]) for c in found] == [("year_month_day", ["yr", "mo", "dy"])]


def test_three_letter_month_names_are_recognised():
    rng = _rng()
    df = pd.DataFrame({"y": 2024 + rng.integers(0, 2, 100), "m": rng.choice(["Jan", "Feb", "Mar"], 100), "d": rng.integers(13, 29, 100)})
    assert [c["kind"] for c in draft.composite_dates(df)] == ["year_monthname_day"]


def test_headers_that_collide_once_trimmed_do_not_break_loading(tmp_path):
    (tmp_path / "t.csv").write_text(" a,a,b\n1,2,3\n4,5,6\n", encoding="utf-8")
    from aib.sources import LOADERS
    df = LOADERS["csv"]({"path": "t.csv"}, tmp_path)
    assert list(df.columns).count("a") == 1 and len(df.columns) == 3


def test_a_second_table_dated_only_by_a_composite_can_be_confirmed(tmp_path):
    rng = _rng()
    sales = pd.DataFrame({"day": _days(rng, 400), "order_id": np.arange(400), "channel": rng.choice(["web", "app"], 400),
                          "amount": rng.normal(60, 9, 400).round(2)})
    months = pd.period_range("2023-01", "2025-12", freq="M")
    visits = pd.DataFrame({"Year": np.repeat(months.year, 2), "Month": np.repeat(months.month, 2),
                           "channel": ["web", "app"] * len(months), "visits": rng.integers(100, 900, 2 * len(months))})
    sales.to_csv(tmp_path / "sales.csv", index=False); visits.to_csv(tmp_path / "visits.csv", index=False)
    ws = tmp_path / "ws"
    d = intake.init([tmp_path / "sales.csv", tmp_path / "visits.csv"], ws, lang="en")
    assert d["main"] == "sales"
    answers = {"kind:visits": "business", "date_column": "day", "role:amount": "amount", "order_id": "order_id",
               "dimensions": ["channel"], "role:visits.visits": "visits"}
    intake.confirm(ws, answers)   # used to raise IndexError (no ordinary date column)
    assert Workspace(ws).sources.specs["visits"]["derive_dates"][0]["kind"] == "year_month"


def test_a_small_orders_table_with_two_dates_is_still_analysed_when_it_is_the_only_fact_table(tmp_path):
    rng = _rng()
    days = pd.date_range("2025-01-01", periods=150)
    orders = pd.DataFrame({"ordered_on": days, "shipped_on": days + pd.to_timedelta(rng.integers(1, 5, 150), unit="D"),
                           "order_id": np.arange(150), "amount": rng.normal(60, 9, 150).round(2)})
    d = _init(tmp_path, {"orders": orders})
    assert d["main"] == "orders"          # used to raise NoTimeAxis: "no amount to add up"
    assert d["tables"]["orders"].get("start_end") == ["ordered_on", "shipped_on"]   # the hint stays visible


def test_the_amount_question_says_how_many_cells_are_empty(tmp_path):
    rng = _rng()
    amt = rng.normal(60, 9, 200).round(2)
    amt[:60] = np.nan                                     # 30% empty
    df = pd.DataFrame({"day": _days(rng, 200), "order_id": np.arange(200), "amount": amt})
    d = _init(tmp_path, {"sales": df})
    q = {x["id"]: x for x in d["questions"]}["measure_columns"]
    assert q["empty_share"]["amount"] == pytest.approx(0.30, abs=0.01)
    label = next(o["label"] for o in q["options"] if o["value"] == "amount")
    assert "30%" in label and "empty" in label


# ---------- 7. blanks, reversals and duplicates (decided with the owner, 2026-11-03) ----------
# A blank amount means the order has no amount: it is left out of the order total used for the average per order,
# so the average is amount over the orders that HAVE an amount. A column that marks cancelled or refunded rows is
# asked about at intake; the rows the user names are left out when the table is loaded, so every number, every check
# and every group size sees the same table.

def _blank_amount_table(rng, n=400, share=0.3):
    amt = rng.normal(60, 9, n).round(2)
    amt[rng.random(n) < share] = np.nan
    return pd.DataFrame({"day": pd.date_range("2025-01-01", periods=n), "order_id": np.arange(n), "amount": amt})


def test_the_average_per_order_ignores_orders_that_have_no_amount(tmp_path):
    rng = _rng()
    df = _blank_amount_table(rng)
    ws = tmp_path / "ws"
    df.to_csv(tmp_path / "b.csv", index=False)
    intake.init([tmp_path / "b.csv"], ws, lang="en")
    intake.confirm(ws, {"date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": []})
    W = Workspace(ws)
    w = (df.day.min().date(), df.day.max().date())
    assert W.total("per_id", w) == pytest.approx(df.amount.dropna().mean(), rel=1e-9)      # was 0.7x of it
    assert W.total("id_count", w) == df.amount.notna().sum()


def _status_table(rng, n=300):
    return pd.DataFrame({"day": pd.date_range("2025-01-01", periods=n), "order_id": np.arange(n),
                         "amount": rng.normal(60, 9, n).round(2),
                         "state": rng.choice(["paid", "cancelled", "refunded"], n, p=[0.8, 0.1, 0.1])})


def test_a_column_that_could_mark_reversals_is_asked_about_with_its_values(tmp_path):
    d = _init(tmp_path, {"sales": _status_table(_rng())})
    q = {x["id"]: x for x in d["questions"]}
    assert "reversal_column" in q
    opts = [o["value"] if isinstance(o, dict) else o for o in q["reversal_column"]["options"]]
    assert "state" in opts and "none" in opts
    assert "reversal_values:state" not in q                          # asked after the column is picked, for that column only
    with pytest.raises(intake.NeedsAnswers) as need:
        intake.confirm(tmp_path / "ws", {"date_column": "day", "role:amount": "amount", "order_id": "order_id",
                                         "dimensions": [], "reversal_column": "state"})
    v = need.value.questions[0]
    assert v["id"] == "reversal_values:state"
    assert sorted(o["value"] if isinstance(o, dict) else o for o in v["options"]) == ["cancelled", "paid", "refunded"]
    assert v.get("multi") is True


def test_rows_the_user_marks_as_reversed_are_left_out_everywhere(tmp_path):
    rng = _rng()
    df = _status_table(rng)
    ws = tmp_path / "ws"
    df.to_csv(tmp_path / "s.csv", index=False)
    intake.init([tmp_path / "s.csv"], ws, lang="en")
    intake.confirm(ws, {"date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": ["state"],
                        "reversal_column": "state", "reversal_values:state": ["cancelled", "refunded"]})
    W = Workspace(ws)
    kept = df[df.state == "paid"]
    w = (df.day.min().date(), df.day.max().date())
    assert W.total("amount", w) == pytest.approx(kept.amount.sum())
    assert W.total("id_count", w) == len(kept)
    assert len(W.sources.frame("s")) == len(kept)           # the same table for the checks and the group sizes


def test_leaving_the_reversal_question_unanswered_changes_nothing(tmp_path):
    rng = _rng()
    df = _status_table(rng)
    ws = tmp_path / "ws"
    df.to_csv(tmp_path / "s.csv", index=False)
    intake.init([tmp_path / "s.csv"], ws, lang="en")
    intake.confirm(ws, {"date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": []})
    assert len(Workspace(ws).sources.frame("s")) == len(df)


def test_exact_duplicate_rows_in_a_table_without_a_key_are_named_in_the_draft(tmp_path):
    rng = _rng()
    base = pd.DataFrame({"day": pd.date_range("2025-01-01", periods=100).repeat(2)[:150],
                         "amount": rng.normal(60, 9, 150).round(2), "grp": rng.choice(["a", "b"], 150)})
    dup = pd.concat([base, base.iloc[:20]], ignore_index=True)       # 20 exact repeats
    d = _init(tmp_path, {"lines": dup})
    t = d["tables"]["lines"]
    assert t["duplicate_rows"] == 20
    q = {x["id"]: x for x in d["questions"]}["exact_copies"]       # asked even though no column could identify a row
    assert "20" in q["ask"] and [o["value"] for o in q["options"]] == ["every_row", "once", "unknown"] and q["suggested"] == "unknown"


def test_the_answer_about_exact_copies_decides_how_rows_are_counted_and_no_row_is_removed(tmp_path):
    rng = _rng()
    base = pd.DataFrame({"day": pd.date_range("2025-01-01", periods=100).repeat(2)[:150],
                         "amount": rng.normal(60, 9, 150).round(2)})
    dup = pd.concat([base, base.iloc[:20]], ignore_index=True)
    dup.to_csv(tmp_path / "l.csv", index=False)
    w = (pd.Timestamp("2025-01-01").date(), pd.Timestamp("2025-12-31").date())
    for choice, rows in (("once", 150), ("every_row", 170), ("unknown", 170)):
        ws = tmp_path / f"ws_{choice}"
        intake.init([tmp_path / "l.csv"], ws, lang="en")
        intake.confirm(ws, {"date_column": "day", "role:amount": "amount", "order_id": "none", "dimensions": [],
                            "exact_copies": choice})
        W = Workspace(ws)
        assert len(W.sources.frame("l")) == 170                    # nothing is removed at import
        assert W.total("id_count", w) == rows                      # the answer decides the count of rows
        assert W.total("amount", w) == pytest.approx(dup.amount.sum())   # a sum counts every row whatever the answer


def test_a_zero_one_flag_column_is_offered_as_a_reversal_marker(tmp_path):
    rng = _rng()
    df = pd.DataFrame({"day": pd.date_range("2025-01-01", periods=300), "order_id": np.arange(300),
                       "amount": rng.normal(60, 9, 300).round(2), "is_cancelled": rng.integers(0, 2, 300)})
    d = _init(tmp_path, {"sales": df})
    q = {x["id"]: x for x in d["questions"]}
    assert "is_cancelled" in [o if isinstance(o, str) else o["value"] for o in q["reversal_column"]["options"]]
    with pytest.raises(intake.NeedsAnswers) as need:
        intake.confirm(tmp_path / "ws", {"date_column": "day", "role:amount": "amount", "order_id": "order_id",
                                         "dimensions": [], "reversal_column": "is_cancelled"})
    assert sorted(o["value"] for o in need.value.questions[0]["options"]) == ["0", "1"]


# ---------- 8. one type per column, and exact copies counted the same way every time ----------

def test_a_column_that_turns_to_text_late_in_the_file_is_read_with_one_type(tmp_path):
    rows = ["a,b"] + [f"{i},{i % 3}" for i in range(300000)] + ["300000,NA"]     # pandas guesses types block by block, from about 250,000 rows
    (tmp_path / "t.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    from aib.sources import LOADERS
    df = LOADERS["csv"]({"path": "t.csv"}, tmp_path)
    kinds = {type(x).__name__ for x in df["b"].dropna()}
    assert len(kinds) == 1, kinds                                                   # was {'int', 'str'}


def test_the_number_of_exact_copies_does_not_depend_on_how_the_file_is_chunked(tmp_path):
    rng = _rng()
    n = 300000
    df = pd.DataFrame({"k": rng.integers(0, 40, n), "c": rng.integers(0, 3, n).astype(object)})
    df.loc[n - 5, "c"] = "NA"
    df = pd.concat([df, df.iloc[:100]], ignore_index=True)
    df.to_csv(tmp_path / "t.csv", index=False)
    from aib.sources import LOADERS
    whole = pd.read_csv(tmp_path / "t.csv", keep_default_na=False, na_values=[""], low_memory=False).duplicated().sum()
    assert LOADERS["csv"]({"path": "t.csv"}, tmp_path).duplicated().sum() == whole


# ---------- 9. links between tables: numeric keys and dated parents (architect's step 1, 2026-11-03) ----------
# A sessions table has dates and its own key; an orders table points at it with a whole-number session id. Both must be
# offered as a link. A second whole-number column (user_id) that only happens to fall inside the same range of numbers
# must not be suggested: a child cannot happen before its parent.

def _shop(rng, n_sessions=3000, n_orders=500):
    sid = np.arange(1, n_sessions + 1)
    started = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 90 * 24 * 60, n_sessions), unit="m")
    sessions = pd.DataFrame({"session_id": sid, "started_at": started, "channel": rng.choice(["search", "social", "direct"], n_sessions)})
    pick = rng.choice(sid, n_orders, replace=False)
    placed = sessions.set_index("session_id").loc[pick, "started_at"].values + pd.to_timedelta(rng.integers(1, 30, n_orders), unit="m")
    orders = pd.DataFrame({"order_id": np.arange(n_orders), "session_id": pick, "user_id": rng.integers(1, n_sessions, n_orders),
                           "placed_at": placed, "amount": rng.normal(60, 9, n_orders).round(2)})
    return orders, sessions


def _links_of(d):
    return {(l["left_table"], l["left_column"], l["right_table"], l["right_column"]): l for l in d["links"]}


def test_a_whole_number_session_id_links_to_a_dated_sessions_table(tmp_path):
    orders, sessions = _shop(_rng())
    d = _init(tmp_path, {"orders": orders, "sessions": sessions})
    assert d["main"] == "orders"
    lk = _links_of(d)[("orders", "session_id", "sessions", "session_id")]
    assert lk["suggested"] == "yes" and lk["coverage"] == 1.0 and lk["right_is_key"]
    assert d["tables"]["sessions"]["suggested_kind"] == "lookup"


def test_a_number_that_only_falls_in_the_same_range_is_not_suggested_as_a_link(tmp_path):
    orders, sessions = _shop(_rng())
    d = _init(tmp_path, {"orders": orders, "sessions": sessions})
    fake = _links_of(d).get(("orders", "user_id", "sessions", "session_id"))
    assert fake is None or fake["suggested"] == "no"


def test_revenue_can_be_cut_by_a_channel_that_lives_in_the_sessions_table(tmp_path):
    orders, sessions = _shop(_rng())
    d = _init(tmp_path, {"orders": orders, "sessions": sessions})
    ans = {"kind:sessions": "lookup", "link:orders.session_id>sessions.session_id": "yes", "date_column": "placed_at",
           "order_id": "order_id", "dimensions": ["channel"]}
    ans.update({"measure_columns": ["amount"], "measure_roles": {"amount": "amount"}})
    ws = tmp_path / "ws"
    intake.confirm(ws, ans)
    W = Workspace(ws)
    m = orders.merge(sessions, on="session_id")
    w = (orders.placed_at.min().date(), orders.placed_at.max().date())
    got = {c: W.total("amount", w, {"channel": c}) for c in ("search", "social", "direct")}
    want = m.groupby("channel").amount.sum().to_dict()
    assert got == pytest.approx(want)
    assert sum(got.values()) == pytest.approx(orders.amount.sum())


def test_a_whole_number_key_in_an_undated_lookup_is_linked(tmp_path):
    rng = _rng()
    orders = pd.DataFrame({"day": _days(rng, 300), "order_id": np.arange(300), "product_id": rng.integers(1, 5, 300),
                           "amount": rng.normal(60, 9, 300).round(2)})
    products = pd.DataFrame({"product_id": [1, 2, 3, 4], "category": ["a", "b", "c", "d"]})
    d = _init(tmp_path, {"orders": orders, "products": products})
    lk = _links_of(d)[("orders", "product_id", "products", "product_id")]
    assert lk["suggested"] == "yes" and lk["right_is_key"]


def test_a_bigger_table_of_dense_ids_is_not_taken_for_the_parent_of_a_smaller_one(tmp_path):
    # pageview ids 1..N cover every session id 1..M by chance when N >= M, and both tables have dates in the same
    # direction. The real parent uses the child's whole range of ids; the coincidence only a fraction of its own.
    rng = _rng()
    orders, sessions = _shop(rng, n_sessions=3000, n_orders=500)
    n = 20000
    views = pd.DataFrame({"pageview_id": np.arange(1, n + 1), "session_id": rng.integers(1, 3001, n),
                          "viewed_at": pd.Timestamp("2025-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 90 * 24 * 60, n)), unit="m")})
    d = _init(tmp_path, {"orders": orders, "sessions": sessions, "views": views})
    lk = _links_of(d)
    assert lk[("orders", "session_id", "sessions", "session_id")]["suggested"] == "yes"
    fake = lk.get(("orders", "session_id", "views", "pageview_id"))
    assert fake is None or fake["suggested"] == "no"
    assert [l["right_table"] for l in d["links"] if l["left_table"] == "orders" and l["left_column"] == "session_id"] == ["sessions"]


def test_a_user_id_that_only_falls_inside_the_session_id_range_is_not_a_link(tmp_path):
    # Measured on the real Fuzzy Factory shop: orders.user_id uses 0.83 of the session ids' range, and its dates happen to
    # pass the "child not before parent" test (1.0), so only the range can tell it from the real link (1.00).
    # Here the order times are placed after the session of the SAME-NUMBERED id as well, to keep the date test out of it.
    rng = _rng()
    started = pd.Timestamp("2025-01-01") + pd.to_timedelta(np.arange(5000), unit="m")
    sessions = pd.DataFrame({"session_id": np.arange(1, 5001), "started_at": started, "channel": rng.choice(["a", "b"], 5000)})
    pick = np.sort(rng.choice(np.arange(1, 5001), 600, replace=False))
    uid = rng.integers(1, 4151, 600)
    uid[0], uid[1] = 1, 4151                                                          # 4150 / 4999 = 0.83 of the span
    placed = started[np.maximum(pick, uid) - 1] + pd.Timedelta(minutes=5)             # after both candidate parents
    orders = pd.DataFrame({"order_id": np.arange(600), "session_id": pick, "user_id": uid, "placed_at": placed,
                           "amount": rng.normal(60, 9, 600).round(2)})
    d = _init(tmp_path, {"orders": orders, "sessions": sessions})
    lk = _links_of(d)
    assert lk[("orders", "user_id", "sessions", "session_id")]["child_not_before_parent"] == 1.0
    assert lk[("orders", "session_id", "sessions", "session_id")]["suggested"] == "yes"
    assert lk[("orders", "user_id", "sessions", "session_id")]["suggested"] == "no"
