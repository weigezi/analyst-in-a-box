"""Data and layout for the business knowledge graph page (and, later, intake / learning / architecture). No wording here.

Two views of the demo shop's workspace, laid out at build time so the page never runs a force simulation:

- tree: the metric tree from model.yaml (north_star, identities, metrics, priorities), left to right by formula depth;
- world: world.yaml in lanes, events -> mechanisms -> entities (grouped by dimension) -> metrics -> actions.

Each demo question's path (cuts, slots, citations, actions from its run state, as returned by sitedata.store_cases)
becomes a set of node ids to light on each view, plus an ordered list of steps.

Sizes are estimated from text length (CJK one em, Latin about half) with a safety margin; the browser check
(tools/browser-check/pages-more.json) verifies that nothing overlaps or overflows in the real fonts.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DEMO_WS = ROOT / "demo" / "store" / "workspace"
for p in (ROOT / "skills" / "analyst-in-a-box" / "scripts",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from aib.explain import entry_text  # noqa: E402
from aib.workspace import Workspace, label  # noqa: E402

LANGS = ("zh", "en")
CANVAS_W = 1104          # content width of the .wrap at 1440 (1152 - 2 * 24)


# ---------------------------------------------------------------- text size estimates

def text_w(s: str, px: float) -> float:
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o >= 0x2E80:
            w += 1.0
        elif ch == " ":
            w += 0.28
        elif ch.isupper() or ch in "%¥€$":
            w += 0.68
        elif ch.isdigit():
            w += 0.6
        elif ch in ",.;:'’()·-":
            w += 0.32
        else:
            w += 0.56
    return w * px * 1.03


def lines(s: str, px: float, width: float) -> int:
    """Greedy wrap: Latin breaks at spaces, CJK at any character."""
    if not s:
        return 0
    n, cur = 1, 0.0
    tokens, buf = [], ""
    for ch in s:
        if ord(ch) >= 0x2E80:
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch == " ":
            tokens.append(buf + " ")
            buf = ""
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    for t in tokens:
        w = text_w(t, px)
        if cur + w > width and cur > 0:
            n += 1
            cur = w if not t.endswith(" ") else w
        else:
            cur += w
    return n


def resolve(items: list[dict], gap: float, top: float = 0.0) -> None:
    """Keep each box near its wanted y, in wanted order, without overlap (push down, then pull the column up
    if it ran past where the boxes wanted to be)."""
    items.sort(key=lambda b: b["want"])
    y = top
    for b in items:
        b["y"] = max(b["want"] - b["h"] / 2, y)
        y = b["y"] + b["h"] + gap
    if items:
        over = items[-1]["y"] + items[-1]["h"] / 2 - items[-1]["want"]
        if over > 0:
            # shift the whole run up as far as the top allows, keeping the gaps
            shift = min(over / 2, items[0]["y"] - top)
            for b in items:
                b["y"] -= max(shift, 0)


def curve(a: dict, b: dict) -> dict:
    """A horizontal S-curve from the right edge of the left box to the left edge of the right box."""
    if a["x"] > b["x"]:
        a, b = b, a
    x1, y1 = a["x"] + a["w"], a["y"] + a["h"] / 2
    x2, y2 = b["x"], b["y"] + b["h"] / 2
    k = max((x2 - x1) * 0.5, 12)
    return {"d": f"M{x1:.1f},{y1:.1f} C{x1 + k:.1f},{y1:.1f} {x2 - k:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"}


# ---------------------------------------------------------------- the metric tree

def _definitional(ws, ident) -> bool:
    """True when the identity holds by the metrics' own definitions (a factor is left / another factor)."""
    for f in ident["factors"]:
        spec = ws.metrics.get(f, {})
        if spec.get("kind") == "ratio":
            others = [x for x in ident["factors"] if x != f]
            if spec.get("numerator") == ident["left"] and spec.get("denominator") in others:
                return True
    return False


def dimension_rule(ws, m: str) -> dict:
    """How the engine picks the next cut for metric m (aib/run.py _order and step_vertical)."""
    pr = (ws.model.get("priorities") or {}).get(m) or {}
    allowed = ws.metric_dimensions(m)
    order = [d for d in (pr.get("order") or []) if d in allowed]
    mode = pr.get("mode", "drill")
    confirmed = pr.get("status") == "confirmed"
    if order and mode == "each":
        rule = "each"                      # every listed dimension is cut once, in this order
    elif order and mode == "fixed":
        rule = "fixed"                     # cut in this order, no scoring
    elif order and confirmed:
        rule = "first_fixed"               # the first cut is fixed, later layers are scored among the rest
    else:
        rule = "scored"                    # every layer picks the best-scoring dimension
    if order:
        dims = [{"dim": d, "rank": i + 1} for i, d in enumerate(order)]
        left_out = sorted(allowed - set(order), key=lambda d: list(ws.dimensions).index(d))
    else:
        dims = [{"dim": d, "rank": None} for d in sorted(allowed, key=lambda d: list(ws.dimensions).index(d))]
        left_out = []
    return {"rule": rule, "dims": dims, "left_out": left_out,
            "source": (pr.get("source") or {}).get("kind") if order else None,
            "status": pr.get("status") if order else None}


def metric_tree(ws) -> dict:
    ns = ws.model.get("north_star")
    idents = ws.model.get("identities", [])
    by_left = {i["left"]: i for i in idents if i.get("operator") == "multiply"}
    order, depth, parent = [], {}, {}

    def walk(m, d):
        if m in depth:
            return
        depth[m] = d
        order.append(m)
        for f in (by_left[m]["factors"] if m in by_left else []):
            if f not in depth:
                parent[f] = m
                walk(f, d + 1)

    walk(ns, 0)
    for m in ws.metrics:                  # metrics no formula reaches still get a card, one column further out
        if m not in depth:
            depth[m] = max(depth.values()) + 1
            order.append(m)
    nodes = {}
    for m in order:
        spec = ws.metrics[m]
        ident = by_left.get(m)
        nodes[m] = {
            "id": f"m:{m}", "metric": m, "label": {lg: label(spec.get("label", m), lg) for lg in LANGS},
            "kind": spec.get("kind", "sum"), "unit": spec.get("unit"), "depth": depth[m], "parent": parent.get(m),
            "ratio": {"numerator": spec["numerator"], "denominator": spec["denominator"]} if spec.get("kind") == "ratio" else None,
            "identity": ({"id": ident["id"], "factors": ident["factors"], "source": (ident.get("source") or {}).get("kind"),
                          "status": ident.get("status"), "definitional": _definitional(ws, ident)} if ident else None),
            "dims": dimension_rule(ws, m),
        }
    return {"north_star": ns, "order": order, "nodes": nodes}


TREE = {"w": 236, "pad": 12, "title": 22, "sub_px": 13, "sub_lh": 20, "gap_in": 10, "chip_h": 24, "chip_pitch": 28,
        "rule_px": 12, "rule_lh": 18, "vgap": 28}


def tree_layout(tree: dict, lang: str, sub_text, rule_text, chip_text) -> dict:
    """Card positions for one language. sub_text / rule_text / chip_text are the page's wording functions, so the
    estimate measures the words that will actually be shown."""
    T = TREE
    inner = T["w"] - 2 * T["pad"]
    max_depth = max(n["depth"] for n in tree["nodes"].values())
    step = (CANVAS_W - T["w"]) / max(max_depth, 1)
    boxes = {}
    for m, n in tree["nodes"].items():
        chips = [chip_text(n, d, lang) for d in n["dims"]["dims"]]
        half = (inner - 6) / 2
        cols = 2 if all(text_w(c, 12) + 30 <= half for c in chips) else 1
        rows = math.ceil(len(chips) / cols)
        h = (T["pad"] + T["title"] + lines(sub_text(n, lang), T["sub_px"], inner) * T["sub_lh"] + T["gap_in"]
             + rows * T["chip_pitch"] + lines(rule_text(n, lang), T["rule_px"], inner) * T["rule_lh"] + 4 + T["pad"])
        boxes[m] = {"x": round(n["depth"] * step), "w": T["w"], "h": math.ceil(h), "chip_cols": cols}
    # tidy tree: leaves stacked in walk order, parents centred on their children
    kids = {m: [k for k, x in tree["nodes"].items() if x["parent"] == m] for m in tree["nodes"]}
    y = [0.0]

    def place(m):
        ch = kids[m]
        if not ch:
            boxes[m]["y"] = y[0]
            y[0] += boxes[m]["h"] + T["vgap"]
            return
        for k in ch:
            place(k)
        first, last = boxes[ch[0]], boxes[ch[-1]]
        mid = (first["y"] + first["h"] / 2 + last["y"] + last["h"] / 2) / 2
        boxes[m]["y"] = mid - boxes[m]["h"] / 2

    roots = [m for m, n in tree["nodes"].items() if n["parent"] is None]
    for r in roots:
        place(r)
    # a parent centred on its children can collide with a leaf in the same column: push down, column by column
    for d in range(max_depth + 1):
        col = sorted((b for m, b in boxes.items() if tree["nodes"][m]["depth"] == d), key=lambda b: b["y"])
        for a, b in zip(col, col[1:]):
            if b["y"] < a["y"] + a["h"] + T["vgap"]:
                b["y"] = a["y"] + a["h"] + T["vgap"]
    top = min(b["y"] for b in boxes.values())
    for b in boxes.values():
        b["y"] = round(b["y"] - top)
    edges = []
    for m, n in tree["nodes"].items():
        if not n["identity"]:
            continue
        a = boxes[m]
        x1, y1 = a["x"] + a["w"], a["y"] + a["h"] / 2
        xm = x1 + (step - T["w"]) / 2
        for f in n["identity"]["factors"]:
            b = boxes[f]
            y2 = b["y"] + b["h"] / 2
            edges.append({"id": f"t:{m}>{f}", "from": f"m:{m}", "to": f"m:{f}",
                          "d": f"M{x1},{y1:.1f} H{xm:.1f} V{y2:.1f} H{b['x']}"})
        edges.append({"id": f"op:{m}", "op": True, "from": f"m:{m}", "x": round(xm, 1), "y": round(y1, 1)})
    height = max(b["y"] + b["h"] for b in boxes.values())
    return {"boxes": {f"m:{m}": b for m, b in boxes.items()}, "edges": edges, "w": CANVAS_W, "h": height}
# ---------------------------------------------------------------- the business world description

def world_model(ws) -> dict:
    w = ws.world
    ents = {e["id"]: e for e in w.get("entities", [])}

    def src(x):
        s = x.get("source") or {}
        lab = s.get("label")
        return {"kind": s.get("kind"), "ref": s.get("ref"),
                "label": {lg: label(lab, lg) for lg in LANGS} if lab else None}

    out = {"entities": {}, "relations": [], "mechanisms": [], "events": [], "actions": []}
    for e in ents.values():
        out["entities"][e["id"]] = {"id": f"e:{e['id']}", "entity": e["id"], "label": {lg: label(e.get("label", e["id"]), lg) for lg in LANGS},
                                    "dimension": e.get("dimension"), "external": bool(e.get("external")),
                                    "source": src(e), "status": e.get("status")}
    for r in w.get("relations", []):
        out["relations"].append({"id": f"r:{r['id']}", "subject": r["subject"], "object": r["object"], "predicate": r["predicate"],
                                 "source": src(r), "status": r.get("status"),
                                 "dims": (ents[r["subject"]].get("dimension"), ents[r["object"]].get("dimension"))})
    for bucket, kind in (("mechanisms", "mechanism"), ("events", "event"), ("actions", "action")):
        for x in w.get(bucket, []):
            row = {"id": f"w:{x['id']}", "entry": x["id"], "kind": kind, "text": {lg: entry_text(x, lg) for lg in LANGS},
                   "entities": list(x.get("entities", [])), "metrics": list(x.get("metrics", [])),
                   "source": src(x), "status": x.get("status"), "external": x.get("kind") == "external",
                   "refuted_by": {lg: label(x["refuted_by"], lg) for lg in LANGS} if x.get("refuted_by") else None}
            if kind == "event":
                row["start"] = str(x["start"]) if x.get("start") else None
                row["end"] = str(x.get("end") or x.get("start")) if x.get("start") else None
            if kind == "action":
                row["owner"] = {lg: label(x.get("owner", ""), lg) for lg in LANGS}
            out[bucket].append(row)
    return out


def _d(s) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def world_layout(world: dict, ws, tree: dict, cases: dict, lang: str, group_text, card_text) -> dict:
    """Lanes left to right: events (on a time axis), mechanisms, entities by dimension, metrics, actions and owners.

    group_text(kind, dim, lang) and card_text(row, lang) return the words the page shows, so sizes are measured on them."""
    ents = world["entities"]
    pill_px, pill_pad, pill_h, pitch = 13, 10, 26, 32
    pill = lambda s: math.ceil(text_w(s, pill_px) + 2 * pill_pad)  # noqa: E731

    # children: a dimension whose values belong to another dimension's values sits in the right half of that group
    child_of = {}
    for r in world["relations"]:
        a, b = r["dims"]
        if r["predicate"] == "belongs_to" and a and b and a != b:
            child_of[a] = b
    attached = {}                         # outside entity -> the entity it is reached through
    for r in world["relations"]:
        s, o = ents[r["subject"]], ents[r["object"]]
        if o["external"] and s["dimension"]:
            attached[r["object"]] = r["subject"]
    groups = []
    for d in ws.dimensions:
        if d in child_of:
            continue
        left = [e for e in ents.values() if e["dimension"] == d]
        if not left:
            continue
        kid = next((c for c, p in child_of.items() if p == d), None)
        groups.append({"dim": d, "child": kid, "left": left,
                       "right": [e for e in ents.values() if e["dimension"] == kid] if kid else
                                [ents[x] for x, via in attached.items() if ents[via]["dimension"] == d]})
    loose = [e for e in ents.values() if e["external"] and e["entity"] not in attached]
    if loose:
        groups.append({"dim": None, "child": None, "left": loose, "right": []})

    # lane widths: the pill lanes fit their longest label, the text lanes share what is left
    lw = max(pill(e["label"][lang]) for g in groups for e in g["left"])
    rw = max([pill(e["label"][lang]) for g in groups for e in g["right"]] or [0])
    mw = max([pill(n["label"][lang]) for n in tree["nodes"].values()] + [104])   # wide enough for the lane heading
    sub_gap, gap = 14, 28
    ent_w = lw + (sub_gap + rw if rw else 0)
    flex = CANVAS_W - ent_w - mw - 4 * gap
    ev_w, me_w = round(flex * 0.36), round(flex * 0.32)
    ac_w = flex - ev_w - me_w
    x = {"event": 0}
    x["mechanism"] = ev_w + gap
    x["entity"] = x["mechanism"] + me_w + gap
    x["entity_r"] = x["entity"] + lw + sub_gap
    x["metric"] = x["entity"] + ent_w + gap
    x["action"] = x["metric"] + mw + gap
    lanes = [{"kind": k, "x": x[k], "w": w} for k, w in
             (("event", ev_w), ("mechanism", me_w), ("entity", ent_w), ("metric", mw), ("action", ac_w))]

    top, head_h, group_gap = 44, 24, 18
    boxes = {}
    y = top
    group_heads = []
    for g in groups:
        group_heads.append({"dim": g["dim"], "child": g["child"], "x": x["entity"], "y": y, "w": ent_w,
                            "text": group_text(g, lang)})
        y += head_h
        if g["child"]:
            row = 0
            for p in g["left"]:
                kids = [c for c in g["right"] if any(r["subject"] == c["entity"] and r["object"] == p["entity"]
                                                     for r in world["relations"])]
                n = max(len(kids), 1)
                boxes[p["id"]] = {"x": x["entity"], "y": y + row * pitch + (n * pitch - 6 - pill_h) / 2, "w": lw, "h": pill_h}
                for i, c in enumerate(kids):
                    boxes[c["id"]] = {"x": x["entity_r"], "y": y + (row + i) * pitch, "w": rw, "h": pill_h}
                row += n
            y += row * pitch
        else:
            for i, e in enumerate(g["left"]):
                boxes[e["id"]] = {"x": x["entity"], "y": y + i * pitch, "w": lw, "h": pill_h}
            for e in g["right"]:
                via = boxes[f"e:{attached[e['entity']]}"]
                boxes[e["id"]] = {"x": x["entity_r"], "y": via["y"], "w": rw, "h": pill_h}
            y += len(g["left"]) * pitch
        y += group_gap
    ent_bottom = y - group_gap

    def card(row, lane, pad=10, extra=0):
        """card_text gives [(text, font px, line height)]; padding and the 1px border match graphmap.css .gm-card."""
        w = lane["w"]
        h = 2 * pad + 2 + extra + sum(lines(s, px, w - 2 * pad - 2) * lh for s, px, lh in card_text(row, lang))
        return {"w": w, "h": math.ceil(h)}

    lane = {l["kind"]: l for l in lanes}
    center = lambda ids: sum(boxes[i]["y"] + boxes[i]["h"] / 2 for i in ids) / len(ids)  # noqa: E731

    # mechanisms and actions sit level with the entities they are about
    for kind, bucket in (("mechanism", "mechanisms"), ("action", "actions")):
        col = []
        for row in world[bucket]:
            b = card(row, lane[kind], extra=6 + (26 if row["status"] == "proposed" else 0))
            ids = [f"e:{e}" for e in row["entities"] if f"e:{e}" in boxes]
            col.append({**b, "id": row["id"], "x": lane[kind]["x"], "want": center(ids) if ids else top})
        resolve(col, 14, top)
        for b in col:
            boxes[b["id"]] = {k: (round(b[k], 1) if k == "y" else b[k]) for k in ("x", "y", "w", "h")}

    # events on a time axis: the axis spans the events and every demo question's period
    dates = [_d(e[k]) for e in world["events"] for k in ("start", "end") if e.get(k)]
    for c in cases.values():
        dates += [_d(c["state"]["current"][0]), _d(c["state"]["current"][1])]
    d0, d1 = min(dates) - dt.timedelta(days=6), max(dates) + dt.timedelta(days=6)
    axis_len = max(ent_bottom - top, 120)
    ty = lambda d: top + (_d(d) - d0).days / max((d1 - d0).days, 1) * axis_len  # noqa: E731
    # month labels sit left of the axis, cards to its right, so a label never falls under a card
    axis_x = lane["event"]["x"] + 36
    ev_lane = {"x": axis_x + 14, "w": lane["event"]["w"] - 50}
    col = []
    for row in world["events"]:
        b = card(row, ev_lane, extra=6 + (26 if row["status"] == "proposed" else 0))
        mid = (ty(row["start"]) + ty(row["end"])) / 2
        col.append({**b, "id": row["id"], "x": ev_lane["x"], "want": mid, "t0": ty(row["start"]), "t1": ty(row["end"])})
    resolve(col, 12, top)
    leaders = []
    for b in col:
        boxes[b["id"]] = {"x": b["x"], "y": round(b["y"], 1), "w": b["w"], "h": b["h"]}
        tm = (b["t0"] + b["t1"]) / 2
        leaders.append({"id": f"l:{b['id']}", "for": b["id"], "t0": round(b["t0"], 1), "t1": round(max(b["t1"], b["t0"] + 3), 1),
                        "d": f"M{axis_x},{tm:.1f} C{axis_x + 10},{tm:.1f} {b['x'] - 10},{b['y'] + b['h'] / 2:.1f} {b['x']},{b['y'] + b['h'] / 2:.1f}"})
    ticks, m = [], dt.date(d0.year, d0.month, 1)
    while m <= d1:
        if m >= d0:
            ticks.append({"date": m.isoformat(), "y": round(ty(m), 1)})
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    windows = {k: {"y0": round(ty(c["state"]["current"][0]), 1), "y1": round(ty(c["state"]["current"][1]), 1),
                   "from": c["state"]["current"][0], "to": c["state"]["current"][1]} for k, c in cases.items()}

    # metrics, in the order of the tree
    for i, m in enumerate(tree["order"]):
        n = tree["nodes"][m]
        boxes[n["id"]] = {"x": x["metric"], "y": top + i * pitch, "w": mw, "h": pill_h}

    edges = []
    for r in world["relations"]:
        edges.append({"id": r["id"], "from": f"e:{r['subject']}", "to": f"e:{r['object']}", "kind": r["predicate"], "shown": True,
                      **curve(boxes[f"e:{r['subject']}"], boxes[f"e:{r['object']}"])})
    for bucket in ("events", "mechanisms", "actions"):
        for row in world[bucket]:
            for e in row["entities"]:
                if f"e:{e}" in boxes:
                    edges.append({"id": f"{row['id']}>{e}", "from": row["id"], "to": f"e:{e}", "kind": row["kind"], "shown": True,
                                  **curve(boxes[row["id"]], boxes[f"e:{e}"])})
            for m in row["metrics"]:
                if f"m:{m}" in boxes:
                    # crosses the entity lane, so it is drawn only when one of its ends is picked
                    edges.append({"id": f"{row['id']}>m:{m}", "from": row["id"], "to": f"m:{m}", "kind": "affects", "shown": False,
                                  **curve(boxes[row["id"]], boxes[f"m:{m}"])})
    for i, b in enumerate(boxes.values()):        # layout order: a parent before its children, for the phone list
        b["seq"] = i
    height = math.ceil(max(b["y"] + b["h"] for b in boxes.values()) + 8)
    return {"w": CANVAS_W, "h": max(height, top + axis_len + 8), "lanes": lanes, "groups": group_heads,
            "boxes": {k: {kk: (round(v, 1) if isinstance(v, float) else v) for kk, v in b.items()} for k, b in boxes.items()},
            "edges": edges, "axis": {"x": axis_x, "y0": top, "y1": round(top + axis_len, 1), "ticks": ticks, "leaders": leaders,
                                     "windows": windows}}


# ---------------------------------------------------------------- one question's path

def case_path(c: dict, ws, tree: dict) -> dict:
    """What a demo question's run went through, as node ids per view and an ordered list of steps.
    Every number is a field of the run state; nothing is recomputed here."""
    from aib.explain import World
    world = World(ws)
    s = c["state"]
    m = s["metric"]
    ent = lambda d, v: world.entity_for(d, v)  # noqa: E731
    tree_lit, world_lit, chips, scope_chips, values = {f"m:{m}"}, {f"m:{m}"}, set(), set(), {}
    for d, v in s.get("filters", {}).items():
        scope_chips.add(f"c:{m}:{d}")
        if ent(d, v):
            world_lit.add(f"e:{ent(d, v)}")
    steps = [{"kind": "scope", "metric": m, "filters": s.get("filters", {}), "current": s["current"], "base": s["base"],
              "order": s.get("order"), "sides": None}]
    side_dim, sides = None, None
    for cut in s["cuts"]:
        if cut.get("sides"):
            side_dim, sides = cut["side_dimension"], cut["sides"]
    if sides:
        steps[0]["sides"] = {"dimension": side_dim, "values": sides}
        for v in sides:
            if ent(side_dim, v):
                world_lit.add(f"e:{ent(side_dim, v)}")
    tr = s.get("tree")
    if tr:
        for ident in tr["identities"]:
            i = next(x for x in ws.model["identities"] if x["id"] == ident)
            tree_lit |= {f"m:{i['left']}"} | {f"m:{f}" for f in i["factors"]}
        # amounts are in the asked metric's unit: the first identity's factors, then the leaves of the whole tree
        for f in s.get("horizontal", []):
            if f["parent"] == m:
                for x in f["factors"]:
                    values[f"m:{x['factor']}"] = x["contribution"]
        for leaf in tr["leaves"]:
            values[f"m:{leaf['factor']}"] = leaf["contribution"]
        values[f"m:{m}"] = tr["y_delta"]
        steps.append({"kind": "formula", "metric": m, "total": tr["y_delta"], "dominant": tr["dominant_factor"],
                      "leaves": [{"metric": x["factor"], "value": x["contribution"]} for x in tr["leaves"]]})
    if c["kind"] == "pvm" and s.get("pvm"):
        p = s["pvm"]
        steps.append({"kind": "pvm", "metric": m, "dimension": p["dimension"], "quantity": p["quantity"], "total": p["delta"],
                      "volume": p["volume_total"], "price": p["price_total"], "mix": p["mix_total"], "larger": p["larger_effect"],
                      "quantity_growth": p["quantity_growth"]})
    for cut in s["cuts"]:
        r = cut["result"]
        chip = f"c:{m}:{cut['dimension']}"
        chips.add(chip)
        drill = cut["decision"]["then"].get("action") == "drill"
        top = next(x for x in r["segments"] if x["key"] == r["top1_key"])
        if r["operator"] == "additive":
            amount, unit = top["delta"], ws.metrics[m].get("unit")
        elif r["operator"] == "divisive":
            amount, unit = top["total"], ws.metrics[m].get("unit")
        else:
            # two sides: each segment's part of the growth gap, in growth points (operators.md section 3)
            amount, unit = top["total"], "growth_points"
        within = [(d, v) for d, v in cut["path"]] or [(d, v) for d, v in cut["filters"].items() if d not in s.get("filters", {})]
        for d, v in within:
            if ent(d, v):
                world_lit.add(f"e:{ent(d, v)}")
        if drill and ent(cut["dimension"], r["top1_key"]):
            world_lit.add(f"e:{ent(cut['dimension'], r['top1_key'])}")
        steps.append({"kind": "cut", "chip": chip, "dimension": cut["dimension"], "within": within, "drill": drill,
                      "reason": cut["decision"]["then"].get("reason"), "top": r["top1_key"], "amount": amount, "unit": unit,
                      "share": top.get("share"), "operator": r["operator"],
                      "sides": ({"a": r["sides"][0], "b": r["sides"][1], "growth_a": r["growth_a"], "growth_b": r["growth_b"],
                                 "gap": r["gap"], "mix": r["mix_total"], "performance": r["performance_total"],
                                 "larger": r["larger_effect"], "top_mix": top.get("mix"), "top_performance": top.get("performance"),
                                 "dimension": cut["side_dimension"]} if cut.get("sides") else None)})
    whys = []
    for slot in s["slots"]:
        world_lit |= {f"e:{e}" for e in slot["context"]}
        cites = []
        for cc in slot["citations"]:
            world_lit.add(f"w:{cc['id']}")
            cites.append({"id": cc["id"], "node": f"w:{cc['id']}", "kind": cc["kind"], "explains": cc.get("explains"),
                          "status": cc.get("status"), "external": bool(cc.get("external")),
                          "checks": (cc.get("checks") or {}).get("status")})
        whys.append({"slot": slot["id"], "status": slot["status"], "citations": cites})
    steps.append({"kind": "why", "slots": whys})
    acts = []
    for a in s.get("actions", []):
        world_lit.add(f"w:{a}")
        acts.append({"id": a, "node": f"w:{a}"})
    steps.append({"kind": "act", "actions": acts})
    return {"id": c["id"], "kind": c["kind"], "question": c["question"], "metric": m,
            "tree": sorted(tree_lit), "chips": sorted(chips), "scope_chips": sorted(scope_chips - chips),
            "world": sorted(world_lit), "values": values, "steps": steps, "labels": c["labels"], "entries": c["entries"],
            "unit": c["unit"]}


# ---------------------------------------------------------------- intake: from several tables to a first report

INTAKE = ROOT / "demo" / "intake"


def _head(path: Path, n: int = 3) -> dict:
    """Column names and the first n rows of a CSV (plain or gzipped), read as text."""
    import csv
    import gzip
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        cols = next(r)
        rows = [row for _, row in zip(range(n), r)]
    return {"columns": cols, "rows": rows}


def intake() -> dict:
    """What demo/intake/run_intake.py formed (formation.json, written at the start of the build), plus what the page
    shows next to it: each table's first rows, the questions in English (init run again on a copy of the tables,
    lang="en"), the weekly report, and the formed workspace read back. Wording that formation_report.py already
    has in both languages (what only a person can add, where it does not match) is passed through, not retyped."""
    import json
    import shutil
    import tempfile

    import yaml
    from aib import intake as ik
    if str(INTAKE) not in sys.path:
        sys.path.insert(0, str(INTAKE))
    import formation_report as FR
    import run_intake as RI

    facts = json.loads((INTAKE / "formation.json").read_text(encoding="utf-8"))
    d = facts["draft"]
    kinds = facts["confirm"]["intake"]["kinds"]
    tables = []
    for name, t in d["tables"].items():
        path = (INTAKE / "workspace" / t["path"]).resolve()
        h = _head(path)
        names = {x["column"]: x.get("name") or {"zh": x["column"], "en": x["column"]} for x in t["profile"]}
        cols = [{"label": names.get(c) or {"zh": c, "en": c}, "raw": c} for c in h["columns"]]
        tables.append({"name": name, "file": path.name, "rows": t["rows"], "suggested": t["suggested_kind"],
                       "answered": kinds.get(name), "columns": cols, "sample": h["rows"]})
    tables.sort(key=lambda t: (t["suggested"] != "main", -t["rows"]))
    with tempfile.TemporaryDirectory() as scratch:
        src = Path(scratch) / "tables"
        shutil.copytree(INTAKE / "tables", src)
        en = ik.init([src], Path(scratch) / "ws", lang="en")
    readable = {}
    for t in d["tables"].values():
        for x in t["profile"]:
            readable[x["column"]] = x.get("name") or {"zh": x["column"], "en": x["column"]}
    def readable_questions(qs, lg):
        out = []
        for q in qs:
            q = dict(q)
            for c, nm in readable.items():
                q["ask"] = q["ask"].replace(f"「{c}」", f"「{label(nm, lg)}」").replace(f'"{c}"', f'"{label(nm, lg)}"')
            q["options"] = [o if isinstance(o, dict) else {"value": o, "label": label(readable.get(o), lg) or o} for o in q.get("options", [])]
            out.append(q)
        return out

    questions = {"zh": readable_questions(d["questions"], "zh"), "en": readable_questions(en["questions"], "en")}
    if [q["id"] for q in questions["zh"]] != [q["id"] for q in questions["en"]]:
        raise AssertionError("init asked different questions in the two languages")
    answers = yaml.safe_load((INTAKE / "answers.yaml").read_text(encoding="utf-8"))
    def as_label(v, lg="zh"):
        if isinstance(v, str):
            return label(readable[v], lg) if v in readable else v
        if isinstance(v, list):
            return [as_label(x, lg) for x in v]
        return v

    for k, v in list(answers.items()):
        answers[k] = as_label(v)
    spec = yaml.safe_load((INTAKE / "proposals.yaml").read_text(encoding="utf-8"))
    accepted = {x["quote"]: x for x in facts["proposed"]["accepted"]}
    proposals = [{"type": it["type"], "quote": it["quote"], "accepted": it["quote"] in accepted, "kind": it["entry"].get("kind"),
                  "text": {lg: label(it["entry"].get("what") or it["entry"].get("claim"), lg) for lg in LANGS}}
                 for it in spec["items"]]
    docs = {"zh": (INTAKE / "docs" / "weekly_report.zh.md").read_text(encoding="utf-8"),
            "en": (INTAKE / "docs" / "weekly_report.md").read_text(encoding="utf-8")}

    formed, store = Workspace(INTAKE / "workspace"), Workspace(DEMO_WS)
    rows, _, _ = FR.compare(store, formed)
    f = facts["formation"]
    items = f["items"]
    joins = [j["source"] for s in formed.sources.specs.values() if s.get("type") == "join" for j in s["joins"]]
    machine = {
        "dimensions": list(formed.dimensions), "dimension_labels": {d: {"zh": label(formed.dimensions[d].get("label", d), "zh"),
                                                                        "en": label(formed.dimensions[d].get("label", d), "en")}
                                                                   for d in formed.dimensions}, "entities": sum(1 for x in items["from_data"] if x["kind"] == "entity"),
        "relations": sum(1 for x in items["from_data"] if x["kind"] == "relation"), "joins": joins,
        "formula_metrics": [m for m, v in formed.metrics.items() if (v.get("source") or {}).get("kind") == "formula"],
        "identities": [{"left": i["left"], "factors": i["factors"]} for i in formed.model.get("identities", [])],
        "north_star": formed.model.get("north_star"), "outside": list(formed.external.specs),
        "table_events": [{"text": {lg: label(e["what"], lg) for lg in LANGS}, "start": str(e["start"]), "end": str(e.get("end") or e["start"])}
                         for e in formed.world.get("events", []) if (e.get("source") or {}).get("kind") == "system_record"],
    }
    counts = {"from_data": len(items["from_data"]), "asked": len(d["questions"]), "answered": facts["confirm"]["intake"]["answered"],
              "accepted": len(facts["proposed"]["accepted"]), "refused": len(facts["proposed"]["rejected"]),
              "needs_a_person": f["counts"]["needs_a_person"]}
    mismatched = {p for p, _, _, m in rows if m != "yes"}
    world = {e["id"]: e for b in ("events", "mechanisms") for e in formed.world.get(b, [])}
    runs = []
    for k, r in facts["runs"].items():
        cfg = RI.QUESTIONS.get(k) or facts["confirm"]["first_run"]
        leaf = next((x for x in r["slots"] if x["leaf"]), None)
        cites = []
        for c in (leaf or {}).get("citations", []):
            if c.get("explains") != "change":
                continue
            e = world.get(c["id"], {})
            cites.append({"text": {lg: entry_text(e, lg) for lg in LANGS}, "source": c["source"], "status": c["status"], "checks": c.get("checks")})
        path = [p.split("=", 1) for p in leaf["id"].split("/")] if leaf else []
        runs.append({"id": k, "first": k == "first_run", "metric": cfg["metric"], "current": cfg["current"],
                     "filters": cfg.get("filters", {}), "path": path, "status": leaf["status"] if leaf else None, "citations": cites})
    first = json.loads((INTAKE / "runs" / "first_run" / "record.json").read_text(encoding="utf-8"))
    wf, nar = first["charts"]["waterfall"], first["narrative"]
    first_report = {"metric": first["metric"], "current": first["current"], "base": first["base"],
                    "total_base": wf["base"], "total_cur": wf["current"], "history_n": first["qualify"].get("history_n"),
                    "unusual": (first.get("verdict_unusual") or {}).get("then", {}).get("verdict"),
                    "main": {"dimension": nar["main"]["dimension"], "key": nar["main"]["key"], "value": nar["main"]["value"],
                             "status": nar["main"]["status"]},
                    "rest_change": nar["rest"]["rest_change"], "rest_usual": nar["rest"]["rest_usual_change"],
                    "onset": (nar.get("onset") or {}).get("start"),
                    "offsets": [{"key": o["key"], "value": o["value"]} for o in nar.get("offsets", [])]}
    return {"tables": tables, "links": d["links"], "questions": questions, "answers": answers, "proposals": proposals,
            "docs": docs, "counts": counts, "machine": machine,
            "metric_labels": {m: {lg: label(v.get("label", m), lg) for lg in LANGS} for m, v in formed.metrics.items()},
            "person": items["needs_a_person"], "person_text": {lg: FR.T[lg]["person"] for lg in LANGS},
            "compare": [{"part": p, "store": len(a) if isinstance(a, list) else a, "formed": len(b) if isinstance(b, list) else b, "match": m}
                        for p, a, b, m in rows],
            "part_text": FR.PART, "match_text": {lg: {m: FR.T[lg][m] for m in ("yes", "no", "partly")} for lg in LANGS},
            "gaps": {lg: [t for p, t in FR.GAPS[lg] if p in mismatched] for lg in LANGS},
            "note_east": {lg: FR.T[lg]["note_east"] for lg in LANGS},
            "runs": runs, "first_report": first_report}


# ---------------------------------------------------------------- learning: one correction, before and after

def learning(learn: dict) -> dict:
    """sitedata.learning() (data["learning"]) has the run states; the page also quotes the two reports, which that
    function writes into a temporary folder. The same two runs are made again here, with the same correction, to keep
    the report text; the states must come out the same, or this raises."""
    import tempfile

    import yaml
    sys.path.insert(0, str(ROOT / "demo" / "store")) if str(ROOT / "demo" / "store") not in sys.path else None
    import answer_key
    from aib import evolve
    from aib.run import run
    import shutil
    spec = yaml.safe_load((ROOT / "demo" / "store" / "correction.yaml").read_text(encoding="utf-8"))
    case = answer_key.CASES[spec["after_case"]]
    cfg = {**case["run"], "id": case["case"], "question": case["question"]}
    out = {}
    with tempfile.TemporaryDirectory() as t:
        root = Path(t) / "ws"
        shutil.copytree(DEMO_WS, root, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
        for tag in ("before", "after"):
            if tag == "after":
                evolve.apply(root, {**spec["correction"], "run": cfg})
            s = run(root, cfg, out_dir=Path(t) / tag)
            if s["coverage"] != learn[tag]["coverage"]:
                raise AssertionError(f"learning {tag}: coverage differs from sitedata.learning()")
            out[tag] = {lg: (Path(t) / tag / f"report.{lg}.md").read_text(encoding="utf-8") for lg in LANGS}
    return {"reports": out, "question": case["question"]}


# ---------------------------------------------------------------- architecture: the engine's state machine

def state_machine(box_w: int = 236, box_h: int = 62, gap_y: int = 18) -> dict:
    """aib/run.py TRANSITIONS laid out top to bottom: rank = longest path from the first step. Where a step has
    several next steps, the "otherwise" one (the usual path) stays in the middle lane and the others take side lanes,
    left then right. A side-lane step runs straight down its own lane and joins the middle where its path rejoins it,
    so no line crosses a box."""
    from aib.run import TRANSITIONS
    steps, nxt = [], {}
    for a, b, why in TRANSITIONS:
        for x in (a, b):
            if x not in steps:
                steps.append(x)
        nxt.setdefault(a, []).append((b, why))
    rank = {steps[0]: 0}
    changed = True
    while changed:
        changed = False
        for a, b, _ in TRANSITIONS:
            if a in rank and rank.get(b, -1) < rank[a] + 1:
                rank[b] = rank[a] + 1
                changed = True
    ins = {}
    for a, b, _ in TRANSITIONS:
        ins[b] = ins.get(b, 0) + 1
    lane = {s: 0 for s in steps if ins.get(s, 0) > 1}     # where paths rejoin: the middle
    lane[steps[0]] = 0
    for a in steps:
        outs = nxt.get(a, [])
        main = next((b for b, why in outs if why.startswith("otherwise")), outs[0][0] if outs else None)
        side = -1
        for b, _ in outs:
            if b in lane:
                continue
            if b == main or len(outs) == 1:
                lane[b] = lane.get(a, 0)
            else:
                lane[b], side = side, -side
    xs = {-1: 0, 0: (CANVAS_W - box_w) // 2, 1: CANVAS_W - box_w}
    boxes = {s: {"x": xs[lane[s]], "y": rank[s] * (box_h + gap_y), "w": box_w, "h": box_h, "lane": lane[s], "rank": rank[s]} for s in steps}
    edges = []
    for a, b, why in TRANSITIONS:
        p, q = boxes[a], boxes[b]
        if p["lane"] == q["lane"]:
            x = p["x"] + p["w"] / 2
            d = f"M{x},{p['y'] + p['h']} V{q['y'] - 6}"
        elif p["lane"] == 0:      # out of the middle into a side lane: from the box's side, then down into the top
            x1 = p["x"] + (0 if q["lane"] < 0 else p["w"])
            xq = q["x"] + q["w"] / 2
            d = f"M{x1},{p['y'] + p['h'] / 2} H{xq} V{q['y'] - 6}"
        else:                     # back from a side lane: down its own lane, then into the middle box's side
            xp = p["x"] + p["w"] / 2
            x2 = q["x"] + (0 if p["lane"] < 0 else q["w"])
            d = f"M{xp},{p['y'] + p['h']} V{q['y'] + q['h'] / 2} H{x2 + (-6 if p['lane'] < 0 else 6)}"
        edges.append({"from": a, "to": b, "why": why, "d": d, "branch": p["lane"] != q["lane"]})
    h = max(b["y"] + b["h"] for b in boxes.values())
    return {"steps": steps, "boxes": boxes, "edges": edges, "w": CANVAS_W, "h": h}


# ---------------------------------------------------------------- entry point

def graph(cases: dict) -> dict:
    """Everything the business knowledge graph page needs, minus layout (which depends on the words, see pages_more)."""
    ws = Workspace(DEMO_WS)
    tree = metric_tree(ws)
    world = world_model(ws)
    return {"ws": ws, "tree": tree, "world": world,
            "paths": {k: case_path(c, ws, tree) for k, c in cases.items()},
            "dimensions": {d: {lg: label(spec.get("label", d), lg) for lg in LANGS} for d, spec in ws.dimensions.items()}}
