"""Every report says what it did not check, built only from facts the run knows."""

import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

from aib.run import run

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store" / "workspace"
sys.path.insert(0, str(Path(__file__).absolute().parent))
import synth  # noqa: E402

CUR, BASE = ("2026-10-19", "2026-10-25"), ("2025-10-20", "2025-10-26")
RUN = {"metric": "revenue", "current": list(CUR), "base": "yoy", "dimensions": ["channel"]}
TITLES = {"en": "What this report did not check", "zh": "这份报告没有检查什么"}


def part(md, lang):
    chunks = {c.split("\n")[0]: c for c in md.split("\n## ")}
    return chunks[TITLES[lang]]


def order(md, lang):
    return [c.split("\n")[0] for c in md.split("\n## ")].index(TITLES[lang])


def build(tmp_path, *, status=False, blanks=False, count_rows=False, seed=3):
    df = synth.orders(seed=seed, per_day=30, start="2025-06-01", end="2026-10-25")
    if status:
        rng = pd.Series(range(len(df)))
        df["status"] = ["cancelled" if i % 9 == 0 else "paid" for i in rng]
    if blanks:
        df.loc[df.index[::7], "channel"] = None
    extra = {}
    if status:
        extra = {"sources": {"orders": {"type": "csv", "path": "data/orders.csv", "date_columns": ["order_date"], "key": "order_id",
                                        "exclude_rows": {"status": ["cancelled"]}}}}
    root = synth.workspace(tmp_path / "ws", df, project_extra=extra)
    if count_rows:
        import yaml
        m = yaml.safe_load((root / "model.yaml").read_text(encoding="utf-8"))
        m["measures"]["rows_m"] = {"source": "orders", "agg": "count", "column": "order_id", "date": "order_date",
                                   "dimensions": ["channel", "region", "customer_type"]}
        m["metrics"]["rows"] = {"label": "Rows", "measure": "rows_m", "unit": "count"}
        (root / "model.yaml").write_text(yaml.safe_dump(m, sort_keys=False), encoding="utf-8")
    return root, df


def reports(root, tmp_path, **cfg):
    s = run(root, {**RUN, **cfg}, out_dir=tmp_path / "out")
    return s, {l: (tmp_path / "out" / f"report.{l}.md").read_text(encoding="utf-8") for l in ("en", "zh")}


def test_the_section_sits_just_before_who_should_act_in_both_languages(tmp_path):
    root, _ = build(tmp_path)
    _, md = reports(root, tmp_path)
    for lang, who in (("en", "Who should act"), ("zh", "谁该做什么")):
        heads = [c.split("\n")[0] for c in md[lang].split("\n## ")]
        assert heads.index(TITLES[lang]) == heads.index(who) - 1, heads


def test_it_names_the_columns_and_tables_the_run_used(tmp_path):
    root, _ = build(tmp_path)
    _, md = reports(root, tmp_path)
    en, zh = part(md["en"], "en"), part(md["zh"], "zh")
    for text in (en, zh):
        assert "orders" in text and "revenue" in text and "order_date" in text and "channel" in text
    assert "taken as they are" in en and "refund" in en.lower()
    assert "原样" in zh and "退款" in zh


def test_it_says_no_outside_event_was_checked_when_none_was(tmp_path):
    root, _ = build(tmp_path)
    s, md = reports(root, tmp_path)
    assert not any(c.get("external") for x in s["slots"] for c in x["citations"])
    assert "No outside event" in part(md["en"], "en")
    assert "没有核对任何外部事件" in part(md["zh"], "zh")


def test_it_counts_the_cancelled_rows_it_removed_from_the_windows(tmp_path):
    root, df = build(tmp_path, status=True)
    _, md = reports(root, tmp_path)
    cancelled = df[df["status"] == "cancelled"]

    def n(w):
        return int(((cancelled["order_date"] >= w[0]) & (cancelled["order_date"] <= w[1])).sum())
    cur, base = n(CUR), n(BASE)
    assert cur > 0 and base > 0
    en = part(md["en"], "en")
    assert f"{cur:,}" in en and f"{base:,}" in en and "status" in en and "cancelled" in en
    zh = part(md["zh"], "zh")
    assert f"{cur:,}" in zh and f"{base:,}" in zh and "status" in zh


def test_without_a_cancelled_rule_it_says_none_were_removed_not_a_count(tmp_path):
    root, _ = build(tmp_path)
    _, md = reports(root, tmp_path)
    en = part(md["en"], "en")
    assert "No rule removes cancelled or reversed rows" in en
    assert "规则" in part(md["zh"], "zh") and "取消" in part(md["zh"], "zh")


def test_it_gives_the_blank_share_of_a_cut_dimension(tmp_path):
    root, df = build(tmp_path, blanks=True)
    _, md = reports(root, tmp_path)
    cur = df[(df["order_date"] >= CUR[0]) & (df["order_date"] <= CUR[1])]
    blank = int(cur["channel"].isna().sum())
    share = f"{blank / len(cur):.1%}"
    en, zh = part(md["en"], "en"), part(md["zh"], "zh")
    assert "channel" in en and f"{blank:,}" in en and share in en
    assert f"{blank:,}" in zh and share in zh


def test_clean_dimensions_are_reported_as_having_no_blanks(tmp_path):
    root, _ = build(tmp_path)
    _, md = reports(root, tmp_path)
    assert "no blank" in part(md["en"], "en").lower()
    assert "没有空白" in part(md["zh"], "zh")


def test_it_says_how_exact_copies_were_counted_only_when_the_measure_depends_on_it(tmp_path):
    root, _ = build(tmp_path)
    _, md = reports(root, tmp_path)
    assert "exact cop" not in part(md["en"], "en").lower()      # revenue is a sum: copies are summed whatever the answer
    root2, _ = build(tmp_path / "rows", count_rows=True)
    s = run(root2, {**RUN, "metric": "rows"}, out_dir=tmp_path / "rows" / "out")
    en = (tmp_path / "rows" / "out" / "report.en.md").read_text(encoding="utf-8")
    assert s["metric"] == "rows"
    assert "exact copies" in part(en, "en").lower() and "no answer" in part(en, "en").lower()


def test_it_counts_the_checks_that_ran_and_the_notes_raised(tmp_path):
    root, _ = build(tmp_path)
    s, md = reports(root, tmp_path)
    ran = len(s["checks"])
    assert ran == 12
    assert f"{ran} pre-delivery checks" in part(md["en"], "en")
    assert f"{ran} 项交付前自检" in part(md["zh"], "zh")


def test_a_blocked_report_still_says_what_it_did_not_check(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO, ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    o = pd.read_csv(ws / "data" / "orders.csv.gz")
    pd.concat([o, o[o["order_date"] == "2026-10-21"].head(5)]).to_csv(ws / "data" / "orders.csv.gz", index=False)
    s = run(ws, {"metric": "revenue", "current": list(CUR), "base": "yoy", "id": "b"}, out_dir=tmp_path / "out")
    assert s["blocked"]
    en = (tmp_path / "out" / "report.en.md").read_text(encoding="utf-8")
    assert "failed" in part(en, "en")                            # the failed check is listed among what ran


def test_nothing_in_the_section_is_a_claim_the_run_cannot_back(tmp_path):
    """Every sentence is built from a fact in the record; with the facts removed the lines disappear."""
    root, _ = build(tmp_path)
    s, md = reports(root, tmp_path)
    en = part(md["en"], "en")
    for word in ("refunded", "returns were netted", "net of", "tax", "shipping"):
        assert word not in en.lower().replace("refund table", ""), word
    assert not re.search(r"\bgross\b", en.lower()) or "unless" in en.lower()


def test_a_row_count_measure_has_no_column_and_is_still_described(tmp_path):
    root, _ = build(tmp_path)
    import yaml
    m = yaml.safe_load((root / "model.yaml").read_text(encoding="utf-8"))
    m["measures"]["rows_m"] = {"source": "orders", "agg": "count", "date": "order_date", "dimensions": ["channel", "region", "customer_type"]}
    m["metrics"]["rows"] = {"label": "Rows", "measure": "rows_m", "unit": "count"}
    (root / "model.yaml").write_text(yaml.safe_dump(m, sort_keys=False), encoding="utf-8")
    run(root, {**RUN, "metric": "rows"}, out_dir=tmp_path / "out")
    en = (tmp_path / "out" / "report.en.md").read_text(encoding="utf-8")
    assert "the number of rows in `orders`" in part(en, "en")
