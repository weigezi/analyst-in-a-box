"""Exact copies of a row, per metric (owner decision 3): room-nights, revenue and the average price count every row;
a count of rows and the ratios built on it depend on whether a copy is a second real record, so both readings are
computed and a second number is shown when they differ by more than 5%.

Every table is invented here (seed 3); nothing is read from outside tmp_path.
"""

import numpy as np
import pandas as pd
import pytest

from aib import intake
from aib.workspace import Workspace

W_ALL = (pd.Timestamp("2025-01-01").date(), pd.Timestamp("2025-03-31").date())


def _rng():
    return np.random.default_rng(3)


def _bookings(copies=60, n=400):
    """No identifier column. `copies` rows are exact repeats of earlier rows."""
    rng = _rng()
    base = pd.DataFrame({"day": (pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 90, n), unit="D")).strftime("%Y-%m-%d"),
                         "site": rng.choice(["north", "south"], n), "nights": rng.integers(1, 6, n),
                         "rate": rng.uniform(50, 200, n).round(2)})
    return pd.concat([base, base.iloc[:copies]], ignore_index=True)


def _ws(tmp_path, frame, copies, name="ws"):
    f = tmp_path / "b.csv"
    frame.to_csv(f, index=False)
    ws = tmp_path / name
    d = intake.init([f], ws, lang="en")
    ans = {q["id"]: "skip" for q in d["questions"] if q["id"].startswith("role:")}
    ans.update(date_column="day", dimensions=["site"], order_id="none", unit_price="rate", unit_price_times="nights",
               **({"exact_copies": copies} if copies else {}))
    intake.confirm(ws, ans)
    return Workspace(ws)


# ---------- the import question ----------

def test_exact_copies_without_a_key_are_asked_with_three_options_and_unknown_is_suggested(tmp_path):
    f = tmp_path / "b.csv"
    _bookings().to_csv(f, index=False)
    d = intake.init([f], tmp_path / "ws", lang="en")
    q = next(x for x in d["questions"] if x["id"] == "exact_copies")
    assert [o["value"] for o in q["options"]] == ["every_row", "once", "unknown"] and q["suggested"] == "unknown"
    assert "60" in q["ask"]
    assert not any(x["id"] == "duplicate_rows" for x in d["questions"])


def test_the_chosen_reading_is_recorded_and_no_row_is_removed_at_import(tmp_path):
    frame = _bookings()
    for choice in ("every_row", "once", "unknown"):
        w = _ws(tmp_path, frame, choice, name=f"ws_{choice}")
        assert w.project["sources"]["b"]["exact_copies"] == choice
        assert len(w.sources.frame("b")) == len(frame)


# ---------- the numbers ----------

def test_nights_revenue_and_the_average_price_count_every_row_under_every_reading(tmp_path):
    frame = _bookings()
    for choice in ("every_row", "once", "unknown"):
        w = _ws(tmp_path, frame, choice, name=f"ws_{choice}")
        assert w.total("nights", W_ALL) == frame.nights.sum()
        assert w.total("rate_times_nights", W_ALL) == pytest.approx((frame.rate * frame.nights).sum())
        assert w.total("per_unit", W_ALL) == pytest.approx((frame.rate * frame.nights).sum() / frame.nights.sum())
        assert w.copies_policy("nights") == "every" and w.copies_policy("per_unit") == "every"


def test_a_count_of_rows_depends_and_has_both_readings(tmp_path):
    frame = _bookings()
    w = _ws(tmp_path, frame, "unknown")
    assert w.copies_policy("id_count") == "depends"
    assert w.total("id_count", W_ALL, copies="each") == len(frame)
    assert w.total("id_count", W_ALL, copies="once") == len(frame.drop_duplicates())
    assert w.total("id_count", W_ALL) == len(frame)                    # the default is every row


def test_the_ratio_over_a_count_depends_too_and_filters_apply_to_both_readings(tmp_path):
    frame = _bookings()
    w = _ws(tmp_path, frame, "unknown")
    assert w.copies_policy("per_id") == "depends"
    once = frame.drop_duplicates()
    south = once[once.site == "south"]
    assert w.total("id_count", W_ALL, {"site": "south"}, copies="once") == len(south)
    assert w.total("nights", W_ALL, {"site": "south"}, copies="once") == south.nights.sum()


def test_both_readings_come_with_a_flag_when_they_differ_by_more_than_five_percent(tmp_path):
    w = _ws(tmp_path, _bookings(copies=60), "unknown")
    r = w.copies_readings("id_count", W_ALL)
    assert r["each"] == 460 and r["once"] == 400 and r["differ"] is True and r["relative_difference"] == pytest.approx(60 / 400)
    assert r["param"] == "copies_second_number_min_diff" and r["reason"]


def test_no_flag_when_the_readings_are_within_five_percent_and_none_for_a_metric_that_does_not_depend(tmp_path):
    w = _ws(tmp_path, _bookings(copies=10), "unknown")
    r = w.copies_readings("id_count", W_ALL)
    assert r["differ"] is False and r["each"] == 410 and r["once"] == 400
    assert w.copies_readings("nights", W_ALL) is None


def test_the_users_answer_chooses_the_headline_reading(tmp_path):
    frame = _bookings()
    assert _ws(tmp_path, frame, "once", name="o").total("id_count", W_ALL) == len(frame.drop_duplicates())
    assert _ws(tmp_path, frame, "every_row", name="e").total("id_count", W_ALL) == len(frame)
