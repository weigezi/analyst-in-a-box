"""Checks a workspace before anything is computed. Problems are listed, never silently ignored."""

from __future__ import annotations

import datetime as dt
import math

from . import judge
from .sources import AGGS
from .workspace import SOURCE_KINDS, STATUSES, Workspace, label

ADDITIVE_AGGS = {"sum", "count"}


def _check_source(where, obj, problems):
    src = obj.get("source")
    if not isinstance(src, dict) or src.get("kind") not in SOURCE_KINDS:
        problems.append(f"{where}: needs source.kind, one of {', '.join(SOURCE_KINDS)}")
    if obj.get("status") not in STATUSES:
        problems.append(f"{where}: status must be one of {', '.join(STATUSES)}")


def model_problems(ws: Workspace) -> list[str]:
    p = []
    dims = ws.dimensions
    for name, m in ws.measures.items():
        w = f"measure {name}"
        if m.get("source") not in ws.sources.specs:
            p.append(f"{w}: unknown source '{m.get('source')}'")
        if m.get("agg") not in AGGS:
            p.append(f"{w}: agg must be one of {', '.join(sorted(AGGS))}")
        if m.get("agg") != "count" and not m.get("column"):
            p.append(f"{w}: needs a column")
        if not m.get("date"):
            p.append(f"{w}: needs a date column")
        for d in m.get("dimensions", []):
            if d not in dims:
                p.append(f"{w}: unknown dimension '{d}'")
        if m.get("agg") not in ADDITIVE_AGGS and "additive_over" not in m:
            p.append(f"{w}: agg '{m.get('agg')}' is not summable in general; list the dimensions it can be added over in additive_over")
    for name, m in ws.metrics.items():
        w = f"metric {name}"
        if m.get("kind") == "ratio":
            for part in ("numerator", "denominator"):
                if m.get(part) not in ws.metrics:
                    p.append(f"{w}: {part} '{m.get(part)}' is not a metric")
        elif m.get("measure") not in ws.measures:
            p.append(f"{w}: unknown measure '{m.get('measure')}'")
    for ident in ws.model.get("identities", []):
        w = f"identity {ident.get('id')}"
        for x in [ident.get("left")] + list(ident.get("factors", [])):
            if x not in ws.metrics:
                p.append(f"{w}: '{x}' is not a metric")
        if ident.get("operator") not in ("multiply", "divide"):
            p.append(f"{w}: operator must be multiply or divide")
        _check_source(w, ident, p)
    for metric, pr in (ws.model.get("priorities") or {}).items():
        w = f"priority {metric}"
        if metric not in ws.metrics:
            p.append(f"{w}: unknown metric")
            continue
        allowed = ws.metric_dimensions(metric)
        for d in pr.get("order", []):
            if d not in dims:
                p.append(f"{w}: unknown dimension '{d}'")
            elif d not in allowed:
                p.append(f"{w}: '{d}' cannot cut this metric (its data has no such column)")
        _check_source(w, pr, p)
    for i, pv in enumerate(ws.model.get("pvm", []) or []):
        w = f"pvm {i}"
        for part in ("metric", "quantity"):
            if pv.get(part) not in ws.metrics:
                p.append(f"{w}: {part} '{pv.get(part)}' is not a metric")
        if pv.get("dimension") not in dims:
            p.append(f"{w}: unknown dimension '{pv.get('dimension')}'")
        elif pv.get("metric") in ws.metrics and pv["dimension"] not in ws.metric_dimensions(pv["metric"]):
            p.append(f"{w}: '{pv['dimension']}' cannot cut {pv['metric']}")
    for c in ws.model.get("comparisons", []):
        w = f"comparison {c.get('id')}"
        if c.get("dimension") not in dims:
            p.append(f"{w}: unknown dimension")
        if c.get("segment_by") and c.get("segment_by") not in dims:
            p.append(f"{w}: unknown segment_by dimension")
        if len(c.get("sides", [])) != 2:
            p.append(f"{w}: needs exactly two sides")
    return p


def rules_problems(ws: Workspace) -> list[str]:
    p = []
    for name, prm in ws.params.items():
        if "value" not in prm:
            p.append(f"param {name}: needs a value")
        _check_source(f"param {name}", prm, p)
    for t in ws.rules.get("tables", []):
        p.extend(judge.validate(t, ws.params))
    return p


def world_problems(ws: Workspace) -> list[str]:
    p = []
    w = ws.world
    ents = {}
    for e in w.get("entities", []):
        if e.get("id") in ents:
            p.append(f"entity {e.get('id')}: duplicate id")
        ents[e.get("id")] = e
        _check_source(f"entity {e.get('id')}", e, p)
        if e.get("dimension") and e["dimension"] not in ws.dimensions:
            p.append(f"entity {e.get('id')}: unknown dimension '{e['dimension']}'")
    names = {}
    for e in ents.values():
        for n in [label(e.get("label"), "en"), label(e.get("label"), "zh")]:
            names.setdefault(n, e["id"])
    for e in ents.values():
        for a in e.get("aliases", []):
            if names.get(a) not in (None, e["id"]):
                p.append(f"entity {e['id']}: alias '{a}' is another entity's name")
    for kind in ("relations", "mechanisms", "events", "actions"):
        seen = set()
        for x in w.get(kind, []):
            xid = x.get("id")
            where = f"{kind[:-1]} {xid}"
            if xid in seen:
                p.append(f"{where}: duplicate id")
            seen.add(xid)
            _check_source(where, x, p)
            refs = [x.get("subject"), x.get("object")] if kind == "relations" else list(x.get("entities", []))
            for r in refs:
                if r not in ents:
                    p.append(f"{where}: unknown entity '{r}'")
            for m in x.get("metrics", []):
                if m not in ws.metrics:
                    p.append(f"{where}: unknown metric '{m}'")
            if kind == "events":
                try:
                    a = dt.date.fromisoformat(str(x["start"]))
                    if x.get("end") is not None and dt.date.fromisoformat(str(x["end"])) < a:
                        p.append(f"{where}: ends before it starts")
                except (KeyError, ValueError):
                    p.append(f"{where}: needs an ISO start date (end is optional: missing means still going)")
                if x.get("kind") not in ("internal", "external"):
                    p.append(f"{where}: kind must be internal or external")
                ev = x.get("evidence") or {}
                if ev.get("source") and ev["source"] not in ws.external.specs:
                    p.append(f"{where}: evidence source '{ev['source']}' is not an external source")
            if kind == "actions" and not x.get("owner"):
                p.append(f"{where}: needs an owner")
    return p


def data_problems(ws: Workspace, w: tuple, filters: dict | None = None) -> list[str]:
    """Identities must actually hold on the data; a formula that does not close is a wrong formula.
    With filters, the identity is also tested inside that slice (a factor whose table labels the slice differently
    would otherwise break the tree only there); identities whose parts cannot be cut by the filter are skipped."""
    p = []
    where = "".join(f" {k}={v}" for k, v in (filters or {}).items())
    for ident in ws.model.get("identities", []):
        if filters and not all(set(filters) <= ws.metric_dimensions(x) for x in [ident["left"], *ident["factors"]]):
            continue
        try:
            left = ws.total(ident["left"], w, filters)
            vals = [ws.total(f, w, filters) for f in ident["factors"]]
            right = math.prod(vals) if ident["operator"] == "multiply" else vals[0] / vals[1]
            if not math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9):
                p.append(f"identity {ident['id']}: {left} != {right} on {w[0]}..{w[1]}{' in' + where if where else ''}")
        except Exception as exc:  # report, do not hide: the user must see which identity cannot be computed
            p.append(f"identity {ident.get('id')}: cannot compute ({exc})")
    return p


def all_problems(ws: Workspace, data_window: tuple | None = None) -> list[str]:
    out = model_problems(ws) + rules_problems(ws) + world_problems(ws)
    if data_window and not out:
        out += data_problems(ws, data_window)
    return out
