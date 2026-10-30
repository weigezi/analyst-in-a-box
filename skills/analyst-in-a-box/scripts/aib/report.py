"""Write the analysis for a person: conclusion first, then the breakdown, then why, then who acts.

Every number comes from the run state; nothing here does arithmetic beyond formatting.
Charts use the Okabe-Ito colour-blind-safe palette (M. Okabe & K. Ito, 2008, "Color Universal Design").
"""

from __future__ import annotations

from pathlib import Path

from .explain import World, entry_text
from .workspace import label

T = {
    "zh": {
        "conclusion": "结论", "unusual": "算不算异常", "breakdown": "拆解", "why": "为什么", "who": "谁该做什么",
        "confirm": "待你确认", "appendix": "附：这次用了什么", "segment": "分组", "base": "基期", "cur": "本期",
        "delta": "变化", "share": "占变化", "structure": "结构", "rate": "指标", "interaction": "交叉",
        "mix": "结构差异", "performance": "表现差异", "unmatched": "只在一边有", "factor": "因子",
        "contribution": "贡献", "vs": "对比", "main_from": "主要来自", "of_change": "占变化的",
        "larger_structure": "结构主导：变化主要来自各组占比变了，而不是各组自己的水平变了。",
        "larger_rate": "指标主导：变化主要来自各组自己的水平变了，而不是占比变了。",
        "larger_mix": "结构差异主导：两边卖的组合不一样。", "larger_performance": "表现差异主导：同一组在两边长得不一样。",
        "spread": "这一刀切下去变化分散在各组，没有单点，停在这一层。", "drill": "单点集中，往下钻：",
        "qualify_scope": "这一节看的是整体{m}，不是两边的差。",
        "unusual_low": "和自己过去 {n} 期比，这一期明显偏低（稳健 z 值 {z}，低于门槛 {t}）。",
        "unusual_high": "和自己过去 {n} 期比，这一期明显偏高（稳健 z 值 {z}，高于门槛 {t}）。",
        "within": "和自己过去 {n} 期比，这一期在通常范围内（稳健 z 值 {z}）。",
        "no_history": "历史太短，判断不了这一期算不算异常。",
        "market_own": "同期大盘 {mg}，按大盘应变化 {mp}，实际变化 {d}；自己的部分 {op}，占 {os}。下滑是自己的问题，往内部拆。",
        "market_market": "同期大盘 {mg}，按大盘应变化 {mp}，实际变化 {d}；大部分是跟着大盘走的（占 {ms}）。",
        "calendar": "注意：两期的节假日对不齐（{items}），同比会被日历放大或压低。",
        "mechanism": "机制", "event": "事件", "hypothesis": "推测", "supported": "推测，已过三道检查",
        "timing_only": "推测，只有时间对得上，未证实", "not_supported": "推测，时间都对不上",
        "timing": "时间", "slice": "影响的那一块", "size": "量级", "evidence": "证据",
        "overlap": "重叠 {n} 天", "slice_text": "占变化 {v}（门槛 {t}）", "size_text": "事件那几天占这一块变化的 {v}（门槛 {t}）",
        "refute": "推翻条件：剔除事件那几天后这一块仍然同样下滑，这个推测就不成立。",
        "gap": "数据上看到「{seg}」的变化，原因待你确认。直接告诉我原因，我会记下来，下次不再问。",
        "status_confirmed": "已确认", "status_proposed": "待确认", "source": "出处", "owner": "负责人",
        "no_action": "还没有登记可做的动作。", "coverage": "需要业务解释的地方：{e}/{n} 处有记录可引（覆盖率 {p}）。",
        "definitions": "口径版本", "decisions": "命中的规则", "checks": "交付前自检", "pass": "通过", "fail": "未通过",
        "blocked": "⚠️ 交付前自检没通过，以下结论不能用：", "you_may_not_know": "你可能还不知道",
        "gap_a_b": "{a} 同比 {ga}，{b} 同比 {gb}，差 {gap}。", "horizontal": "按公式拆",
        "rate_change": "从 {b} 到 {c}（{d}）。", "amount_change": "比基期 {g}（{b} → {c}）。",
        "main_share": "主要来自 **{seg}**：{v}，占全部变化的 {p}。",
        "main_over": "主要来自 **{seg}**：{v}，单它一项就比总变化（{total}）还大，其他各组合计 {rest}，抵掉了一部分。",
        "main_abs": "主要来自 **{seg}**：{v}，占全部变动幅度的 {p}。",
        "market_own2": "同期大盘 {mg}，照大盘走本该 {mp}；实际 {d}。差出来的 {op} 是自己的，往内部拆。",
        "market_market2": "同期大盘 {mg}，照大盘走本该 {mp}；实际 {d}，大部分是跟着大盘走的。",
        "size_text2": "事件那几天的变化 {e}，是这一块全部变化 {all} 的 {v}（门槛 {t}）",
        "size_note": "超过 100% 说明其余几天这一块在涨。",
        "confirm_external": "「{what}」目前是推测（{st}）。你确认后我会把它标成已确认。",
        "confirm_proposed": "「{what}」还没确认。",
    },
    "en": {
        "conclusion": "Conclusion", "unusual": "Is it unusual?", "breakdown": "Breakdown", "why": "Why", "who": "Who should act",
        "confirm": "Waiting for you", "appendix": "Appendix: what this run used", "segment": "Segment", "base": "Base",
        "cur": "Current", "delta": "Change", "share": "Share of change", "structure": "Structure", "rate": "Rate",
        "interaction": "Interaction", "mix": "Mix", "performance": "Performance", "unmatched": "One side only",
        "factor": "Factor", "contribution": "Contribution", "vs": "vs", "main_from": "Mainly from", "of_change": "of the change",
        "larger_structure": "Structure-led: the change comes mainly from the mix of groups, not from each group's own level.",
        "larger_rate": "Rate-led: the change comes mainly from each group's own level, not from the mix.",
        "larger_mix": "Mix-led: the two sides sell a different mix.", "larger_performance": "Performance-led: the same group grew differently on the two sides.",
        "spread": "This cut spreads the change across groups; no single point, so the analysis stops here.",
        "drill": "Single point; drilling into: ",
        "qualify_scope": "This section is about {m} as a whole, not the gap between the two sides.",
        "unusual_low": "Against its own last {n} periods this one is clearly low (robust z {z}, below the threshold {t}).",
        "unusual_high": "Against its own last {n} periods this one is clearly high (robust z {z}, above the threshold {t}).",
        "within": "Against its own last {n} periods this one is within the usual range (robust z {z}).",
        "no_history": "Not enough history to say whether this period is unusual.",
        "market_own": "The market moved {mg}; following the market we would have changed by {mp}, we actually changed by {d}. Our own part is {op} ({os}). It is our own problem; break it down internally.",
        "market_market": "The market moved {mg}; following the market we would have changed by {mp}, we actually changed by {d}. Most of it moved with the market ({ms}).",
        "calendar": "Note: the two periods hold different holidays ({items}); year-on-year figures are distorted by the calendar.",
        "mechanism": "Mechanism", "event": "Event", "hypothesis": "Hypothesis", "supported": "Hypothesis, passed all three checks",
        "timing_only": "Hypothesis, timing matches only, not proven", "not_supported": "Hypothesis, timing does not match",
        "timing": "Timing", "slice": "Affected slice", "size": "Size", "evidence": "Evidence",
        "overlap": "{n} days overlap", "slice_text": "{v} of the change (threshold {t})", "size_text": "{v} of the slice's change falls on the event's days (threshold {t})",
        "refute": "Refuted if, without the event's days, this slice still falls just as much.",
        "gap": "The data shows a change in \"{seg}\"; the reason is waiting for you. Tell me the reason and I will record it and not ask again.",
        "status_confirmed": "confirmed", "status_proposed": "to confirm", "source": "source", "owner": "owner",
        "no_action": "No actions recorded yet.", "coverage": "Places that need a business explanation: {e} of {n} can cite a record (coverage {p}).",
        "definitions": "Definitions version", "decisions": "Rules that fired", "checks": "Pre-delivery checks", "pass": "pass", "fail": "FAIL",
        "blocked": "⚠️ Pre-delivery checks failed; do not use the conclusions below:", "you_may_not_know": "You may not know",
        "gap_a_b": "{a} {ga} year on year, {b} {gb}; a gap of {gap}.", "horizontal": "By formula",
        "rate_change": " moved from {b} to {c} ({d}).", "amount_change": " {g} vs base ({b} → {c}).",
        "main_share": "Mainly from **{seg}**: {v}, {p} of the total change.",
        "main_over": "Mainly from **{seg}**: {v}. This one item is larger than the total change ({total}); the other groups added {rest} and offset part of it.",
        "main_abs": "Mainly from **{seg}**: {v}, {p} of all movement.",
        "market_own2": "The market moved {mg}; following it we would have changed by {mp}. We actually changed by {d}. The difference, {op}, is our own; break it down internally.",
        "market_market2": "The market moved {mg}; following it we would have changed by {mp}. We actually changed by {d}; most of it moved with the market.",
        "size_text2": "the change on the event's days, {e}, is {v} of the slice's whole change {all} (threshold {t})",
        "size_note": "above 100% means the slice grew on the other days.",
        "confirm_external": "\"{what}\" is a hypothesis ({st}). Confirm it and I will mark it confirmed.",
        "confirm_proposed": "\"{what}\" is not confirmed yet.",
    },
}


SOURCE_KINDS = {
    "zh": {"user": "用户原话", "document": "文档", "data": "数据推出", "system_record": "系统记录",
           "general_knowledge": "通用常识", "demo_setting": "演示设定", "formula": "公式"},
    "en": {"user": "user's words", "document": "document", "data": "inferred from data", "system_record": "system record",
           "general_knowledge": "general knowledge", "demo_setting": "demo setting", "formula": "formula"},
}
PUNCT = {"zh": {"colon": "：", "comma": "，", "semi": "；", "open": "（", "close": "）", "stop": "。"},
         "en": {"colon": ": ", "comma": ", ", "semi": "; ", "open": " (", "close": ")", "stop": "."}}


def fmt(v, unit=None, signed=False):
    if v is None:
        return "—"
    if unit == "ratio":
        return f"{v:+.2%}" if signed else f"{v:.2%}"
    if unit == "count":
        return f"{v:+,.0f}" if signed else f"{v:,.0f}"
    if abs(v) >= 1000:
        return f"{v:+,.0f}" if signed else f"{v:,.0f}"
    return f"{v:+,.2f}" if signed else f"{v:,.2f}"


def pct(v, signed=True):
    return "—" if v is None else (f"{v:+.1%}" if signed else f"{v:.1%}")


def pp(v):
    return "—" if v is None else f"{v * 100:+.1f}pp"


def seg_label(ws, world, dim, key, lang):
    eid = world.entity_for(dim, key)
    return label(world.entities[eid].get("label"), lang) if eid else str(key)


def slot_label(ws, world, slot, lang):
    parts = [*slot["path"], [slot["dimension"], slot["value"]]]
    return " → ".join(f"{label(ws.dimensions[d].get('label', d), lang)}={seg_label(ws, world, d, v, lang)}" for d, v in parts)


def bar_svg(rows, title=""):
    """rows: [(label, value, share)] -> a horizontal bar chart of contributions, as an SVG string."""
    w, h, left, pad = 640, 26, 170, 8
    height = pad * 2 + h * len(rows) + (22 if title else 0)
    top = pad + (22 if title else 0)
    mx = max((abs(v) for _, v, _ in rows), default=1) or 1
    has_neg, has_pos = any(v < 0 for _, v, _ in rows), any(v > 0 for _, v, _ in rows)
    span = w - left - 70
    zero = left + (span / 2 if has_neg and has_pos else span if has_neg else 0)
    scale = (span / 2 if has_neg and has_pos else span) / mx
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" font-family="sans-serif" font-size="12">']
    if title:
        out.append(f'<text x="{pad}" y="16" font-weight="bold">{_esc(title)}</text>')
    for i, (lab, v, sh) in enumerate(rows):
        y = top + i * h
        x0, x1 = sorted((zero, zero + v * scale))
        color = "#0072B2" if v >= 0 else "#D55E00"
        out.append(f'<text x="{left - 6}" y="{y + 17}" text-anchor="end">{_esc(lab)}</text>')
        out.append(f'<rect x="{x0:.1f}" y="{y + 5}" width="{max(x1 - x0, 1):.1f}" height="{h - 10}" fill="{color}"/>')
        tx = x1 + 4 if v >= 0 else x0 - 4
        out.append(f'<text x="{tx:.1f}" y="{y + 17}" text-anchor="{"start" if v >= 0 else "end"}">{_esc(pct(sh) if sh is not None else "")}</text>')
    out.append(f'<line x1="{zero:.1f}" y1="{top}" x2="{zero:.1f}" y2="{top + h * len(rows)}" stroke="#555"/>')
    out.append("</svg>")
    return "\n".join(out)


def _esc(x):
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def _cut_table(ws, world, cut, unit, lang):
    t, r = T[lang], cut["result"]
    op, d = r["operator"], cut["dimension"]
    sl = lambda k: seg_label(ws, world, d, k, lang)  # noqa: E731
    if op == "additive":
        return _table([t["segment"], t["base"], t["cur"], t["delta"], t["share"]],
                      [[sl(x["key"]), fmt(x["base"], unit), fmt(x["cur"], unit), fmt(x["delta"], unit, True), pct(x["share"])]
                       for x in r["segments"]])
    if op == "divisive":
        return _table([t["segment"], t["base"], t["cur"], t["structure"], t["rate"], t["interaction"], t["share"]],
                      [[sl(x["key"]), f'{fmt(x["rate_base"], unit)} ({x["weight_base"]:.0%})', f'{fmt(x["rate_cur"], unit)} ({x["weight_cur"]:.0%})',
                        fmt(x["structure"], unit, True), fmt(x["rate"], unit, True), fmt(x["interaction"], unit, True), pct(x["share"])]
                       for x in r["segments"]])
    if op == "second_order_sides":
        a, b = (seg_label(ws, world, cut["side_dimension"], v, lang) for v in cut["sides"])
        return _table([t["segment"], f"{a} %", f"{b} %", t["mix"], t["performance"], t["unmatched"], t["share"]],
                      [[sl(x["key"]), pct(x["growth_a"]), pct(x["growth_b"]), pp(x["mix"]), pp(x["performance"]), pp(x["unmatched"]), pct(x["share"])]
                       for x in r["segments"]])
    rows = []
    for x in r["segments"]:
        a, b = x.get("contrib_w1"), x.get("contrib_w2")
        rows.append([sl(x["key"]), pp(a) if a is not None else "", pp(b) if b is not None else "",
                     pp(x["change"]) if unit != "currency" or a is not None else fmt(x["change"], unit, True), pct(x["share"])])
    return _table([t["segment"], "w1", "w2", t["delta"], t["share"]], rows)


def _cut_value(cut):
    r = cut["result"]
    return {"additive": "delta", "divisive": "total"}.get(r["operator"], "total" if r["operator"].startswith("second_order_sides") else "change")


def find_entry(ws, eid):
    return next((x for k in ("events", "mechanisms", "actions") for x in ws.world.get(k, []) if x["id"] == eid), {})


def source_text(entry, lang):
    src = entry.get("source") or {}
    kind = SOURCE_KINDS[lang].get(src.get("kind"), src.get("kind", ""))
    return f"{kind} · {src['ref']}" if src.get("ref") else kind


def _cite_line(ws, c, lang, unit=None):
    t, p = T[lang], PUNCT[lang]
    entry = find_entry(ws, c["id"])
    when = f'{entry.get("start")}~{entry.get("end") or "…"} ' if c["kind"] == "event" else ""
    tag = t["mechanism"] if c["kind"] == "mechanism" else t["event"]
    if c.get("external"):
        tag = t[c["checks"]["status"]]
    status = t["status_confirmed"] if c["status"] == "confirmed" else t["status_proposed"]
    lines = [f'- **{tag}** `{c["id"]}`{p["colon"]}{when}{entry_text(entry, lang)}'
             f'{p["open"]}{t["source"]}{p["colon"]}{source_text(entry, lang)}{p["semi"]}{status}{p["close"]}']
    ck = c.get("checks") or {}
    if "slice" in ck:
        sz = ck["size"]
        size = t["size_text2"].format(e=fmt(sz["change_on_event_days"], unit, True), all=fmt(ck["slice"]["slice_delta"], unit, True),
                                      v=pct(sz["share_of_slice_change"], False), t=pct(sz["threshold"], False))
        if (sz["share_of_slice_change"] or 0) > 1:
            size += p["comma"] + t["size_note"]
        lines.append(f'  - {t["timing"]}{p["colon"]}{t["overlap"].format(n=ck["timing"]["overlap_days"])}')
        lines.append(f'  - {t["slice"]}{p["colon"]}{t["slice_text"].format(v=pct(ck["slice"]["share_of_change"], False), t=pct(ck["slice"]["threshold"], False))}')
        lines.append(f'  - {t["size"]}{p["colon"]}{size}')
        ev = ck.get("evidence")
        if ev:
            u = ev.get("unit") or ""
            lines.append(f'  - {t["evidence"]}{p["colon"]}{ev["source"]} {fmt(ev["mean_on_event_days"])}{u} {t["vs"]} {fmt(ev["mean_other_days"])}{u}')
        lines.append(f'  - {t["refute"]}')
    return lines


def _decision_text(d):
    return ", ".join(f"{k}={v}" for k, v in d["then"].items())


def render(ws, s, lang="zh", out_dir: Path | None = None) -> str:
    t, world, m = T[lang], World(ws), s["metric"]
    unit = ws.metrics[m].get("unit")
    mlab = label(ws.metrics[m].get("label", m), lang)
    q = s["qualify"]
    title = label(s["config"].get("question"), lang) if s["config"].get("question") else f"{mlab} {s['current'][0]}~{s['current'][1]}"
    L = [f"# {title}", ""]
    if s["blocked"]:
        L += [t["blocked"], *[f"- {c['check']}: {c['detail']}" for c in s["checks"] if not c["pass"]], ""]

    p = PUNCT[lang]
    L += [f"## {t['conclusion']}", ""]
    period = f"{s['current'][0]}~{s['current'][1]} {t['vs']} {s['base'][0]}~{s['base'][1]}"
    first = s["cuts"][0]["result"] if s["cuts"] else None
    head = f"**{mlab}**{p['open']}{period}{p['close']}"
    if s["order"] == "second_sides" and first:
        a, b = (seg_label(ws, world, s["cuts"][0]["side_dimension"], v, lang) for v in s["cuts"][0]["sides"])
        L.append(head + p["colon"] + t["gap_a_b"].format(a=a, b=b, ga=pct(first["growth_a"]), gb=pct(first["growth_b"]), gap=pp(first["gap"])))
    elif ws.metrics[m].get("kind") == "ratio":
        L.append(head + t["rate_change"].format(b=fmt(q["total_base"], unit), c=fmt(q["total_cur"], unit), d=fmt(q["total_cur"] - q["total_base"], unit, True)))
    else:
        g = q["total_cur"] / q["total_base"] - 1 if q["total_base"] else None
        L.append(head + t["amount_change"].format(g=pct(g), b=fmt(q["total_base"], unit), c=fmt(q["total_cur"], unit)))
    if first and first.get("larger_effect") in ("structure", "rate", "mix", "performance"):
        L += ["", t[f"larger_{first['larger_effect']}"]]
    if s["slots"]:
        top = s["slots"][0]
        cut = s["cuts"][top["cut"]]
        r = cut["result"]
        seg = next(x for x in r["segments"] if x["key"] == top["value"])
        val = seg[_cut_value(cut)]
        vtxt = fmt(val, unit, True) if r["operator"] in ("additive", "divisive") else pp(val)
        total = {"additive": "total_delta", "divisive": "rate_delta"}.get(r["operator"], "gap" if "sides" in r["operator"] else "growth_change")
        tot = r.get(total)
        sh = seg.get("share")
        segname = slot_label(ws, world, top, lang)
        if sh is not None and sh > 1 and r["operator"] in ("additive", "divisive"):
            L += ["", t["main_over"].format(seg=segname, v=vtxt, total=fmt(tot, unit, True), rest=fmt(tot - val, unit, True))]
        elif sh is not None and 0 <= sh <= 1:
            L += ["", t["main_share"].format(seg=segname, v=vtxt, p=pct(sh, False))]
        else:
            L += ["", t["main_abs"].format(seg=segname, v=vtxt, p=pct(r.get("top1_abs_share"), False))]
        solid = [c for c in top["citations"] if not c.get("external") or c["checks"]["status"] == "supported"]
        solid.sort(key=lambda c: c["kind"] != "event")
        if solid:
            L.append(f"> **{t['you_may_not_know']}**{p['colon']}{entry_text(find_entry(ws, solid[0]['id']), lang)}")
        elif top["status"] == "gap":
            L.append("> " + t["gap"].format(seg=segname))
    L.append("")

    L += [f"## {t['unusual']}", ""]
    if s["order"] != "first":
        L += [t["qualify_scope"].format(m=mlab), ""]
    v = (s.get("verdict_unusual") or {}).get("then", {}).get("verdict")
    z = q.get("robust_z")
    if z is None:
        L.append(t["no_history"])
    else:
        key = {"unusual_low": "unusual_low", "unusual_high": "unusual_high"}.get(v, "within")
        thr = ws.params.get("unusual_z_low" if key == "unusual_low" else "unusual_z", {}).get("value")
        L.append(t[key].format(n=q["history_n"], z=f"{z:.2f}", t=thr))
    if q.get("market_growth") is not None:
        mv = (s.get("verdict_market") or {}).get("then", {}).get("verdict")
        d = q["total_cur"] - q["total_base"]
        L.append("")
        L.append(t["market_own2" if mv == "own" else "market_market2"].format(
            mg=pct(q["market_growth"]), mp=fmt(q["market_part"], unit, True), d=fmt(d, unit, True),
            op=fmt(q["own_part"], unit, True), os=pct(q["own_share"], False), ms=pct(q["market_share"], False)))
    if q.get("holiday_misaligned"):
        items = p["comma"].join(f"{h.get('label_' + lang) or h['name']} {h['base_days']}→{h['current_days']}"
                                for h in q["calendar"]["holidays"] if h["difference"])
        L += ["", t["calendar"].format(items=items)]
    L.append("")

    L += [f"## {t['breakdown']}", ""]
    for h in s["horizontal"]:
        ident = next(i for i in ws.model.get("identities", []) if i["id"] == h["identity"])
        formula = f"{label(ws.metrics[ident['left']].get('label'), lang)} = " + \
                  " × ".join(label(ws.metrics[f].get("label"), lang) for f in ident["factors"])
        L += [f"**{t['horizontal']}**{p['colon']}{formula}", ""]
        L += _table([t["factor"], t["base"], t["cur"], t["contribution"], t["share"]],
                    [[label(ws.metrics[f["factor"]].get("label", f["factor"]), lang), fmt(f["base"], ws.metrics[f["factor"]].get("unit")),
                      fmt(f["cur"], ws.metrics[f["factor"]].get("unit")), fmt(f["contribution"], unit, True), pct(f["share"])]
                     for f in h["factors"]])
        L.append("")
    for i, cut in enumerate(s["cuts"]):
        dl = label(ws.dimensions[cut["dimension"]].get("label", cut["dimension"]), lang)
        scope = " / ".join(f"{label(ws.dimensions[k].get('label', k), lang)}={seg_label(ws, world, k, val, lang)}" for k, val in cut["filters"].items())
        L += [f"### {i + 1}. {dl}" + (f"{p['open']}{scope}{p['close']}" if scope else ""), ""]
        L += _cut_table(ws, world, cut, unit, lang)
        act = cut["decision"]["then"].get("action")
        L += ["", (t["drill"] + f"**{seg_label(ws, world, cut['dimension'], cut['result']['top1_key'], lang)}**") if act == "drill" else t["spread"]]
        if out_dir is not None:
            vf = _cut_value(cut)
            rows = [(seg_label(ws, world, cut["dimension"], x["key"], lang), x[vf], x.get("share")) for x in cut["result"]["segments"]]
            charts = Path(out_dir) / "charts"
            charts.mkdir(parents=True, exist_ok=True)
            name = f"cut{i + 1}.{lang}.svg"
            (charts / name).write_text(bar_svg(rows, dl), encoding="utf-8")
            L += ["", f"![{dl}](charts/{name})"]
        L.append("")

    L += [f"## {t['why']}", ""]
    for slot in s["slots"]:
        L += [f"**{slot_label(ws, world, slot, lang)}**", ""]
        if slot["status"] == "gap":
            L.append("- " + t["gap"].format(seg=slot_label(ws, world, slot, lang)))
        for c in slot["citations"]:
            L += _cite_line(ws, c, lang, unit)
        L.append("")
    if not s["slots"]:
        L += [t["spread"], ""]

    L += [f"## {t['who']}", ""]
    acts = {a["id"]: a for a in ws.world.get("actions", [])}
    L += [f"- **{label(acts[a]['owner'], lang)}**{p['colon']}{label(acts[a]['action'], lang)}" for a in s["actions"]] or [t["no_action"]]
    L.append("")

    if s["gaps"] or s["to_confirm"]:
        L += [f"## {t['confirm']}", ""]
        for g in s["gaps"]:
            slot = next(x for x in s["slots"] if x["id"] == g["slot"])
            L.append("- " + t["gap"].format(seg=slot_label(ws, world, slot, lang)))
        seen = set()
        for c in s["to_confirm"]:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            what = entry_text(find_entry(ws, c["id"]), lang)
            slot = next(x for x in s["slots"] if x["id"] == c["slot"])
            cite = next(x for x in slot["citations"] if x["id"] == c["id"])
            if cite.get("external"):
                L.append("- " + t["confirm_external"].format(what=what, st=t[cite["checks"]["status"]]))
            else:
                L.append("- " + t["confirm_proposed"].format(what=what))
        L.append("")

    cov = s["coverage"]
    L += [f"## {t['appendix']}", ""]
    if cov["slots"]:
        L += [t["coverage"].format(e=cov["explained"], n=cov["slots"], p=pct(cov["share"], False)), ""]
    L.append(f"- {t['definitions']}{p['colon']}" + p["comma"].join(f"{k} `{v}`" for k, v in s["definitions"].items() if v))
    L.append(f"- {t['decisions']}{p['colon']}" + p["semi"].join(f"`{d['table']}` row {d['row']} → {_decision_text(d)}" for d in s["decisions"]))
    L.append(f"- {t['checks']}{p['colon']}" + p["semi"].join(f"{c['check']} {t['pass'] if c['pass'] else t['fail']}" for c in s["checks"]))
    L.append("")
    return "\n".join(L)
