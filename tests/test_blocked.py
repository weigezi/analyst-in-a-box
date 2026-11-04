"""A report whose pre-delivery checks failed speaks with one voice: nothing on the page is a finding yet.

Found by two outside reviewers who ran the published tool: the head said "do not use the conclusions below" while the
same page said "the breakdown is still computed" and "the conclusions stand", and the Conclusion named a main cause.
"""

import copy
import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from aib import report
from aib.run import run
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store" / "workspace"
WEEK = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}


def heads(md):
    return {h.split("\n")[0]: h for h in md.split("\n## ")}


@pytest.fixture(scope="module")
def blocked(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blocked")
    ws = tmp / "ws"
    shutil.copytree(DEMO, ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    o = pd.read_csv(ws / "data" / "orders.csv.gz")
    pd.concat([o, o[o["order_date"] == "2026-10-21"].head(5)]).to_csv(ws / "data" / "orders.csv.gz", index=False)
    s = run(ws, {**WEEK, "id": "blk"}, out_dir=tmp / "out")
    assert s["blocked"] and s["quality"]["suspect"]
    return s, tmp / "out", ws


def md_of(out, lang):
    return (out / f"report.{lang}.md").read_text(encoding="utf-8")


def test_blocked_report_never_says_the_conclusions_stand(blocked):
    _, out, _ = blocked
    en, zh = md_of(out, "en"), md_of(out, "zh")
    for phrase in ("conclusions stand", "still computed", "conclusions are given"):
        assert phrase not in en, phrase
    for phrase in ("结论照常给出", "下面的拆解照算"):
        assert phrase not in zh, phrase


def test_first_block_says_what_failed_and_that_no_number_is_a_finding_yet(blocked):
    _, out, _ = blocked
    en, zh = md_of(out, "en").split("\n## ")[0], md_of(out, "zh").split("\n## ")[0]
    assert "no number" in en.lower() and "finding" in en.lower()
    assert "order ids repeat" in en                       # plain words, not only the check id
    assert "没有一个数" in zh and "发现" in zh
    assert "订单编号有重复" in zh
    assert zh.count("交付前自检没通过") == 1


def test_conclusion_names_no_cause_and_prints_no_number_as_if_it_held(blocked):
    _, out, _ = blocked
    for lang, word in (("en", "Conclusion"), ("zh", "结论")):
        c = heads(md_of(out, lang))[word]
        assert not re.search(r"main cause|second cause|Offsetting|Ruled out|It started on|The last weeks|主因|次因|抵消|排除|最近几周|开始", c), c
        assert "Marketplace" not in c and "平台" not in c
    en = heads(md_of(out, "en"))["Conclusion"]
    assert "not a finding" in en.lower()                  # the headline number, if shown, is labelled as unverified


def test_breakdown_does_not_say_what_led_or_where_to_drill(blocked):
    _, out, _ = blocked
    b = heads(md_of(out, "en"))["Breakdown"]
    assert "What led" not in b and "drilling into" not in b and "Single point" not in b and "analysis stops here" not in b
    assert "| Segment |" in b                            # the computed table stays, so a person can look for the fault
    bz = heads(md_of(out, "zh"))["拆解"]
    assert "主导判断" not in bz and "往下钻" not in bz


def test_why_and_who_say_not_computed_because_the_check_failed(blocked):
    _, out, _ = blocked
    en = heads(md_of(out, "en"))
    assert "check failed" in en["Why"] and "Marketplace" not in en["Why"]
    assert "check failed" in en["Who should act"] and "No actions recorded yet." not in en["Who should act"]
    zh = heads(md_of(out, "zh"))
    assert "自检没通过" in zh["为什么"] and "自检没通过" in zh["谁该做什么"]
    assert "Waiting for you" not in en and "待你确认" not in zh


def test_data_notes_in_a_blocked_report_do_not_promise_the_numbers_hold(tmp_path):
    root = tmp_path / "ws"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    pd.concat([o, o[o["order_date"] == "2026-10-21"].head(5)]).to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(root, {**WEEK, "id": "n"}, write=False)
    s = copy.deepcopy(s)
    s["quality"]["notes"] = [{"note": "zero_amounts", "source": "orders", "column": "revenue", "rows": 100, "zero": 30, "share": 0.3}]
    s["quality"]["warned"] = ["daily_volume_steady"]
    for c in s["quality"]["checks"]:
        if c["check"] == "daily_volume_steady":
            c["status"] = "fail"
            c["days"] = [{"day": "2026-10-20", "ratio": 2.0}]
    en = report.render(Workspace(root), s, "en")
    assert "Data note" in en and "stop the report" not in en and "conclusions stand" not in en
    zh = report.render(Workspace(root), s, "zh")
    assert "数据提醒" in zh and "结论照常给出" not in zh and "不阻止出报告" not in zh


def test_a_check_other_than_data_quality_blocks_with_one_voice(blocked):
    s, _, ws_root = blocked
    s = copy.deepcopy(s)
    s["quality"]["suspect"] = False
    s["quality"]["failed"] = []
    for c in s["checks"]:
        if c["check"] == "data_quality":
            c.update({"pass": True, "detail": ""})
        if c["check"] == "segments_add_up_to_total":
            c.update({"pass": False, "detail": "Channel: groups add to 1.00, total is 2.00"})
    s["blocked"] = True
    en = report.render(Workspace(ws_root), s, "en")
    head = en.split("\n## ")[0]
    assert "Channel: groups add to 1.00, total is 2.00" in head and "no number" in head.lower()
    assert "Data in doubt" not in en                      # the data-quality paragraph is only for a data-quality failure
    assert "main cause" not in en.lower() and "What led" not in en
    assert "check failed" in heads(en)["Why"]


def test_a_clean_report_is_unchanged_and_the_demo_figures_do_not_move(tmp_path):
    root = tmp_path / "ws"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    s = run(root, {**WEEK, "id": "ok"}, out_dir=tmp_path / "out")
    assert not s["blocked"]
    q = s["qualify"]
    assert round(q["total_cur"] / q["total_base"] - 1, 4) == -0.0965 and round(q["robust_z"], 2) == -4.47
    en = (tmp_path / "out" / "report.en.md").read_text(encoding="utf-8")
    assert "The main cause is" in en and "What led" in en
    assert "do not use" not in en and "no number" not in en.split("\n## ")[0].lower()
    assert len(s["checks"]) == 12
