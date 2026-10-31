"""The demo shop has known causes planted in its data. The skill must find every one of them."""

import shutil
import sys
from pathlib import Path

import pytest
import yaml

from aib import evolve
from aib.run import run
from aib.workspace import Workspace

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
DEMO = ROOT / "demo" / "store"
sys.path.insert(0, str(DEMO))
import answer_key  # noqa: E402

CASES = answer_key.CASES


def copy_workspace(tmp: Path) -> Path:
    dst = tmp / "workspace"
    shutil.copytree(DEMO / "workspace", dst, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    return dst


@pytest.fixture(scope="module")
def ws(tmp_path_factory):
    return Workspace(copy_workspace(tmp_path_factory.mktemp("demo")))


@pytest.fixture(scope="module")
def runs(ws, tmp_path_factory):
    out = tmp_path_factory.mktemp("runs")
    return {k: run(ws, {**c["run"], "id": k, "question": c["question"]}, out_dir=out / k) for k, c in CASES.items()}


@pytest.mark.parametrize("case", list(CASES))
def test_planted_cause_is_found(runs, case):
    rows = answer_key.check(CASES[case], runs[case])
    assert all(ok for _, ok in rows), [r for r in rows if not r[1]]


def test_every_explanation_slot_cites_or_flags(runs):
    for s in runs.values():
        for slot in s["slots"]:
            assert slot["status"] in ("explained", "hypothesis", "gap")
            assert slot["citations"] or slot["status"] == "gap"


def test_reports_written_in_both_languages(runs):
    for s in runs.values():
        out = Path(s["out_dir"])
        zh, en = (out / "report.zh.md").read_text(encoding="utf-8"), (out / "report.en.md").read_text(encoding="utf-8")
        assert zh.startswith("# ") and en.startswith("# ")
        assert zh.count("\n## ") == en.count("\n## ")
        assert list((out / "charts").glob("*.svg"))


def test_correction_closes_the_gap_and_is_remembered(tmp_path):
    root = copy_workspace(tmp_path)
    spec = yaml.safe_load((DEMO / "correction.yaml").read_text(encoding="utf-8"))
    case = CASES[spec["after_case"]]
    config = {**case["run"], "id": case["case"]}

    # 0.2: 0.1 asserted 0.5 -> 1.0 here. Its 0.5 counted two slots (fruit baskets, new customers) for one cause, and
    # its 1.0 came from a record true in both years ("new customers buy small first orders"), which cannot explain
    # a year-on-year change. Now: one cause (new customers x fruit baskets), unexplained before, explained by an
    # event the user names. tests/test_explain_fit.py checks that the old record no longer raises coverage.
    before = run(root, config, write=False)
    assert before["coverage"]["share"] == 0.0

    result = evolve.apply(root, {**spec["correction"], "run": config})
    after = run(root, config, write=False)
    assert after["coverage"]["share"] == 1.0
    assert result["target"] in answer_key.cited(after)
    assert (root / "corrections.jsonl").read_text(encoding="utf-8").count("\n") == 1

    rows = evolve.regress(root)
    assert rows and all(r["pass"] for r in rows)

    # Forgetting must be caught: drop the new record and the regression fails.
    world = yaml.safe_load((root / "world.yaml").read_text(encoding="utf-8"))
    for bucket in ("mechanisms", "events"):
        world[bucket] = [m for m in world.get(bucket, []) if m["id"] != result["target"]]
    (root / "world.yaml").write_text(yaml.safe_dump(world, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert not all(r["pass"] for r in evolve.regress(root))


def test_windows_of_different_length_are_blocked(ws):
    s = run(ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": ["2025-10-20", "2025-10-27"]}, write=False)
    assert s["blocked"]
    assert any(c["check"] == "windows_same_length" and not c["pass"] for c in s["checks"])


def test_other_correction_types(tmp_path):
    root = copy_workspace(tmp_path)
    config = {**CASES["revenue_last_week"]["run"], "id": "revenue_last_week"}
    evolve.apply(root, {"type": "set_priority", "metric": "revenue", "order": ["region", "channel"], "quote": "look at regions first", "run": config})
    evolve.apply(root, {"type": "set_param", "name": "single_point_min_share", "value": 0.6, "quote": "60% counts as one point"})
    evolve.apply(root, {"type": "add_alias", "entity": "ch_marketplace", "alias": "platform", "quote": "we call it the platform"})
    evolve.apply(root, {"type": "confirm", "bucket": "events", "id": "ev_east_rainstorm", "quote": "yes, it rained"})
    rows = evolve.regress(root)
    assert len(rows) == 4 and all(r["pass"] for r in rows), rows
    s = run(root, config, write=False)
    assert s["cuts"][0]["dimension"] == "region"
