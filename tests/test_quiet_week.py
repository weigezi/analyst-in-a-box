"""A quiet week stops at the first cut. The report must still name where the movement sat (item 4), and its two
sentences about the top group must agree with the user's single-point threshold (item 5)."""

import re
import sys
from pathlib import Path

import pytest

from aib.run import run

sys.path.insert(0, str(Path(__file__).absolute().parent))
import synth  # noqa: E402

RUN = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "dimensions": ["channel"]}


def quiet(tmp_path, seed, **rules):
    df = synth.orders(seed=seed, per_day=40, start="2025-06-01", end="2026-10-25")
    root = synth.workspace(tmp_path / f"ws{seed}", df, rules_extra=rules)
    s = run(root, {**RUN, "id": "q"}, out_dir=tmp_path / f"out{seed}")
    md = {l: (tmp_path / f"out{seed}" / f"report.{l}.md").read_text(encoding="utf-8") for l in ("en", "zh")}
    return s, md


def section(md, *titles):
    return next(c for c in md.split("\n## ") if c.startswith(titles))


def test_a_quiet_week_names_the_largest_movers_of_the_first_cut(tmp_path):
    s, md = quiet(tmp_path, 1)
    cut = s["cuts"][0]
    assert not s["slots"] and cut["decision"]["then"]["reason"] == "whole_number_within_usual_range"
    ranked = sorted(cut["result"]["segments"], key=lambda x: -abs(x["delta"]))
    en = section(md["en"], "Who should act")
    assert "No actions recorded yet." not in en
    for seg in ranked[:2]:
        sign = "−" if seg["delta"] < 0 else "+"
        assert f"channel={seg['key']} {sign}" in en, en
    assert f"channel={ranked[2]['key']}" not in en
    assert "no owner" in en.lower() and "within its usual range" in en
    zh = section(md["zh"], "谁该做什么")
    assert "没有登记负责人" in zh and f"channel={ranked[0]['key']}" in zh
    assert re.search(r"[+\u2212]\d", zh)


def test_nothing_is_invented_the_movers_are_the_cut_rows_not_an_owner(tmp_path):
    s, md = quiet(tmp_path, 1)
    en = section(md["en"], "Who should act")
    assert "manager" not in en.lower() and "responsible for" not in en.lower()
    assert "Tell me who owns it" in en


def test_a_recorded_action_still_wins_over_the_fallback(tmp_path):
    s, md = quiet(tmp_path, 1)
    assert s["actions"] == []
    # the existing fallback for a drilled slice is untouched
    s2, md2 = quiet(tmp_path, 9)
    assert s2["slots"]
    assert "The movement sits here: channel=" in section(md2["en"], "Who should act")


def test_a_group_above_the_threshold_that_is_not_drilled_is_explained(tmp_path):
    s, md = quiet(tmp_path, 2)
    cut = s["cuts"][0]
    share = cut["gate"]["top1_abs_share"]
    assert cut["decision"]["then"]["action"] == "stop" and share > 0.5
    assert cut["decision"]["then"]["reason"] == "whole_number_within_usual_range"
    en = section(md["en"], "Breakdown")
    assert "no group moved clearly beyond the others" not in en
    assert f"{share:.1%}" in en and "50.0%" in en                  # what the share is, what the threshold is
    assert "usual range" in en and "not drilled" in en.lower()
    zh = section(md["zh"], "拆解")
    assert f"{share:.1%}" in zh and "50.0%" in zh and "不往下钻" in zh


def test_the_sentence_follows_the_users_threshold(tmp_path):
    s, md = quiet(tmp_path, 1, single_point_min_share=0.3)
    share = s["cuts"][0]["gate"]["top1_abs_share"]
    assert 0.3 < share < 0.5
    en = section(md["en"], "Breakdown")
    assert f"{share:.1%}" in en and "30.0%" in en
    s0, md0 = quiet(tmp_path, 1)
    assert "no group moved clearly beyond the others" in section(md0["en"], "Breakdown")   # below threshold: the plain sentence


def test_a_spread_that_fails_the_swing_test_says_which_test(tmp_path):
    s, md = quiet(tmp_path, 14)
    cut = s["cuts"][0]
    assert cut["decision"]["then"]["reason"] == "spread_or_noise" and cut["gate"]["top1_abs_share"] > 0.5
    en = section(md["en"], "Breakdown")
    assert "no group moved clearly beyond the others" not in en
    assert f"{cut['gate']['top1_abs_share']:.1%}" in en and "50.0%" in en
    assert "own usual swings" in en or "in step with" in en
