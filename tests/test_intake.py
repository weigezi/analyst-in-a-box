"""Intake: a folder of tables and a document become a workspace, every inference confirmed, every quote checked."""

import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from aib import cli, intake
from aib.run import run
from aib.validate import all_problems
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
INTAKE = ROOT / "demo" / "intake"
sys.path.insert(0, str(INTAKE))
import build_tables  # noqa: E402

REV = {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}


@pytest.fixture(scope="module")
def formed(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("intake")
    tables = tmp / "tables"
    build_tables.main(tables)
    ws = tmp / "ws"
    d = intake.init([tables], ws, lang="zh")
    answers = yaml.safe_load((INTAKE / "answers.yaml").read_text(encoding="utf-8"))
    out = intake.confirm(ws, answers)
    spec = yaml.safe_load((INTAKE / "proposals.yaml").read_text(encoding="utf-8"))
    prop = intake.propose(ws, INTAKE / spec["doc"], spec["items"])
    return {"tmp": tmp, "tables": tables, "ws": ws, "draft": d, "confirm": out, "proposed": prop}


# ---------- end to end ----------

def test_the_draft_reads_shapes(formed):
    d = formed["draft"]
    kinds = {n: t["suggested_kind"] for n, t in d["tables"].items()}
    assert d["main"] == "orders"
    assert kinds["products"] == kinds["cities"] == "lookup"
    assert kinds["promotions"] == kinds["price_changes"] == "events"
    assert kinds["holidays"] == "calendar"
    assert kinds["market"] == "series" and kinds["weather"] == "series" and kinds["traffic"] == "business"
    links = {(lk["left_table"], lk["left_column"], lk["right_table"], lk["right_column"]): lk for lk in d["links"]}
    sku = links[("orders", "sku", "products", "sku")]
    assert sku["coverage"] == 1.0 and sku["right_is_key"] and sku["suggested"] == "yes"
    assert ("orders", "city", "cities", "city") in links
    # every inference is a question; nothing is in the workspace before confirm
    ids = {q["id"] for q in d["questions"]}
    assert "link:orders.sku>products.sku" in ids and "kind:promotions" in ids and "main_table" in ids


def test_nothing_is_written_before_confirm(tmp_path, formed):
    ws = tmp_path / "ws"
    intake.init([formed["tables"]], ws, lang="en")
    assert (ws / "draft.json").exists()
    assert not (ws / "model.yaml").exists() and not (ws / "world.yaml").exists()


def test_formed_workspace_is_valid_and_complete(formed):
    ws = Workspace(formed["ws"])
    assert all_problems(ws) == []
    assert set(ws.dimensions) == {"channel", "category", "region", "city", "delivery", "customer_type"}
    assert {"revenue", "gross_profit", "id_count", "per_id", "margin", "visits", "conversion"} <= set(ws.metrics)
    assert ws.sources.specs["orders"]["type"] == "join"
    rel = {(r["subject"], r["object"]) for r in ws.world["relations"]}
    assert ("city:Shanghai", "region:east") in rel and len(rel) == 8
    assert {s["role"] for s in ws.external.specs.values()} == {"calendar", "market", "series"}


def test_event_tables_become_events_to_confirm(formed):
    ev = [e for e in Workspace(formed["ws"]).world["events"] if e["source"]["kind"] == "system_record"]
    card = next(e for e in ev if e["start"] == "2026-10-01")
    assert set(card["entities"]) == {"category:fruit_basket", "customer_type:new"}
    assert card["status"] == "proposed" and "promotions" in card["source"]["ref"]
    price = next(e for e in ev if e["start"] == "2026-06-01")
    assert price["entities"] == ["category:gift_box"] and price["details"]["change"] == pytest.approx(0.15)


def test_document_proposals_are_kept_with_their_quote(formed):
    assert len(formed["proposed"]["accepted"]) == 3 and not formed["proposed"]["rejected"]
    w = Workspace(formed["ws"]).world
    fee = next(e for e in w["events"] if e["id"] == "ev_marketplace_fee_terms")
    assert fee["status"] == "proposed" and fee["source"]["kind"] == "document"
    assert fee["source"]["ref"].endswith("weekly_report.zh.md") and "10 月 12 日" in fee["source"]["quote"]


def test_the_formed_workspace_answers_revenue_but_does_not_call_it_explained(formed, tmp_path):
    s = run(formed["ws"], REV, out_dir=tmp_path / "rev")
    leaf = next(x for x in s["slots"] if x.get("leaf", True))
    assert leaf["id"] == "channel=marketplace" and not s["blocked"]
    assert leaf["status"] == "hypothesis" and leaf["pending_confirmation"] == ["ev_marketplace_fee_terms"]
    assert s["coverage"]["explained"] == 0
    zh = (tmp_path / "rev" / "report.zh.md").read_text(encoding="utf-8").split("\n## ")[1]
    en = (tmp_path / "rev" / "report.en.md").read_text(encoding="utf-8").split("\n## ")[1]
    assert "来自文档，待确认" in zh and "不算已解释" in zh and "10 月 12 日起执行新的费用条款" in zh
    assert "from a document, to confirm" in en


def test_confirming_the_document_event_explains_it(formed, tmp_path):
    from aib import evolve
    ws = tmp_path / "ws"
    shutil.copytree(formed["ws"], ws)
    for f in ("project.yaml",):
        p = yaml.safe_load((ws / f).read_text(encoding="utf-8"))
        for spec in [*p["sources"].values(), *p.get("external", {}).values()]:
            if "path" in spec:
                spec["path"] = str((formed["ws"] / spec["path"]).resolve())
        (ws / f).write_text(yaml.safe_dump(p, allow_unicode=True), encoding="utf-8")
    evolve.apply(ws, {"type": "confirm", "bucket": "events", "id": "ev_marketplace_fee_terms", "quote": "对，就是平台改条款"})
    s = run(ws, REV, write=False)
    assert next(x for x in s["slots"] if x.get("leaf", True))["status"] == "explained"


def test_cli_init_takes_a_folder_and_confirm_dispatches(formed, tmp_path, capsys):
    ws = tmp_path / "ws"
    assert cli.main(["init", str(formed["tables"]), "--workspace", str(ws), "--lang", "en"]) == 0
    out = capsys.readouterr().out
    assert '"main": "orders"' in out
    assert cli.main(["confirm", "--workspace", str(ws), "--answers", str(INTAKE / "answers.yaml")]) == 0
    assert Workspace(ws).sources.specs["orders"]["type"] == "join"
    assert cli.main(["formation", "--workspace", str(ws)]) == 0
    assert '"needs_a_person"' in capsys.readouterr().out


# ---------- links ----------

def _two_tables(tmp, match_share):
    n = 400
    keys = [f"P{i}" for i in range(10)]
    other = [f"X{i}" for i in range(10)]
    vals = [keys[i % 10] if (i / n) < match_share else other[i % 10] for i in range(n)]
    pd.DataFrame({"order_id": [f"o{i}" for i in range(n)], "day": pd.date_range("2026-01-01", periods=n, freq="D").strftime("%Y-%m-%d"),
                  "item": vals, "amount": [10.0 + i % 7 for i in range(n)]}).to_csv(tmp / "sales.csv", index=False)
    pd.DataFrame({"code": keys, "group": ["g1"] * 5 + ["g2"] * 5}).to_csv(tmp / "items.csv", index=False)


@pytest.mark.parametrize("share,asked,suggested", [(1.0, True, "yes"), (0.7, True, "no"), (0.3, False, None)])
def test_low_coverage_is_never_linked_by_default(tmp_path, share, asked, suggested):
    _two_tables(tmp_path, share)
    d = intake.init([tmp_path / "sales.csv", tmp_path / "items.csv"], tmp_path / "ws", lang="en")
    lk = next((x for x in d["links"] if x["left_column"] == "item" and x["right_column"] == "code"), None)
    assert (lk is not None) == asked
    if lk:
        assert lk["suggested"] == suggested and lk["coverage"] == pytest.approx(share, abs=0.01)
    assert d["joins"] == ([{"source": "items", "on": {"item": "code"}, "columns": ["group"]}] if suggested == "yes" else [])


def test_an_unanswered_link_is_not_joined(tmp_path):
    _two_tables(tmp_path, 1.0)
    ws = tmp_path / "ws"
    intake.init([tmp_path], ws, lang="en")
    intake.confirm(ws, {"kind:items": "lookup", "date_column": "day", "role:amount": "amount", "order_id": "order_id",
                        "dimensions": ["item"]})
    assert Workspace(ws).sources.specs["sales"]["type"] == "csv"


def test_event_table_found_by_shape_not_name(tmp_path):
    _two_tables(tmp_path, 1.0)
    pd.DataFrame({"a": ["2026-03-01", "2026-05-10"], "b": ["2026-03-07", "2026-05-12"], "c": ["spring push", "clearance"],
                  "d": ["P1", "P4"]}).to_csv(tmp_path / "t3.csv", index=False)
    d = intake.init([tmp_path], tmp_path / "ws", lang="en")
    assert d["tables"]["t3"]["suggested_kind"] == "events" and d["tables"]["t3"]["start_end"] == ["a", "b"]
    ws = tmp_path / "ws"
    intake.confirm(ws, {"kind:items": "lookup", "kind:t3": "events", "link:t3.d>sales.item": "yes", "event_text:t3": "c",
                        "date_column": "day", "role:amount": "amount", "order_id": "order_id", "dimensions": ["item"]})
    ev = Workspace(ws).world["events"]
    assert [e["entities"] for e in ev] == [["item:P1"], ["item:P4"]]
    assert all(e["status"] == "proposed" and e["source"]["kind"] == "system_record" for e in ev)


# ---------- quotes ----------

def test_a_made_up_quote_is_refused(formed, tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(formed["ws"], ws)
    doc = INTAKE / "docs" / "weekly_report.zh.md"
    real = "华东 21 日到 23 日连着三天大暴雨，上海、杭州两地的当日达几乎停摆"
    made_up = "华东 21 日到 23 日连着三天大暴雨，上海、杭州两地的门店全部关门"
    entry = {"kind": "external", "start": "2026-10-21", "entities": ["region:east"], "what": {"zh": "暴雨"}}
    r = intake.propose(ws, doc, [{"type": "event", "quote": made_up, "entry": entry},
                                 {"type": "event", "quote": "大暴雨", "entry": entry},
                                 {"type": "event", "quote": real, "entry": {**entry, "entities": ["region:nowhere"]}},
                                 {"type": "event", "quote": real.replace("，", "，\n  "), "entry": entry}])
    reasons = [x["reason"] for x in r["rejected"]]
    assert len(r["rejected"]) == 3 and len(r["accepted"]) == 1
    assert "not in the document" in reasons[0] and "shorter" in reasons[1] and "unknown entities" in reasons[2]
    ids = {e["id"] for e in Workspace(ws).world["events"]}
    assert r["accepted"][0]["id"] in ids
    assert not any(e.get("source", {}).get("quote") == made_up for e in Workspace(ws).world["events"])


def test_cli_propose_exits_non_zero_on_a_refusal(formed, tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(formed["ws"], ws)
    rc = cli.main(["propose", "--workspace", str(ws), "--doc", str(INTAKE / "docs" / "weekly_report.zh.md"), "--type", "event",
                   "--quote", "平台在 10 月 12 日把我们的店铺下架了，所有订单清零", "--json",
                   '{"start": "2026-10-12", "entities": ["channel:marketplace"], "what": {"zh": "下架"}}'])
    assert rc == 1
