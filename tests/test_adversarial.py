"""v0.2 item 9: questions built to trip the skill. Each one has a known truth and an expected behaviour.

Expected behaviours:
  find      the planted slice is the reported main cause
  quiet     nothing is drilled into (the honest answer is "within the usual range")
  suspect   the data is flagged as in doubt and nothing is marked explained
  blocked   the pre-delivery checks stop the report
  unsure    the run says it cannot tell (no history, or the slice is too small to judge)

At the end the run prints a false-alarm rate (drilled or claimed something where nothing was planted) and a
miss rate (did not find what was planted), and asserts both are zero on this set.
"""

import datetime as dt
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

from aib.run import run
from aib.workspace import Workspace

sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402

WEEK = ["2026-10-19", "2026-10-25"]
RESULTS = []


def leaf_pairs(s):
    out = []
    for x in s["slots"]:
        if x.get("leaf", True):
            out.append({(d, v) for d, v in x["path"]} | {(x["dimension"], x["value"])})
    return out


def judge(s, expect, want=None):
    drilled = bool(s["slots"])
    if expect == "find":
        return any(set(want) <= p for p in leaf_pairs(s)) and not s["blocked"]
    if expect == "quiet":
        return not drilled
    if expect == "suspect":
        return s["quality"]["suspect"] and not any(x["status"] == "explained" for x in s["slots"])
    if expect == "blocked":
        return s["blocked"]
    if expect == "warned":
        return bool(s["quality"]["warned"]) and all(x["status"] != "explained" for x in s["slots"])
    if expect == "unsure":
        return not drilled or all(x["status"] != "explained" for x in s["slots"])
    raise ValueError(expect)


def ws_for(tmp, df, **kw):
    return Workspace(synth.workspace(tmp, df, **kw))


CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


@case
def missing_two_days(tmp):
    df = synth.orders(seed=21)
    df = df[~df["order_date"].isin(["2026-10-24", "2026-10-25"])]
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "suspect", None


@case
def week_loaded_twice(tmp):
    df = synth.orders(seed=22)
    df = pd.concat([df, df[df["order_date"] >= WEEK[0]]])
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "suspect", None


@case
def pure_noise_week(tmp):
    return ws_for(tmp, synth.orders(seed=23)), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "quiet", None


@case
def pure_noise_aov(tmp):
    return ws_for(tmp, synth.orders(seed=24)), {"metric": "aov", "current": WEEK, "base": "yoy"}, "quiet", None


@case
def two_value_dimension_quiet(tmp):
    return (ws_for(tmp, synth.orders(seed=25)),
            {"metric": "revenue", "current": ["2026-08-03", "2026-08-09"], "base": "pop", "dimensions": ["customer_type"],
             "mode": "fixed"}, "quiet", None)


@case
def cross_cause(tmp):
    df = synth.orders(seed=26, effects=[{"where": {"channel": "b", "region": "y"}, "start": "2026-10-12", "orders": 0.2}])
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "find", [("channel", "b"), ("region", "y")]


@case
def single_channel_drop(tmp):
    df = synth.orders(seed=27, effects=[{"where": {"channel": "a"}, "start": "2026-10-12", "orders": 0.6}])
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "find", [("channel", "a")]


@case
def new_product_without_base(tmp):
    dims = {"channel": {"a": 0.5, "b": 0.3, "c": 0.2}, "category": {"old1": 0.5, "old2": 0.5, "fresh": 0.3}}
    df = synth.orders(seed=28, dims=dims, effects=[{"where": {"category": "fresh"}, "end": "2026-10-11", "orders": 0.0}])
    return (ws_for(tmp, df, dims=["channel", "category"]),
            {"metric": "revenue", "current": WEEK, "base": "yoy"}, "find", [("category", "fresh")])


@case
def second_order_with_empty_base(tmp):
    df = synth.orders(seed=35, start="2026-09-20")
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy", "previous": True}, "blocked", None


@case
def definition_switch_to_cents(tmp):
    df = synth.orders(seed=29)
    m = df["order_date"] >= "2026-10-22"
    df.loc[m, "revenue"] = df.loc[m, "revenue"] * 100
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "suspect", None


@case
def channel_renamed(tmp):
    # A rename is a 'warn' check (maintainer, 2026-10-31): flagged at the top, not blocked. It must still not be
    # explained as a real change, and with no world entry nothing can be cited, so "unsure" is the right answer.
    df = synth.orders(seed=30)
    df.loc[(df["order_date"] >= "2026-10-19") & (df["channel"] == "b"), "channel"] = "b2"
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "yoy"}, "warned", None


@case
def tiny_denominator(tmp):
    dims = {"category": {"big1": 0.5, "big2": 0.5, "tiny": 0.0015}, "region": {"x": 0.6, "y": 0.4}}
    df = synth.orders(seed=31, dims=dims, per_day=400, sigma=0.3,
                      effects=[{"where": {"category": "tiny"}, "start": WEEK[0], "price": 25.0}])
    return (ws_for(tmp, df, dims=["category", "region"]),
            {"metric": "aov", "current": WEEK, "base": "yoy", "mode": "fixed", "dimensions": ["category"]}, "unsure", None)


@case
def holiday_in_one_period(tmp):
    df = synth.orders(seed=32, effects=[{"start": "2026-09-21", "end": "2026-09-25", "orders": 1.8}])
    cal = [{"name": "festival", "start": "2025-10-04", "end": "2025-10-08"},
           {"name": "festival", "start": "2026-09-21", "end": "2026-09-25"}]
    ws = ws_for(tmp, df, calendar=cal)
    return ws, {"metric": "revenue", "current": ["2026-09-21", "2026-09-27"], "base": "yoy", "holiday": "exclude"}, "quiet", None


@case
def unequal_months(tmp):
    return (ws_for(tmp, synth.orders(seed=33)),
            {"metric": "revenue", "current": ["2026-10-01", "2026-10-25"], "base": ["2026-09-01", "2026-09-30"]}, "blocked", None)


@case
def no_history_at_all(tmp):
    df = synth.orders(seed=34, start="2026-10-05", effects=[{"where": {"channel": "a"}, "start": "2026-10-19", "orders": 0.9}])
    return ws_for(tmp, df), {"metric": "revenue", "current": WEEK, "base": "pop"}, "unsure", None


@pytest.mark.parametrize("name", list(CASES))
def test_adversarial(name, tmp_path):
    ws, cfg, expect, want = CASES[name](tmp_path)
    s = run(ws, cfg, write=False)
    ok = judge(s, expect, want)
    RESULTS.append({"case": name, "expect": expect, "ok": ok, "drilled": bool(s["slots"]),
                    "planted": expect == "find"})
    assert ok, (name, expect, [x["id"] for x in s["slots"]], s["quality"]["status"],
                [c["check"] for c in s["checks"] if not c["pass"]])


def test_rates_summary():
    if len(RESULTS) < len(CASES):
        pytest.skip("run the whole file to get the rates")
    nothing = [r for r in RESULTS if not r["planted"]]
    planted = [r for r in RESULTS if r["planted"]]
    false_alarm = sum(1 for r in nothing if not r["ok"]) / len(nothing)
    miss = sum(1 for r in planted if not r["ok"]) / len(planted)
    print(f"\nadversarial: {len(RESULTS)} cases, false-alarm rate {false_alarm:.0%} ({len(nothing)} without a planted cause), "
          f"miss rate {miss:.0%} ({len(planted)} with one)")
    assert false_alarm == 0 and miss == 0
