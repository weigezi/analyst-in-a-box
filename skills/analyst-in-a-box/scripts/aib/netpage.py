"""The business knowledge graph as one self-contained HTML page.

`aib network --workspace W` reads model.yaml (the metric tree) and world.yaml (the business world description)
and writes W/knowledge.html: a force-directed network with a detail panel and a legend of how far each part can be
trusted. The page draws only what the files contain. It adds no node and no claim; where a record has no source
or status of its own, the page says so instead of filling the gap.

Trust tiers are derived from `source.kind` and `status` of the record alone (see `tier_of`).
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

from .report import SOURCE_KINDS
from .workspace import Workspace, label

TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "network"

FACT_KINDS = ("user", "system_record", "data", "formula")
INFERENCE_KINDS = ("general_knowledge", "demo_setting")
TIERS = ("fact", "confirm", "inference", "retired", "none")
_WEAKNESS = {"fact": 0, "confirm": 1, "inference": 2}

UI = {
    "en": {
        "page_title": "Business knowledge graph", "tab_tree": "Metric tree", "tab_world": "Business world description",
        "tabs_label": "Views", "legend": "How far to trust it", "legend_more": "What the outlines mean",
        "tier_fact": "Fact", "tier_confirm": "To confirm", "tier_inference": "AI inference", "tier_retired": "Retired",
        "text_fact": "A person said it, or it comes from a system record, the data or arithmetic, and it is confirmed.",
        "text_confirm": "Proposed, or taken from a document. Nobody has confirmed it yet.",
        "text_inference": "General knowledge or a setting of the demo. A draft until a person confirms it.",
        "text_retired": "Kept for history. Never used in an analysis.",
        "tier_none": "No source recorded", "text_none": "The model uses it, but no record says where it came from.",
        "badge_none": "no source", "banner_none": "no source recorded",
        "no_record_metric": "This metric appears in the model but no record says where it came from.",
        "badge_confirm": "to confirm", "badge_inference": "inference", "badge_retired": "retired",
        "banner_inference": "inference: a draft until a person confirms it",
        "banner_confirm": "to confirm: nobody has confirmed this yet",
        "banner_fact": "fact: confirmed, from a person, a record, the data or arithmetic",
        "banner_retired": "retired: kept for history, not used",
        "filter_inference": "Hide AI inference", "cards": "cards", "links": "links",
        "hint_tree": "Hover a card to see how it is cut (tap it on a touch screen).",
        "hint": "Drag a card to move it. Click or press Enter for details. Drag the background to pan.",
        "close": "Close", "source": "Source", "said": "Quoted", "date": "Date", "note": "Note", "status": "Status",
        "refuted": "What data would refute it", "connected": "Connected to", "trust": "Trust",
        "no_source": "The file records no source and no status for this entry.",
        "zoom_in": "Zoom in", "zoom_out": "Zoom out", "zoom_fit": "Fit to screen",
        "kind_metric": "Metric", "kind_north": "North star", "kind_dimension": "Cut", "kind_entity": "Entity",
        "kind_outside": "Outside party", "kind_mechanism": "Mechanism", "kind_event": "Event", "kind_action": "Action",
        "edge_formula": "Formula", "edge_cut": "Cut order", "edge_relation": "Relation", "edge_about": "Link",
        "empty_tree": "model.yaml has no metrics to draw yet.", "empty_world": "world.yaml has no entries yet.",
        "footer": "Drawn only from model.yaml and world.yaml in this workspace. The page adds nothing of its own.",
        "time": "time", "from": "from", "to": "to", "also_called": "Also called", "value_in_data": "Value in the data",
        "dimension": "Dimension", "owner": "Owner", "direction": "Direction", "metrics": "Metrics", "evidence": "Checked against",
        "formula": "Formula", "breaks_into": "Breaks into", "computed_from": "Computed from", "cut_by": "Can be cut by",
        "cut_order": "Cut order", "unordered": "no order recorded", "used_in": "Cuts these metrics (its position in their cut order)",
        "defined_by": "Defined by", "weakest": "Takes the weakest tier of the records it rests on.",
        "no_own_record": "No record of its own; takes the weakest tier of the cut orders that name it.",
        "status_confirmed": "confirmed", "status_proposed": "to confirm", "status_retired": "retired",
        "dir_lower": "lowers it", "dir_higher": "raises it", "dir_sensitive": "moves it either way",
        "of": "of", "column": "column", "table": "table", "scatter": "Scatter again",
    },
    "zh": {
        "page_title": "业务知识图谱", "tab_tree": "指标树", "tab_world": "业务世界描述",
        "tabs_label": "视图", "legend": "可信程度", "legend_more": "轮廓的含义",
        "tier_fact": "事实", "tier_confirm": "待确认", "tier_inference": "AI 推断", "tier_retired": "已作废",
        "text_fact": "有人说过，或来自系统记录、数据、公式，并且已确认。",
        "text_confirm": "还是提议，或来自文档。还没有人确认。",
        "text_inference": "通用常识或演示设定。有人确认之前只是草稿。",
        "text_retired": "留作历史，不再用于分析。",
        "tier_none": "无出处记录", "text_none": "模型里用到了它，但没有任何记录说明它从哪来。",
        "badge_none": "无出处", "banner_none": "无出处记录",
        "no_record_metric": "这个指标出现在模型里，但没有任何记录说明它从哪来。",
        "badge_confirm": "待确认", "badge_inference": "推断", "badge_retired": "已作废",
        "banner_inference": "推断：在有人确认之前只是草稿",
        "banner_confirm": "待确认：还没有人确认过",
        "banner_fact": "事实：已确认，来自某个人、系统记录、数据或公式",
        "banner_retired": "已作废：留作历史，不再使用",
        "filter_inference": "隐藏 AI 推断", "cards": "个节点", "links": "条连线",
        "hint_tree": "把鼠标移到卡片上，看它是怎么切分的（触屏上点一下）。",
        "hint": "拖动卡片可以挪位置，点一下或按回车看详情，拖动空白处可以平移。",
        "close": "关闭", "source": "出处", "said": "原话", "date": "日期", "note": "备注", "status": "状态",
        "refuted": "什么数据能推翻它", "connected": "相连的内容", "trust": "可信程度",
        "no_source": "文件里没有记录这一条的出处和状态。",
        "zoom_in": "放大", "zoom_out": "缩小", "zoom_fit": "适应屏幕",
        "kind_metric": "指标", "kind_north": "北极星指标", "kind_dimension": "维度", "kind_entity": "实体",
        "kind_outside": "外部方", "kind_mechanism": "机制", "kind_event": "事件", "kind_action": "动作",
        "edge_formula": "公式", "edge_cut": "切分顺序", "edge_relation": "关系", "edge_about": "关联",
        "empty_tree": "model.yaml 里还没有可画的指标。", "empty_world": "world.yaml 里还没有内容。",
        "footer": "只画这个工作目录里 model.yaml 和 world.yaml 的内容，页面自己不添加任何东西。",
        "time": "时间", "from": "自", "to": "至", "also_called": "也叫", "value_in_data": "数据里的取值",
        "dimension": "维度", "owner": "负责人", "direction": "方向", "metrics": "涉及指标", "evidence": "对照的数据",
        "formula": "公式", "breaks_into": "拆成", "computed_from": "算自", "cut_by": "可以按这些维度切",
        "cut_order": "切分顺序", "unordered": "未记录顺序", "used_in": "用来切这些指标（括号里是它在该指标切分顺序里的位置）",
        "defined_by": "定义来自", "weakest": "取它所依据的记录里最弱的一档。",
        "no_own_record": "自己没有记录；取提到它的切分顺序里最弱的一档。",
        "status_confirmed": "已确认", "status_proposed": "待确认", "status_retired": "已作废",
        "dir_lower": "拉低", "dir_higher": "拉高", "dir_sensitive": "双向都会动",
        "of": "的", "column": "列", "table": "表", "scatter": "重新打散",
    },
}


# ---------- trust tiers ----------

def tier_of(rec) -> str:
    """fact / confirm / inference / retired, from the record's own source.kind and status and nothing else.

    Order matters when the two fields disagree: retired wins over everything; an inference source (general
    knowledge, a demo setting) stays an inference even when marked confirmed, because confirming a draft
    does not turn general knowledge into an observation; proposed or document means a person still has to
    confirm; only a person, a system record, the data or arithmetic, confirmed, is a fact. A record with no
    usable source is never a fact.
    """
    src = rec.get("source") if isinstance(rec, dict) else None
    kind = src.get("kind") if isinstance(src, dict) else None
    status = rec.get("status") if isinstance(rec, dict) else None
    if status == "retired":
        return "retired"
    if kind in INFERENCE_KINDS:
        return "inference"
    if status == "proposed" or kind == "document":
        return "confirm"
    if kind in FACT_KINDS and status == "confirmed":
        return "fact"
    return "confirm"


def weakest(tiers) -> str | None:
    """The least trusted live tier among `tiers`; retired only if every one of them is retired."""
    tiers = list(tiers)
    live = [t for t in tiers if t != "retired"]
    if live:
        return max(live, key=_WEAKNESS.__getitem__)
    return "retired" if tiers else None


# ---------- small helpers ----------

def _src(rec, lang: str) -> dict:
    s = rec.get("source") if isinstance(rec.get("source"), dict) else {}
    kind = s.get("kind")
    return {
        "kind": kind or "", "kind_text": SOURCE_KINDS[lang].get(kind, kind or ""),
        "name": label(s["label"], lang) if s.get("label") else str(s.get("ref") or ""),
        "quote": str(s.get("quote") or ""), "date": str(s["date"]) if s.get("date") else "",
        "note": label(s.get("note"), lang), "tier": tier_of(rec),
    }


def _shorten(text: str, lang: str) -> str:
    """The first clause of a long sentence for the card; the whole sentence stays in the panel."""
    text = " ".join(str(text).split())
    limit = 30 if lang == "zh" else 60
    m = re.search(r"[。；;！？!?]|\.\s|,\s|，", text)
    if m and m.end() >= 6:
        text = text[: m.start()]
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _date(x):
    try:
        return dt.date.fromisoformat(str(x))
    except (TypeError, ValueError):
        return None


def _metric_dims(ws: Workspace, name: str, seen=()) -> set:
    """Dimensions every measure behind a metric lists; read from the file, no data loaded."""
    m = ws.metrics.get(name) or {}
    if name in seen:
        return set()
    if m.get("kind") == "ratio":
        parts = [_metric_dims(ws, m.get(k), seen + (name,)) for k in ("numerator", "denominator")]
        return set.intersection(*parts)
    return set((ws.measures.get(m.get("measure")) or {}).get("dimensions") or [])


def _fact(k, v):
    return [k, v]


# ---------- the metric tree ----------

def _tree(ws: Workspace, lang: str, ui: dict) -> dict:
    metrics, dims = ws.metrics, ws.dimensions
    ident = [i for i in (ws.model.get("identities") or []) if i.get("left") in metrics]
    prios = {k: v for k, v in (ws.model.get("priorities") or {}).items() if k in metrics and isinstance(v, dict)}
    ml = lambda m: label((metrics.get(m) or {}).get("label", m), lang)  # noqa: E731
    dl = lambda d: label((dims.get(d) or {}).get("label", d), lang)  # noqa: E731

    # depth below the north star, following the formulas; the cut dimensions form the last row
    north = ws.model.get("north_star") if ws.model.get("north_star") in metrics else None
    depth: dict = {}
    roots = [north] if north else [m for m in metrics if not any(m in i.get("factors", []) for i in ident)]
    frontier = [r for r in roots if r in metrics]
    for r in frontier:
        depth[r] = 0
    while frontier:
        nxt = []
        for i in ident:
            if i["left"] in frontier:
                for f in i.get("factors", []):
                    if f in metrics and f not in depth:
                        depth[f] = depth[i["left"]] + 1
                        nxt.append(f)
        frontier = nxt
    for m in metrics:
        depth.setdefault(m, 1 if depth else 0)

    nodes, edges = [], []
    tiers_of_metric: dict = {m: [] for m in metrics}
    for i in ident:
        for m in [i["left"], *[f for f in i.get("factors", []) if f in metrics]]:
            tiers_of_metric[m].append(tier_of(i))
    ident_by_metric: dict = {m: [] for m in metrics}
    for i in ident:
        for m in [i["left"], *[f for f in i.get("factors", []) if f in metrics]]:
            ident_by_metric[m].append(i)
    op = {"multiply": " × ", "divide": " ÷ "}

    def formula_text(i):
        return f"{ml(i['left'])} = " + op.get(i.get("operator"), " ? ").join(ml(f) for f in i.get("factors", []))

    for m, spec in metrics.items():
        measure = ws.measures.get(spec.get("measure")) or {}
        facts = []
        if spec.get("kind") == "ratio":
            facts.append(_fact(ui["formula"], f"{ml(spec.get('numerator'))} ÷ {ml(spec.get('denominator'))}"))
        elif measure:
            facts.append(_fact(ui["computed_from"], f"{ui['table']} {measure.get('source')} · {measure.get('agg')} {ui['of']} {ui['column']} {measure.get('column') or '*'}"))
        for i in ident:
            if i["left"] == m:
                facts.append(_fact(ui["breaks_into"], op[i["operator"]].join(ml(f) for f in i.get("factors", [])) if i.get("operator") in op else ""))
        allowed = _metric_dims(ws, m)
        order = [d for d in (prios.get(m) or {}).get("order", []) if d in dims]
        rest = sorted(d for d in allowed if d not in order and d in dims)
        if order:
            facts.append(_fact(ui["cut_order"], ", ".join(f"{i} {dl(d)}" for i, d in enumerate(order, 1))))
        if rest:
            facts.append(_fact(ui["cut_by"], ", ".join(dl(d) for d in rest) + f" ({ui['unordered']})"))
        own = ident_by_metric[m]
        t = weakest(tiers_of_metric[m])
        sources = []
        for i in own:
            s = _src(i, lang)
            s["what"] = formula_text(i)
            sources.append(s)
        if t is None:
            t = "none"
        nodes.append({
            "id": f"metric:{m}", "kind": "metric", "north": m == north, "depth": depth[m],
            "label": ml(m), "full": ml(m), "tag": ui["kind_north"] if m == north else ui["kind_metric"],
            "tier": t, "status": "", "sources": sources, "no_source": False,
            "note": ui["weakest"] if len(own) > 1 else (ui["no_record_metric"] if not own else ""), "refuted_by": "", "facts": facts,
        })

    cut_edges: list = []
    used: dict = {}
    for m, pr in prios.items():
        for n, d in enumerate([x for x in pr.get("order", []) if x in dims], 1):
            used.setdefault(d, []).append((m, pr, n))
            cut_edges.append((m, d, n, pr))
    for d, uses in used.items():
        spec = dims[d]
        facts = [_fact(ui["column"], str(spec.get("column", d)))]
        facts.append(_fact(ui["used_in"], ", ".join(f"{ml(m)} ({n})" for m, _, n in uses)))
        nodes.append({
            "id": f"dimension:{d}", "kind": "dimension", "depth": 99, "label": dl(d), "full": dl(d), "tag": ui["kind_dimension"],
            "tier": weakest(tier_of(p) for _, p, _n in uses), "status": "", "sources": [],
            "no_source": False, "note": ui["no_own_record"], "refuted_by": "", "facts": facts,
        })

    for n, i in enumerate(ident):
        for f in i.get("factors", []):
            if f not in metrics:
                continue
            glyph = op.get(i.get("operator"), "").strip()
            if i.get("operator") == "divide" and f == i["factors"][0]:
                glyph = ""
            edges.append(_edge(f"formula:{i.get('id', n)}:{f}", f"metric:{i['left']}", f"metric:{f}", "formula", glyph, i, lang,
                               what=formula_text(i), tag=ui["edge_formula"]))
    for m, d, n, pr in cut_edges:
        edges.append(_edge(f"cut:{m}:{d}", f"metric:{m}", f"dimension:{d}", "cut", str(n), pr, lang,
                           what=f"{ml(m)} → {dl(d)} ({n})", tag=ui["edge_cut"], mode=pr.get("mode")))
    return {"nodes": nodes, "edges": edges}


def _edge(eid, s, t, kind, glyph, rec, lang, what, tag, **extra):
    src = _src(rec, lang)
    return {"id": eid, "s": s, "t": t, "kind": kind, "glyph": glyph, "tier": tier_of(rec), "status": rec.get("status") or "",
            "full": what, "tag": tag, "sources": [src], "refuted_by": label(rec.get("refuted_by"), lang), "facts": [], **extra}


# ---------- the business world description ----------

def _world(ws: Workspace, lang: str, ui: dict) -> dict:
    w = ws.world
    ents = {e["id"]: e for e in w.get("entities", []) if isinstance(e, dict) and "id" in e}
    dims, metrics = ws.dimensions, ws.metrics
    el = lambda e: label((ents.get(e) or {}).get("label", e), lang)  # noqa: E731
    ml = lambda m: label((metrics.get(m) or {}).get("label", m), lang)  # noqa: E731
    nodes, edges = [], []

    def base(rec, kind, text, tag, facts, full=None):
        return {"id": f"{kind}:{rec['id']}", "kind": kind, "label": text, "full": full or text, "tag": tag,
                "tier": tier_of(rec), "status": rec.get("status") or "", "sources": [_src(rec, lang)],
                "no_source": not isinstance(rec.get("source"), dict), "note": "",
                "refuted_by": label(rec.get("refuted_by"), lang), "facts": facts}

    for e in ents.values():
        dim = e.get("dimension")
        outside = bool(e.get("external"))
        facts = []
        if dim:
            facts.append(_fact(ui["dimension"], label((dims.get(dim) or {}).get("label", dim), lang)))
        if e.get("key") is not None:
            facts.append(_fact(ui["value_in_data"], str(e["key"])))
        if e.get("aliases"):
            facts.append(_fact(ui["also_called"], ", ".join(str(a) for a in e["aliases"])))
        tag = ui["kind_outside"] if outside else (label((dims.get(dim) or {}).get("label", dim), lang) if dim else ui["kind_entity"])
        nodes.append(base(e, "entity", el(e["id"]), tag, facts))

    for x in w.get("mechanisms", []):
        facts = []
        if x.get("direction"):
            facts.append(_fact(ui["direction"], ui.get("dir_" + str(x["direction"]), str(x["direction"]))))
        if x.get("metrics"):
            facts.append(_fact(ui["metrics"], ", ".join(ml(m) for m in x["metrics"])))
        text = label(x.get("claim"), lang)
        nodes.append(base(x, "mechanism", _shorten(text, lang), ui["kind_mechanism"], facts, text))

    dated = []
    for x in w.get("events", []):
        a, b = _date(x.get("start")), _date(x.get("end"))
        if b and a and b.year == a.year:
            when = f"{a.isoformat()} – {b.strftime('%m-%d')}"
        elif b:
            when = f"{x.get('start')} – {x.get('end')}"
        else:
            when = f"{ui['from']} {x.get('start')}"
        facts = [_fact(ui["date"], f"{x.get('start')} – {x.get('end') or '…'}")]
        ev = x.get("evidence") or {}
        if ev.get("source"):
            flt = ", ".join(f"{k} = {v}" for k, v in (ev.get("filters") or {}).items())
            facts.append(_fact(ui["evidence"], f"{ev['source']}" + (f" ({flt})" if flt else "")))
        if x.get("metrics"):
            facts.append(_fact(ui["metrics"], ", ".join(ml(m) for m in x["metrics"])))
        text = label(x.get("what"), lang)
        n = base(x, "event", _shorten(text, lang), f"{ui['kind_event']} · {when}", facts, text)
        n["t"] = a.toordinal() if a else None
        n["when"] = str(x.get("start") or "")
        nodes.append(n)
        if a:
            dated.append(a)

    for x in w.get("actions", []):
        owner = label(x.get("owner"), lang)
        text = label(x.get("action"), lang)
        nodes.append(base(x, "action", _shorten(text, lang), f"{ui['kind_action']} · {owner}", [_fact(ui["owner"], owner)], text))

    for r in w.get("relations", []):
        s, o = f"entity:{r.get('subject')}", f"entity:{r.get('object')}"
        if r.get("subject") in ents and r.get("object") in ents:
            pred = str(r.get("predicate", "")).replace("_", " ")
            edges.append(_edge(f"relation:{r.get('id')}", s, o, "relation", pred, r, lang,
                               what=f"{el(r['subject'])} {pred} {el(r['object'])}", tag=ui["edge_relation"]))
    for kind, key in (("mechanism", "mechanisms"), ("event", "events"), ("action", "actions")):
        for x in w.get(key, []):
            for e in x.get("entities", []):
                if e in ents:
                    edges.append(_edge(f"about:{kind}:{x['id']}:{e}", f"{kind}:{x['id']}", f"entity:{e}", "about", "", x, lang,
                                       what=f"{next(n['full'] for n in nodes if n['id'] == kind + ':' + x['id'])} → {el(e)}", tag=ui["edge_about"]))
    axis = None
    if dated:
        axis = {"min": min(dated).toordinal(), "max": max(dated).toordinal(), "from": min(dated).isoformat(), "to": max(dated).isoformat()}
    return {"nodes": nodes, "edges": edges, "axis": axis}


# ---------- page ----------

def build_data(ws: Workspace, lang: str | None = None) -> dict:
    lang = lang or ws.lang
    lang = lang if lang in UI else "en"
    ui = UI[lang]
    views = {"tree": _tree(ws, lang, ui), "world": _world(ws, lang, ui)}
    for v in views.values():
        v["counts"] = {t: sum(1 for n in v["nodes"] if n["tier"] == t) for t in TIERS}
    name = label(ws.project.get("name"), lang) or ws.root.name
    return {"lang": lang, "name": name, "ui": ui, "views": views}


def _json_for_script(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    for ch, rep in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        s = s.replace(ch, rep)
    return s


def render(ws: Workspace, lang: str | None = None, data: dict | None = None) -> str:
    data = data or build_data(ws, lang)
    words = {**data["ui"], "name": data["name"], "lang_code": data["lang"]}
    page = (TEMPLATES / "network.html").read_text(encoding="utf-8")
    page = re.sub(r"\{\{(\w+)\}\}", lambda m: html.escape(str(words.get(m.group(1), m.group(0)))), page)
    # style, script and data go in after the placeholders are filled, so a {{...}} inside a user's text is never read as one
    page = page.replace("<!--STYLE-->", (TEMPLATES / "network.css").read_text(encoding="utf-8"))
    page = page.replace("<!--SCRIPT-->", (TEMPLATES / "network.js").read_text(encoding="utf-8"))
    return page.replace("<!--DATA-->", _json_for_script(data))


def write(ws: Workspace, out: Path | None = None, lang: str | None = None) -> dict:
    data = build_data(ws, lang)
    out = Path(out or ws.root / "knowledge.html")
    out.write_text(render(ws, data=data), encoding="utf-8")
    return {"page": str(out), "lang": data["lang"],
            **{k: {"nodes": len(v["nodes"]), "edges": len(v["edges"])} for k, v in data["views"].items()}}
