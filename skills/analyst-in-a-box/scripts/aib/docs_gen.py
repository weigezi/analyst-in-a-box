"""Readable pages generated from the YAML, for people who do not read YAML.

The YAML stays the only source; these pages are rebuilt from it and never edited by hand.
Pages link to each other with ordinary relative Markdown links, so the folder also opens as a
linked graph in Obsidian or any Markdown tool that follows links.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .report import SOURCE_KINDS, source_text
from .workspace import Workspace, label

H = {
    "zh": {"index": "这家公司的分析知识", "metrics": "指标", "dims": "维度", "world": "世界", "rules": "规则",
           "entities": "实体", "relations": "关系", "mechanisms": "机制", "events": "事件", "actions": "动作和负责人",
           "formula": "公式", "breaks_into": "拆成", "cut_by": "可以按这些维度切", "priority": "默认先切",
           "status": "状态", "source": "出处", "related": "相关", "owner": "负责人", "when": "时间",
           "north_star": "北极星", "generated": "本页由 YAML 自动生成，不要手改；改 YAML 后重新生成。",
           "params": "门槛", "tables": "决策表", "value": "值", "used_by": "被这些指标用到"},
    "en": {"index": "This company's analysis knowledge", "metrics": "Metrics", "dims": "Dimensions", "world": "World",
           "rules": "Rules", "entities": "Entities", "relations": "Relations", "mechanisms": "Mechanisms", "events": "Events",
           "actions": "Actions and owners", "formula": "Formula", "breaks_into": "Breaks into", "cut_by": "Can be cut by",
           "priority": "Default cut order", "status": "Status", "source": "Source", "related": "Related", "owner": "Owner",
           "when": "When", "north_star": "North star", "generated": "Generated from the YAML; do not edit. Edit the YAML and regenerate.",
           "params": "Thresholds", "tables": "Decision tables", "value": "Value", "used_by": "Used by"},
}


STATUS = {"zh": {"confirmed": "已确认", "proposed": "待确认", "retired": "已作废"},
          "en": {"confirmed": "confirmed", "proposed": "to confirm", "retired": "retired"}}


def _fn(x: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(x)) + ".md"


def _link(text, path):
    return f"[{text}]({path})"


def build(ws: Workspace, out: Path | None = None) -> Path:
    out = Path(out or ws.root / "docs")
    if out.exists():
        shutil.rmtree(out)
    for lang in ("zh", "en"):
        _build_lang(ws, out / lang, lang)
    return out


def _build_lang(ws, root: Path, lang: str):
    h = H[lang]
    (root / "metrics").mkdir(parents=True)
    (root / "world").mkdir(parents=True)
    w = ws.world
    ents = {e["id"]: e for e in w.get("entities", [])}
    ml = lambda m: label(ws.metrics[m].get("label", m), lang)  # noqa: E731
    el = lambda e: label(ents[e].get("label", e), lang) if e in ents else e  # noqa: E731
    mlink = lambda m, up=1: _link(ml(m), f"{'../' * up}metrics/{_fn(m)}")  # noqa: E731
    elink = lambda e, up=1: _link(el(e), f"{'../' * up}world/{_fn(e)}")  # noqa: E731

    for m, spec in ws.metrics.items():
        L = [f"# {ml(m)}", "", f"_{h['generated']}_", ""]
        if spec.get("kind") == "ratio":
            L += [f"**{h['formula']}**: {mlink(spec['numerator'])} ÷ {mlink(spec['denominator'])}", ""]
        for ident in ws.model.get("identities", []):
            if ident["left"] == m:
                L.append(f"- {h['breaks_into']}: " + " × ".join(mlink(x) for x in ident["factors"]))
        dims = sorted(ws.metric_dimensions(m))
        if dims:
            L += ["", f"**{h['cut_by']}**: " + ", ".join(label(ws.dimensions[d].get("label", d), lang) for d in dims)]
        pr = (ws.model.get("priorities") or {}).get(m)
        if pr:
            L += [f"**{h['priority']}**: " + " → ".join(label(ws.dimensions[d].get("label", d), lang) for d in pr.get("order", []))
                  + f" ({STATUS[lang].get(pr.get('status'), pr.get('status'))})"]
        rel = [x for k in ("mechanisms", "events") for x in w.get(k, []) if m in x.get("metrics", [])]
        if rel:
            L += ["", f"## {h['related']}", ""] + [f"- {_link(x['id'], '../world/' + _fn(x['id']))}" for x in rel]
        (root / "metrics" / _fn(m)).write_text("\n".join(L) + "\n", encoding="utf-8")

    def entry_page(x, kind):
        text = label(x.get("claim") or x.get("what") or x.get("action") or x.get("label"), lang)
        L = [f"# {text if kind != 'entities' else el(x['id'])}", "", f"_{h['generated']}_", "",
             f"- {h['status']}: {STATUS[lang].get(x.get('status'), x.get('status'))}", f"- {h['source']}: {source_text(x, lang)}"]
        if kind == "events":
            L.append(f"- {h['when']}: {x.get('start')} ~ {x.get('end') or '…'}")
        if kind == "actions":
            L.append(f"- {h['owner']}: {label(x.get('owner'), lang)}")
        if x.get("entities"):
            L.append(f"- {h['entities']}: " + ", ".join(elink(e) for e in x["entities"]))
        if x.get("metrics"):
            L.append(f"- {h['metrics']}: " + ", ".join(mlink(m) for m in x["metrics"] if m in ws.metrics))
        if kind == "entities":
            for r in w.get("relations", []):
                if r["subject"] == x["id"]:
                    L.append(f"- {r['predicate']} → {elink(r['object'])}")
                elif r["object"] == x["id"]:
                    L.append(f"- ← {r['predicate']} {elink(r['subject'])}")
            for k in ("mechanisms", "events", "actions"):
                for y in w.get(k, []):
                    if x["id"] in y.get("entities", []):
                        L.append(f"- {h[k]}: {_link(y['id'], _fn(y['id']))}")
        (root / "world" / _fn(x["id"])).write_text("\n".join(L) + "\n", encoding="utf-8")

    for kind in ("entities", "mechanisms", "events", "actions"):
        for x in w.get(kind, []):
            entry_page(x, kind)

    R = [f"# {h['rules']}", "", f"_{h['generated']}_", "", f"## {h['params']}", ""]
    R += [f"- `{k}` = {v.get('value')} ({source_text(v, lang)})" for k, v in ws.params.items()]
    R += ["", f"## {h['tables']}", ""]
    for t in ws.rules.get("tables", []):
        R += [f"### `{t['id']}`", "", label(t.get("question"), lang) if t.get("question") else "", ""]
        R += [f"{i + 1}. {r.get('when') or '—'} → {r['then']}" for i, r in enumerate(t["rows"])] + [""]
    (root / "rules.md").write_text("\n".join(R), encoding="utf-8")

    ns = ws.model.get("north_star")
    I = [f"# {h['index']}", "", f"_{h['generated']}_", ""]
    if ns:
        I += [f"**{h['north_star']}**: {_link(ml(ns), f'metrics/{_fn(ns)}')}", ""]
    I += [f"## {h['metrics']}", ""] + [f"- {_link(ml(m), f'metrics/{_fn(m)}')}" for m in ws.metrics]
    for kind in ("entities", "mechanisms", "events", "actions"):
        items = w.get(kind, [])
        if items:
            I += ["", f"## {h[kind]}", ""]
            I += [f"- {_link(el(x['id']) if kind == 'entities' else x['id'], 'world/' + _fn(x['id']))}" for x in items]
    I += ["", _link(h["rules"], "rules.md"), ""]
    (root / "index.md").write_text("\n".join(I), encoding="utf-8")


__all__ = ["build", "SOURCE_KINDS"]
