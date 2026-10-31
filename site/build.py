"""Build the demo site: run the engine, shape what each page shows, render Jinja2 templates.

    uv run python site/build.py          -> site/dist/ (open site/dist/index.html; works from file://)

Numbers come from sitedata.collect(), which runs the engine fresh on every build; if the engine fails, the build
fails. This file only picks engine fields and arranges them for the templates: wording lives in templates/,
drawing in assets/charts.js. The only arithmetic here is `rest = total change − the groups shown` for the
collapsed "other N groups" node of a breakdown tree, flagged where it is done.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DIST = SITE / "dist"
sys.path.insert(0, str(SITE / "vendor"))
sys.path.insert(0, str(SITE))

import jinja2  # noqa: E402

import sitedata  # noqa: E402

LANGS = ("zh", "en")
MINUS = "\u2212"
CASE_IDS = ("revenue_last_week", "east_last_week", "aov_last_week", "june_price_volume", "app_vs_web")

# Navigation, shared with the pages another builder renders (pages_more). Paths are inside a language root.
NAV = [
    {"key": "graph", "path": "graph.html", "label": {"zh": "知识图谱", "en": "Knowledge graph"}},
    {"key": "reports", "path": "reports/revenue_last_week.html", "label": {"zh": "案例报告", "en": "Reports"}},
    {"key": "intake", "path": "intake.html", "label": {"zh": "采集", "en": "Bringing data in"}},
    {"key": "learning", "path": "learning.html", "label": {"zh": "它怎么学", "en": "How it learns"}},
    {"key": "architecture", "path": "architecture.html", "label": {"zh": "怎么搭的", "en": "How it is built"}},
]
NAV_REPORTS = [
    {"path": "reports/revenue_last_week.html", "label": {"zh": "营收为什么跌了", "en": "Why revenue fell"},
     "note": {"zh": "按渠道拆，原因有记录", "en": "By channel, cause on record"}},
    {"path": "reports/east_last_week.html", "label": {"zh": "华东为什么跌得多", "en": "Why the east fell more"},
     "note": {"zh": "外部事件过三道检查", "en": "An outside event, three checks"}},
    {"path": "reports/aov_last_week.html", "label": {"zh": "客单价为什么降了", "en": "Why order value fell"},
     "note": {"zh": "结构和各组自身", "en": "Mix against each group's own level"}},
    {"path": "reports/june_price_volume.html", "label": {"zh": "6 月：卖得多还是卖得贵", "en": "June: more sold, or higher prices"},
     "note": {"zh": "量、价、结构", "en": "Volume, price, mix"}},
    {"path": "reports/app_vs_web.html", "label": {"zh": "App 为什么比网页长得慢", "en": "Why the app grew slower than the web"},
     "note": {"zh": "两边比：结构差和表现差", "en": "Two sides: mix gap and performance gap"}},
    {"path": "reports/public.html", "label": {"zh": "公开数据：英国网店", "en": "Public data: a UK online shop"},
     "note": {"zh": "真实数据，第一次运行", "en": "Real data, first run"}},
]

# ---------------------------------------------------------------- formatting (mirrored in assets/fmt.js)

def _sign(x, signed):
    return MINUS if x < 0 else ("+" if x > 0 and signed else "")


def f_num(x, dp=0, signed=False):
    r = round(x, dp)
    return _sign(r, signed) + f"{abs(r):,.{dp}f}"


def f_pct(x, dp=1, signed=True):
    r = round(x * 100, dp)
    return _sign(r, signed) + f"{abs(r):.{dp}f}%"


def f_money(x, lang, signed=False, dp=0, currency="CNY"):
    r = round(x, dp)
    if currency == "GBP":
        return _sign(r, signed) + "£" + f"{abs(r):,.{dp}f}"
    return f_num(r, dp, signed) + " 元" if lang == "zh" else _sign(r, signed) + "¥" + f"{abs(r):,.{dp}f}"


def f_wan(x, lang, signed=False):
    """Rounded money for headlines: 7.9 万元 / ¥79k."""
    if lang == "zh":
        r = round(abs(x) / 1e4, 1)
        return _sign(x, signed) + (f"{r:.1f} 万元" if abs(x) >= 1e4 else f"{abs(x):,.0f} 元")
    return _sign(x, signed) + (f"¥{abs(x) / 1e3:.0f}k" if abs(x) >= 1e4 else f"¥{abs(x):,.0f}")


def f_md(iso, lang, year=False):
    y, m, d = (int(p) for p in str(iso)[:10].split("-"))
    if lang == "zh":
        return (f"{y} 年 " if year else "") + f"{m} 月 {d} 日"
    mon = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[m - 1]
    return f"{d} {mon}" + (f" {y}" if year else "")


def f_range(r, lang):
    a, b = str(r[0]), str(r[1])
    year = a[:4] != b[:4]
    first = f_md(a, lang, year=True)
    if lang == "zh":
        return first + " 至 " + f_md(b, lang, year=year)
    return f_md(a, lang, year=year) + "\u2013" + f_md(b, lang, year=True)


def f_delta(x, lang, unit="currency", dp=0, signed=True, currency="CNY"):
    if unit == "points":
        r = round(x * 100, dp)
        return _sign(r, signed) + f"{abs(r):.{dp}f}" + (" 个百分点" if lang == "zh" else " points")
    return f_money(x, lang, signed, dp, currency)


@jinja2.pass_context
def _delta_filter(ctx, x, unit="currency", dp=0, signed=True):
    return f_delta(x, ctx["lang"], unit, dp, signed, ctx.get("currency", "CNY"))


def T(x, lang):
    """Pick one language from an engine {zh, en} label; plain strings pass through."""
    if isinstance(x, dict) and "zh" in x and "en" in x:
        return x[lang]
    return x


def _ctx_filter(fn):
    @jinja2.pass_context
    def f(ctx, x, *a, **k):
        return fn(x, ctx["lang"], *a, **k)
    return f


@jinja2.pass_context
def _money_filter(ctx, x, signed=False, dp=0):
    return f_money(x, ctx["lang"], signed, dp, ctx.get("currency", "CNY"))


def make_env() -> jinja2.Environment:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(SITE / "templates")), autoescape=True,
                             undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    env.filters.update({
        "num": lambda x, dp=0, signed=False: f_num(x, dp, signed),
        "pct": lambda x, dp=1, signed=True: f_pct(x, dp, signed),
        "times": lambda x: f"{abs(x):.1f}",
        "money": _money_filter,
        "wan": _ctx_filter(lambda x, lang, signed=False: f_wan(x, lang, signed)),
        "md": _ctx_filter(lambda x, lang, year=False: f_md(x, lang, year)),
        "daterange": _ctx_filter(f_range),
        "t": _ctx_filter(T),
        "tone": lambda x: "neg" if x < 0 else "pos",
        # A change in the report's own unit: money, or points of growth (0.0103 -> "+1.0 个百分点").
        "delta": _delta_filter,
    })
    env.globals.update({"NAV": NAV, "NAV_REPORTS": NAV_REPORTS, "T": T})
    return env


# ---------------------------------------------------------------- one case -> what its report shows

class Labels:
    # Columns of the public dataset that intake left unlabelled (its label is the raw column name).
    FALLBACK = {"country_group": {"zh": "国家分组", "en": "Country group"}, "revenue": {"zh": "营收", "en": "Revenue"},
                "items": {"zh": "件数", "en": "Items"}}

    def __init__(self, case):
        self.L = case["labels"]

    def _fix(self, key, x):
        return self.FALLBACK[key] if key in self.FALLBACK and x.get("zh") == key else x

    def value(self, dim, key):
        return self.L["values"][dim][str(key)]

    def dim(self, dim):
        return self._fix(dim, self.L["dimensions"][dim])

    def metric(self, m):
        return self._fix(m, self.L["metrics"][m])


# What a group's change is measured in, by cut operator: money for sums and ratio levels, points for growth gaps.
def unit_of(s, case):
    if s.get("order") == "second_sides":
        return "points", 1
    return ("currency", 2) if s["metric"] in ("aov", "per_id") else ("currency", 0)


def formula_tree(s, lab: Labels):
    """The metric's formula, down to the leaves the engine priced in money (state.tree.leaves)."""
    tree = s.get("tree")
    if not tree:
        return None
    by_parent = {h["parent"]: h for h in s["horizontal"] if h.get("operator") == "multiplicative"}
    leaves = {x["factor"]: x for x in tree["leaves"]}

    def node(metric, f):
        n = {"label": lab.metric(metric), "growth": f["growth"], "children": []}
        h = by_parent.get(metric)
        if h and metric != s["metric"]:
            n["children"] = [node(c["factor"], c) for c in h["factors"]]
        # Leaves carry the engine's money contribution; a middle factor (orders) carries its first-level contribution.
        n["amount"] = leaves[metric]["contribution"] if metric in leaves else f["contribution"]
        n["formula"] = [c["label"] for c in n["children"]]
        return n

    top = by_parent[s["metric"]]
    kids = [node(c["factor"], c) for c in top["factors"]]
    return {"label": lab.metric(s["metric"]), "amount": tree["y_delta"], "children": kids,
            "formula": [k["label"] for k in kids]}


def cut_total(res):
    """The change a cut splits, by operator (engine fields only)."""
    op = res["operator"]
    if op == "additive":
        return res["total_delta"]
    if op == "divisive":
        return res["rate_delta"]
    if op == "second_order_sides":
        return res["gap"]
    raise KeyError(f"cut operator {op} has no page layout yet")


def seg_view(op, g, lab, dim):
    v = {"key": g["key"], "label": lab.value(dim, g["key"])}
    if op == "additive":
        v.update(amount=g["delta"], growth=g["growth"], abs_share=g["abs_share"])
    elif op == "divisive":
        v.update(amount=g["total"], structure=g["structure"], rate=g["rate"], interaction=g["interaction"],
                 rate_base=g["rate_base"], rate_cur=g["rate_cur"], weight_base=g["weight_base"], weight_cur=g["weight_cur"])
    else:
        v.update(amount=g["total"], growth_a=g["growth_a"], growth_b=g["growth_b"], mix=g["mix"], performance=g["performance"])
    return v


def cut_tree(s, lab: Labels, entries):
    """The path the breakdown took through the cuts (state.cuts), one level per cut, siblings collapsed."""
    cuts = [c for c in s["cuts"] if c.get("role", "layer") == "layer"]
    by_path = {tuple(tuple(p) for p in c["path"]): c for c in cuts}
    slots = {(tuple(tuple(p) for p in x["path"]), x["dimension"], x["value"]): x for x in s["slots"]}

    def level(path):
        c = by_path.get(path)
        if c is None:
            return None
        res = c["result"]
        op = res["operator"]
        dec = (c.get("decision") or {}).get("then") or {"action": "drill" if s["slots"] else "stop", "reason": None}
        segs = sorted(res["segments"], key=lambda g: -(g["abs_share"] if "abs_share" in g else abs(g["total"])))
        shown = [g for g in segs if path + ((c["dimension"], g["key"]),) in by_path or (path, c["dimension"], g["key"]) in slots]
        if not shown and dec["action"] == "stop":
            shown = segs[:2]
        groups, separate = [], []
        for g in shown:
            slot = slots.get((path, c["dimension"], g["key"]))
            nxt = level(path + ((c["dimension"], g["key"]),))
            item = {**seg_view(op, g, lab, c["dimension"]), "cause": cause_of(slot, entries) if slot else None,
                    "next": nxt}
            child_cut = by_path.get(path + ((c["dimension"], g["key"]),))
            if op == "divisive" and nxt is not None and child_cut is not None:
                # One account per page: the group's contribution (structure + its own level + overlap) closes on
                # `total`; the cut inside it closes on the group's OWN level change (rate_delta), which is a
                # different account. Drawing them nested made a parent that did not add up.
                item["next"] = None
                separate.append({"label": lab.value(c["dimension"], g["key"]),
                                 "total": cut_total(child_cut["result"]) if child_cut else None, "level": nxt})
            groups.append(item)
        total = cut_total(res)
        rest_n = len(segs) - len(shown)
        # The one sum done here: what the collapsed groups add up to, so the node can carry an amount.
        rest = {"n": rest_n, "amount": total - sum(g["amount"] for g in groups)} if rest_n else None
        out = {"dimension": lab.dim(c["dimension"]), "op": op, "action": dec["action"], "reason": dec["reason"],
               "total": total, "n_groups": len(segs), "groups": groups, "rest": rest, "larger": None,
               "separate": separate}
        if op == "divisive":
            out.update(structure=res["structure_total"], rate=res["rate_total"], interaction=res["interaction_total"],
                       larger=res["larger_effect"])
        if op == "second_order_sides":
            out.update(mix=res["mix_total"], performance=res["performance_total"], larger=res["larger_effect"],
                       growth_a=res["growth_a"], growth_b=res["growth_b"],
                       sides=[lab.value(c["side_dimension"], k) for k in res["sides"]])
        return out

    return level(())


def assert_tree_closes(level, where):
    """Every level of the drawn tree must add up: its groups plus the collapsed rest equal the level's total.
    A page that shows a parent which does not equal its children would break the promise that scripts do the sums."""
    if not level:
        return
    parts = sum(g["amount"] for g in level["groups"]) + ((level["rest"] or {}).get("amount") or 0.0)
    if abs(parts - level["total"]) > 1e-6 * max(1.0, abs(level["total"])):
        raise AssertionError(f"{where}: the drawn groups add to {parts:,.3f} but the level says {level['total']:,.3f}")
    for g in level["groups"]:
        assert_tree_closes(g.get("next"), where)
    for sp in level.get("separate") or []:
        assert_tree_closes(sp.get("level"), where)


def cause_of(slot, entries):
    cites = [entries[c["id"]] | {"id": c["id"], "explains": c.get("explains"), "external": c.get("external"),
                                 "checks": c.get("checks"), "cite_status": c.get("status")}
             for c in slot["citations"]]
    acts = [entries[a] for a in slot.get("actions", [])]
    return {"status": slot["status"], "term": slot["dominant_term"], "citations": cites, "actions": acts,
            "cross_check": slot.get("cross_check")}


def chart_specs(cid, s, lab: Labels, unit, dp, tree):
    """Numbers for every chart of one report, from state.charts / state.cuts / state.pvm. Wording is in templates."""
    ch, out = s["charts"], {}
    main = (s.get("narrative") or {}).get("main") or {}
    ratio = s["metric"] in ("aov", "per_id")
    if "waterfall" in ch:
        w = ch["waterfall"]
        rows = []
        for st in w["steps"]:
            if st.get("label_key") in (None, "others"):
                rows.append({"kind": "others", "n": st["others"], "value": st["value"]})
            else:
                rows.append({"label": lab.value(st["dimension"], st["label_key"]), "value": st["value"],
                             "emph": st["label_key"] == main.get("key") and st["dimension"] == main.get("dimension")})
        rows.append({"kind": "total", "value": w["current"] - w["base"]})
        out[f"{cid}.waterfall"] = {"kind": "waterfall", "unit": unit, "dp": dp, "rows": rows}
    elif tree and tree["op"] == "second_order_sides":
        rows = [{"label": g["label"], "value": g["amount"], "emph": True} for g in tree["groups"]]
        if tree["rest"]:
            rows.append({"kind": "others", "n": tree["rest"]["n"], "value": tree["rest"]["amount"]})
        rows.append({"kind": "total", "value": tree["total"]})
        out[f"{cid}.waterfall"] = {"kind": "waterfall", "unit": unit, "dp": dp, "rows": rows}
    # Per-cut term splits: structure / own level (ratios), mix / performance (two sides).
    k = 0
    node = tree
    while node:
        if node["op"] == "divisive":
            out[f"{cid}.terms{k}"] = {"kind": "waterfall", "unit": unit, "dp": dp, "rows": [
                {"label": {"zh": "结构", "en": "Mix"}, "value": node["structure"]},
                {"label": {"zh": "各组自身", "en": "Own level"}, "value": node["rate"]},
                {"label": {"zh": "两者交叉", "en": "Both together"}, "value": node["interaction"]},
                {"kind": "total", "value": node["total"]}]}
        if node["op"] == "second_order_sides":
            out[f"{cid}.terms{k}"] = {"kind": "waterfall", "unit": unit, "dp": dp, "rows": [
                {"label": {"zh": "结构差", "en": "Mix gap"}, "value": node["mix"]},
                {"label": {"zh": "表现差", "en": "Performance gap"}, "value": node["performance"]},
                {"kind": "total", "value": node["total"]}]}
        k += 1
        nxt = next((g["next"] for g in node["groups"] if g["next"]), None)
        if nxt is None and node.get("separate"):
            nxt = node["separate"][0]["level"]   # a ratio drilled into one group: its own account is the next level
        node = nxt
    if s.get("pvm"):
        pv = s["pvm"]
        out[f"{cid}.pvm"] = {"kind": "waterfall", "unit": unit, "dp": 0, "rows": [
            {"label": {"zh": "卖得多少（量）", "en": "How much sold (volume)"}, "value": pv["volume_total"]},
            {"label": {"zh": "卖了什么（结构）", "en": "What was sold (mix)"}, "value": pv["mix_total"]},
            {"label": {"zh": "卖多少钱（价格）", "en": "At what price (price)"}, "value": pv["price_total"]},
            {"kind": "total", "value": pv["delta"]}]}
    d = ch["daily"]
    out[f"{cid}.daily"] = {"kind": "daily", "unit": "currency", "dp": dp, "current": d["current"], "base": d["base"]}
    r = ch["range"]
    hist = sorted(r["history"], key=lambda h: h["window"][0])
    pts = [{"start": h["window"][0], "change": h["change"]} for h in hist] + [{"start": s["current"][0], "change": r["current_change"]}]
    clipped = s["qualify"].get("unusual_below_clipped")
    out[f"{cid}.range"] = {"kind": "band", "unit": "currency" if ratio else "pct", "dp": dp, "points": pts,
                           "usual": r["usual_range"], "below": None if clipped else r["unusual_below"], "above": r["unusual_above"]}
    out[f"{cid}.spark"] = {"kind": "spark", "series": [p["change"] for p in pts]}
    on = (s.get("narrative") or {}).get("onset") or {}
    if on.get("found"):
        # For a mix-led ratio slot the engine's daily series is the group's weight in its parent (narrative._series_value).
        out[f"{cid}.onset"] = {"kind": "onset", "unit": "points" if ratio else "currency", "dp": dp, "days": on["daily"],
                               "start": on["start"], "before": on["mean_before"], "after": on["mean_after"]}
    return out


def case_view(cid, case, world_params, entries=None):
    s, lab = case["state"], Labels(case)
    entries = entries if entries is not None else case.get("entries", {})
    n = s.get("narrative") or {}
    q = s["qualify"]
    unit, dp = unit_of(s, case)
    ratio = s["metric"] in ("aov", "per_id")
    main = n.get("main")
    slot = next((x for x in s["slots"] if main and x["id"] == main["slot"]), None)
    onset = n.get("onset") or {}
    events = [{**entries[e["event"]], **e} for e in onset.get("events", []) if e["event"] in entries]
    ruled = []
    for r in n.get("ruled_out", []):
        x = dict(r)
        if "dimension" in r:
            x["dimension_label"] = lab.dim(r["dimension"])
            x["filter_labels"] = [lab.value(k, v) for k, v in r.get("filters", {}).items()]
        if r.get("id"):
            x["entry"] = entries[r["id"]]
        ruled.append(x)
    tree = cut_tree(s, lab, entries)
    assert_tree_closes(tree, cid)
    pv = s.get("pvm")
    view = {
        "id": cid, "kind": case.get("kind"), "question": case.get("question"), "metric": lab.metric(s["metric"]),
        "currency": "GBP" if cid == "public" else "CNY",
        "metric_id": s["metric"], "unit": unit, "dp": dp, "ratio": ratio, "current": s["current"], "base": s["base"],
        "base_kind": s["config"].get("base"), "filters": [lab.value(k, v) for k, v in s.get("filters", {}).items()],
        # For a ratio (order value) the engine's "change" is the difference in yuan, not a growth rate.
        "total": {"base": q["total_base"], "cur": q["total_cur"], "change": q["current_change"],
                  "delta": (s.get("tree") or {}).get("y_delta", tree["total"] if tree and tree["op"] != "second_order_sides" else None),
                  "growth": None if ratio else q["current_change"]},
        "q": q, "verdict": s["verdict_unusual"]["then"]["verdict"],
        "z_line": world_params["unusual_z"], "history_n": q["history_n"], "left_out": q["history_basis"]["left_out_for_holidays"],
        "range": s["charts"]["range"], "narrative": n, "main": main, "secondary": n.get("secondary"),
        "main_label": lab.value(main["dimension"], main["key"]) if main else None,
        "main_dim": lab.dim(main["dimension"]) if main else None,
        "secondary_label": lab.value(n["secondary"]["dimension"], n["secondary"]["key"]) if n.get("secondary") else None,
        "cause": cause_of(slot, entries) if slot else None,
        "offsets": [{**o, "label": lab.value(o["dimension"], o["key"])} for o in n.get("offsets", [])],
        "rest": n.get("rest"), "onset": onset, "events": events, "ruled_out": ruled, "market": n.get("market"),
        "recent_weeks": n.get("recent_weeks", []),
        "formula": formula_tree(s, lab), "cuts": tree,
        "factors": [{**f, "label": lab.metric(f["factor"])} for f in (s["horizontal"][0]["factors"] if s["horizontal"] else [])],
        "checks": s["checks"], "quality": s["quality"], "gaps": s["gaps"],
        "to_confirm": [{**t, "entry": entries.get(t["id"])} for t in s["to_confirm"]],
        "pvm": ({**pv, "dimension_label": lab.dim(pv["dimension"]),
                 "segments": [{**g, "label": lab.value(pv["dimension"], g["key"])} for g in pv["segments"]]} if pv else None),
        "calendar": q.get("calendar"), "labels": case["labels"], "entries": entries,
    }
    return view, chart_specs(cid, s, lab, unit, dp, tree)


# ---------------------------------------------------------------- home page

def _check(quality, name):
    return next(c for c in quality["checks"] if c["check"] == name)


def unsure_view(u):
    miss = _check(u["missing_two_days"]["quality"], "calendar_complete")
    dup = _check(u["week_loaded_twice"]["quality"], "key_unique")["duplicates"][0]
    for k in ("pure_noise_week", "missing_two_days", "week_loaded_twice"):
        if not u[k]["ok"]:
            raise AssertionError(f"adversarial case {k} no longer behaves as expected; the home page would be wrong")
    return {"noise": u["pure_noise_week"], "noise_weeks": u["noise_weeks"],
            "missing": {"days": miss["missing"]["current"], "blocked": u["missing_two_days"]["blocked"]},
            "dup": {"rows": dup["rows"], "duplicates": dup["duplicates"], "blocked": u["week_loaded_twice"]["blocked"]}}


def intake_summary(d):
    """From the intake run sitedata.collect() just did (demo/intake/run_intake.py -> formation.json)."""
    return {"tables": len(d["draft"]["tables"]), "counts": d["formation"]["counts"]}


def tone_of(state):
    """confirmed / pending / none for one case, from the slots' status and the records they cite."""
    if not state["slots"]:
        return "none"
    tones = []
    for slot in state["slots"]:
        if slot["status"] != "explained":
            tones.append("none" if slot["status"] == "gap" else "pending")
            continue
        sure = all(not c.get("checks") and c.get("status") == "confirmed" for c in slot.get("citations", []))
        tones.append("confirmed" if sure else "pending")
    if all(t == "confirmed" for t in tones):
        return "confirmed"
    if any(t in ("confirmed", "pending") for t in tones):
        return "pending"
    return "none"


def home_view(data, views):
    pub = data["public"]["state"]
    learn = data["learning"]
    statuses = {cid: [x["status"] for x in data["cases"][cid]["state"]["slots"]] for cid in CASE_IDS}
    return {
        "unsure": unsure_view(data["unsure"]),
        "world": data["world"],
        "statuses": statuses,
        "explained": sum(1 for v in statuses.values() if v and all(x == "explained" for x in v)),
        # a cause counts as confirmed only when every record behind it is confirmed and none is an outside event
        # judged by the three checks; those stay hypotheses, and the home card says so rather than calling them found
        "confirmed": sum(1 for cid in CASE_IDS if tone_of(data["cases"][cid]["state"]) == "confirmed"),
        "pending": sum(1 for cid in CASE_IDS if tone_of(data["cases"][cid]["state"]) == "pending"),
        "none": sum(1 for cid in CASE_IDS if tone_of(data["cases"][cid]["state"]) == "none"),
        "gap_cases": [cid for cid, v in statuses.items() if "gap" in v],
        "public": {"verdict": pub["verdict_unusual"]["then"]["verdict"], "change": pub["qualify"]["current_change"],
                   "invoices": data["public"]["source"]["invoices"], "current": pub["current"]},
        "learning": {"before": learn["before"]["coverage"], "after": learn["after"]["coverage"],
                     "caught": learn["forget"]["caught"], "regress": len(learn["regress"])},
        "intake": intake_summary(data["intake"]),
        "n_checks": len(data["cases"]["revenue_last_week"]["state"]["checks"]),
        "rev": views["revenue_last_week"],
    }


# ---------------------------------------------------------------- rendering

def page_ctx(path: str, lang: str, nav_active: str) -> dict:
    """path is inside a language root, e.g. "index.html" or "reports/x.html"."""
    rel = path if lang == "zh" else "en/" + path
    depth = rel.count("/")
    root = "../" * depth
    alt_rel = "en/" + path if lang == "zh" else path
    return {"lang": lang, "zh": lang == "zh", "root": root, "alt_href": root + alt_rel, "nav_active": nav_active,
            "path": path, "out": rel}


def render(env, template, ctx, extra):
    html = env.get_template(template).render({**extra, **ctx})
    out = DIST / ctx["out"]
    folder = out.parent
    folder.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return ctx["out"]


def write_assets(data, charts):
    a = DIST / "assets"
    shutil.copytree(SITE / "assets", a, dirs_exist_ok=True)
    payload = {"charts": charts, "meta": data["meta"]}
    (a / "site-data.js").write_text(
        "// Written by site/build.py from this build's engine runs. Do not edit.\n"
        "window.AIB_SITE = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
        "window.AIB_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def more_pages():
    if importlib.util.find_spec("pages_more") is None:
        return None
    import pages_more
    return pages_more


def build():
    data = sitedata.collect()
    params = {p["id"]: p["value"] for p in data["world"]["params"]}
    only = list(CASE_IDS)
    views, charts = {}, {}
    for cid in only:
        views[cid], c = case_view(cid, data["cases"][cid], params)
        charts.update(c)
    pub = data["public"]
    views["public"], c = case_view("public", {"state": pub["state"], "labels": pub["labels"], "kind": "public",
                                              "question": None, "entries": {}}, params)
    charts.update(c)
    home = home_view(data, views)
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    env = make_env()
    env.globals["site_meta"] = {**data["meta"], "footer": {
        "zh": "演示店「花果篮」是虚构的，数据由程序生成；页面上每个数字都来自这次构建时引擎的运行结果。",
        "en": "The demo shop, Bloom & Basket, is fictional and its data is generated; every number on this site comes from the engine's runs at build time."}}
    written = []
    for lang in LANGS:
        written.append(render(env, "home.html.j2", page_ctx("index.html", lang, "home"), {"h": home, "data": data}))
        for cid in only:
            written.append(render(env, "report.html.j2", page_ctx(f"reports/{cid}.html", lang, "reports"),
                                  {"v": views[cid], "data": data}))
        written.append(render(env, "public.html.j2", page_ctx("reports/public.html", lang, "public"),
                              {"v": views["public"], "pub": data["public"], "data": data, "currency": "GBP"}))
    # Assets first: if the other builder's pages fail, the build still fails, but these pages stay usable to inspect.
    write_assets(data, charts)
    pm = more_pages()
    if pm is not None:
        for lang in LANGS:
            for p in pm.pages(data, lang):
                ctx = page_ctx(p["path"], lang, p.get("nav_active", p["path"].split(".")[0]))
                ctx.update({k: v for k, v in p.items() if k in ("nav_active",)})
                written.append(render(env, p["template"], ctx, p["context"]))
    print(f"built {len(written)} pages into {DIST.relative_to(ROOT)}; engine at {data['meta']['git_head']}"
          f"{' (uncommitted engine changes)' if data['meta']['engine_has_uncommitted_changes'] else ''}")
    return written


if __name__ == "__main__":
    build()
