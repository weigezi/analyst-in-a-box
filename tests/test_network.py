"""The knowledge page draws what the workspace files say, with the right trust tier, and nothing else."""

import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from aib import netpage
from aib.workspace import Workspace

ROOT = Path(__file__).parent.parent.resolve()
DEMOS = {"store": ROOT / "demo" / "store" / "workspace", "intake": ROOT / "demo" / "intake" / "workspace"}
KINDS = ("user", "document", "data", "system_record", "general_knowledge", "demo_setting", "formula")
STATUSES = ("confirmed", "proposed", "retired")

# source.kind x status -> tier, written out by hand from the rules of the page
EXPECTED = {
    ("user", "confirmed"): "fact", ("user", "proposed"): "confirm", ("user", "retired"): "retired",
    ("system_record", "confirmed"): "fact", ("system_record", "proposed"): "confirm", ("system_record", "retired"): "retired",
    ("data", "confirmed"): "fact", ("data", "proposed"): "confirm", ("data", "retired"): "retired",
    ("formula", "confirmed"): "fact", ("formula", "proposed"): "confirm", ("formula", "retired"): "retired",
    ("document", "confirmed"): "confirm", ("document", "proposed"): "confirm", ("document", "retired"): "retired",
    ("general_knowledge", "confirmed"): "inference", ("general_knowledge", "proposed"): "inference", ("general_knowledge", "retired"): "retired",
    ("demo_setting", "confirmed"): "inference", ("demo_setting", "proposed"): "inference", ("demo_setting", "retired"): "retired",
}


def embedded(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="aib-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


@pytest.fixture(scope="module", params=sorted(DEMOS))
def demo(request):
    ws = Workspace(DEMOS[request.param])
    return ws, netpage.render(ws, "en"), netpage.render(ws, "zh")


def test_every_kind_and_status_pair_has_a_hand_checked_tier():
    assert set(EXPECTED) == set(itertools.product(KINDS, STATUSES))
    for (kind, status), tier in EXPECTED.items():
        assert netpage.tier_of({"source": {"kind": kind}, "status": status}) == tier, (kind, status)


def test_a_record_without_a_usable_source_is_never_a_fact():
    for rec in ({}, {"status": "confirmed"}, {"source": {}, "status": "confirmed"}, {"source": {"kind": "invented"}, "status": "confirmed"},
                {"source": "user", "status": "confirmed"}, {"source": {"kind": "user"}}):
        assert netpage.tier_of(rec) == "confirm", rec


def test_a_metric_in_a_formula_takes_its_tier_and_one_in_none_has_no_source(demo):
    ws, en, _ = demo
    in_formula = {m for i in ws.model.get("identities", []) for m in [i["left"], *i["factors"]]}
    for n in embedded(en)["views"]["tree"]["nodes"]:
        if n["kind"] == "metric":
            assert (n["tier"] == "none") == (n["id"].split(":", 1)[1] not in in_formula), n["id"]


def test_weakest_tier_of_several_records():
    assert netpage.weakest(["fact", "fact"]) == "fact"
    assert netpage.weakest(["fact", "confirm"]) == "confirm"
    assert netpage.weakest(["fact", "inference", "confirm"]) == "inference"
    assert netpage.weakest(["retired", "fact"]) == "fact"
    assert netpage.weakest(["retired"]) == "retired"
    assert netpage.weakest([]) is None


def test_world_page_holds_every_entry_of_world_yaml(demo):
    ws, en, zh = demo
    world = ws.world
    for page in (en, zh):
        ids = {n["id"] for n in embedded(page)["views"]["world"]["nodes"]}
        for kind, node_kind in (("entities", "entity"), ("mechanisms", "mechanism"), ("events", "event"), ("actions", "action")):
            for x in world.get(kind, []):
                assert f"{node_kind}:{x['id']}" in ids, (kind, x["id"])
        assert len(ids) == sum(len(world.get(k, [])) for k in ("entities", "mechanisms", "events", "actions"))


def test_world_page_holds_every_relation_and_link(demo):
    ws, en, _ = demo
    edges = {e["id"] for e in embedded(en)["views"]["world"]["edges"]}
    for r in ws.world.get("relations", []):
        assert f"relation:{r['id']}" in edges
    for kind, key in (("mechanism", "mechanisms"), ("event", "events"), ("action", "actions")):
        for x in ws.world.get(key, []):
            for e in x.get("entities", []):
                assert f"about:{kind}:{x['id']}:{e}" in edges


def test_tree_page_holds_every_metric_and_formula(demo):
    ws, en, zh = demo
    for page in (en, zh):
        tree = embedded(page)["views"]["tree"]
        ids = {n["id"] for n in tree["nodes"]}
        assert {f"metric:{m}" for m in ws.metrics} <= ids
        edges = {e["id"] for e in tree["edges"]}
        for i in ws.model.get("identities", []):
            for f in i["factors"]:
                assert f"formula:{i['id']}:{f}" in edges
        for m, pr in (ws.model.get("priorities") or {}).items():
            for d in pr["order"]:
                assert f"cut:{m}:{d}" in edges and f"dimension:{d}" in ids


def test_every_node_and_edge_tier_follows_its_own_record(demo):
    ws, en, _ = demo
    data = embedded(en)["views"]
    by_id = {}
    for kind, node_kind in (("entities", "entity"), ("mechanisms", "mechanism"), ("events", "event"), ("actions", "action")):
        for x in ws.world.get(kind, []):
            by_id[f"{node_kind}:{x['id']}"] = x
    for n in data["world"]["nodes"]:
        assert n["tier"] == EXPECTED[(by_id[n["id"]]["source"]["kind"], by_id[n["id"]]["status"])], n["id"]
    idents = {i["id"]: i for i in ws.model.get("identities", [])}
    for e in data["tree"]["edges"]:
        if e["kind"] == "formula":
            i = idents[e["id"].split(":")[1]]
            assert e["tier"] == EXPECTED[(i["source"]["kind"], i["status"])]


def test_the_page_quotes_the_sentence_a_document_claim_rests_on(demo):
    ws, en, zh = demo
    quoted = [x for k in ("mechanisms", "events") for x in ws.world.get(k, []) if (x.get("source") or {}).get("quote")]
    shown = [s["quote"] for n in embedded(zh)["views"]["world"]["nodes"] for s in n["sources"]]
    for x in quoted:
        assert x["source"]["quote"] in shown


def test_the_page_is_self_contained(demo):
    _, en, zh = demo
    for page in (en, zh):
        scripts = re.findall(r"<script[^>]*>", page)
        assert all("src=" not in s for s in scripts)
        assert not re.search(r"<link\b|@import|@font-face|<img\b|<iframe\b|<source\b", page)
        assert not re.search(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", page)
        assert not re.search(r"url\(\s*[\"']?(?:https?:)?//", page)
        assert not re.search(r"(?:fetch|XMLHttpRequest|WebSocket|importScripts|sendBeacon)\s*\(", page)
        assert not re.search(r"https?://", page), re.findall(r".{20}https?://.{20}", page)[:3]
        assert "ontology" not in page.lower()
        assert not re.search(r"(?<!业务)世界描述", page)


def test_page_language_follows_the_flag(demo):
    _, en, zh = demo
    assert '<html lang="en">' in en and "Business knowledge graph" in en and "AI inference" in en
    assert '<html lang="zh">' in zh and "业务知识图谱" in zh and "AI 推断" in zh
    assert "指标树" in zh and "业务世界描述" in zh and "无出处记录" in zh
    assert embedded(zh)["lang"] == "zh"


def test_script_closing_tags_inside_text_cannot_end_the_data_block(tmp_path):
    ws = Workspace(DEMOS["store"])
    ws.world = {**ws.world, "mechanisms": [{**ws.world["mechanisms"][0], "claim": {"en": "x </script><b>{{name}}</b>", "zh": "x"}}]}
    page = netpage.render(ws, "en")
    assert page.count("</script>") == 2
    assert "{{name}}" in embedded(page)["views"]["world"]["nodes"][-1]["full"] or any(
        "{{name}}" in n["full"] for n in embedded(page)["views"]["world"]["nodes"])


def test_nothing_is_invented_for_a_workspace_without_a_world(tmp_path):
    (tmp_path / "project.yaml").write_text("name: Tiny\nlanguage: en\nsources: {}\n")
    (tmp_path / "model.yaml").write_text(yaml.safe_dump({
        "north_star": "m", "measures": {"mm": {"source": "t", "agg": "count", "date": "d", "dimensions": []}},
        "metrics": {"m": {"label": {"en": "M"}, "measure": "mm", "unit": "count"}}}))
    ws = Workspace(tmp_path)
    data = netpage.build_data(ws, "en")
    assert [n["id"] for n in data["views"]["tree"]["nodes"]] == ["metric:m"]
    only = data["views"]["tree"]["nodes"][0]
    assert only["tier"] == "none" and only["sources"] == []
    assert only["note"] == "This metric appears in the model but no record says where it came from."
    assert data["views"]["tree"]["counts"]["none"] == 1
    assert data["views"]["world"]["nodes"] == []


def test_cli_writes_knowledge_html(tmp_path):
    out = tmp_path / "k.html"
    cli = ROOT / "skills" / "analyst-in-a-box" / "scripts" / "aib_cli.py"
    r = subprocess.run([sys.executable, str(cli), "network", "--workspace", str(DEMOS["store"]), "--lang", "en", "--out", str(out)],
                       capture_output=True, text=True, check=True)
    assert json.loads(r.stdout)["world"]["nodes"] == 35
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_cut_order_is_listed_in_the_panel_and_cut_links_are_hover_only(demo):
    ws, en, zh = demo
    tree = embedded(en)["views"]["tree"]
    nodes = {n["id"]: n for n in tree["nodes"]}
    for m, pr in (ws.model.get("priorities") or {}).items():
        order = [d for d in pr["order"] if d in ws.dimensions]
        facts = {k: v for k, v in nodes[f"metric:{m}"]["facts"]}
        want = ", ".join(f"{i} {netpage.label(ws.dimensions[d]['label'], 'en')}" for i, d in enumerate(order, 1))
        assert facts["Cut order"] == want, m
        for i, d in enumerate(order, 1):
            used = {k: v for k, v in nodes[f"dimension:{d}"]["facts"]}["Cuts these metrics (its position in their cut order)"]
            assert f"{netpage.label(ws.metrics[m]['label'], 'en')} ({i})" in used
    assert '.view[data-view="tree"] .edge-g.k-cut { visibility: hidden; }' in en
    assert "Hover a card to see how it is cut" in en
    assert "把鼠标移到卡片上" in zh and 'id="hint-tree"' in zh
