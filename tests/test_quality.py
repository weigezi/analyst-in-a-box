"""v0.2 item 1: a data-quality step runs before anything is attributed. Bad data must never read as 'explained'."""

import shutil
from pathlib import Path

import pandas as pd
import pytest

from aib.run import run
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store" / "workspace"
WEEK = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}


def demo_copy(tmp: Path, name: str) -> Path:
    dst = tmp / name
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    return dst


def check(s, name):
    return next(c for c in s["quality"]["checks"] if c["check"] == name)


def test_clean_demo_week_passes_quality(tmp_path):
    s = run(Workspace(demo_copy(tmp_path, "clean")), WEEK, write=False)
    assert s["quality"]["status"] == "ok", s["quality"]
    assert not s["quality"]["suspect"]


def test_two_missing_days_are_flagged_and_nothing_is_explained(tmp_path):
    root = demo_copy(tmp_path, "missing")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    o[~o["order_date"].isin(["2026-10-24", "2026-10-25"])].to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), WEEK, out_dir=tmp_path / "out")
    c = check(s, "calendar_complete")
    assert c["status"] == "fail" and set(c["missing"]["current"]) == {"2026-10-24", "2026-10-25"}
    assert s["quality"]["suspect"]
    assert not any(x["status"] == "explained" for x in s["slots"])
    assert s["coverage"]["explained"] == 0
    zh = (tmp_path / "out" / "report.zh.md").read_text(encoding="utf-8")
    en = (tmp_path / "out" / "report.en.md").read_text(encoding="utf-8")
    first_zh = zh.split("\n## ")[1]
    assert "数据存疑" in first_zh and "2026-10-24" in first_zh
    assert "Data in doubt" in en.split("\n## ")[1]


def test_a_week_loaded_twice_is_reported(tmp_path):
    root = demo_copy(tmp_path, "dup")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    pd.concat([o, o[o["order_date"] >= "2026-10-19"]]).to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), WEEK, write=False)
    assert check(s, "key_unique")["status"] == "fail"
    assert check(s, "daily_volume_steady")["status"] == "fail"
    assert s["quality"]["suspect"] and s["blocked"]
    assert not any(x["status"] == "explained" for x in s["slots"])


def test_duplicate_rows_without_a_key_still_show_as_a_volume_jump(tmp_path):
    root = demo_copy(tmp_path, "dup_nokey")
    import yaml
    p = yaml.safe_load((root / "project.yaml").read_text(encoding="utf-8"))
    p["sources"]["orders"].pop("key", None)
    (root / "project.yaml").write_text(yaml.safe_dump(p, allow_unicode=True), encoding="utf-8")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    pd.concat([o, o[o["order_date"] >= "2026-10-19"]]).to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), WEEK, out_dir=tmp_path / "out")
    # Without a key the only evidence is the volume jump, a 'warn' check (maintainer, 2026-10-31): the report says so
    # at the top and still gives conclusions. With a key the same data is blocked (test above).
    assert check(s, "daily_volume_steady")["status"] == "fail"
    assert "daily_volume_steady" in s["quality"]["warned"] and not s["quality"]["suspect"]
    assert "数据提醒" in (tmp_path / "out" / "report.zh.md").read_text(encoding="utf-8").split("\n## ")[1]


def test_one_huge_order_is_named(tmp_path):
    root = demo_copy(tmp_path, "big")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    i = o.index[o["order_date"] == "2026-10-20"][0]
    o.loc[i, "revenue"] = 150000.0
    o.to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), WEEK, write=False)
    c = check(s, "no_single_row_dominates")
    assert c["status"] in ("warn", "fail")
    assert c["rows"][0]["key"] == o.loc[i, "order_id"]


# ---------- two levels (maintainer, 2026-10-31) ----------

def test_block_level_stops_the_report(tmp_path):
    root = demo_copy(tmp_path, "blk")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    pd.concat([o, o[o["order_date"] == "2026-10-21"].head(5)]).to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), WEEK, out_dir=tmp_path / "out")
    assert check(s, "key_unique")["level"] == "block"
    assert s["blocked"] and s["quality"]["suspect"]
    assert not any(x["status"] == "explained" for x in s["slots"])
    md = (tmp_path / "out" / "report.zh.md").read_text(encoding="utf-8")
    assert md.split("\n## ")[0].count("交付前自检没通过") == 1 and "数据存疑" in md.split("\n## ")[1]


def test_warn_level_reminds_and_still_concludes(tmp_path):
    root = demo_copy(tmp_path, "wrn")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    i = o.index[o["order_date"] == "2026-10-20"][0]
    o.loc[i, "revenue"] = 150000.0
    o.to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), WEEK, out_dir=tmp_path / "out")
    c = check(s, "no_single_row_dominates")
    assert c["status"] == "fail" and c["level"] == "warn"
    assert not s["blocked"] and not s["quality"]["suspect"]
    assert s["slots"] and all(x["status"] != "data_suspect" for x in s["slots"])
    zh = (tmp_path / "out" / "report.zh.md").read_text(encoding="utf-8").split("\n## ")[1]
    en = (tmp_path / "out" / "report.en.md").read_text(encoding="utf-8").split("\n## ")[1]
    assert zh.lstrip("结论\n").startswith("**数据提醒**") and o.loc[i, "order_id"] in zh
    assert "Data note" in en


def test_levels_are_a_param_with_a_source():
    from aib import defaults
    p = defaults.PARAMS["quality_check_levels"]
    assert p["source"]["kind"] == "user" and "2026-10-31" in p["source"]["date"]
    assert set(p["value"].values()) == {"block", "warn"}
    assert p["value"]["key_unique"] == "block" and p["value"]["daily_volume_steady"] == "warn"


def test_old_identity_check_is_renamed_and_a_real_reconciliation_runs(tmp_path):
    s = run(Workspace(demo_copy(tmp_path, "names")), WEEK, write=False)
    names = {c["check"] for c in s["checks"]}
    assert "identities_hold_on_data" not in names
    assert "identities_computable" in names
    assert "segments_add_up_to_total" in names


def test_rows_missing_a_dimension_value_break_the_reconciliation(tmp_path):
    root = demo_copy(tmp_path, "nulls")
    o = pd.read_csv(root / "data" / "orders.csv.gz")
    o.loc[(o["order_date"] >= "2026-10-19") & (o["channel"] == "web"), "channel"] = None
    o.to_csv(root / "data" / "orders.csv.gz", index=False)
    s = run(Workspace(root), {**WEEK, "dimensions": ["channel"], "mode": "fixed"}, write=False)
    c = next(c for c in s["checks"] if c["check"] == "segments_add_up_to_total")
    assert not c["pass"] and "channel" in c["detail"]
