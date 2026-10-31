"""A follow-up question on one answer: "and inside that, what?".

It reads the earlier run's record, takes one of its causes (a slot), and builds the next run's config:
same metric, periods and base rule, the earlier filters plus the slot's whole path, and the dimensions to cut
next (or the earlier order without the ones already used). The new run records which run it followed.
"""

from __future__ import annotations

import json
from pathlib import Path


def load(run_dir) -> dict:
    return json.loads((Path(run_dir) / "record.json").read_text(encoding="utf-8"))


def config(run_dir, slot_id: str, dimensions: list | None = None) -> dict:
    rec = load(run_dir)
    slot = next((x for x in rec["slots"] if x["id"] == slot_id), None)
    if slot is None:
        known = ", ".join(x["id"] for x in rec["slots"]) or "none"
        raise KeyError(f"slot '{slot_id}' is not in run {rec.get('run_id')} (its slots: {known})")
    old = rec["config"]
    filters = dict(old.get("filters") or {})
    filters.update(slot.get("filters") or {})
    filters.update({d: v for d, v in slot["path"]})
    filters[slot["dimension"]] = slot["value"]
    for d, v in slot.get("extra") or []:
        filters.setdefault(d, v)
    if old.get("compare"):
        # the sides being compared stay sides, not a filter
        side_dim = next((c.get("side_dimension") for c in rec["cuts"] if c.get("side_dimension")), None)
        filters.pop(side_dim, None)
    cfg = {k: v for k, v in old.items() if k not in ("id", "question", "filters", "dimensions", "parent_run", "parent_slot")}
    cfg["filters"] = filters
    if dimensions:
        cfg["dimensions"] = list(dimensions)
    elif old.get("dimensions"):
        rest = [d for d in old["dimensions"] if d not in filters]
        if rest:
            cfg["dimensions"] = rest
    cfg["parent_run"] = rec.get("run_id")
    cfg["parent_slot"] = slot_id
    cfg["id"] = f"{rec.get('run_id')}~{slot_id.replace('/', '_').replace('=', '-')}"
    return cfg
