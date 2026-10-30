"""Build the demo site from real runs on the demo shop. Nothing on the page is typed by hand.

    uv run python site/build.py          -> site/dist/ (open site/dist/index.html, works from file://)

Every number and sentence comes from the run state or the generated report, so the page can never
disagree with what the skill actually does.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DEMO = ROOT / "demo" / "store"
sys.path.insert(0, str(ROOT / "skills" / "analyst-in-a-box" / "scripts"))
sys.path.insert(0, str(DEMO))

import answer_key  # noqa: E402
from aib import evolve  # noqa: E402
from aib.explain import World, entry_text  # noqa: E402
from aib.report import seg_label, slot_label  # noqa: E402
from aib.run import TRANSITIONS, run  # noqa: E402
from aib.workspace import Workspace, label  # noqa: E402

DIST = ROOT / "site" / "dist"
ASSETS = ROOT / "site" / "assets"
CASE_ORDER = ["revenue_last_week", "east_last_week", "aov_last_week", "app_vs_web"]


# ---------------------------------------------------------------- markdown (the subset the reports use)

def _inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"(?<![\w*])_([^_]+)_(?![\w*])", r"<em>\1</em>", t)
    return t


def md_to_html(md: str) -> str:
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[-|\s]+\|$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            head, body = rows[0], rows[1:]
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
        elif ln.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith("> "):
                buf.append(lines[i][2:])
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>")
        elif re.match(r"^\s*- ", ln):
            out.append("<ul>")
            depth = 0
            while i < len(lines) and re.match(r"^\s*- ", lines[i]):
                d = (len(lines[i]) - len(lines[i].lstrip())) // 2
                while d > depth:
                    out.append("<ul>")
                    depth += 1
                while d < depth:
                    out.append("</ul>")
                    depth -= 1
                out.append(f"<li>{_inline(lines[i].lstrip()[2:])}</li>")
                i += 1
            out.append("</ul>" * (depth + 1))
        elif re.match(r"^\d+\. ", ln):
            out.append("<ol>")
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                item = re.sub(r"^\d+\. ", "", lines[i])
                out.append(f"<li>{_inline(item)}</li>")
                i += 1
            out.append("</ol>")
        else:
            buf = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||> |\s*- |\d+\. )", lines[i]):
                buf.append(lines[i])
                i += 1
            out.append(f"<p>{_inline(' '.join(buf))}</p>")
    return "\n".join(out)


def sections(md: str) -> dict:
    """Split a report into its ## sections, keyed by position (0 = conclusion, 1 = unusual, ...)."""
    parts = re.split(r"\n## ", "\n" + md.split("\n", 1)[1])
    return {i - 1: "## " + p for i, p in enumerate(parts) if i > 0}


# ---------------------------------------------------------------- runs

def copy_ws(dst: Path) -> Path:
    shutil.copytree(DEMO / "workspace", dst, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    return dst


def run_cases(tmp: Path):
    ws = Workspace(copy_ws(tmp / "ws"))
    states = {}
    for k in CASE_ORDER:
        c = answer_key.CASES[k]
        out = DIST / "reports" / k
        states[k] = run(ws, {**c["run"], "id": k, "question": c["question"]}, out_dir=out)
    return ws, states


PUBLIC = ROOT / "demo" / "public"


def run_public(tmp: Path) -> dict:
    """The public dataset through the same flow a new user takes: init -> confirm -> first run."""
    from aib import draft
    src = PUBLIC / "data" / "invoices.csv.gz"
    if not src.exists():
        raise SystemExit(f"{src} is missing; build it with demo/public/prepare.py (see demo/public/README.md)")
    data = tmp / "public" / src.name
    data.parent.mkdir(parents=True)
    shutil.copy(src, data)
    answers = yaml.safe_load((PUBLIC / "answers.yaml").read_text(encoding="utf-8"))
    out = {}
    for lang in ("zh", "en"):
        ws_dir = tmp / "public" / f"ws_{lang}"
        draft.init(data, ws_dir, lang=lang)
        first = draft.confirm(ws_dir, answers)["first_run"]
        out[lang] = run(Workspace(ws_dir), first, out_dir=tmp / "public" / f"run_{lang}")
    dst = DIST / "reports" / "public"
    dst.mkdir(parents=True, exist_ok=True)
    for lang in ("zh", "en"):
        run_dir = Path(out[lang]["out_dir"])
        shutil.copy(run_dir / f"report.{lang}.md", dst / f"report.{lang}.md")
        if (run_dir / "charts").exists():
            shutil.copytree(run_dir / "charts", dst / "charts", dirs_exist_ok=True)
    out["source"] = json.loads((PUBLIC / "data" / "source.json").read_text(encoding="utf-8"))
    return out


def run_learning(tmp: Path) -> dict:
    root = copy_ws(tmp / "learn")
    spec = yaml.safe_load((DEMO / "correction.yaml").read_text(encoding="utf-8"))
    case = answer_key.CASES[spec["after_case"]]
    cfg = {**case["run"], "id": case["case"], "question": case["question"]}
    before = run(root, cfg, out_dir=DIST / "reports" / "learning_before")
    applied = evolve.apply(root, {**spec["correction"], "run": cfg})
    after = run(root, cfg, out_dir=DIST / "reports" / "learning_after")
    rows = evolve.regress(root)
    world = yaml.safe_load((root / "world.yaml").read_text(encoding="utf-8"))
    world["mechanisms"] = [m for m in world["mechanisms"] if m["id"] != applied["target"]]
    (root / "world.yaml").write_text(yaml.safe_dump(world, allow_unicode=True, sort_keys=False), encoding="utf-8")
    forgot = evolve.regress(root)
    ws_after = Workspace(copy_ws(tmp / "learn_view"))
    return {"spec": spec, "before": before, "after": after, "applied": applied, "regress": rows,
            "forget_caught": not all(r["pass"] for r in forgot), "ws": ws_after}


# ---------------------------------------------------------------- graph

def graph(ws: Workspace) -> dict:
    world = World(ws)
    nodes, links = {}, []
    ns = ws.model.get("north_star")
    factors = {f for i in ws.model.get("identities", []) for f in i["factors"]}

    def add(nid, kind, lab, views, **kw):
        nodes[nid] = {"id": nid, "kind": kind, "label": lab, "views": views, **kw}

    # Rings follow the formula tree: the north star in the middle, each identity one ring further out.
    depth, frontier = {ns: 0}, [ns]
    while frontier:
        nxt = []
        for left in frontier:
            for i in ws.model.get("identities", []):
                if i["left"] == left:
                    for f in i["factors"]:
                        if f not in depth:
                            depth[f] = depth[left] + 1
                            nxt.append(f)
        frontier = nxt
    deepest = max(depth.values(), default=0)
    for m, spec in ws.metrics.items():
        ring = depth.get(m, deepest + 1)
        add(f"m:{m}", "metric", {l: label(spec.get("label", m), l) for l in ("zh", "en")}, ["metrics"], ring=ring)
    for i in ws.model.get("identities", []):
        for f in i["factors"]:
            links.append({"s": f"m:{i['left']}", "t": f"m:{f}", "kind": "identity", "views": ["metrics"]})
    for m, spec in ws.metrics.items():
        if spec.get("kind") == "ratio":
            for part in ("numerator", "denominator"):
                links.append({"s": f"m:{m}", "t": f"m:{spec[part]}", "kind": "ratio", "views": ["metrics"]})
    dim_ring = deepest + 2
    for d, spec in ws.dimensions.items():
        add(f"d:{d}", "dimension", {l: label(spec.get("label", d), l) for l in ("zh", "en")}, ["metrics", "world"], ring=dim_ring)
    # A relation between values (Shanghai belongs to East) is a relation between their dimensions (city -> region).
    seen = set()
    for r in ws.world.get("relations", []):
        a, b = world.entities.get(r["subject"], {}), world.entities.get(r["object"], {})
        pair = (a.get("dimension"), b.get("dimension"), r["predicate"])
        if a.get("dimension") and b.get("dimension") and pair not in seen:
            seen.add(pair)
            links.append({"s": f"d:{pair[0]}", "t": f"d:{pair[1]}", "kind": "relation", "label": pair[2], "views": ["metrics"]})
    for m in ws.metrics:
        order = (ws.model.get("priorities") or {}).get(m, {}).get("order", [])
        for rank, d in enumerate(order):
            links.append({"s": f"m:{m}", "t": f"d:{d}", "kind": "cut", "rank": rank + 1, "views": ["metrics"]})
    for e in world.entities.values():
        add(f"e:{e['id']}", "entity", {l: label(e.get("label", e["id"]), l) for l in ("zh", "en")}, ["world"],
            ring=dim_ring + 1, external=bool(e.get("external")), etype=e.get("type"))
        if e.get("dimension"):
            links.append({"s": f"d:{e['dimension']}", "t": f"e:{e['id']}", "kind": "value", "views": ["world"]})
    for r in ws.world.get("relations", []):
        links.append({"s": f"e:{r['subject']}", "t": f"e:{r['object']}", "kind": "relation", "label": r["predicate"], "views": ["world"]})
    for kind, bucket in (("mechanism", "mechanisms"), ("event", "events"), ("action", "actions")):
        for x in ws.world.get(bucket, []):
            add(f"w:{x['id']}", kind, {l: entry_text(x, l) for l in ("zh", "en")}, ["world"], ring=dim_ring + 2,
                status=x.get("status"), external=x.get("kind") == "external", short=x["id"])
            for e in x.get("entities", []):
                links.append({"s": f"w:{x['id']}", "t": f"e:{e}", "kind": kind, "views": ["world"]})
    return {"nodes": list(nodes.values()), "links": links}


def story_html(md: str) -> str:
    """A report section as a story card: the card already names the step, and entry ids are for the report, not the story."""
    h = md_to_html(md)
    h = re.sub(r"<h2>.*?</h2>", "", h, count=1)
    return re.sub(r"\s*<code>[a-z0-9_]+</code>", "", h)


def case_story(ws: Workspace, s: dict, G: dict, lang: str) -> dict:
    world = World(ws)
    md = (Path(s["out_dir"]) / f"report.{lang}.md").read_text(encoding="utf-8")
    sec = sections(md)
    m = f"m:{s['metric']}"
    ent = lambda d, v: f"e:{world.entity_for(d, v)}" if world.entity_for(d, v) else None  # noqa: E731
    steps = [{"kind": "conclusion", "html": story_html(sec[0]), "lit": [m]},
             {"kind": "unusual", "html": story_html(sec[1]), "lit": [m]}]
    breakdown = sec[2].split("\n### ")
    if s["horizontal"]:
        h = s["horizontal"][0]
        steps.append({"kind": "formula", "html": story_html(breakdown[0]), "lit": [m] + [f"m:{f['factor']}" for f in h["factors"]]})
    for i, cut in enumerate(s["cuts"]):
        r = cut["result"]
        lit = [m, f"d:{cut['dimension']}"] + [ent(d, v) for d, v in cut["path"]] + [ent(d, v) for d, v in cut["filters"].items()]
        if cut.get("sides"):
            lit += [ent(cut["side_dimension"], v) for v in cut["sides"]]
        drill = cut["decision"]["then"].get("action") == "drill"
        if drill:
            lit.append(ent(cut["dimension"], r["top1_key"]))
        vf = "delta" if r["operator"] == "additive" else "total" if r["operator"] in ("divisive", "second_order_sides", "second_order_sides_rate") else "change"
        bars = [{"label": seg_label(ws, world, cut["dimension"], x["key"], lang), "value": x[vf], "share": x.get("share"),
                 "top": x["key"] == r["top1_key"] and drill, "id": ent(cut["dimension"], x["key"])} for x in r["segments"]]
        block = "### " + breakdown[i + 1] if i + 1 < len(breakdown) else ""
        block = re.sub(r"\n\|.*", "", block)          # the table is drawn as bars instead
        block = re.sub(r"\n!\[.*", "", block)
        steps.append({"kind": "cut", "html": story_html(block), "lit": [x for x in lit if x], "bars": bars,
                      "drill": drill, "dims": [e for e in (b["id"] for b in bars) if e]})
    why_lit = []
    for slot in s["slots"]:
        why_lit += [f"e:{e}" for e in slot["context"]] + [f"w:{c['id']}" for c in slot["citations"]]
    steps.append({"kind": "why", "html": story_html(sec[3]), "lit": why_lit, "gaps": [g["slot"] for g in s["gaps"]]})
    acts = [f"w:{a}" for a in s["actions"]]
    act_ents = [f"e:{e}" for a in ws.world.get("actions", []) if a["id"] in s["actions"] for e in a["entities"]]
    if not acts:
        # No owner recorded yet: light the slices that still lack one, so the step shows where the gap is.
        act_ents = [f"e:{e}" for slot in s["slots"] for e in slot["context"]]
    steps.append({"kind": "act", "html": story_html(sec[4]), "lit": acts + act_ents})
    keep = {x for st in steps for x in st["lit"]} | {e for st in steps for e in st.get("dims", [])}
    keep |= {f"d:{c['dimension']}" for c in s["cuts"]}
    sub_nodes = [n for n in G["nodes"] if n["id"] in keep]
    sub_links = [l for l in G["links"] if l["s"] in keep and l["t"] in keep]
    return {"steps": steps, "nodes": sub_nodes, "links": sub_links}


# ---------------------------------------------------------------- words on the page

UI = {
    "zh": {
        "tagline": "这个数为什么变了，接下来该谁去做什么。",
        "sub": "把分析师排查异动的方法做成一个 skill。机器从数据起草，人确认补充；被纠正一次，就记住一次。",
        "demo": "演示店：花果篮（虚构）", "nav": {"story": "一个案子", "graph": "完整图谱", "learning": "它怎么学",
                                              "arch": "怎么搭的"}, "other_lang": "English",
        "steps": {"conclusion": "结论", "unusual": "算不算异常", "formula": "按公式拆", "cut": "切一刀", "why": "为什么", "act": "谁该做什么"},
        "reveal": "答案对照", "reveal_sub": "演示店是虚构的。生成数据时埋进了这些原因；skill 从头到尾没读过这份答案。",
        "asked": "问题", "found": "skill 找出来的", "planted": "生成数据时埋的", "checks": "逐条核对",
        "report": "看完整报告", "views": {"metrics": "指标树", "world": "世界"},
        "graph_hint": "拖动一个节点，和它相连的会跟着走；点一下看详情。上方选一道题，看它走过的路。",
        "case_none": "不选题", "learn_title": "被纠正一次，就记住一次",
        "learn_sub": "同一道题跑两次，中间用户说了一句话。",
        "coverage": "需要业务解释的地方，有记录可引的比例", "before": "纠正前", "after": "纠正后",
        "user_said": "用户说", "recorded": "记成", "regression": "回归题", "forget": "把这条删掉再跑回归",
        "forget_caught": "回归题没通过：忘了会被发现。", "arch_title": "怎么搭的",
        "arch_sub": "skill 只读数据，不改数据；每个数都由脚本算，每条解释都带出处。",
        "footer": "演示店「花果篮」是虚构的，所有数据由程序生成，原因事先埋好。",
        "pass": "对上了", "fail": "没对上", "legend": {"metric": "指标", "dimension": "维度", "entity": "实体",
                                                       "mechanism": "机制", "event": "事件", "action": "动作"},
        "start": "往下滚，看它一步一步怎么查。", "stop_drill": "往下钻", "stop_spread": "分散，停",
        "public_title": "真实数据：一家英国网店",
        "public_sub": "一份项目从没见过的公开数据，按新用户的路子走：读表、答选择题、出第一份报告。它没有标准答案，只证明真实数据接得进、跑得出、自检能过。",
        "public_src": "数据：{citation} {doi} · {licence} · {first_day} 至 {last_day}，{invoices:,} 张发票 · 整理方法见 demo/public。",
    },
    "en": {
        "tagline": "Why did this number move, and who should act next?",
        "sub": "An analyst's way of investigating a moving number, packaged as a skill. The machine drafts from the data, a person confirms; correct it once and it remembers.",
        "demo": "Demo shop: Bloom & Basket (fictional)", "nav": {"story": "One case", "graph": "Full graph",
                                                                 "learning": "How it learns", "arch": "How it is built"},
        "other_lang": "中文",
        "steps": {"conclusion": "Conclusion", "unusual": "Is it unusual?", "formula": "By formula", "cut": "One cut", "why": "Why", "act": "Who acts"},
        "reveal": "Answer key", "reveal_sub": "The shop is fictional. These causes were planted when its data was generated; the skill never reads this key.",
        "asked": "Question", "found": "What the skill found", "planted": "What was planted", "checks": "Checks",
        "report": "Full report", "views": {"metrics": "Metric tree", "world": "World"},
        "graph_hint": "Drag a node and its neighbours follow; click for details. Pick a question above to see the path it took.",
        "case_none": "No question", "learn_title": "Corrected once, remembered",
        "learn_sub": "The same question, run twice. In between, the user said one sentence.",
        "coverage": "Share of places needing a business explanation that can cite a record", "before": "Before", "after": "After",
        "user_said": "The user said", "recorded": "Recorded as", "regression": "Regression case", "forget": "Delete it and replay the regressions",
        "forget_caught": "The regression fails: forgetting is caught.", "arch_title": "How it is built",
        "arch_sub": "The skill reads data and never writes it; every number is computed by a script, every explanation has a source.",
        "footer": "Bloom & Basket is fictional; all of its data is generated, with the causes planted in advance.",
        "pass": "matches", "fail": "does not match", "legend": {"metric": "Metric", "dimension": "Dimension", "entity": "Entity",
                                                                  "mechanism": "Mechanism", "event": "Event", "action": "Action"},
        "start": "Scroll to watch it investigate, step by step.", "stop_drill": "drill", "stop_spread": "spread, stop",
        "public_title": "Real data: a UK online retailer",
        "public_sub": "A public dataset the project has never seen, run the way a new user would: read the table, answer the choices, get a first report. It has no answer key; it shows that real data loads, runs and passes the checks.",
        "public_src": "Data: {citation} {doi} · {licence} · {first_day} to {last_day}, {invoices:,} invoices · preparation in demo/public.",
    },
}

LAYERS = {
    "zh": [("数据", "CSV、Excel、SQLite、DuckDB；日历、天气、大盘等外部数据。换来源不改 skill。"),
           ("方法层", "第零层 公式拆解 · 第一层 维度和先切哪刀 · 第二层 比了几次（一阶 / 二阶）· 第三层 解法、停止条件（决策表）、坑"),
           ("世界", "实体 · 关系 · 机制 · 事件 · 动作和负责人。只描述能解释数字的那部分。"),
           ("状态机", "定题 → 先判断 → 拆解 → 解释（外部事件过三道检查）→ 谁该做什么 → 交付前自检 → 运行记录"),
           ("自进化", "每次纠正记下用户原话、改一个文件、生成一道回归题；覆盖率随使用上涨。")],
    "en": [("Data", "CSV, Excel, SQLite, DuckDB; outside data such as calendars, weather, market benchmarks. Changing the source never changes the skill."),
           ("Method", "Layer 0 formula breakdown · Layer 1 dimensions and which cut first · Layer 2 how many comparisons (first / second order) · Layer 3 methods, stop conditions (decision tables), traps"),
           ("World", "Entities · relations · mechanisms · events · actions and owners. Only the part of the world that explains the numbers."),
           ("State machine", "frame → qualify → break down → explain (outside events pass three checks) → who acts → pre-delivery checks → run record"),
           ("Self-improvement", "Each correction keeps the user's words, changes one file, and becomes a regression case; coverage rises with use.")],
}
COMPARE = {
    "zh": [("", "回答什么", "怎么建"), ("A concept-logic system", "概念是什么、概念之间的逻辑", "专家用专门工具手写"),
           ("A data-integration platform", "公司有哪些东西、能对它们做什么（动作会改写系统数据）", "在打通的数仓上搭"),
           ("analyst-in-a-box", "这个数为什么变了、该谁去做什么", "机器从数据和文档起草，人确认和补")],
    "en": [("", "Answers", "Built by"), ("A concept-logic system", "What a concept is, and the logic between concepts", "Experts, in specialised tools"),
           ("A data-integration platform", "What a company has and what can be done to it (actions write back)", "On top of an integrated warehouse"),
           ("analyst-in-a-box", "Why this number moved, and who should act next", "The machine drafts from data and documents; a person confirms")],
}
NOT_MORE = {"zh": "它不比 其他系统 更完善：表达力、推理、写回、权限、规模都远不如。它只对「这个数为什么变了」这一个问题做到完整。",
            "en": "It is not more complete than other systems: far weaker in expressiveness, reasoning, write-back, permissions and scale. It is complete for one question only: why did this number move."}


# ---------------------------------------------------------------- pages

def _json(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str).replace("</", "<\\/")


def shell(lang, name, title, body, data=None, scripts=()):
    u, pre = UI[lang], ("" if lang == "zh" else "../")
    other = (f"en/{name}" if lang == "zh" else f"../{name}")
    nav = "".join(f'<a href="{p}.html" class="{"on" if p + ".html" == name else ""}">{u["nav"][k]}</a>'
                  for k, p in (("story", "index"), ("graph", "graph"), ("learning", "learning"), ("arch", "architecture")))
    data_tag = f"<script>window.AIB={_json(data)};</script>" if data is not None else ""
    js = "".join(f'<script src="{pre}assets/{s}"></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · analyst-in-a-box</title>
<link rel="stylesheet" href="{pre}assets/app.css"></head>
<body data-lang="{lang}"><div class="paper"></div>
<header class="top"><a class="brand" href="{'index.html'}">analyst<span>-in-a-</span>box</a>
<nav>{nav}</nav><a class="lang" href="{other}">{u['other_lang']}</a></header>
<main>{body}</main>
<footer><p>{u['footer']}</p></footer>
{data_tag}{js}</body></html>"""


def legend(lang):
    return "<ul class=legend>" + "".join(f'<li><i class="k-{k}"></i>{v}</li>' for k, v in UI[lang]["legend"].items()) + "</ul>"


CHECK_ZH = [(r"^pre-delivery checks pass$", "交付前自检通过"), (r"^answered as a second-order question$", "按二阶题回答"),
            (r"^first cut is (.+)$", r"第一刀切 \1"), (r"^top segment is (.+)$", r"排第一的是 \1"),
            (r"^(\w+): top segment is (.+)$", r"\1：排第一的是 \2"), (r"^(\w+): (\w+) effect is larger$", r"\1：\2效应更大"),
            (r"^(\w+) effect is larger$", r"\1效应更大"), (r"^cites (.+)$", r"引用了 \1"),
            (r"^outside event checks: (.+)$", r"外部事件检查：\1"), (r"^reports a gap at (.+)$", r"在 \1 报出缺口")]


def check_text(desc, lang):
    if lang == "en":
        return desc
    for pat, rep in CHECK_ZH:
        if re.match(pat, desc):
            return re.sub(pat, rep, desc)
    return desc


def found_text(ws, s, lang):
    world = World(ws)
    out = []
    for slot in s["slots"]:
        cites = [entry_text(next((x for k in ("events", "mechanisms") for x in ws.world.get(k, []) if x["id"] == c["id"]), {}), lang)
                 for c in slot["citations"] if not c.get("external") or c["checks"]["status"] == "supported"]
        head = f"<strong>{html.escape(slot_label(ws, world, slot, lang))}</strong>"
        if cites:
            out.append(head + "：" * (lang == "zh") + ": " * (lang == "en") + html.escape(cites[0]))
        else:
            out.append(head + ("：原因待确认（缺口）" if lang == "zh" else ": reason waiting for the user (gap)"))
    return "<br>".join(out)


def page_index(lang, ws, states, stories, learn, public):
    u = UI[lang]
    tabs = "".join(f'<button data-case="{k}" class="{"on" if i == 0 else ""}">{html.escape(label(answer_key.CASES[k]["question"], lang))}</button>'
                   for i, k in enumerate(CASE_ORDER))
    rows = []
    for k in CASE_ORDER:
        exp, s = answer_key.CASES[k], states[k]
        checks = answer_key.check(exp, s)
        ok = all(c for _, c in checks)
        planted = "<br>".join(html.escape(label(n, lang)) for n in answer_key.planted_notes(exp))
        detail = "".join(f'<li class="{"ok" if c else "no"}">{html.escape(check_text(d, lang))}</li>' for d, c in checks)
        rows.append(f"""<tr><td class=q>{html.escape(label(exp['question'], lang))}<a class=rep href="{'' if lang == 'zh' else '../'}reports/{k}/{lang}.html">{u['report']} →</a></td>
<td>{found_text(ws, s, lang)}</td><td>{planted}</td>
<td><span class="stamp {'ok' if ok else 'no'}">{u['pass'] if ok else u['fail']}</span><details><summary>{u['checks']} ({sum(c for _, c in checks)}/{len(checks)})</summary><ul>{detail}</ul></details></td></tr>""")
    b, a = learn["before"]["coverage"]["share"], learn["after"]["coverage"]["share"]
    body = f"""
<section class=hero><p class=kicker>{u['demo']}</p><h1>{u['tagline']}</h1><p class=sub>{u['sub']}</p>
<p class=hint>{u['start']}</p></section>
<section class=cases><div class=tabs>{tabs}</div></section>
<section class=story><div class=steps id=steps></div>
<div class=stage><div class=stage-inner><svg id=story-graph></svg>{legend(lang)}</div></div></section>
<section class=reveal id=reveal><h2>{u['reveal']}</h2><p class=sub>{u['reveal_sub']}</p>
<table class=key><thead><tr><th>{u['asked']}</th><th>{u['found']}</th><th>{u['planted']}</th><th>{u['checks']}</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></section>
<section class=teaser><h2>{u['learn_title']}</h2><p class=sub>{u['learn_sub']}</p>
<div class=meter><div><span>{u['before']}</span><b style="--v:{b}">{b:.0%}</b></div><div><span>{u['after']}</span><b style="--v:{a}">{a:.0%}</b></div></div>
<p><a class=cta href="learning.html">{u['nav']['learning']} →</a> <a class=cta href="graph.html">{u['nav']['graph']} →</a></p></section>
<section class=public><h2>{u['public_title']}</h2><p class=sub>{u['public_sub']}</p>
<div class=public-card>{story_html(sections((Path(public[lang]['out_dir']) / f'report.{lang}.md').read_text(encoding='utf-8'))[0])}
<p class=more><a href="{'' if lang == 'zh' else '../'}reports/public/{lang}.html">{u['report']} →</a></p></div>
<p class=caption>{u['public_src'].format(**public['source'])}</p></section>"""
    data = {"lang": lang, "ui": {k: u[k] for k in ("steps", "stop_drill", "stop_spread", "report")},
            "cases": {k: {**stories[k][lang], "report": f"{'' if lang == 'zh' else '../'}reports/{k}/{lang}.html"} for k in CASE_ORDER}}
    return shell(lang, "index.html", u["tagline"], body, data, ["graph.js", "story.js"])


def page_graph(lang, G, stories):
    u = UI[lang]
    opts = f'<option value="">{u["case_none"]}</option>' + "".join(
        f'<option value="{k}">{html.escape(label(answer_key.CASES[k]["question"], lang))}</option>' for k in CASE_ORDER)
    body = f"""<section class=graphpage><div class=toolbar>
<div class=views><button data-view=metrics class=on>{u['views']['metrics']}</button><button data-view=world>{u['views']['world']}</button></div>
<select id=case>{opts}</select><p class=hint>{u['graph_hint']}</p></div>
<div class=graphwrap><svg id=full-graph></svg><aside id=detail></aside></div>{legend(lang)}</section>"""
    lit = {k: sorted({x for st in stories[k][lang]["steps"] for x in st["lit"]}) for k in CASE_ORDER}
    data = {"lang": lang, "graph": G, "lit": lit, "ui": {"legend": u["legend"]}}
    return shell(lang, "graph.html", u["nav"]["graph"], body, data, ["graph.js", "graphpage.js"])


def page_learning(lang, learn):
    u, ws = UI[lang], learn["ws"]
    world = World(ws)
    b, a = learn["before"], learn["after"]
    gap = next(x for x in b["slots"] if x["status"] == "gap")
    quote = label(learn["spec"]["correction"]["quote"], lang)
    claim = label(learn["spec"]["correction"]["entry"]["claim"], lang)
    rows = learn["regress"]
    steps = [
        (u["before"], f"<b class=big>{b['coverage']['share']:.0%}</b>",
         html.escape(slot_label(ws, world, gap, lang)) + (" · 原因待确认" if lang == "zh" else " · reason waiting for the user"),
         "reports/learning_before"),
        (u["user_said"], f"<blockquote>{html.escape(quote)}</blockquote>", "", None),
        (u["recorded"], f"<code>{learn['applied']['target']}</code>", html.escape(claim) +
         f"<br><small>{'出处：用户原话' if lang == 'zh' else 'source: the user'} · {learn['applied']['correction']['date']}</small>", None),
        (u["after"], f"<b class=big>{a['coverage']['share']:.0%}</b>",
         html.escape(slot_label(ws, world, gap, lang)) + " → " + learn["applied"]["target"], "reports/learning_after"),
        (u["regression"], f"<b class=big>{sum(r['pass'] for r in rows)}/{len(rows)}</b>", html.escape(rows[0]["detail"]) if rows else "", None),
        (u["forget"], "<b class=big>✗</b>" if learn["forget_caught"] else "<b class=big>?</b>",
         u["forget_caught"] if learn["forget_caught"] else "", None),
    ]
    items = "".join(f"""<li><span class=when>{html.escape(t)}</span><div>{big}<p>{txt}</p>
{f'<a href="{"" if lang == "zh" else "../"}{link}/{lang}.html">{u["report"]} →</a>' if link else ''}</div></li>""" for t, big, txt, link in steps)
    body = f"""<section class=hero small><h1>{u['learn_title']}</h1><p class=sub>{u['learn_sub']}</p></section>
<section class=teaser><p class=caption>{u['coverage']}</p><div class=meter><div><span>{u['before']}</span><b style="--v:{b['coverage']['share']}">{b['coverage']['share']:.0%}</b></div>
<div><span>{u['after']}</span><b style="--v:{a['coverage']['share']}">{a['coverage']['share']:.0%}</b></div></div></section>
<section><ol class=timeline>{items}</ol></section>"""
    return shell(lang, "learning.html", u["learn_title"], body)


STEP_LABELS = {
    "zh": {"frame": "定题", "qualify": "先判断", "horizontal": "按公式拆", "vertical": "按维度切", "second_sides": "二阶·比两侧",
           "second_time": "二阶·比时段", "explain": "解释", "actions": "谁该做什么", "checks": "交付前自检", "record": "运行记录"},
    "en": {"frame": "Frame", "qualify": "Qualify", "horizontal": "By formula", "vertical": "By dimension", "second_sides": "2nd · two sides",
           "second_time": "2nd · two windows", "explain": "Explain", "actions": "Who acts", "checks": "Pre-delivery checks", "record": "Run record"},
}
STEP_POS = {"frame": (0, 1), "qualify": (1, 1), "horizontal": (2, 0), "vertical": (3, 0), "second_sides": (2.5, 1),
            "second_time": (2.5, 2), "explain": (4, 1), "actions": (5, 1), "checks": (6, 1), "record": (7, 1)}


def flow_svg(lang):
    W, H, bw, bh = 132, 64, 112, 34
    pos = {k: (20 + x * W, 18 + y * H) for k, (x, y) in STEP_POS.items()}
    out = [f'<svg class=flow viewBox="0 0 {20 + 8 * W} {40 + 3 * H}" role="img">',
           '<defs><marker id=ar viewBox="0 0 8 8" refX=8 refY=4 markerWidth=7 markerHeight=7 orient=auto><path d="M0,0 L8,4 L0,8 z"/></marker></defs>']
    for a, b, why in TRANSITIONS:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        out.append(f'<path d="M{x1 + bw},{y1 + bh / 2} C{x1 + bw + 30},{y1 + bh / 2} {x2 - 30},{y2 + bh / 2} {x2},{y2 + bh / 2}" marker-end="url(#ar)"><title>{html.escape(why)}</title></path>')
    for k, (x, y) in pos.items():
        out.append(f'<g class="st st-{k}"><rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="3"/>'
                   f'<text x="{x + bw / 2}" y="{y + bh / 2 + 5}" text-anchor="middle">{STEP_LABELS[lang][k]}</text></g>')
    return "".join(out) + "</svg>"


def page_arch(lang, ws):
    u = UI[lang]
    layers = "".join(f"<div class=layer><h3>{html.escape(t)}</h3><p>{html.escape(d)}</p></div>" for t, d in LAYERS[lang])
    rows = COMPARE[lang]
    table = ("<table><thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"
             + "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</tbody></table>")
    counts = {"metrics": len(ws.metrics), "dimensions": len(ws.dimensions), "entities": len(ws.world.get("entities", [])),
              "mechanisms": len(ws.world.get("mechanisms", [])), "events": len(ws.world.get("events", [])),
              "actions": len(ws.world.get("actions", [])), "tables": len(ws.rules.get("tables", []))}
    stats = "".join(f"<li><b>{v}</b><span>{k}</span></li>" for k, v in counts.items())
    body = f"""<section class=hero small><h1>{u['arch_title']}</h1><p class=sub>{u['arch_sub']}</p></section>
<section class=layers>{layers}</section>
<section><h2>{'状态机' if lang == 'zh' else 'State machine'}</h2>{flow_svg(lang)}</section>
<section><h2>{'演示店的规模' if lang == 'zh' else 'The demo shop, by size'}</h2><ul class=stats>{stats}</ul></section>
<section><h2>{'和其他系统的区别' if lang == 'zh' else 'How it differs from other systems'}</h2>{table}<p class=note>{NOT_MORE[lang]}</p></section>"""
    return shell(lang, "architecture.html", u["arch_title"], body)


def report_page(lang, md: str, title: str) -> str:
    return f"""<!doctype html><html lang="{'zh-CN' if lang == 'zh' else 'en'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<link rel="stylesheet" href="../../assets/app.css"></head><body data-lang="{lang}"><div class="paper"></div>
<header class="top"><a class="brand" href="../../{'' if lang == 'zh' else 'en/'}index.html">analyst<span>-in-a-</span>box</a>
<nav><a href="{'en' if lang == 'zh' else 'zh'}.html">{UI[lang]['other_lang']}</a></nav></header>
<main class=report>{md_to_html(md)}</main></body></html>"""


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "en").mkdir(parents=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        ws, states = run_cases(tmp)
        learn = run_learning(tmp)
        public = run_public(tmp)
        G = graph(ws)
        stories = {k: {lang: case_story(ws, states[k], G, lang) for lang in ("zh", "en")} for k in CASE_ORDER}
        for lang, out in (("zh", DIST), ("en", DIST / "en")):
            (out / "index.html").write_text(page_index(lang, ws, states, stories, learn, public), encoding="utf-8")
            (out / "graph.html").write_text(page_graph(lang, G, stories), encoding="utf-8")
            (out / "learning.html").write_text(page_learning(lang, learn), encoding="utf-8")
            (out / "architecture.html").write_text(page_arch(lang, ws), encoding="utf-8")
        for d in (DIST / "reports").iterdir():
            for lang in ("zh", "en"):
                md = (d / f"report.{lang}.md").read_text(encoding="utf-8")
                (d / f"{lang}.html").write_text(report_page(lang, md, md.split("\n", 1)[0][2:]), encoding="utf-8")
    shutil.copytree(ASSETS, DIST / "assets")
    print(f"site written to {DIST}")


if __name__ == "__main__":
    main()
