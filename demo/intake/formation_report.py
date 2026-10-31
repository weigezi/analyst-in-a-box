"""Write the formation report: what the intake formed, where each part came from, and where it differs from the
hand-written demo workspace. Every count is read from the two workspaces; nothing is typed in."""

from __future__ import annotations

import yaml

from aib.workspace import Workspace

# Store metric id -> the id intake gives the same number (intake names come from columns and the formula starter).
METRIC_MAP = {"revenue": "revenue", "gross_profit": "gross_profit", "orders": "id_count", "aov": "per_id",
              "margin_rate": "margin", "visits": "visits", "cr": "conversion"}

T = {
    "zh": {
        "title": "形成报告：从几张原始表到一个能答题的工作区",
        "link": "[English](formation.md)",
        "intro": "演示店「花果篮」的同一批数据，拆成真实系统常见的 {n} 张表（`tables/`），外加一份周报（`docs/weekly_report.zh.md`）。"
                 "skill 自己读表、出选择题，店主回答（`answers.yaml`），AI 工具读周报提出候选（`proposals.yaml`），然后直接答题。"
                 "下面把自动形成的工作区（`workspace/`）和手写的演示工作区（`../store/workspace/`）逐项对照。本报告由 `run_intake.py` 生成，数字都是从两个工作区读出来的。",
        "s_counts": "一、四类来源各有多少", "s_machine": "二、机器自己从数据推出来的", "s_user": "三、用户在选择题里确认的",
        "s_docs": "四、从文档抽出来、待确认的", "s_person": "五、只有人能补的", "s_compare": "六、和手写工作区逐项对照",
        "s_answers": "七、拿形成的工作区答题", "s_gaps": "八、没对上的地方",
        "kind": "类", "count": "数量", "what": "内容",
        "c_machine": "机器从数据推出（再经选择题确认）", "c_user": "选择题（问了 / 答了）", "c_docs": "从文档抽出、待确认（收下 / 拒收）",
        "c_person": "只有人能补、目前空着",
        "dims": "维度", "entities": "维度值（实体）", "relations": "「属于」关系", "metrics_formula": "公式算出的指标",
        "metrics_cols": "靠用户指认含义才有的指标（金额、毛利、访问量、订单数）", "identities": "恒等式", "joins": "查找表并进主表", "external": "外部数据",
        "events_table": "事件表里的事件（系统记录，待确认）",
        "q_head": ["问题", "建议的答案", "用户的回答"], "q_changed": "改了建议",
        "d_head": ["类型", "原句", "记成"], "rejected": "拒收",
        "p_head": ["要补的", "为什么只有人能补"],
        "cmp_head": ["项目", "手写工作区", "自动形成", "对得上吗"], "yes": "对上", "no": "没对上", "partly": "部分对上",
        "a_head": ["问题", "主因", "引用", "状态"],
        "status": {"explained": "已解释", "hypothesis": "推测 / 待确认", "gap": "缺口", "data_suspect": "数据存疑"},
        "src": {"document": "文档", "system_record": "系统记录", "user": "用户", "data": "数据", "demo_setting": "演示设定",
                "general_knowledge": "通用常识"},
        "cstatus": {"proposed": "待确认", "confirmed": "已确认"},
        "checks": {"supported": "对着天气数据过了三道检查", "timing_only": "只有时间对得上", "not_supported": "时间对不上"},
        "note_east": "暴雨虽然来自周报，却算已解释：外部事件看的是对着外部数据（这里是降雨量）的三道检查，不看谁确认过。这是 0.1 起对外部事件的规则，没有改。",
    },
    "en": {
        "title": "Formation report: from a few raw tables to a workspace that answers questions",
        "link": "[中文](formation.zh.md)",
        "intro": "The same data as the demo shop \"Bloom & Basket\", split into {n} tables shaped like real system exports (`tables/`), "
                 "plus a weekly report (`docs/weekly_report.zh.md`). The skill reads the tables and asks multiple-choice questions; the owner "
                 "answers (`answers.yaml`); an AI tool reads the report and proposes candidates (`proposals.yaml`); then it answers questions. "
                 "Below, the formed workspace (`workspace/`) is set against the hand-written demo workspace (`../store/workspace/`) part by part. "
                 "`run_intake.py` writes this report; every number is read from the two workspaces.",
        "s_counts": "1. How much came from each source", "s_machine": "2. What the machine inferred from the data",
        "s_user": "3. What the user confirmed in the questions", "s_docs": "4. What was taken from a document, to confirm",
        "s_person": "5. What only a person can add", "s_compare": "6. Against the hand-written workspace",
        "s_answers": "7. Asking the formed workspace", "s_gaps": "8. Where it does not match",
        "kind": "Kind", "count": "Count", "what": "What",
        "c_machine": "inferred from the data (then confirmed in a question)", "c_user": "questions (asked / answered)",
        "c_docs": "from a document, to confirm (accepted / refused)", "c_person": "only a person can add; empty so far",
        "dims": "dimensions", "entities": "dimension values (entities)", "relations": "\"belongs to\" relations",
        "metrics_formula": "metrics from formulas", "metrics_cols": "Metrics that exist because the user named a column's meaning (amount, profit, visits, orders)",
        "identities": "identities",
        "joins": "lookup tables joined to the main table", "external": "outside data",
        "events_table": "events from event tables (system records, to confirm)",
        "q_head": ["Question", "Suggested", "Answered"], "q_changed": "changed the suggestion",
        "d_head": ["Type", "Sentence", "Recorded as"], "rejected": "refused",
        "p_head": ["To add", "Why only a person can"],
        "cmp_head": ["Part", "Hand-written", "Formed", "Match"], "yes": "match", "no": "differs", "partly": "partly",
        "a_head": ["Question", "Main cause", "Cites", "Status"],
        "status": {"explained": "explained", "hypothesis": "hypothesis / to confirm", "gap": "gap", "data_suspect": "data in doubt"},
        "src": {"document": "document", "system_record": "system record", "user": "user", "data": "data", "demo_setting": "demo setting",
                "general_knowledge": "general knowledge"},
        "cstatus": {"proposed": "to confirm", "confirmed": "confirmed"},
        "checks": {"supported": "passed the three checks against the weather data", "timing_only": "timing matches only",
                   "not_supported": "timing does not match"},
        "note_east": "The rainstorm counts as explained although it came from the report: an outside event is judged by the three checks "
                     "against outside data (here the rainfall), not by who confirmed it. That is the 0.1 rule for outside events, kept.",
        "person": {
            "mechanisms": ("mechanisms", "why a group's number is naturally different (a commission, a cheaper category); {have} so far, all "
                                         "from the report and waiting for confirmation, {confirmed} confirmed"),
            "actions": ("actions and owners", "who acts, and what they can do"),
            "priorities": ("cut order", "which dimension to look at first; until then every layer is chosen by score"),
            "comparisons": ("comparisons", "which two sides are worth comparing (app vs web)"),
            "pvm": ("price-volume-mix", "which number is the quantity and which dimension to split prices by"),
            "labels": ("readable names", "names for codes (marketplace → 电商平台); the data holds only codes"),
        },
    },
}
T["zh"]["person"] = {
    "mechanisms": ("机制", "某一组的数为什么天生不一样（抽佣金、品类便宜）；目前 {have} 条，都来自周报、待确认，已确认 {confirmed} 条"),
    "actions": ("动作和负责人", "谁去做、能做什么"),
    "priorities": ("切分顺序", "先看哪个维度；定之前每一层按打分选"),
    "comparisons": ("对比组", "哪两边值得比（App 对比网页）"),
    "pvm": ("量-结构-价格", "哪个数是「量」、价格按哪个维度拆"),
    "labels": ("可读名字", "代码对应的名字（marketplace → 电商平台）；数据里只有代码"),
}


def _table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *["| " + " | ".join(str(c) for c in r) + " |" for r in rows]]


def _lab(x, lang):
    if isinstance(x, dict):
        return str(x.get(lang) or x.get("zh") or x.get("en") or "")
    return str(x)


def _ent_key(world, eid):
    e = next((x for x in world.get("entities", []) if x["id"] == eid), None)
    return (e.get("dimension"), str(e.get("key"))) if e and e.get("dimension") else (None, eid)


def compare(store: Workspace, formed: Workspace):
    """[(part, store side, formed side, match)] with match in yes / no / partly."""
    rows = []
    sd, fd = set(store.dimensions), set(formed.dimensions)
    rows.append(("dimensions", sorted(sd), sorted(fd), "yes" if sd == fd else "partly" if sd & fd else "no"))
    sm = {METRIC_MAP.get(m, m) for m in store.metrics}
    fm = set(formed.metrics)
    rows.append(("metrics", sorted(store.metrics), sorted(fm), "yes" if sm == fm else "partly" if sm & fm else "no"))
    si = {(METRIC_MAP.get(i["left"], i["left"]), tuple(sorted(METRIC_MAP.get(f, f) for f in i["factors"]))) for i in store.model.get("identities", [])}
    fi = {(i["left"], tuple(sorted(i["factors"]))) for i in formed.model.get("identities", [])}
    rows.append(("identities", len(si), len(fi), "yes" if si == fi else "partly" if si & fi else "no"))
    se = {_ent_key(store.world, e["id"]) for e in store.world.get("entities", []) if e.get("dimension")}
    fe = {_ent_key(formed.world, e["id"]) for e in formed.world.get("entities", [])}
    rows.append(("entities", len(se), len(fe), "yes" if se == fe else "partly" if se & fe else "no"))
    readable = lambda w: sum(1 for e in w.world.get("entities", []) if e.get("dimension") and _lab(e.get("label"), "zh") != str(e.get("key")))  # noqa: E731
    rows.append(("labels", readable(store), readable(formed), "yes" if readable(formed) == readable(store) else "no"))
    rel = lambda w: {(_ent_key(w.world, r["subject"]), _ent_key(w.world, r["object"])) for r in w.world.get("relations", [])}  # noqa: E731
    sr, fr = rel(store), rel(formed)
    rows.append(("relations", len(sr), len(fr), "yes" if sr == fr else "partly" if sr & fr else "no"))

    def ev_keys(w):
        return {(str(e["start"]), frozenset(_ent_key(w.world, x) for x in e.get("entities", []))): e for e in w.world.get("events", [])}
    sev, fev = ev_keys(store), ev_keys(formed)
    rows.append(("events", sorted(e["id"] for e in sev.values()), sorted(e["id"] for e in fev.values()),
                 "yes" if set(sev) == set(fev) else "partly" if set(sev) & set(fev) else "no"))
    rows.append(("mechanisms", len(store.world.get("mechanisms", [])), len(formed.world.get("mechanisms", [])),
                 "yes" if len(store.world.get("mechanisms", [])) == len(formed.world.get("mechanisms", [])) else "no"))
    rows.append(("actions", len(store.world.get("actions", [])), len(formed.world.get("actions", [])),
                 "yes" if len(store.world.get("actions", [])) == len(formed.world.get("actions", [])) else "no"))
    rows.append(("comparisons", len(store.model.get("comparisons", [])), len(formed.model.get("comparisons", [])),
                 "yes" if len(store.model.get("comparisons", [])) == len(formed.model.get("comparisons", [])) else "no"))
    conf = lambda w: sorted(m for m, p in (w.model.get("priorities") or {}).items() if p.get("status") == "confirmed")  # noqa: E731
    rows.append(("confirmed priorities", conf(store), conf(formed), "yes" if conf(store) == conf(formed) else "no"))
    rows.append(("price-volume-mix", len(store.model.get("pvm", []) or []), len(formed.model.get("pvm", []) or []),
                 "yes" if bool(store.model.get("pvm")) == bool(formed.model.get("pvm")) else "no"))
    roles = lambda w: sorted(s.get("role") for s in w.external.specs.values())  # noqa: E731
    rows.append(("outside data", roles(store), roles(formed), "yes" if roles(store) == roles(formed) else "partly"))
    return rows, sev, fev


PART = {"zh": {"dimensions": "维度", "metrics": "指标", "identities": "恒等式", "entities": "维度值", "labels": "有可读名字的维度值",
               "relations": "「属于」关系", "events": "事件", "mechanisms": "机制", "actions": "动作和负责人", "comparisons": "对比组",
               "confirmed priorities": "确认过的切分顺序", "price-volume-mix": "量-结构-价格拆解", "outside data": "外部数据"},
        "en": {k: k for k in ("dimensions", "metrics", "identities", "entities", "relations", "events", "mechanisms", "actions",
                              "comparisons", "confirmed priorities", "price-volume-mix", "outside data")} | {"labels": "dimension values with a readable name"}}

GAPS = {
    "zh": [
        ("metrics", "指标名字不同：手写版叫 orders / aov / margin_rate / cr，自动形成的叫 id_count / per_id / margin / conversion（起步模板的叫法）。算法一样，名字要人改。"),
        ("labels", "维度值没有可读名字：自动形成的是 marketplace、fruit_basket 这样的代码，手写版是「电商平台」「果篮」。数据里没有中文名，只有人能补。"),
        ("events", "事件不完全一样：「App 首页撤掉绿植推荐位」在手写版里来自 App 发版记录，这次没给这份记录，所以没形成。"
                   "反过来，活动日历和调价记录里的三件事（情人节主推、10 月新客果篮送贺卡、6 月礼盒涨价）是自动形成独有的；手写版里贺卡活动是靠用户纠正补上的。"),
        ("mechanisms", "机制只形成了 1 条（从周报抽出的「当日达靠骑手」）；手写版的 3 条里，「平台抽佣金所以毛利低」「果篮最便宜」数据和周报里都没有，只有人能说。"),
        ("relations", "「属于」关系少一类：手写版有「电商平台经由平台方」这种连到外部实体的关系，数据里推不出来。"),
        ("comparisons", "没有对比组：「App 对比网页」这道二阶题，要人说哪两边值得比，所以形成的工作区答不了那一题。"),
        ("confirmed priorities", "切分顺序都是「待确认」：手写版是维护者定的顺序；形成的工作区每层按打分选，第一刀不一定是渠道。"),
        ("price-volume-mix", "没有量-结构-价格拆解：要人说哪个数是「量」、按哪个维度拆，6 月那道题因此只拆到品类，没有拆量和价。"),
    ],
    "en": [
        ("metrics", "Metric names differ: hand-written orders / aov / margin_rate / cr, formed id_count / per_id / margin / conversion (the formula starter's names). Same arithmetic; a person renames them."),
        ("labels", "Dimension values have no readable names: the formed workspace has codes like marketplace and fruit_basket, the hand-written one has 电商平台 and 果篮. The data has no display names; only a person can add them."),
        ("events", "The events are not the same set. \"The app home page dropped its plants slot\" comes from the app's release notes in the hand-written workspace; no such record was given, so it was not formed. "
                   "The other way round, three entries from the campaign calendar and the price-change log (the Valentine's push, the October card offer, the June gift-box price rise) exist only in the formed one; in the hand-written workspace the card offer was added by a user correction."),
        ("mechanisms", "One mechanism was formed (from the report: same-day needs riders). Of the hand-written three, \"the marketplace takes a commission, so margin is lower\" and \"fruit baskets are the cheapest\" are in neither the data nor the report; only a person can say them."),
        ("relations", "One kind of relation is missing: the hand-written workspace links the marketplace to an outside entity (the marketplace operator); the data cannot show that."),
        ("comparisons", "No comparison: the second-order question \"app vs web\" needs a person to say which two sides are worth comparing, so the formed workspace cannot answer it."),
        ("confirmed priorities", "Every cut order is \"to confirm\": the hand-written one is the maintainer's order; the formed one chooses every layer by score, so the first cut is not always the channel."),
        ("price-volume-mix", "No price-volume-mix: a person has to say which number is the quantity and which dimension to split by, so the June question stops at the category and does not split volume and price."),
    ],
}


def render(ws_root, store_root, facts, lang):
    t = T[lang]
    formed, store = Workspace(ws_root), Workspace(store_root)
    f, d = facts["formation"], facts["draft"]
    L = [f"# {t['title']}", "", t["link"], "", t["intro"].format(n=len(d["tables"])), ""]
    counts = f["counts"]
    rec = f["intake"] or {}
    acc, rej = facts["proposed"]["accepted"], facts["proposed"]["rejected"]
    asked = len(d["questions"])
    answered = rec.get("answered", 0)
    L += [f"## {t['s_counts']}", ""]
    machine = [x for x in f["items"]["from_data"]]
    L += _table([t["kind"], t["count"]], [[t["c_machine"], len(machine)], [t["c_user"], f"{asked} / {answered}"],
                                          [t["c_docs"], f"{len(acc)} / {len(rej)}"], [t["c_person"], counts["needs_a_person"]]])
    L += [""]

    L += [f"## {t['s_machine']}", ""]
    by = {}
    for x in machine:
        by.setdefault(x["kind"], []).append(x)
    metrics_formula = [m for m, v in formed.metrics.items() if (v.get("source") or {}).get("kind") == "formula"]
    metrics_cols = [m for m, v in formed.metrics.items() if (v.get("source") or {}).get("kind") != "formula"]
    joins = [j["source"] for s in formed.sources.specs.values() if s.get("type") == "join" for j in s["joins"]]
    ev_t = [e for e in formed.world.get("events", []) if (e.get("source") or {}).get("kind") == "system_record"]
    rows = [[t["dims"], len(formed.dimensions), ", ".join(formed.dimensions)],
            [t["entities"], len(by.get("entity", [])), ""],
            [t["relations"], len(by.get("relation", [])), ", ".join(sorted({r["id"].split(">")[0].split(":")[1] + "→" + r["id"].split(">")[1].split(":")[0]
                                                                         for r in formed.world.get("relations", [])}))],
            [t["joins"], len(joins), ", ".join(joins)],
            [t["metrics_formula"], len(metrics_formula), ", ".join(metrics_formula)],
            [t["identities"], len(formed.model.get("identities", [])), ", ".join(i["id"] for i in formed.model.get("identities", []))],
            [t["external"], len(formed.external.specs), ", ".join(f"{n} ({s.get('role')})" for n, s in formed.external.specs.items())],
            [t["events_table"], len(ev_t), "; ".join(f"{_lab(e['what'], lang)} {e['start']}~{e['end']}" for e in ev_t)]]
    L += _table([t["kind"], t["count"], t["what"]], rows) + [""]

    L += [f"## {t['s_user']}", ""]
    answers = {x["id"]: x["answer"] for x in f["items"]["user_answers"] if x["kind"] == "answer"}

    def cell(a):
        if a is None:
            return "—"
        if isinstance(a, list):
            return ", ".join(map(str, a))
        if isinstance(a, dict):
            return str(a.get("days", a))
        return str(a)
    qrows = []
    for q in d["questions"]:
        a = answers.get(q["id"])
        sug = q.get("suggested")
        mark = f" ({t['q_changed']})" if sug is not None and a is not None and str(a) != str(sug) else ""
        qrows.append([f"`{q['id']}`", cell(sug), cell(a) + mark])
    L += _table(t["q_head"], qrows) + [""]
    L += [f"{t['metrics_cols']}{'：' if lang == 'zh' else ': '}{', '.join(metrics_cols)}", ""]

    L += [f"## {t['s_docs']}", ""]
    drows = [[x["type"], f"「{x['quote']}」" if lang == "zh" else f"\"{x['quote']}\"", f"`{x['id']}`"] for x in acc]
    drows += [[x["type"], x["quote"], f"{t['rejected']}: {x['reason']}"] for x in rej]
    L += _table(t["d_head"], drows) + [""]

    L += [f"## {t['s_person']}", ""]
    L += _table(t["p_head"], [[t["person"][x["reason"]][0], t["person"][x["reason"]][1].format(**x)]
                              for x in f["items"]["needs_a_person"]]) + [""]

    L += [f"## {t['s_compare']}", ""]
    rows, _, _ = compare(store, formed)
    fmtv = lambda v: (", ".join(map(str, v)) or "—") if isinstance(v, list) else str(v)  # noqa: E731
    L += _table(t["cmp_head"], [[PART[lang][p], fmtv(a), fmtv(b), t[m]] for p, a, b, m in rows]) + [""]

    L += [f"## {t['s_answers']}", ""]
    arows = []
    for k, r in facts["runs"].items():
        leaf = next((x for x in r["slots"] if x["leaf"]), None)
        if not leaf:
            arows.append([k, "—", "—", "—"])
            continue
        sep = "，" if lang == "zh" else ", "
        cites = "; ".join(f"`{c['id']}` ({t['src'].get(c['source'], c['source'])}{sep}{t['cstatus'].get(c['status'], c['status'])}"
                          + (f"{sep}{t['checks'].get(c['checks'], c['checks'])}" if c.get("checks") else "") + ")"
                          for c in leaf["citations"] if c.get("explains") == "change")
        arows.append([k, f"`{leaf['id']}`", cites or "—", t["status"].get(leaf["status"], leaf["status"])])
    L += _table(t["a_head"], arows) + ["", t["note_east"], ""]

    L += [f"## {t['s_gaps']}", ""]
    mismatched = {p for p, _, _, m in rows if m != "yes"}
    for part, text in GAPS[lang]:
        if part in mismatched:
            L.append(f"- {text}")
    L.append("")
    return "\n".join(L)
