"""Five engine problems the reviewer found in 0.2's first reports, each pinned down with the demo shop's numbers."""

import re
import shutil
import sys
from pathlib import Path

import pytest

from aib.run import run

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store"
sys.path.insert(0, str(DEMO))
import answer_key  # noqa: E402


@pytest.fixture(scope="module")
def rev(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rev")
    ws = tmp / "ws"
    shutil.copytree(DEMO / "workspace", ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    c = answer_key.CASES["revenue_last_week"]
    return run(ws, {**c["run"], "id": "rev"}, out_dir=tmp / "out"), tmp / "out"


def conclusion(out, lang):
    return (out / f"report.{lang}.md").read_text(encoding="utf-8").split("\n## ")[1]


def test_market_expectation_uses_the_usual_gap(rev):
    s, out = rev
    q = s["qualify"]
    # the shop runs about 4.5 points below its market every week; the plain split credits that gap to "own" each time
    assert -0.06 < q["usual_gap"] < -0.03
    assert q["expected_growth"] == pytest.approx(q["market_growth"] + q["usual_gap"])
    assert abs(q["own_part_usual"]) < abs(q["own_part"])
    assert q["own_part"] == pytest.approx(-104662, abs=1)          # 0.1's plain number, still recorded
    assert s["narrative"]["market"]["is_estimate"]
    unusual = (out / "report.zh.md").read_text(encoding="utf-8").split("\n## ")[2]
    assert "估计" in unusual and "−104,662" in unusual


def test_holiday_weeks_are_left_out_of_the_history_and_named(rev):
    s, out = rev
    lo = s["qualify"]["history_basis"]["left_out_for_holidays"]
    assert any(x["window"][0] == "2026-09-21" for x in lo)          # the Mid-Autumn week (year on year -24.8%)
    assert all(h["window"][0] not in {x["window"][0] for x in lo} for h in s["qualify"]["history"])
    assert "没算进比较的历史" in (out / "report.zh.md").read_text(encoding="utf-8")


def test_no_share_above_100_or_against_the_sign(rev):
    s, out = rev
    for lang in ("zh", "en"):
        md = (out / f"report.{lang}.md").read_text(encoding="utf-8")
        for v in re.findall(r"(\d+(?:\.\d+)?)%", md):
            assert float(v) <= 100.0, (lang, v)
    rest = s["narrative"]["rest"]
    assert rest["top_change"] == pytest.approx(-0.686, abs=0.001)    # marketplace on its own
    assert 0.10 < rest["rest_change"] < 0.115                         # web + app
    assert rest["rest_verdict"] == "as_usual"
    zh = conclusion(out, "zh")
    assert "去掉这一块，其余部分 +10.8%" in zh and "−68.6%" in zh


def test_onset_matches_the_event(rev):
    s, out = rev
    o = s["narrative"]["onset"]
    assert o["found"] and o["start"] == "2026-10-12"
    assert o["events"] == [{"event": "ev_marketplace_fee_change", "event_start": "2026-10-12", "days_from_onset": 0}]
    weeks = s["narrative"]["recent_weeks"]
    prev = next(w for w in weeks if w["window"][0] == "2026-10-12")
    assert prev["whole_change"] == pytest.approx(-0.085, abs=0.001)  # the week before was already -8.5%
    zh = conclusion(out, "zh")
    assert "从 2026-10-12 开始" in zh and "同一天" in zh and "10-12~10-18 −8.5%" in zh


def test_usual_range_and_threshold_lines_are_separate(rev):
    s, _ = rev
    q, r = s["qualify"], s["charts"]["range"]
    lo, hi = q["usual_range"]
    assert lo < q["history_median"] < hi
    assert q["unusual_below"] < lo and q["unusual_above"] > hi
    assert set(r) >= {"usual_range", "unusual_below", "unusual_above", "history", "current_change"}
