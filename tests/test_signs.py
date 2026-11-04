"""The headline picks its direction word from the true sign of the unrounded change, and says so when nothing shows.

Found by an outside reviewer: a conversion rate near 1e-6 printed `fell from 0.00% to 0.00% (-0.00%)`.
"""

import copy
import sys
from pathlib import Path

import pytest

from aib import report
from aib.run import run
from aib.workspace import Workspace

sys.path.insert(0, str(Path(__file__).absolute().parent))
import synth  # noqa: E402


@pytest.fixture(scope="module")
def base_state(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("signs")
    df = synth.orders(seed=2, per_day=20, start="2025-08-01", end="2026-10-25")
    root = synth.workspace(tmp / "ws", df)
    s = run(root, {"metric": "aov", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    return root, s


def headline(base_state, lang, metric_unit, base, cur):
    root, s = base_state
    ws = Workspace(root)
    ws.metrics["aov"]["unit"] = metric_unit
    s = copy.deepcopy(s)
    s["qualify"]["total_base"], s["qualify"]["total_cur"] = base, cur
    md = report.render(ws, s, lang)
    line = next(x for x in md.split("\n## ")[1].split("\n") if x.startswith("**"))
    return line


def test_a_tiny_ratio_that_falls_does_not_print_zero_to_zero(base_state):
    en = headline(base_state, "en", "ratio", 1.0e-6, 0.8867e-6)
    assert "0.00% to 0.00%" not in en and "−0.00%" not in en
    assert "no visible change at this precision" in en
    assert "1.00e-06" in en and "8.87e-07" in en           # the unrounded values, so the reader can see they differ
    zh = headline(base_state, "zh", "ratio", 1.0e-6, 0.8867e-6)
    assert "0.00% 到 0.00%" not in zh and "−0.00%" not in zh
    assert "在这个精度下看不出变化" in zh and "1.00e-06" in zh


def test_equal_values_say_no_visible_change_not_fell_or_rose(base_state):
    for lang, up, down in (("en", "rose", "fell"), ("zh", "升", "降")):
        line = headline(base_state, lang, "ratio", 0.05, 0.05)
        assert up not in line and down not in line, line
        assert "no visible change" in line or "看不出变化" in line


def test_the_true_sign_picks_the_word_in_both_languages(base_state):
    up_en = headline(base_state, "en", "ratio", 0.10, 0.12)
    assert " rose from 10.00% to 12.00% (+2.00%)" in up_en
    down_en = headline(base_state, "en", "ratio", 0.12, 0.10)
    assert " fell from 12.00% to 10.00% (−2.00%)" in down_en
    assert "升到 12.00%（+2.00%）" in headline(base_state, "zh", "ratio", 0.10, 0.12)
    assert "降到 10.00%（−2.00%）" in headline(base_state, "zh", "ratio", 0.12, 0.10)


def test_a_small_rise_that_the_rounding_hides_is_not_called_a_fall(base_state):
    # +0.3 on 1,000: shown to two decimals as 1,000.00 -> 1,000.30; the word must be "rose" and the change must show
    line = headline(base_state, "en", "ratio", 0.100001, 0.100002)
    assert "fell" not in line and "−" not in line


def test_an_amount_that_rounds_to_zero_is_not_reported_as_up_zero(base_state):
    # aov is kind=ratio, so check the amount branch through the revenue metric
    root, _ = base_state
    s = run(root, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    s = copy.deepcopy(s)
    s["qualify"]["total_base"], s["qualify"]["total_cur"] = 50.00, 50.004
    en = report.render(Workspace(root), s, "en").split("\n## ")[1]
    line = next(x for x in en.split("\n") if x.startswith("**"))
    assert "up 0 " not in line and "down 0 " not in line
    assert "no visible change at this precision" in line
    s["qualify"]["total_base"], s["qualify"]["total_cur"] = 50.00, 49.0
    line = next(x for x in report.render(Workspace(root), s, "en").split("\n## ")[1].split("\n") if x.startswith("**"))
    assert "down 1 on the base" in line and "−2.0%" in line
