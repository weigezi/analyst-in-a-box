"""v0.2 item 8: the report says what a senior analyst would say, with amounts, and draws two new charts."""

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
def revenue(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rep")
    ws = tmp / "ws"
    shutil.copytree(DEMO / "workspace", ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    c = answer_key.CASES["revenue_last_week"]
    s = run(ws, {**c["run"], "id": "rev", "question": c["question"]}, out_dir=tmp / "out")
    return s, tmp / "out"


def section(md, n):
    return md.split("\n## ")[n]


def test_first_sentence_has_the_amount(revenue):
    s, out = revenue
    for lang in ("zh", "en"):
        md = (out / f"report.{lang}.md").read_text(encoding="utf-8")
        first = section(md, 1).split("\n", 2)[2].split("\n")[0]
        delta = s["qualify"]["total_cur"] - s["qualify"]["total_base"]
        assert f"{abs(delta):,.0f}" in first, first


def test_conclusion_names_main_cause_offsets_and_ruled_out(revenue):
    s, out = revenue
    n = s["narrative"]
    assert n["main"]["key"] == "marketplace"
    assert any(o["key"] == "web" and o["value"] > 0 for o in n["offsets"])
    assert n["ruled_out"]
    zh = section((out / "report.zh.md").read_text(encoding="utf-8"), 1)
    en = section((out / "report.en.md").read_text(encoding="utf-8"), 1)
    assert "抵掉" in zh and "offset" in en.lower()
    assert "排除" in zh and "ruled out" in en.lower()


def test_every_cut_states_what_led_it(revenue):
    s, out = revenue
    md = (out / "report.zh.md").read_text(encoding="utf-8")
    bd = section(md, 3)
    assert bd.count("主导判断") >= len(s["cuts"])


def test_waterfall_and_daily_charts_with_their_data(revenue):
    s, out = revenue
    ch = s["charts"]
    wf = ch["waterfall"]
    assert wf["base"] == pytest.approx(s["qualify"]["total_base"])
    assert wf["current"] == pytest.approx(s["qualify"]["total_cur"])
    assert wf["base"] + sum(x["value"] for x in wf["steps"]) == pytest.approx(wf["current"])
    daily = ch["daily"]
    assert len(daily["current"]) == len(daily["base"]) == 7
    for lang in ("zh", "en"):
        for name in ("waterfall", "daily"):
            svg = (out / "charts" / f"{name}.{lang}.svg").read_text(encoding="utf-8")
            assert "#D55E00" in svg or "#0072B2" in svg
            assert "#FF0000" not in svg.upper() and "#00FF00" not in svg.upper()
            assert re.search(r"[+\u2212-]\d", svg)
        md = (out / f"report.{lang}.md").read_text(encoding="utf-8")
        assert "charts/waterfall" in md and "charts/daily" in md


def test_ratio_report_states_structure_inside_the_slot(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO / "workspace", ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    c = answer_key.CASES["aov_last_week"]
    run(ws, {**c["run"], "id": "aov"}, out_dir=tmp_path / "out")
    zh = section((tmp_path / "out" / "report.zh.md").read_text(encoding="utf-8"), 1)
    assert "结构" in zh and "新客" in zh and "果篮" in zh
