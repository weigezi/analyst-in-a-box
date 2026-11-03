"""Wording and page contexts for the business knowledge graph, intake, learning and architecture pages.

    pages(data, lang) -> [{"path", "template", "context"}]   (data = sitedata.collect())

Numbers and structure come from graphdata (which reads the run states in data["cases"] and the demo workspace);
this module only turns them into words, in both languages, section for section.
"""

from __future__ import annotations

import html
import json
import re

import graphdata as G
from aib.report import SOURCE_KINDS

MINUS = "\u2212"
DIST = G.SITE / "dist"


# ---------------------------------------------------------------- formatting (same conventions as the report pages)

def _m(s: str) -> str:
    return s.replace("-", MINUS)


def money(v, lang, signed=True, dp=None):
    if v is None:
        return "—"
    dp = (0 if abs(v) >= 1000 else 2) if dp is None else dp
    sign = ("+" if v > 0 else MINUS if v < 0 else "") if signed else (MINUS if v < 0 else "")
    n = f"{abs(v):,.{dp}f}"
    return f"{sign}{n} 元" if lang == "zh" else f"{sign}¥{n}"


def amount(v, unit, lang, signed=True):
    if unit == "currency":
        return money(v, lang, signed)
    if unit == "ratio":
        return _m(f"{v * 100:+.2f}" if signed else f"{v * 100:.2f}") + (" 个百分点" if lang == "zh" else " points")
    if unit == "growth_points":
        return _m(f"{v * 100:+.1f}" if signed else f"{v * 100:.1f}") + (" 个百分点" if lang == "zh" else " points")
    return _m(f"{v:+,.0f}" if signed else f"{v:,.0f}")


def pct(v, signed=False):
    return _m(f"{v:+.0%}" if signed else f"{v:.0%}")


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def day(s, lang, year=True):
    y, m, d = (int(x) for x in str(s)[:10].split("-"))
    if lang == "zh":
        return f"{y} 年 {m} 月 {d} 日" if year else f"{m} 月 {d} 日"
    return f"{MONTHS[m - 1]} {d}, {y}" if year else f"{MONTHS[m - 1]} {d}"


def span(a, b, lang):
    if a == b:
        return day(a, lang)
    ya, yb = str(a)[:4], str(b)[:4]
    if lang == "zh":
        if ya == yb and str(a)[5:7] == str(b)[5:7]:
            return f"{ya} 年 {int(str(a)[5:7])} 月 {int(str(a)[8:10])} 日至 {int(str(b)[8:10])} 日"
        return f"{day(a, lang)} 至 {day(b, lang, year=ya != yb)}"
    if ya == yb and str(a)[5:7] == str(b)[5:7]:
        return f"{MONTHS[int(str(a)[5:7]) - 1]} {int(str(a)[8:10])} to {int(str(b)[8:10])}, {ya}"
    return f"{day(a, lang, year=ya != yb)} to {day(b, lang)}"


def month_tick(s, lang):
    y, m, _ = (int(x) for x in s.split("-"))
    return f"{m} 月" if lang == "zh" else MONTHS[m - 1]


def join(items, lang):
    items = list(items)
    if lang == "zh":
        return "、".join(items)
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------------------------------------------------------------- words

W = {
    "zh": {
        "title": "业务知识图谱",
        "h1": ["指标树决定往哪拆，", "业务世界描述决定为什么、该谁去做。"],
        "lede": "这一页是演示店「花果篮」的全部底子。左边那张按公式把毛利一层层拆到底，每个指标下面写着能按什么切、先切哪个；"
                "另一张记着这家店的世界：哪些渠道、品类、城市，发生过什么事，背后是什么道理，出了问题找谁。"
                "选一道题，看它在这两张图上走过哪些地方。",
        "views": {"tree": "指标树", "world": "业务世界描述"},
        "pick": "按题目高亮", "none": "不选题，看全图", "clear_btn": "清除",
        "path_h": "这道题走过的路", "report": "看这道题的完整报告",
        "hint_tree": "点一个指标，看它是什么、怎么切、出处在哪。",
        "hint_world": "点一条记录，看出处、状态，以及什么数据出现会推翻它。",
        "lanes": {"event": "事件", "mechanism": "机制", "entity": "实体（按维度分组）", "metric": "指标", "action": "动作和负责人"},
        "lane_short": {"event": "事件", "mechanism": "机制", "entity": "实体", "metric": "指标", "action": "动作和负责人"},
        "kind": {"event": "事件", "mechanism": "机制", "entity": "实体", "metric": "指标", "action": "动作"},
        "legend": {"lit": "这道题走过的", "scope": "题目限定的范围", "proposed": "待确认", "belongs": "属于"},
        "detail": {"what": "是什么", "source": "出处", "status": "状态", "refute": "什么会推翻它", "cuts": "能切的维度和先后",
                   "close": "关闭", "ents": "涉及", "metrics": "影响的指标", "owner": "负责人", "when": "时间", "children": "下面有"},
        "status": {"confirmed": "已确认", "proposed": "待确认", None: "未标"},
        "sum": "{col}加总", "count": "{col}去重计数", "ratio": "= {a} ÷ {b}", "ident": "= {fs}",
        "rule": {"first_fixed": "先后：第一刀由维护者定，往下每层按打分选",
                 "scored": "先后：没有人定，每层按打分选",
                 "each": "先后：由维护者定，每个维度各切一次",
                 "fixed": "先后：由维护者定，不打分"},
        "chip_scored": "可切",
        "group": {"belongs": "{a} · 下属{b}", "via": "{a} · 外部", "loose": "外部"},
        "affects": "影响：{m}", "from": "{d}起",
        "ok_mobile": "手机上改成按泳道排的列表，内容和桌面版相同。",
        "steps": {"scope": "定题", "formula": "按公式拆", "pvm": "量、价、结构", "cut": "按{d}切", "why": "为什么", "act": "该谁去做"},
    },
    "en": {
        "title": "Business knowledge graph",
        "h1": ["The metric tree decides where to break a number down;", "the business world description decides why, and who acts."],
        "lede": "This page is everything the skill knows about the demo shop, Bloom & Basket. One view breaks gross profit down by "
                "formula, level by level, and lists under each metric what it can be cut by and in which order. The other records "
                "the shop's world: its channels, categories and cities, what happened, the reasons behind it, and who to go to. "
                "Pick a question to see where it went on both.",
        "views": {"tree": "Metric tree", "world": "Business world description"},
        "pick": "Highlight a question", "none": "No question, whole graph", "clear_btn": "Clear",
        "path_h": "The path this question took", "report": "Read this question's full report",
        "hint_tree": "Click a metric to see what it is, how it is cut, and where that comes from.",
        "hint_world": "Click a record to see its source, its status, and what data would overturn it.",
        "lanes": {"event": "Events", "mechanism": "Mechanisms", "entity": "Entities (by dimension)", "metric": "Metrics", "action": "Actions and owners"},
        "lane_short": {"event": "Events", "mechanism": "Mechanisms", "entity": "Entities", "metric": "Metrics", "action": "Actions and owners"},
        "kind": {"event": "Event", "mechanism": "Mechanism", "entity": "Entity", "metric": "Metric", "action": "Action"},
        "legend": {"lit": "On this question's path", "scope": "Limited by the question", "proposed": "To confirm", "belongs": "Belongs to"},
        "detail": {"what": "What it is", "source": "Source", "status": "Status", "refute": "What would overturn it", "cuts": "Dimensions and order",
                   "close": "Close", "ents": "About", "metrics": "Affects", "owner": "Owner", "when": "When", "children": "Contains"},
        "status": {"confirmed": "Confirmed", "proposed": "To confirm", None: "Not marked"},
        "sum": "Sum of {col}", "count": "Distinct count of {col}", "ratio": "= {a} ÷ {b}", "ident": "= {fs}",
        "rule": {"first_fixed": "Order: the maintainer sets the first cut; each layer below is picked by score",
                 "scored": "Order: nobody set one; each layer is picked by score",
                 "each": "Order: set by the maintainer; every dimension is cut once",
                 "fixed": "Order: set by the maintainer, no scoring"},
        "chip_scored": "can cut",
        "group": {"belongs": "{a} · {b} within", "via": "{a} · outside", "loose": "Outside"},
        "affects": "Affects: {m}", "from": "from {d}",
        "ok_mobile": "On a phone this becomes a list by lane, with the same content as on desktop.",
        "steps": {"scope": "The question", "formula": "By formula", "pvm": "Volume, price, mix", "cut": "Cut by {d}", "why": "Why", "act": "Who acts"},
    },
}
AGG = {"zh": {"sum": "逐条记录加总", "count_distinct": "数不重复的个数"},
       "en": {"sum": "added up record by record", "count_distinct": "a count of distinct records"}}

# What would overturn an entry. Each line restates a rule the engine applies; where it applies none, the line says so.
REFUTE = {
    "zh": {
        "identity": "推翻不了：这是按定义成立的等式（{r}），不靠数据。数据只决定每一项各占多少。",
        "ratio": "推翻不了：这是定义。要改，就是改口径。",
        "leaf": "推翻不了：它就是数据的加总。数据本身有问题（订单重复、整天缺数）时，报告会停发。",
        "value": "这是数据里出现的值，没有要推翻的判断；数据里不再出现，它就不再出现在拆解里。",
        "belongs": "「{a}属于{b}」是从数据推出的：每个{da}只出现在一个{db}下。只要有一个{da}同时出现在两个{db}下，这条就不成立。",
        "outside": "这是一条手工登记的记录，不从数据推出；用户纠正时改。",
        "mechanism": "没有单独的推翻条件。它说的是两期都成立的道理，所以只能解释「为什么结构一变数字就跟着变」，"
                     "解释不了这次为什么变；引用时会被这样标出来。",
        "event_in": "没有单独的推翻条件，取自系统记录。引用时会检查它在两期里生效的天数是否不同，相同就不算这次变化的原因。",
        "event_out": "外部事件只当推测，要过三道检查才进结论：时间对得上、影响的那一块对得上、量级说得过去。"
                     "剔除事件那几天后这一块仍然同样下滑，这个推测就不成立。",
        "action": "这是建议去做的事，不是判断，没有要推翻的。",
        "order": "这是维护者的选择，不是从数据推出的。",
    },
    "en": {
        "identity": "Cannot be overturned: it holds by definition ({r}), not by the data. The data only decides how much each part contributes.",
        "ratio": "Cannot be overturned: it is a definition. Changing it means changing what the number means.",
        "leaf": "Cannot be overturned: it is a sum of the data. When the data itself is wrong (orders loaded twice, whole days missing), the report is withheld.",
        "value": "A value that appears in the data; there is no judgment to overturn. If it stops appearing, it drops out of the breakdown.",
        "belongs": "\u201c{a} belongs to {b}\u201d is inferred from the data: every {da} appears under one {db} only. A single {da} appearing under two {db}s would break it.",
        "outside": "A record entered by hand, not inferred from the data; changed when the user corrects it.",
        "mechanism": "No separate condition. It describes something true in both periods, so it can explain why a shift in mix moves the "
                     "number, but not why the number moved this time; it is labelled that way when cited.",
        "event_in": "No separate condition; it comes from a system record. When cited, the engine checks whether it was in force on a different "
                    "share of days in the two periods; if not, it does not count as a cause of this change.",
        "event_out": "An outside event is only a guess until it passes three checks: the timing matches, the slice it hits matches, and the size "
                     "is plausible. If this slice still falls just as much without the event's days, the guess fails.",
        "action": "A suggested step, not a judgment; there is nothing to overturn.",
        "order": "The maintainer's choice, not inferred from the data.",
    },
}

EXPLAINS = {
    "zh": {"change": "能解释这次的变化", "why_mix_matters": "只解释了结构为什么会影响数字，解释不了结构为什么变",
           "cannot_explain_change": "两期都成立，解释不了这次的变化", "term_mismatch": "变了，但它说的是另一项",
           None: ""},
    "en": {"change": "explains this change", "why_mix_matters": "explains why the mix matters, not why the mix shifted",
           "cannot_explain_change": "true in both periods, so it cannot explain this change",
           "term_mismatch": "it changed, but it is about the other part", None: ""},
}
CHECKS = {"zh": {"supported": "已过三道检查", "timing_only": "只有时间对得上，未证实", "not_supported": "时间都对不上"},
          "en": {"supported": "passed the three checks", "timing_only": "only the timing matches; not shown",
                 "not_supported": "even the timing does not match"}}
REASON = {
    "zh": {"single_point": "集中在这一组，接着往下拆", "single_point_inside_a_quiet_total": "总数没出正常范围，但这一组特别突出，接着往下拆",
           "single_point_without_history": "集中在这一组（没有历史可比），接着往下拆", "spread_or_noise": "各组都在变，没有哪一组特别突出，拆到这里为止",
           "whole_number_within_usual_range": "整体在正常波动内，不再往下拆", "top_group_too_small": "最大的一组也太小，不再往下拆"},
    "en": {"single_point": "the change sits in this group, so it breaks that group down next",
           "single_point_inside_a_quiet_total": "the total is within its usual range, but this group stands out, so it breaks that group down next",
           "single_point_without_history": "the change sits in this group (no history to compare), so it breaks that group down next",
           "spread_or_noise": "every group moved and none stands out, so it stops here",
           "whole_number_within_usual_range": "the whole number is within its usual range, so it goes no further",
           "top_group_too_small": "even the largest group is too small, so it goes no further"},
}


def src_text(src, lang):
    kind = (src or {}).get("kind")
    t = SOURCE_KINDS[lang].get(kind, kind or ("未标" if lang == "zh" else "not marked"))
    ref = ((src or {}).get("label") or {}).get(lang) or (src or {}).get("ref")
    return f"{t}（{ref}）" if ref and lang == "zh" else f"{t} ({ref})" if ref else t
# ---------------------------------------------------------------- the graph page: words for each card

def _ml(g, m, lang):
    return g["tree"]["nodes"][m]["label"][lang]


def _dl(g, d, lang):
    return g["dimensions"][d][lang]


def _el(g, eid, lang):
    return g["world"]["entities"][eid]["label"][lang]


def sub_text(g, n, lang):
    w = W[lang]
    if n["identity"]:
        return w["ident"].format(fs=" × ".join(_ml(g, f, lang) for f in n["identity"]["factors"]))
    if n["ratio"]:
        return w["ratio"].format(a=_ml(g, n["ratio"]["numerator"], lang), b=_ml(g, n["ratio"]["denominator"], lang))
    spec = g["ws"].measures[g["ws"].metrics[n["metric"]]["measure"]]
    t = AGG[lang].get(spec["agg"], spec["agg"])
    return t[0].upper() + t[1:] if lang == "en" else t


def rule_text(n, lang):
    return W[lang]["rule"][n["dims"]["rule"]]


def chip_text(g, d, lang):
    lab = _dl(g, d["dim"], lang)
    return f"{d['rank']} {lab}" if d["rank"] else lab


def metric_detail(g, n, lang):
    w, D, R = W[lang], W[lang]["detail"], REFUTE[lang]
    rows = [(D["what"], sub_text(g, n, lang))]
    dims = n["dims"]
    order = join((chip_text(g, d, lang) for d in dims["dims"]), lang)
    cuts = f"{order}。{rule_text(n, lang)}。" if lang == "zh" else f"{order}. {rule_text(n, lang)}."
    if dims["left_out"]:
        lo = join((_dl(g, d, lang) for d in dims["left_out"]), lang)
        cuts += f"{lo}也能切，但不在维护者给的顺序里，默认不切。" if lang == "zh" else f" {lo} could also be cut, but is not in the maintainer's order, so it is not cut by default."
    if dims["source"]:
        cuts += (f"顺序出处：{src_text({'kind': dims['source']}, lang)}，{w['status'][dims['status']]}。" if lang == "zh"
                 else f" Source of the order: {src_text({'kind': dims['source']}, lang)}, {w['status'][dims['status']].lower()}.")
    rows.append((D["cuts"], cuts))
    if n["identity"]:
        i = n["identity"]
        rows += [(D["source"], src_text({"kind": i["source"]}, lang)), (D["status"], w["status"][i["status"]])]
        if i["definitional"]:
            rows.append((D["refute"], R["identity"].format(r=f"{_ml(g, n['metric'], lang)} {sub_text(g, n, lang)}")))
        else:
            # an identity that is not a definition is a modelling choice; the engine does not test it against the data
            rows.append((D["refute"], R["order"]))
    elif n["ratio"]:
        rows += [(D["source"], src_text({"kind": "formula"}, lang)), (D["refute"], R["ratio"])]
    else:
        rows += [(D["source"], src_text({"kind": "data"}, lang)), (D["refute"], R["leaf"])]
    return {"title": n["label"][lang], "kind": w["kind"]["metric"], "rows": rows}


def entity_detail(g, e, lang):
    w, D, R = W[lang], W[lang]["detail"], REFUTE[lang]
    rels = g["world"]["relations"]
    up = [r for r in rels if r["subject"] == e["entity"] and r["predicate"] == "belongs_to"]
    down = [r for r in rels if r["object"] == e["entity"] and r["predicate"] == "belongs_to"]
    via = [r for r in rels if r["object"] == e["entity"] and r["predicate"] != "belongs_to"]
    if e["dimension"]:
        what = (f"{_dl(g, e['dimension'], lang)}的一个值。" if lang == "zh" else f"A value of {_dl(g, e['dimension'], lang).lower()}.")
    else:
        what = "数据之外的东西。" if lang == "zh" else "Something outside the data."
    for r in up:
        what += f"属于{_el(g, r['object'], lang)}。" if lang == "zh" else f" Belongs to {_el(g, r['object'], lang)}."
    for r in via:
        what += (f"{_el(g, r['subject'], lang)}经由它卖货。" if lang == "zh" else f" {_el(g, r['subject'], lang)} sells through it.")
    rows = [(D["what"], what)]
    if down:
        rows.append((D["children"], join((_el(g, r["subject"], lang) for r in down), lang)))
    rows += [(D["source"], src_text(e["source"], lang)), (D["status"], w["status"][e["status"]])]
    if up or down:
        r = (up or down)[0]
        da, db = r["dims"]
        rows.append((D["refute"], R["belongs"].format(a=_el(g, r["subject"], lang), b=_el(g, r["object"], lang),
                                                       da=_dl(g, da, lang), db=_dl(g, db, lang))))
    elif e["external"]:
        rows.append((D["refute"], R["outside"]))
    else:
        rows.append((D["refute"], R["value"]))
    return {"title": e["label"][lang], "kind": w["kind"]["entity"], "rows": rows}


def entry_detail(g, x, lang):
    w, D, R = W[lang], W[lang]["detail"], REFUTE[lang]
    ents = join((_el(g, e, lang) for e in x["entities"]), lang)
    rows = [(D["what"], x["text"][lang])]
    if x["kind"] == "event":
        rows.append((D["when"], span(x["start"], x["end"], lang)))
    if x["kind"] == "action":
        rows.append((D["owner"], x["owner"][lang]))
    rows.append((D["ents"], ents))
    if x["metrics"]:
        rows.append((D["metrics"], join((_ml(g, m, lang) for m in x["metrics"]), lang)))
    rows += [(D["source"], src_text(x["source"], lang)), (D["status"], w["status"][x["status"]])]
    # the record's own condition when it has one (world.yaml refuted_by), otherwise the rule the engine applies
    rows.append((D["refute"], x["refuted_by"][lang] if x.get("refuted_by") else R["action"] if x["kind"] == "action"
                 else R["mechanism"] if x["kind"] == "mechanism" else R["event_out"] if x["external"] else R["event_in"]))
    return {"title": x["text"][lang] if x["kind"] != "action" else x["owner"][lang], "kind": w["kind"][x["kind"]], "rows": rows,
            "proposed": x["status"] == "proposed"}


def card_lines(g, x, lang):
    """(text, font px, line height) per line of a world card; graphdata measures these, the template prints them."""
    w = W[lang]
    if x["kind"] == "event":
        return [(span(x["start"], x["end"], lang), 12, 18), (x["text"][lang], 13, 20)]
    if x["kind"] == "mechanism":
        return [(x["text"][lang], 13, 20), (w["affects"].format(m=join((_ml(g, m, lang) for m in x["metrics"]), lang)), 12, 18)]
    return [(x["owner"][lang], 12, 18), (x["text"][lang], 13, 20)]


def group_text(g, grp, lang):
    w = W[lang]["group"]
    if grp["dim"] is None:
        return w["loose"]
    a = _dl(g, grp["dim"], lang)
    if grp["child"]:
        return w["belongs"].format(a=a, b=_dl(g, grp["child"], lang).lower() if lang == "en" else _dl(g, grp["child"], lang))
    if grp["right"]:
        return w["via"].format(a=a)
    return a
# ---------------------------------------------------------------- the graph page: one question's path in words

def _e(s):
    return html.escape(str(s), quote=False)


_CJK = "\u4e00-\u9fff"


def zh_space(s: str) -> str:
    """A space between Chinese and Latin letters or digits (house style); tags start with '<', so markup is untouched."""
    s = re.sub(rf"(?<=[{_CJK}])(?=[A-Za-z0-9+\u2212¥])", " ", s)
    return re.sub(rf"(?<=[A-Za-z0-9%])(?=[{_CJK}])", " ", s)


def slot_text(s: str, lang: str) -> str:
    """The engine's slot label reads 'dimension=value → dimension=value'; on the page it reads 'dimension: value'."""
    return s.replace("=", "：" if lang == "zh" else ": ")


def path_steps(g, p, lang):
    """[(title, html)] for one question. Labels are escaped; amounts are wrapped in <b>."""
    w, zh = W[lang], lang == "zh"
    L = p["labels"]
    val = lambda d, v: L["values"].get(d, {}).get(str(v), {}).get(lang, str(v))  # noqa: E731
    ml = lambda m: _e(_ml(g, m, lang))  # noqa: E731
    dl = lambda d: _e(_dl(g, d, lang))  # noqa: E731
    unit = g["ws"].metrics[p["metric"]].get("unit")
    out = []
    for st in p["steps"]:
        k = st["kind"]
        if k == "scope":
            where = "".join((f"，只看{_e(val(d, v))}" if zh else f", {_e(val(d, v))} only") for d, v in st["filters"].items())
            if st["sides"]:
                a, b = (_e(val(st["sides"]["dimension"], v)) for v in st["sides"]["values"])
                t = (f"{ml(st['metric'])}：{a}对比{b}，{_e(span(*st['current'], lang))}，各自对比去年同期。" if zh else
                     f"{ml(st['metric'])}: {a} against {b}, {_e(span(*st['current'], lang))}, each against the same days a year earlier.")
            else:
                t = (f"{ml(st['metric'])}{where}；{_e(span(*st['current'], lang))}，对比去年同期（{_e(span(*st['base'], lang))}）。" if zh else
                     f"{ml(st['metric'])}{where}; {_e(span(*st['current'], lang))}, against the same days a year earlier ({_e(span(*st['base'], lang))}).")
            out.append((w["steps"]["scope"], t))
        elif k == "formula":
            parts = join((f"{ml(x['metric'])} <b>{_e(amount(x['value'], unit, lang))}</b>" for x in st["leaves"]), lang)
            t = (f"{ml(st['metric'])}变化 <b>{_e(amount(st['total'], unit, lang))}</b>，按公式拆成 {parts}；动得最多的是{ml(st['dominant'])}。" if zh else
                 f"{ml(st['metric'])} moved <b>{_e(amount(st['total'], unit, lang))}</b>; by formula that is {parts}. "
                 f"{ml(st['dominant'])} moved it most.")
            out.append((w["steps"]["formula"], t))
        elif k == "pvm":
            big = {"volume": ("卖得多", "selling more"), "price": ("卖得贵", "charging more"), "mix": ("结构", "the mix")}[st["larger"]][0 if zh else 1]
            t = (f"按{dl(st['dimension'])}看，{ml(st['quantity'])}{_e(pct(st['quantity_growth'], True))}。"
                 f"卖得多 <b>{_e(amount(st['volume'], unit, lang))}</b>，卖得贵 <b>{_e(amount(st['price'], unit, lang))}</b>，"
                 f"贵的卖得多一些（结构）<b>{_e(amount(st['mix'], unit, lang))}</b>；{big}占大头。" if zh else
                 f"By {dl(st['dimension']).lower()}, {ml(st['quantity']).lower()} {_e(pct(st['quantity_growth'], True))}. "
                 f"Selling more <b>{_e(amount(st['volume'], unit, lang))}</b>, charging more <b>{_e(amount(st['price'], unit, lang))}</b>, "
                 f"a richer mix <b>{_e(amount(st['mix'], unit, lang))}</b>; {big} is the larger part.")
            out.append((w["steps"]["pvm"], t))
        elif k == "cut":
            within = join((_e(val(d, v)) for d, v in st["within"]), lang)
            pre = (f"在{within}里面，" if zh else f"Within {within}, ") if within else ("" if zh else "")
            top = _e(val(st["dimension"], st["top"]))
            if st["sides"]:
                sd = st["sides"]
                a, b = (_e(val(sd["dimension"], v)) for v in (sd["a"], sd["b"]))
                gp = lambda v: _e(amount(v, "growth_points", lang))  # noqa: E731
                what = (f"{a}同比 {_e(pct(sd['growth_a'], True))}，{b} {_e(pct(sd['growth_b'], True))}，增速差 <b>{gp(sd['gap'])}</b>"
                        f"（1 个百分点就是两边同比增速差 1%）。其中两边卖的品类结构不同贡献 {gp(sd['mix'])}，"
                        f"同一品类两边长得不一样贡献 {gp(sd['performance'])}；差得最多的是{top}，<b>{gp(st['amount'])}</b>" if zh else
                        f"{a} grew {_e(pct(sd['growth_a'], True))} year on year and {b} {_e(pct(sd['growth_b'], True))}, a gap of <b>{gp(sd['gap'])}</b> "
                        f"(one point is a 1% difference in the two growth rates). Selling a different mix accounts for {gp(sd['mix'])}, "
                        f"the same category growing differently on each side for {gp(sd['performance'])}; the category that differs most is {top}, <b>{gp(st['amount'])}</b>")
            else:
                what = (f"变化最大的是{top}，<b>{_e(amount(st['amount'], st['unit'], lang))}</b>" if zh else
                        f"the largest change is {top}, <b>{_e(amount(st['amount'], st['unit'], lang))}</b>")
            if not zh and not pre:
                what = what[0].upper() + what[1:]
            reason = REASON[lang].get(st["reason"], "")
            t = f"{pre}{what}；{_e(reason)}。" if zh else f"{pre}{what}; {_e(reason)}."
            out.append((w["steps"]["cut"].format(d=_dl(g, st["dimension"], lang) if zh else _dl(g, st["dimension"], lang).lower()), t))
        elif k == "why":
            if not st["slots"]:
                out.append((w["steps"]["why"], "变化分散、没有哪一组突出，就不硬找原因。" if zh else "The change is spread and no group stands out, so it does not force a cause."))
                continue
            lines = []
            for sl in st["slots"]:
                head = _e(slot_text(L["slots"][sl["slot"]][lang], lang))
                cites = []
                for c in sl["citations"]:
                    e = p["entries"][c["id"]]
                    bit = f"「{_e(e['text'][lang])}」" if zh else f"\u201c{_e(e['text'][lang])}\u201d"
                    notes = [EXPLAINS[lang].get(c["explains"], "")]
                    if c["external"] and c["checks"]:
                        notes.append(CHECKS[lang].get(c["checks"], ""))
                    elif c["status"] == "proposed":
                        notes.append(w["status"]["proposed"])
                    notes = [x for x in notes if x]
                    cites.append(bit + ((f"（{_e('；'.join(notes))}）" if zh else f" ({_e('; '.join(notes))})") if notes else ""))
                state = ("原因待你确认" if sl["status"] == "gap" else "有记录可引") if zh else ("reason waiting for you" if sl["status"] == "gap" else "a record explains it")
                body = ("，".join(cites) if zh else "; ".join(cites)) or ("没有可引的记录" if zh else "no record to cite")
                lines.append(f"<b>{head}</b>：{state}。引用 {body}。" if zh else f"<b>{head}</b>: {state}. Cites {body}.")
            out.append((w["steps"]["why"], "<br>".join(lines)))
        elif k == "act":
            if not st["actions"]:
                t = "还没有登记可做的动作。" if zh else "No action is recorded yet."
            else:
                t = "<br>".join(f"<b>{_e(p['entries'][a['id']]['owner'][lang])}</b>：{_e(p['entries'][a['id']]['action'][lang])}" if zh else
                                f"<b>{_e(p['entries'][a['id']]['owner'][lang])}</b>: {_e(p['entries'][a['id']]['action'][lang])}" for a in st["actions"])
            out.append((w["steps"]["act"], t))
    return [(zh_space(a), zh_space(b)) for a, b in out] if zh else out


def chip_notes(g, p, lang):
    """A short note on each lit dimension chip: the value it was limited to, or the group it drilled into."""
    L = p["labels"]
    val = lambda d, v: L["values"].get(d, {}).get(str(v), {}).get(lang, str(v))  # noqa: E731
    out = {}
    for st in p["steps"]:
        if st["kind"] == "scope":
            for d, v in st["filters"].items():
                out[f"c:{p['metric']}:{d}"] = "= " + val(d, v)
        if st["kind"] == "cut":
            note = ("→ " if st["drill"] else "· ") + val(st["dimension"], st["top"])
            key = st["chip"]
            out[key] = (out[key] + " " + note) if key in out and note not in out[key] else note
    return out
# ---------------------------------------------------------------- page contexts

_CACHE: dict = {}


def _graph(data):
    key = id(data)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = G.graph(data["cases"])
    return _CACHE[key]


def _signed_class(v):
    return "neg" if v is not None and v < 0 else "pos" if v is not None and v > 0 else ""


def graph_context(data, lang) -> dict:
    g = _graph(data)
    w = W[lang]
    tree, world = g["tree"], g["world"]
    T = G.tree_layout(tree, lang, lambda n, lg: sub_text(g, n, lg), rule_text, lambda n, d, lg: chip_text(g, d, lg))
    Wl = G.world_layout(world, g["ws"], tree, data["cases"], lang, lambda grp, lg: group_text(g, grp, lg),
                        lambda row, lg: card_lines(g, row, lg))
    details = {}
    tcards = []
    for m in tree["order"]:
        n = tree["nodes"][m]
        details[n["id"]] = metric_detail(g, n, lang)
        tcards.append({"id": n["id"], "title": n["label"][lang], "sub": sub_text(g, n, lang), "rule": rule_text(n, lang),
                       "ns": m == tree["north_star"], "box": T["boxes"][n["id"]], "depth": n["depth"],
                       "chips": [{"id": f"c:{m}:{d['dim']}", "label": _dl(g, d["dim"], lang), "rank": d["rank"]} for d in n["dims"]["dims"]]})
    # each lane is an ordered list (group headings among the cards), so on a phone it reads top to bottom
    lanes = {k: [] for k in ("event", "mechanism", "entity", "metric", "action")}
    for e in world["entities"].values():
        details[e["id"]] = entity_detail(g, e, lang)
        b = Wl["boxes"][e["id"]]
        lanes["entity"].append({"type": "card", "id": e["id"], "pill": True, "external": e["external"], "box": b,
                                "lines": [(e["label"][lang], 13, 20)], "sub": b["x"] > Wl["lanes"][2]["x"], "key": (b["seq"],)})
    for h in Wl["groups"]:
        first = min((b["seq"] for b in Wl["boxes"].values() if b["x"] >= h["x"] and b["y"] >= h["y"] and b["x"] < h["x"] + h["w"]), default=0)
        lanes["entity"].append({"type": "head", "text": h["text"], "box": {"x": h["x"], "y": h["y"], "w": h["w"]}, "key": (first - 0.5,)})
    for bucket, kind in (("events", "event"), ("mechanisms", "mechanism"), ("actions", "action")):
        for x in world[bucket]:
            details[x["id"]] = entry_detail(g, x, lang)
            b = Wl["boxes"][x["id"]]
            lanes[kind].append({"type": "card", "id": x["id"], "lines": card_lines(g, x, lang), "box": b,
                                "proposed": x["status"] == "proposed", "external": x["external"], "key": (b["y"], 0)})
    for m in tree["order"]:
        n = tree["nodes"][m]
        b = Wl["boxes"][n["id"]]
        lanes["metric"].append({"type": "card", "id": n["id"], "pill": True, "box": b, "lines": [(n["label"][lang], 13, 20)], "key": (b["y"], 0)})
    for k in lanes:
        lanes[k].sort(key=lambda it: it["key"])
        for it in lanes[k]:                    # the build's Jinja env is strict: every card carries every flag
            for f in ("pill", "sub", "proposed", "external"):
                it.setdefault(f, False)
    if lang == "zh":
        for d in details.values():
            d["rows"] = [(a, zh_space(b)) for a, b in d["rows"]]
            d["title"] = zh_space(d["title"])
        for items in lanes.values():
            for it in items:
                if it["type"] == "card":
                    it["lines"] = [(zh_space(t), px, lh) for t, px, lh in it["lines"]]
    order = list(data["cases"])
    cases, steps = {}, {}
    for k in order:
        p = g["paths"][k]
        steps[k] = path_steps(g, p, lang)
        cases[k] = {"tree": p["tree"], "chips": p["chips"], "scope": p["scope_chips"], "world": p["world"],
                    "notes": chip_notes(g, p, lang),
                    "values": {nid: {"t": amount(v, p["unit"], lang), "c": _signed_class(v)} for nid, v in p["values"].items()},
                    "window": Wl["axis"]["windows"][k]}
    edges_tree = [{"id": e["id"], "from": e["from"], "to": e["to"]} for e in T["edges"] if not e.get("op")]
    edges_world = [{"id": e["id"], "from": e["from"], "to": e["to"]} for e in Wl["edges"]]
    payload = {"lang": lang, "details": details, "cases": cases, "edges": {"tree": edges_tree, "world": edges_world},
               "ui": {"close": w["detail"]["close"], "proposed": w["status"]["proposed"]}}
    return {
        "w": w, "page_title": w["title"], "description": ("" if lang == "zh" else " ").join(w["h1"]),
        # report pages sit in the same language root (build.py NAV_REPORTS); build.py renders them before these pages,
        # so a report it did not build this time (a partial build) gets no link instead of a broken one
        "questions": [{"id": k, "text": data["cases"][k]["question"][lang],
                       "report": f"reports/{k}.html" if (DIST / ("" if lang == "zh" else "en") / "reports" / f"{k}.html").exists() else None}
                      for k in order],
        "tree": {"w": T["w"], "h": T["h"], "cards": tcards, "edges": [e for e in T["edges"] if not e.get("op")],
                 "ops": [e for e in T["edges"] if e.get("op")]},
        "world": {"w": Wl["w"], "h": Wl["h"], "edges": Wl["edges"],
                  "lanes": [{**l, "text": w["lanes"][l["kind"]], "entries": lanes[l["kind"]]} for l in Wl["lanes"]],
                  "axis": {**Wl["axis"], "ticks": [{**t, "text": month_tick(t["date"], lang)} for t in Wl["axis"]["ticks"]]}},
        "steps": steps, "payload": json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"),
    }


# ---------------------------------------------------------------- intake page
IW = {
    "zh": {
        "title": "采集", "colon": "：",
        "h1": ["放进几张表，", "答几道选择题，", "就拿到第一份报告。"],
        "lede": "演示店「花果篮」的 {n} 张表加一份周报。脚本认出主表、表和表怎么对上，AI 从周报里提出原因；"
                "你只判断它的理解对不对，纠正几处。",
        "s_tables": "一、9 张表各长什么样", "s_tables_sub": "每张表只露前 3 行。标签是脚本认的，店主改过的另注明。",
        "rows": "{n:,} 行", "kinds": {"main": "主表", "lookup": "查找表", "business": "业务数据", "events": "事件记录", "calendar": "节假日日历",
                                    "series": "外部连续数据", "market": "行业大盘", "ignore": "不用"},
        "changed": "店主改成了「{k}」",
        "s_q": "二、脚本提的选择题，和店主的回答",
        "s_q_sub": "共 {asked} 道，店主答了 {answered} 道，没答的不生效。下面挑出 {n} 道。",
        "suggest": "建议", "answer": "店主选了", "evidence": "证据", "overrode": "改了建议",
        "coverage": "{m:,} / {n:,} 行对得上（{p}）",
        "q_all": "看全部题目和店主的回答",
        "yes": "是", "no": "否", "internal": "自己做的事", "external": "外面发生的事", "none": "都不是",
        "s_doc": "三、周报里的原句，和它记成了什么",
        "s_doc_sub": "AI 读周报、提出候选，脚本只核对引用是否逐字出现在周报里。收下 {a} 条，拒收 {r} 条。",
        "doc_src": "周报原文（被引用的这一份）", "doc_tr": "",
        "rec_as": "记成", "rec_kind": {"event": "事件", "mechanism": "机制"}, "to_confirm": "来自文档，待确认",
        "s_formed": "四、形成了什么", "s_formed_sub": "四类来源各有多少。",
        "c_data": "机器从数据推出，再经选择题确认", "c_q": "选择题（问了 / 答了）", "c_doc": "从文档抽出、待确认（收下 / 拒收）", "c_person": "只有人能补、现在空着",
        "tree_h": "形成的指标树", "tree_note": "名字是脚本起的，改名要人来。",
        "dims_h": "能切的维度", "world_h": "形成的业务世界描述",
        "world_items": "{e} 个维度值、{r} 条「属于」关系（城市属于大区）、{j} 张查找表并进主表、{o} 份外部数据。",
        "events_h": "从事件记录里读出的事（系统记录，待确认）",
        "person_h": "只有人能补的", "graph_link": "业务知识图谱页画的是演示店手写的那一份，可以对着看",
        "s_gaps": "五、和手写的那一份没对上的地方", "s_gaps_sub": "同一家店，手写一份、自动形成一份，逐项对照。每一处为什么没对上，见形成报告第八节。",
        "cmp_head": ["项目", "手写", "自动形成", "对得上吗"],
        "s_runs": "六、拿形成的工作区答题", "s_runs_sub": "演示店的题目和采集完马上出的第一份报告，都用自动形成的工作区来答。",
        "run_head": ["问题", "主因", "引用的记录", "状态"], "first": "采集完马上出的第一份",
        "q_text": "{m}，{span}{f}，对比去年同期", "status": {"explained": "已解释", "hypothesis": "推测，待确认", "gap": "原因待补"},
        "cite_src": {"document": "文档", "system_record": "系统记录"}, "cite_checks": "对着降雨量过了三道检查",
        "first_h": "第一份报告，开头这样说",
        "first_body": "{m}（{cur}，对比 {base}）少了 <b>{d}</b>（{g}），低于过去 {n} 期里的每一期，算异常。"
                      "主要在 {dim} 的 <code>{key}</code>：<b>{v}</b>。去掉这一块，其余部分 {rc}，平时是 {ru}，和平时差不多。"
                      "从 {onset} 开始，和周报里「{ev}」是同一天；这条来自文档，还没人确认，所以只算推测。",
        "first_off": "反过来涨的有 {items}，抵掉了一部分。",
    },
    "en": {
        "title": "Bringing data in", "colon": ": ",
        "h1": ["Put in a few tables,", "answer a few multiple-choice questions,", "and get a first report."],
        "lede": "The demo shop Bloom & Basket: {n} tables and a weekly report. The scripts find the main table and how the tables join; "
                "the AI proposes causes from the report. You only judge whether its understanding is right, and correct a few spots.",
        "s_tables": "1. What the 9 tables look like",
        "s_tables_sub": "The first 3 rows of each. The scripts chose the label; where the owner changed it, that is noted.",
        "rows": "{n:,} rows", "kinds": {"main": "main table", "lookup": "lookup", "business": "business data", "events": "event records",
                                     "calendar": "holiday calendar", "series": "outside series", "market": "market benchmark", "ignore": "not used"},
        "changed": "the owner changed it to \u201c{k}\u201d",
        "s_q": "2. The questions the scripts ask, and the owner's answers",
        "s_q_sub": "{asked} in all; the owner answered {answered}, and an unanswered one has no effect. {n} of them below.",
        "suggest": "Suggested", "answer": "The owner chose", "evidence": "Evidence", "overrode": "changed the suggestion",
        "coverage": "{m:,} / {n:,} rows match ({p})",
        "q_all": "All questions and the owner's answers",
        "yes": "yes", "no": "no", "internal": "something we did", "external": "something outside", "none": "neither",
        "s_doc": "3. Sentences from the weekly report, and what they became",
        "s_doc_sub": "The AI reads the report and proposes candidates; the scripts only check that each quote appears in it word for word. {a} accepted, {r} refused.",
        "doc_src": "The report as quoted (the shop writes in Chinese)", "doc_tr": "English translation, for reading",
        "rec_as": "Recorded as", "rec_kind": {"event": "event", "mechanism": "mechanism"}, "to_confirm": "from a document, to confirm",
        "s_formed": "4. What was formed", "s_formed_sub": "How much came from each of the four sources.",
        "c_data": "Inferred from the data, then confirmed in a question", "c_q": "Questions (asked / answered)",
        "c_doc": "From a document, to confirm (accepted / refused)", "c_person": "Only a person can add; empty so far",
        "tree_h": "The metric tree it formed",
        "tree_note": "The scripts named them; a person renames them.",
        "dims_h": "Dimensions it can cut by", "world_h": "The business world description it formed",
        "world_items": "{e} dimension values, {r} \u201cbelongs to\u201d relations (city belongs to region), {j} lookup tables joined to the main table, {o} sources of outside data.",
        "events_h": "Events read from the event tables (system records, to confirm)",
        "person_h": "What only a person can add", "graph_link": "The business knowledge graph page draws the demo shop's hand-written one, to set side by side",
        "s_gaps": "5. Where it differs from the hand-written one",
        "s_gaps_sub": "The same shop, written by hand once and formed automatically once, compared part by part. Why each part differs is in section 8 of the formation report.",
        "cmp_head": ["Part", "Hand-written", "Formed", "Match"],
        "s_runs": "6. Asking the formed workspace",
        "s_runs_sub": "The demo shop's questions and the first report right after intake are all answered from the formed workspace.",
        "run_head": ["Question", "Main cause", "Record cited", "Status"], "first": "the first report, straight after intake",
        "q_text": "{m}, {span}{f}, against the same days a year earlier",
        "status": {"explained": "explained", "hypothesis": "a guess, to confirm", "gap": "reason missing"},
        "cite_src": {"document": "document", "system_record": "system record"}, "cite_checks": "passed the three checks against the rainfall",
        "first_h": "How the first report opens",
        "first_body": "{m} ({cur}, against {base}) was down <b>{d}</b> ({g}), below every one of the last {n} periods: unusual. "
                      "Most of it is in {dim} <code>{key}</code>: <b>{v}</b>. Without it the rest changed {rc}, against a usual {ru}: about as usual. "
                      "It started on {onset}, the same day as \u201c{ev}\u201d in the weekly report; that comes from a document nobody has confirmed, so it is only a guess.",
        "first_off": " Moving the other way: {items}, which offset part of it.",
    },
}
FEATURED = ["main_table", "kind:market", "link:weather.region>cities.region", "belongs:city>region", "north_star"]
FORMATION_REPORT = "https://github.com/weigezi/analyst-in-a-box/blob/main/demo/intake/formation"
def _opt(q, v, lang):
    """(words, is_code) for one option value of a question: its label when it has one, otherwise the value itself
    (a table or column name of the user's own data, shown as code)."""
    for o in q.get("options", []):
        if isinstance(o, dict) and str(o["value"]) == str(v):
            return o["label"], False
    if isinstance(v, list):
        return ", ".join(map(str, v)), True
    if str(v) in ("yes", "no", "internal", "external", "none"):
        return IW[lang][str(v)], False
    return str(v), True


def _ask(q):
    """The question as init wrote it, without the bracketed evidence (shown on its own line)."""
    s = q["ask"]
    if q.get("evidence"):
        s = s.replace(f"（{q['evidence']}）", "").replace(f" ({q['evidence']})", "")
    return s


def _plain(s):
    """Python list brackets in init's evidence become plain names: ['city'] -> city."""
    return re.sub(r"\[([^\]]*)\]", lambda m: m.group(1).replace("'", ""), s)


def _paras(md):
    """[(heading, [paragraphs])] of the weekly report, without its title, language link and note on the translation."""
    out, cur = [], None
    for ln in md.split("\n"):
        if ln.startswith("## "):
            cur = (ln[3:].strip(), [])
            out.append(cur)
        elif ln.strip() and cur is not None:
            cur[1].append(ln.strip())
    return out


def cited_sections(md, quotes, zh_md=None):
    """_paras(md) cut down to the sections the Chinese report quotes from. The English translation wraps its lines
    differently, so the two are matched by section (heading order), not by paragraph; zh_md says which sections those are."""
    ref = _paras(zh_md or md)
    own = _paras(md)
    assert len(ref) == len(own), "the two weekly reports no longer have the same sections"
    return [(hd, ps) for (_, zps), (hd, ps) in zip(ref, own) if any(q in z for z in zps for _, q in quotes)]


def _mark(text, quotes):
    h = _e(text)
    for i, q in quotes:
        h = h.replace(_e(q), f'<mark class="ik-mark"><span class="ik-n">{i}</span>{_e(q)}</mark>')
    return h


def _sgn(v):
    return _m(f"{v:+.1%}")


def intake_context(data, lang) -> dict:
    d = G.intake()
    w, zh = IW[lang], lang == "zh"
    sp = zh_space if zh else (lambda s: s)
    tables = [{**t, "label": w["kinds"].get(t["suggested"], t["suggested"]),
               "changed": w["changed"].format(k=w["kinds"].get(t["answered"], t["answered"])) if t["answered"] != t["suggested"] else None,
               "rows_text": w["rows"].format(n=t["rows"])} for t in d["tables"]]
    qs = {q["id"]: q for q in d["questions"][lang]}
    links = {f"link:{x['left_table']}.{x['left_column']}>{x['right_table']}.{x['right_column']}": x for x in d["links"]}

    def card(q):
        a, sug = d["answers"].get(q["id"]), q.get("suggested")
        lk = links.get(q["id"])
        ev = w["coverage"].format(m=lk["matched_rows"], n=lk["rows"], p=pct(lk["coverage"])) if lk else (_plain(q["evidence"]) if q.get("evidence") else None)
        at, acode = _opt(q, a, lang) if a is not None else ("—", False)
        st, scode = _opt(q, sug, lang) if sug is not None else (None, False)
        ask = _ask(q)
        if lk:   # the coverage is the evidence; init also puts it in the question
            ask = re.split(r"[0-9,]+/[0-9,]+ (行|rows)", ask)[0].rstrip()
        return {"ask": sp(ask), "evidence": ev, "suggest": st, "suggest_code": scode, "answer": at, "answer_code": acode,
                "overrode": sug is not None and a is not None and str(a) != str(sug)}
    featured = [card(qs[k]) for k in FEATURED if k in qs]

    accepted = [p for p in d["proposals"] if p["accepted"]]
    quotes = [(i + 1, p["quote"]) for i, p in enumerate(accepted)]
    recs = [{"n": i + 1, "kind": w["rec_kind"][p["type"]], "text": p["text"][lang]} for i, p in enumerate(accepted)]
    ml = lambda m: d["metric_labels"].get(m, {}).get(lang, m)  # noqa: E731
    mc = lambda m: {"t": ml(m), "code": ml(m) == m}  # noqa: E731
    M = d["machine"]
    person = join((d["person_text"][lang][x["reason"]][0] for x in d["person"]), lang)
    # formation_report's English part names are its own keys; one of them reads as a field name on a page
    en_part = {"identities": "formulas", "confirmed priorities": "confirmed cut orders"}
    part = lambda k: en_part.get(k, d["part_text"][lang][k]) if lang == "en" else d["part_text"][lang][k]  # noqa: E731
    cmp = [{"part": part(r["part"]), "store": r["store"], "formed": r["formed"],
            "match": d["match_text"][lang][r["match"]], "ok": r["match"] == "yes"} for r in d["compare"]]
    runs = []
    for r in d["runs"]:
        f = "".join((f"，只看 {v}" if zh else f", {v} only") for v in r["filters"].values())
        q = w["q_text"].format(m=ml(r["metric"]) if ml(r["metric"]) != r["metric"] else f"\x00{r['metric']}\x01", span=span(*r["current"], lang), f=f)
        cites = [{"text": c["text"][lang], "src": w["cite_src"].get(c["source"], c["source"]),
                  "checks": w["cite_checks"] if c["checks"] == "supported" else None} for c in r["citations"]]
        q = _e(sp(q)).replace("\x00", "<code>").replace("\x01", "</code>")
        path = [(M["dimension_labels"].get(dim, {}).get(lang, dim), v) for dim, v in r["path"]]
        runs.append({"q": q, "first": r["first"], "path": path, "status": w["status"].get(r["status"], "—"),
                     "explained": r["status"] == "explained", "cites": cites})
    fr = d["first_report"]
    ev = next((c["text"][lang] for r in d["runs"] if r["first"] for c in r["citations"]), "")
    first = w["first_body"].format(
        m=(f"<code>{_e(fr['metric'])}</code>" if ml(fr["metric"]) == fr["metric"] else _e(ml(fr["metric"]))), cur=_e(span(*fr["current"], lang)), base=_e(span(*fr["base"], lang)),
        d=_e(money(fr["total_cur"] - fr["total_base"], lang)), g=_e(_sgn(fr["total_cur"] / fr["total_base"] - 1)),
        n=fr["history_n"], dim=_e(M["dimension_labels"].get(fr["main"]["dimension"], {}).get(lang, fr["main"]["dimension"])),
        key=_e(fr["main"]["key"]), v=_e(money(fr["main"]["value"], lang)),
        rc=_e(_sgn(fr["rest_change"])), ru=_e(_sgn(fr["rest_usual"])), onset=_e(day(fr["onset"], lang)), ev=_e(ev))
    if fr["offsets"]:
        first += w["first_off"].format(items=_e(join((f"{M['dimension_labels'].get(o.get('dimension'), {}).get(lang, '')} {o['key']} {money(o['value'], lang)}".strip()
                                  for o in fr["offsets"]), lang)))
    return {
        "w": w, "page_title": w["title"], "description": ("" if zh else " ").join(w["h1"]), "lede": w["lede"].format(n=len(tables)),
        "tables": tables, "featured": featured,
        "q_sub": w["s_q_sub"].format(asked=d["counts"]["asked"], answered=d["counts"]["answered"], n=len(featured)),
        "q_all": w["q_all"], "q_all_href": FORMATION_REPORT + (".zh.md" if zh else ".md"),
        "doc_sub": w["s_doc_sub"].format(a=d["counts"]["accepted"], r=d["counts"]["refused"]),
        "doc": [(hd, [_mark(x, quotes) for x in ps]) for hd, ps in cited_sections(d["docs"]["zh"], quotes)],
        "doc_tr": [(hd, [_e(x) for x in ps]) for hd, ps in cited_sections(d["docs"]["en"], quotes, d["docs"]["zh"])] if not zh else None, "recs": recs,
        "counts": [(w["c_data"], str(d["counts"]["from_data"])), (w["c_q"], f"{d['counts']['asked']} / {d['counts']['answered']}"),
                   (w["c_doc"], f"{d['counts']['accepted']} / {d['counts']['refused']}"), (w["c_person"], str(d["counts"]["needs_a_person"]))],
        "tree": [{"left": mc(i["left"]), "factors": [mc(f) for f in i["factors"]]} for i in M["identities"]],
        "dims": [M["dimension_labels"][x][lang] for x in M["dimensions"]],
        "world_items": w["world_items"].format(e=M["entities"], r=M["relations"], j=len(M["joins"]), o=len(M["outside"])),
        "table_events": [{"text": e["text"][lang], "when": span(e["start"], e["end"], lang)} for e in M["table_events"]],
        "person": person, "cmp": cmp,
        "note_east": re.sub(r"(这是 0\.1 起对外部事件的规则，没有改。| That is the 0\.1 rule for outside events, kept\.)", "", d["note_east"][lang]),
        "runs": runs, "first_body": zh_space(first) if zh else first,
    }


# ---------------------------------------------------------------- learning page
LW = {
    "zh": {
        "title": "它怎么学", "colon": "：",
        "h1": ["纠正一次，", "这道题下次会引用这条记录；", "忘掉它，回归题会抓到。"],
        "lede": "同一道题「{q}」跑两次，中间用户说了一句话。下面三栏：两份报告里讲原因的那一段原样摘出，中间是用户的原话。",
        "s_cmp": "纠正前、用户原话、纠正后", "before": "纠正前", "said": "用户原话", "after": "纠正后",
        "excerpt": "报告原文摘录：去掉了记录的内部编号，维度和值之间的等号换成了冒号，其余一字未改。",
        "rec_h": "记成了一条事件", "rec_when": "生效时间", "rec_src": "出处", "rec_status": "状态",
        "share_h": "这一处为什么变了，有没有记录能解释", "share_b": "纠正前", "share_a": "纠正后",
        "share_why": "这次下跌是真的：新记下的是 10 月 1 日起的活动，两期里生效的天数不同，所以能解释今年和去年为什么不一样。"
                     "原来那条「果篮最便宜」两期都成立，只能说明占比一变客单价就跟着变，解释不了占比为什么变，所以纠正前不算。",
        "s_forget": "忘掉一条，会被回归题抓到", "forget_sub": "每次纠正都会变成一道回归题：这道题、这一处，必须引到这条记录。",
        "f_steps": ["记住之后，跑回归题", "把这条记录从工作区删掉，再跑一次"],
        "f_pass": "通过", "f_fail": "没通过", "f_expect": "要求：在「{slot}」这一处引到「{rec}」。",
        "f_got_pass": "实际引到了：{cites}。", "f_got_fail": "实际只引到：{cites}。",
        "f_caught": "回归题没通过：忘了会被发现，不会悄悄退回去。",
        "s_not": "它没做到的", "not": [
            "一次纠正只记一条记录；一句话里有两件事，要分开说两次。",
            "它不会自己去核实这个活动是不是真的办过：用户说了就照记，出处写「用户原话」。",
            "回归题只保证这一处还引得到这条记录；别的题会不会因此答偏，要靠其余的回归题。"],
        "ids": "存在哪里（给维护者看）", "ids_rows": [("记录", "where"), ("回归题", "case"), ("用户原话", "log"), ("纠正日期", "date")],
    },
    "en": {
        "title": "How it learns", "colon": ": ",
        "h1": ["Corrected once,", "this question cites that record next time;", "drop it and a regression case catches you."],
        "lede": "The same question, \u201c{q}\u201d, run twice; in between, the user said one sentence. Below: the paragraph about the cause "
                "from each report, taken as it is, with the user's words in the middle.",
        "s_cmp": "Before, the user's words, after", "before": "Before", "said": "The user said", "after": "After",
        "excerpt": "Taken from the reports: record ids are left out and the equals sign between a dimension and its value is written as a colon; nothing else is changed.",
        "rec_h": "Recorded as an event", "rec_when": "In force", "rec_src": "Source", "rec_status": "Status",
        "share_h": "Places needing a business explanation that can cite a record", "share_b": "Before", "share_a": "After",
        "share_why": "This fall is real: the new record is a campaign that started on 1 October, in force on a different number of days in the "
                     "two periods, so it can explain why this year differs from last. The old record (\u201cfruit baskets are the cheapest\u201d) is "
                     "true in both years: it explains why a shift in mix moves the average, not why the mix shifted, so it did not count before.",
        "s_forget": "Forget one, and a regression case catches it",
        "forget_sub": "Every correction becomes a regression case: this question, at this place, must cite this record.",
        "f_steps": ["After it learns, run the regression cases", "Delete the record from the workspace and run them again"],
        "f_pass": "passes", "f_fail": "fails", "f_expect": "Required: at \u201c{slot}\u201d, cite \u201c{rec}\u201d.",
        "f_got_pass": "It cited: {cites}.", "f_got_fail": "It cited only: {cites}.",
        "f_caught": "The regression case fails: forgetting is noticed, not quietly undone.",
        "s_not": "What it does not do", "not": [
            "One correction records one entry; two things in one sentence have to be said twice.",
            "It does not check that the campaign really ran: what the user says is recorded, with the source \u201cthe user's words\u201d.",
            "A regression case only guarantees this place still cites this record; whether other questions drift is up to the other cases."],
        "ids": "Where it is kept (for the maintainer)", "ids_rows": [("Record", "where"), ("Regression case", "case"), ("The user's words", "log"), ("Correction date", "date")],
    },
}
def _report_part(md):
    """The conclusion's opening lines and the whole "why" section of a report (section order: references/report.md §1)."""
    secs = ("\n" + md.split("\n", 1)[1]).split("\n## ")[1:]
    concl = [ln for ln in secs[0].split("\n")[1:] if ln.strip()]
    keep = [concl[0]] + [ln for ln in concl if ln.startswith(("主因是", "The main cause", "和「", "That is the same day"))]
    why = [ln for ln in secs[3].split("\n")[1:] if ln.strip()]
    return keep, why


def _md_lines(lines, lang):
    """The kinds of line the two excerpts hold: paragraphs, bold, lists. Record ids dropped, "=" written as a colon."""
    out, depth = [], -1
    for ln in lines:
        ln = re.sub(r"\s*`[a-z0-9_]+`", "", ln).replace("=", "：" if lang == "zh" else ": ")
        m = re.match(r"^(\s*)- (.*)", ln)
        body = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", _e(m.group(2) if m else ln))
        if m:
            d = len(m.group(1)) // 2
            while depth < d:
                out.append("<ul>")
                depth += 1
            while depth > d:
                out.append("</ul>")
                depth -= 1
            out.append(f"<li>{body}</li>")
        else:
            out += ["</ul>"] * (depth + 1)
            depth = -1
            out.append(f"<p>{body}</p>")
    out += ["</ul>"] * (depth + 1)
    return "".join(out)


def learning_context(data, lang) -> dict:
    L = data["learning"]
    R = G.learning(L)
    w, zh = LW[lang], lang == "zh"
    sp = zh_space if zh else (lambda s: s)
    cols = {}
    for tag in ("before", "after"):
        head, why = _report_part(R["reports"][tag][lang])
        cols[tag] = _md_lines(head, lang) + _md_lines(why, lang)
    ap = L["applied"]
    e = L["entries"][ap["target"]]
    rec = {"text": e["text"][lang], "when": span(e["start"], e["end"], lang) if e.get("start") else "—",
           "src": src_text(e.get("source"), lang), "status": W[lang]["status"].get(e.get("status"), e.get("status"))}
    slots = L["labels"]["slots"]
    q = lambda x: f"「{x}」" if zh else f"\u201c{x}\u201d"  # noqa: E731

    def reg(rows):
        out = []
        for r in rows:
            slot = slot_text(slots.get(r["expect"]["slot"], {}).get(lang, r["expect"]["slot"]), lang)
            got = [x for x in re.findall(r"'([a-z0-9_]+)'", r["detail"]) if x in L["entries"]]
            out.append({"pass": r["pass"], "expect": w["f_expect"].format(slot=slot, rec=L["entries"][r["expect"]["cites"]]["text"][lang]),
                        "got": (w["f_got_pass"] if r["pass"] else w["f_got_fail"]).format(cites=join((q(L["entries"][x]["text"][lang]) for x in got), lang))})
        return out
    # files and sections rather than raw ids: the site's check bans engine ids on a page, folded or not
    ids = {"where": f"world.yaml · {e['bucket']}", "case": f"regressions/ · {len(L['regress'])}",
           "log": "corrections.jsonl", "date": ap["correction"]["date"]}
    return {"w": w, "page_title": w["title"], "description": ("" if zh else " ").join(w["h1"]),
            "lede": sp(w["lede"].format(q=R["question"][lang])),
            "before": sp(cols["before"]) if zh else cols["before"], "after": sp(cols["after"]) if zh else cols["after"],
            "quote": ap["correction"]["quote"][lang], "rec": rec,
            "share": [(w["share_b"], L["before"]["coverage"]), (w["share_a"], L["after"]["coverage"])],
            "steps": [{"title": w["f_steps"][0], "rows": reg(L["regress"])}, {"title": w["f_steps"][1], "rows": reg(L["forget"]["rows"])}],
            "caught": L["forget"]["caught"], "ids": [(a, ids[b]) for a, b in w["ids_rows"]]}


# ---------------------------------------------------------------- architecture page
# One question per page: "can I trust how it works?". Method details live in the skill's references, not here.
REPO_REFS = "https://github.com/weigezi/analyst-in-a-box/blob/main/skills/analyst-in-a-box/references/"
AW = {
    "zh": {
        "title": "怎么搭的",
        "h1": ["数由脚本算，", "解释带出处，", "拿不准的由人定。"],
        "lede": "一组在你电脑上跑的 Python 脚本，加一份写给 AI 的做法说明。数据只读，不出你的电脑。",
        "s_roles": "三方各管一件事",
        "roles": [("脚本", "算每一个数，拆完都核对加起来等于总变化"),
                  ("AI 工具", "把结果讲成大白话，只引用有出处的记录"),
                  ("你", "确认每列是什么、原因和负责人；纠正一次就记下")],
        "s_flow": "一道题走过的步骤",
        "step": {
            "frame": ("定题", "看哪个数、和什么比"), "quality": ("查数据", "重复、缺天、突然跳"),
            "qualify": ("算不算异常", "和自己的历史比"), "horizontal": ("按公式拆", "营收 = 订单数 × 客单价"),
            "second_sides": ("比两边", "App 对比网页"), "second_time": ("比两段时间", "这期和上期比"),
            "vertical": ("按维度切", "切到集中的那一组"), "explain": ("解释", "引用有出处的记录"),
            "actions": ("该谁去做", "动作和负责人"), "checks": ("交付前自检", "不过就不交"), "record": ("记录", "这次用了什么"),
        },
        "methods": "拆分和判断用的是 12 种公开发表过的统计方法。",
        "methods_link": "完整清单和出处",
        "s_not": "还没做的", "not": ["AB 实验不做，只做经营分析。", "第一版一个人用，没有多人协作。"],
    },
    "en": {
        "title": "How it is built",
        "h1": ["Scripts do the arithmetic,", "explanations carry a source,", "and a person decides what is unclear."],
        "lede": "A set of Python scripts that run on your computer, plus a written method for your AI tool. Your data is only read, and it stays on your machine.",
        "s_roles": "Three parts, one job each",
        "roles": [("Scripts", "compute every number, and check each breakdown adds up to the total change"),
                  ("Your AI tool", "puts the results in plain words and cites only records with a source"),
                  ("You", "confirm what each column means, the causes and the owners; a correction is kept")],
        "s_flow": "The steps one question goes through",
        "step": {
            "frame": ("Frame", "which number, against what"), "quality": ("Check the data", "duplicates, gaps, jumps"),
            "qualify": ("Unusual?", "against its own history"), "horizontal": ("By formula", "revenue = orders × AOV"),
            "second_sides": ("Two sides", "app against web"), "second_time": ("Two periods", "this one against the last"),
            "vertical": ("By dimension", "until it sits in one group"), "explain": ("Explain", "cite records with a source"),
            "actions": ("Who acts", "actions and owners"), "checks": ("Final checks", "no pass, no report"), "record": ("Record", "what this run used"),
        },
        "methods": "The breakdowns and tests use 12 published statistical methods.",
        "methods_link": "The full list and sources",
        "s_not": "Not done yet", "not": ["No A/B testing; business analysis only.", "Version 1 is for one person; no team use."],
    },
}


def arch_context(data, lang) -> dict:
    w, zh = AW[lang], lang == "zh"
    sp = zh_space if zh else (lambda s: s)
    sm = G.state_machine()
    steps = [{"id": s, "t": w["step"][s][0], "d": w["step"][s][1], "box": sm["boxes"][s], "col": sm["boxes"][s]["rank"]} for s in sm["steps"]]
    return {"w": w, "page_title": w["title"], "description": ("" if zh else " ").join(w["h1"]), "lede": sp(w["lede"]),
            "roles": [(a, sp(b)) for a, b in w["roles"]],
            "flow": {"w": sm["w"], "h": sm["h"], "steps": sorted(steps, key=lambda x: (x["col"], x["box"]["y"])), "edges": sm["edges"]},
            "methods": sp(w["methods"]), "methods_href": REPO_REFS + ("operators.zh.md" if zh else "operators.md")}


def pages(data, lang) -> list[dict]:
    """Paths are inside a language root (build.py page_ctx adds "en/", root, alt_href and lang)."""
    return [{"path": "graph.html", "template": "graph.html.j2", "nav_active": "graph", "context": graph_context(data, lang)},
            {"path": "intake.html", "template": "intake.html.j2", "nav_active": "intake", "context": intake_context(data, lang)},
            {"path": "learning.html", "template": "learning.html.j2", "nav_active": "learning", "context": learning_context(data, lang)},
            {"path": "architecture.html", "template": "architecture.html.j2", "nav_active": "architecture", "context": arch_context(data, lang)}]
