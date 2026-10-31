"""v0.2 items 5, 6 and 7: windows that line up, the bugs found in the 0.1 audit, and a metric tree expanded to its leaves."""

import datetime as dt
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

from aib import qualify, windows
from aib.run import run
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store" / "workspace"
sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402

D = dt.date.fromisoformat


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    dst = tmp_path_factory.mktemp("demo") / "ws"
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    return Workspace(dst)


# ---------- 5. windows ----------

def test_month_to_date_aligns_by_calendar():
    b, note = windows.base((D("2026-10-01"), D("2026-10-25")), "pop")
    assert b == (D("2026-09-01"), D("2026-09-25")) and note == "month_to_date"
    b, note = windows.base((D("2026-02-01"), D("2026-02-28")), "pop")
    assert b == (D("2026-01-01"), D("2026-01-31")) and note == "calendar_month"
    b, _ = windows.base((D("2026-06-01"), D("2026-06-30")), "yoy")
    assert b == (D("2025-06-01"), D("2025-06-30"))


def test_single_day_pop_aligns_weekday():
    b, note = windows.base((D("2026-10-22"), D("2026-10-22")), "pop")
    assert b == (D("2026-10-15"), D("2026-10-15")) and note == "same_weekday_last_week"


def test_week_yoy_stays_weekday_aligned():
    b, note = windows.base((D("2026-10-19"), D("2026-10-25")), "yoy")
    assert b == (D("2025-10-20"), D("2025-10-26")) and note == "same_weekdays_364_days"


def test_history_matches_the_base_kind():
    cur, base = (D("2026-10-01"), D("2026-10-25")), (D("2026-09-01"), D("2026-09-25"))
    h = windows.history(cur, base, "pop", 3)
    assert h[0] == ((D("2026-09-01"), D("2026-09-25")), (D("2026-08-01"), D("2026-08-25")))
    cur, base = (D("2026-10-19"), D("2026-10-25")), (D("2026-09-21"), D("2026-09-27"))
    h = windows.history(cur, base, None, 2)
    assert h[0] == ((D("2026-10-12"), D("2026-10-18")), (D("2026-09-14"), D("2026-09-20")))


def test_explicit_month_base_gives_a_comparable_z(demo):
    s = run(demo, {"metric": "revenue", "current": ["2026-10-01", "2026-10-25"], "base": ["2026-09-01", "2026-09-25"]}, write=False)
    q = s["qualify"]
    # the history is month-to-date against the month before, like the question (0.1 used weekly year-on-year)
    assert q["history_basis"]["kind"] == "month_to_date"
    newest = q["history"][0]
    assert newest["window"][0].endswith("-01") and newest["window"][1].endswith("-25") and newest["base"][1].endswith("-25")
    # September against August holds Mid-Autumn on one side only: it is left out of the history, and named
    assert {"window": ["2026-09-01", "2026-09-25"], "base": ["2026-08-01", "2026-08-25"], "holidays": ["mid_autumn"]} \
        in q["history_basis"]["left_out_for_holidays"]
    assert q["robust_z"] is not None


def test_unequal_months_are_compared_per_day(demo):
    s = run(demo, {"metric": "revenue", "current": ["2026-10-01", "2026-10-25"], "base": ["2026-09-01", "2026-09-30"],
                   "per_day": True}, write=False)
    assert not s["blocked"], [c for c in s["checks"] if not c["pass"]]
    assert s["window_days"] == [25, 30] and s["per_day"]
    full = demo.total("revenue", (D("2026-09-01"), D("2026-09-30")))
    assert s["qualify"]["total_base"] == pytest.approx(full / 30)


def test_unequal_windows_without_per_day_are_blocked_with_a_way_out(demo):
    s = run(demo, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": ["2025-10-20", "2025-10-27"]}, write=False)
    c = next(c for c in s["checks"] if c["check"] == "windows_same_length")
    assert not c["pass"] and "per_day" in c["detail"]


def test_single_day_run_notes_the_weekday_alignment(demo):
    s = run(demo, {"metric": "revenue", "current": ["2026-10-22", "2026-10-22"], "base": "pop"}, write=False)
    assert s["base"] == (D("2026-10-15"), D("2026-10-15"))
    assert any(n.get("window") == "same_weekday_last_week" for n in s["notes"])


def test_holiday_in_one_period_offers_and_applies_an_exclusion(demo):
    cfg = {"metric": "revenue", "current": ["2026-09-21", "2026-09-27"], "base": "yoy"}
    s = run(demo, cfg, write=False)
    assert s["qualify"]["holiday_misaligned"]
    plans = s["qualify"]["holiday_plans"]
    assert {p["kind"] for p in plans} >= {"exclude", "shift_base"}
    ex = run(demo, {**cfg, "holiday": "exclude"}, write=False)
    assert ex["excluded_days"] and "2026-09-21" in ex["excluded_days"]
    g0 = s["qualify"]["total_cur"] / s["qualify"]["total_base"] - 1
    g1 = ex["qualify"]["total_cur"] / ex["qualify"]["total_base"] - 1
    assert abs(g1 - 0.08) < abs(g0 - 0.08)


# ---------- 6. bugs from the audit ----------

def test_flat_history_is_not_called_too_short():
    q = qualify.unusualness([0.1, 0.1, 0.1, 0.1, 0.2], 0.5)
    assert q["history_mad"] == 0 and q["robust_z"] is not None and q["z_method"] == "mean_absolute_deviation"
    q = qualify.unusualness([0.1] * 6, 0.5)
    assert q["robust_z"] is None and q["z_missing_reason"] == "flat_history"
    q = qualify.unusualness([0.1], 0.5)
    assert q["z_missing_reason"] == "short_history"


def test_flat_history_report_says_flat(tmp_path):
    from aib import report
    ws = Workspace(DEMO)
    s = run(ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    s["qualify"].update(robust_z=None, z_missing_reason="flat_history", history_n=10)
    for lang, word in (("zh", "一模一样"), ("en", "flat")):
        assert word in report.render(ws, s, lang)


def test_second_order_without_a_base_does_not_crash(tmp_path):
    df = synth.orders(seed=2, start="2026-09-01")
    ws = Workspace(synth.workspace(tmp_path, df))
    s = run(ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "previous": True}, write=False)
    assert s["blocked"]
    assert any(c["check"] == "base_has_data" and not c["pass"] for c in s["checks"])


def test_new_category_with_no_base_does_not_crash(tmp_path, demo):
    root = tmp_path / "ws"
    shutil.copytree(demo.root, root, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    new = o[o["order_date"] >= "2026-10-19"].sample(150, random_state=1).copy()
    new["order_id"] = new["order_id"].astype(str) + "N"
    new["category"] = "candle"
    pd.concat([o, new]).to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy",
                              "compare": "app_vs_web", "filters": {"category": "candle"}}, write=False)
    assert s["blocked"] and any(c["check"] == "base_has_data" and not c["pass"] for c in s["checks"])


# ---------- 7. metric tree ----------

def test_tree_expands_to_leaves_and_closes(demo):
    s = run(demo, {"metric": "gross_profit", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    t = s["tree"]
    leaves = {f["factor"] for f in t["leaves"]}
    assert leaves == {"visits", "cr", "aov", "margin_rate"}
    assert t["closed"]
    assert {i["identity"] for i in s["horizontal"]} == {"profit_by_margin", "revenue_by_orders", "orders_by_traffic"}
    assert set(t["ratio_splits"]) >= {"aov", "margin_rate"}
    for split in t["ratio_splits"].values():
        assert split["closed"] and split["larger_effect"] in ("structure", "rate", "tie")


def test_tree_stops_where_a_factor_cannot_be_filtered(demo):
    s = run(demo, {"metric": "gross_profit", "current": ["2026-10-19", "2026-10-25"], "base": "yoy",
                   "filters": {"region": "east"}}, write=False)
    leaves = {f["factor"] for f in s["tree"]["leaves"]}
    assert leaves == {"orders", "aov", "margin_rate"}
