"""v0.2 item 4: a record is cited as explaining a change only if it can explain a change.

Something true in both periods (new customers always buy smaller first orders) cannot explain why a number
moved between them. It may explain why a shift in mix matters, never why the mix shifted.
"""

import shutil
import sys
from pathlib import Path

import yaml

from aib import evolve
from aib.run import run
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store"
sys.path.insert(0, str(DEMO))
import answer_key  # noqa: E402

AOV = answer_key.CASES["aov_last_week"]


def copy(tmp):
    dst = tmp / "ws"
    shutil.copytree(DEMO / "workspace", dst, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    return dst


def test_aov_finds_new_customers_times_fruit_baskets(tmp_path):
    s = run(copy(tmp_path), {**AOV["run"], "id": "aov"}, write=False)
    leaf = [x for x in s["slots"] if x.get("leaf", True)]
    assert len(leaf) == 1
    pairs = {(d, v) for d, v in leaf[0]["path"]} | {(leaf[0]["dimension"], leaf[0]["value"])}
    assert {("category", "fruit_basket"), ("customer_type", "new")} <= pairs
    # inside new customers the fruit-basket share roughly doubles and the change is structure-led
    xc = next(c for c in s["cuts"] if c.get("role") == "cross_check")
    assert xc["filters"] == {"customer_type": "new"} and xc["dimension"] == "category"
    fb = next(x for x in xc["result"]["segments"] if x["key"] == "fruit_basket")
    assert fb["weight_base"] < 0.32 and fb["weight_cur"] > 0.45
    assert xc["result"]["larger_effect"] == "structure"


def test_a_both_periods_mechanism_does_not_raise_coverage(tmp_path):
    root = copy(tmp_path)
    cfg = {**AOV["run"], "id": "aov"}
    before = run(root, cfg, write=False)
    leaf = next(x for x in before["slots"] if x.get("leaf", True))
    evolve.apply(root, {"type": "add_mechanism", "slot": leaf["id"], "quote": "New customers buy small first orders.",
                        "entry": {"hint": "first order", "entities": ["cust_new"], "metrics": ["aov"], "period": "both",
                                  "acts_on": "rate", "claim": {"en": "New customers buy smaller first orders.",
                                                               "zh": "新客第一单买得小。"}}, "run": cfg})
    after = run(root, cfg, write=False)
    assert after["coverage"]["explained"] == before["coverage"]["explained"]
    slot = next(x for x in after["slots"] if x["id"] == leaf["id"])
    cite = next(c for c in slot["citations"] if c["id"].startswith("mech_first_order"))
    assert cite["explains"] == "cannot_explain_change"


def test_demo_correction_lands_on_the_fruit_basket_structure(tmp_path):
    root = copy(tmp_path)
    spec = yaml.safe_load((DEMO / "correction.yaml").read_text(encoding="utf-8"))
    cfg = {**answer_key.CASES[spec["after_case"]]["run"], "id": spec["after_case"]}
    before = run(root, cfg, write=False)
    assert before["coverage"]["share"] == 0.0
    res = evolve.apply(root, {**spec["correction"], "run": cfg})
    after = run(root, cfg, write=False)
    assert after["coverage"]["share"] == 1.0
    slot = next(x for x in after["slots"] if x["id"] == spec["correction"]["slot"])
    cite = next(c for c in slot["citations"] if c["id"] == res["target"])
    assert cite["explains"] == "change"


def test_event_running_through_both_periods_cannot_explain(tmp_path):
    root = copy(tmp_path)
    w = yaml.safe_load((root / "world.yaml").read_text(encoding="utf-8"))
    ev = next(e for e in w["events"] if e["id"] == "ev_marketplace_fee_change")
    ev["start"] = "2025-01-01"
    (root / "world.yaml").write_text(yaml.safe_dump(w, allow_unicode=True, sort_keys=False), encoding="utf-8")
    s = run(root, {**answer_key.CASES["revenue_last_week"]["run"], "id": "r"}, out_dir=tmp_path / "out")
    slot = next(x for x in s["slots"] if x.get("leaf", True))
    cite = next(c for c in slot["citations"] if c["id"] == "ev_marketplace_fee_change")
    assert cite["explains"] == "cannot_explain_change"
    assert slot["status"] == "gap"
    zh = (tmp_path / "out" / "report.zh.md").read_text(encoding="utf-8")
    assert "解释不了这次的变化" in zh


def test_outside_event_checks_work_for_a_ratio_and_report_the_rest(tmp_path):
    root = copy(tmp_path)
    s = run(root, {"metric": "aov", "current": ["2026-10-19", "2026-10-25"], "base": "yoy",
                   "filters": {"region": "east"}, "dimensions": ["delivery"], "mode": "fixed", "drill_when_usual": True},
            write=False)
    ext = [c for x in s["slots"] for c in x["citations"] if c.get("external")]
    for c in ext:
        assert c["checks"]["status"] != "timing_only" or "slice" in c["checks"]
        assert "residual_change" in c["checks"]["size"]


def test_additive_outside_event_reports_change_without_event_days(tmp_path):
    root = copy(tmp_path)
    s = run(root, {**answer_key.CASES["east_last_week"]["run"], "id": "e"}, write=False)
    c = next(c for x in s["slots"] for c in x["citations"] if c.get("external"))
    sz = c["checks"]["size"]
    assert sz["residual_change"] == sz["residual_change"]  # a number, not NaN
    assert abs(sz["residual_change"]) < abs(c["checks"]["slice"]["slice_delta"])
