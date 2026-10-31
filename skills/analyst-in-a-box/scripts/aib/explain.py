"""Join a number's movement to the world: which mechanisms, events and actions explain a slice.

A slice needs explaining when a decision table said "this is a single point". Its context is every
entity on the way to it: the run's filters, the drill path, the slice itself, the sides being compared.
An entry is cited only if all of its entities are in that context, so a rainstorm in the east is never
cited for "the marketplace channel" just because the two share some orders.

Outside events (weather, news) are hypotheses. They are cited as supported only after three checks:
timing, affected slice, and size.
"""

from __future__ import annotations

import datetime as dt
import math

from .workspace import Workspace, label

LIVE = ("confirmed", "proposed")


class World:
    def __init__(self, ws: Workspace):
        self.ws = ws
        w = ws.world
        self.entities = {e["id"]: e for e in w.get("entities", [])}
        self.by_value = {}
        for e in self.entities.values():
            if e.get("dimension"):
                self.by_value[(e["dimension"], str(e["key"]))] = e["id"]
                for a in e.get("aliases", []):
                    self.by_value.setdefault((e["dimension"], str(a)), e["id"])

    def entity_for(self, dim, value):
        return self.by_value.get((dim, str(value)))

    def filters_for(self, entity_ids):
        """Entities that are dimension values -> data filters. Outside entities have no data filter."""
        out = {}
        for eid in entity_ids:
            e = self.entities.get(eid, {})
            if e.get("dimension"):
                out[e["dimension"]] = str(e["key"])
        return out

    def context(self, pairs):
        return {eid for eid in (self.entity_for(d, v) for d, v in pairs) if eid}

    def _family(self, metric):
        m = self.ws.metrics.get(metric, {})
        fam = {metric}
        if m.get("kind") == "ratio":
            fam |= {m["numerator"], m["denominator"]}
        return fam

    def cite(self, metric, ctx: set, cur: tuple):
        """Mechanisms, events and actions whose entities all sit inside the context."""
        w = self.ws.world
        fam = self._family(metric)
        mech = [m for m in w.get("mechanisms", []) if m.get("status") in LIVE
                and set(m.get("entities", [])) <= ctx and (not m.get("metrics") or fam & set(m["metrics"]))]
        events = []
        for e in w.get("events", []):
            if e.get("status") not in LIVE or not set(e.get("entities", [])) <= ctx:
                continue
            start = dt.date.fromisoformat(str(e["start"]))
            end = dt.date.fromisoformat(str(e["end"])) if e.get("end") else None
            if start <= cur[1] and (end is None or end >= cur[0]):
                events.append(e)
        actions = [a for a in w.get("actions", []) if a.get("status") in LIVE and set(a.get("entities", [])) <= ctx]
        return mech, events, actions


def _days(w):
    return [w[0] + dt.timedelta(days=i) for i in range((w[1] - w[0]).days + 1)]


def _ratio_slice(ws, metric, base, cur, scope, slice_filters):
    """A ratio's slice contribution: split the scope into 'inside the slice' and 'the rest' and take the inside
    group's exact contribution to the scope's rate change (rate decomposition, two groups)."""
    from .ops import divisive
    m = ws.metrics[metric]
    nums = [ws.total(m["numerator"], w, f) for w in (base, cur) for f in (slice_filters, scope)]
    dens = [ws.total(m["denominator"], w, f) for w in (base, cur) for f in (slice_filters, scope)]
    nb_in, nb_all, nc_in, nc_all = nums
    db_in, db_all, dc_in, dc_all = dens
    seg = {"in": (nb_in, db_in, nc_in, dc_in), "out": (nb_all - nb_in, db_all - db_in, nc_all - nc_in, dc_all - dc_in)}
    r = divisive.decompose(seg)
    return next(x["total"] for x in r["segments"] if x["key"] == "in")


def external_checks(ws: Workspace, world: World, event: dict, metric: str, base: tuple, cur: tuple,
                    scope_filters: dict, total_delta: float) -> dict:
    """Three checks for an outside event. Numbers are always reported; a check without a threshold is 'not judged'.

    Size is measured two ways and both are reported: the change on the event's days (day by day against the same
    position in the base), and the residual: what the slice still changes by with the event's days left out of the
    current period and their paired days left out of the base."""
    params = ws.params
    ratio = ws.metrics[metric].get("kind") == "ratio"
    start = dt.date.fromisoformat(str(event["start"]))
    end = dt.date.fromisoformat(str(event["end"])) if event.get("end") else cur[1]
    ev_days = [d for d in _days(cur) if start <= d <= end]
    out = {"event": event["id"], "event_days": [d.isoformat() for d in ev_days], "measure": "rate" if ratio else "amount"}

    out["timing"] = {"overlap_days": len(ev_days), "pass": len(ev_days) > 0}

    slice_filters = {**scope_filters, **world.filters_for(event.get("entities", []))}
    if ratio:
        slice_delta = _ratio_slice(ws, metric, base, cur, scope_filters, slice_filters)
    else:
        slice_delta = ws.total(metric, cur, slice_filters) - ws.total(metric, base, slice_filters)
    slice_share = slice_delta / total_delta if total_delta else None
    p = params.get("external_slice_min_share")
    out["slice"] = {"filters": slice_filters, "slice_delta": slice_delta, "share_of_change": slice_share,
                    "threshold": p["value"] if p else None,
                    "pass": None if (p is None or slice_share is None) else slice_share >= p["value"]}

    # Same position one window earlier: day i of the base lines up with day i of the current window.
    cur_days, base_days = _days(cur), _days(base)
    paired = [b for c, b in zip(cur_days, base_days) if c in ev_days]
    with ws.excluding(set(ev_days) | set(paired)):
        if ratio:
            residual = _ratio_slice(ws, metric, base, cur, scope_filters, slice_filters) if len(ev_days) < len(cur_days) else 0.0
        else:
            residual = ws.total(metric, cur, slice_filters) - ws.total(metric, base, slice_filters)
    if ratio:
        on_event = slice_delta - residual
    else:
        diffs = [ws.total(metric, (c, c), slice_filters) - ws.total(metric, (b, b), slice_filters)
                 for c, b in zip(cur_days, base_days)]
        on_event = math.fsum(d for day, d in zip(cur_days, diffs) if day in ev_days)
    size_share = on_event / slice_delta if slice_delta else None
    q = params.get("external_size_min_share")
    out["size"] = {"change_on_event_days": on_event, "share_of_slice_change": size_share, "residual_change": residual,
                   "threshold": q["value"] if q else None,
                   "pass": None if (q is None or size_share is None) else size_share >= q["value"]}

    ev = event.get("evidence") or {}
    if ev.get("source") in ws.external.specs:
        spec = ws.external.specs[ev["source"]]
        df = ws.external.frame(ev["source"])
        for k, v in (ev.get("filters") or {}).items():
            df = df[df[k] == v]
        dcol, vcol = spec.get("date", "date"), spec["value"]
        inside = df[df[dcol].dt.date.isin(ev_days)][vcol]
        outside = df[df[dcol].dt.date.isin([d for d in cur_days if d not in ev_days])][vcol]
        out["evidence"] = {"source": ev["source"], "unit": spec.get("unit"),
                           "mean_on_event_days": float(inside.mean()) if len(inside) else None,
                           "mean_other_days": float(outside.mean()) if len(outside) else None}

    verdicts = [out["timing"]["pass"], out["slice"]["pass"], out["size"]["pass"]]
    if all(v is True for v in verdicts):
        out["status"] = "supported"
    elif out["timing"]["pass"]:
        out["status"] = "timing_only"
    else:
        out["status"] = "not_supported"
    return out


def _active_share(entry: dict, w: tuple) -> float:
    """Share of the window's days on which a dated entry is in force. Undated entries are in force every day."""
    if not entry.get("start"):
        return 1.0
    start = dt.date.fromisoformat(str(entry["start"]))
    end = dt.date.fromisoformat(str(entry["end"])) if entry.get("end") else None
    d = _days(w)
    return sum(1 for x in d if x >= start and (end is None or x <= end)) / len(d)


def dominant_term(seg: dict | None) -> str:
    """What moved inside a slot: 'change' for an amount; 'structure' or 'rate' for a ratio's group."""
    if not seg or "structure" not in seg:
        return "change"
    s, r = abs(seg.get("structure", 0.0)), abs(seg.get("rate", 0.0))
    return "structure" if s > r else "rate" if r > s else "tie"


def fit(entry: dict, base: tuple, cur: tuple, term: str) -> str:
    """Can this record explain the change seen in the slot?

    change                 dated, and in force on a different share of days in the two periods
    term_mismatch          it changed between the periods, but it says it acts on the other term (rate vs structure)
    why_mix_matters        in force in both periods and acts on the mix: it explains why a shift in mix moves the
                           number, not why the mix shifted
    cannot_explain_change  in force the same way in both periods (or undated) and not about the mix
    """
    acts = entry.get("acts_on")
    standing = entry.get("period") == "both" or not entry.get("start")
    changed = not standing and abs(_active_share(entry, cur) - _active_share(entry, base)) > 1e-9
    if changed:
        if acts in ("structure", "rate") and term in ("structure", "rate") and acts != term:
            return "term_mismatch"
        return "change"
    if term == "structure" and acts in (None, "structure"):
        return "why_mix_matters"
    return "cannot_explain_change"


def entry_text(entry: dict, lang: str) -> str:
    for key in ("claim", "what", "action"):
        if key in entry:
            return label(entry[key], lang)
    return entry.get("id", "")
