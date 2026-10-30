"""Compare a run with what was planted. Shared by the tests and the demo page, so both say the same thing."""

from __future__ import annotations

from pathlib import Path

import yaml

PLANTED = yaml.safe_load((Path(__file__).parent / "planted.yaml").read_text(encoding="utf-8"))
CASES = {c["case"]: c for c in PLANTED["expected"]}
EFFECTS = {e["id"]: e for e in PLANTED["effects"]}


def cited(state) -> set:
    return {c["id"] for s in state["slots"] for c in s["citations"]}


def check(exp: dict, s: dict) -> list[tuple[str, bool]]:
    """Every expectation of one case as (description, passed)."""
    rows = [("pre-delivery checks pass", not s["blocked"])]
    if exp.get("order") == "second":
        rows.append(("answered as a second-order question", s["order"] == "second_sides"))
    first = s["cuts"][0] if s["cuts"] else {"dimension": None, "result": {}}
    if "first_cut" in exp:
        rows.append((f"first cut is {exp['first_cut']}", first["dimension"] == exp["first_cut"]))
    if "top1" in exp:
        rows.append((f"top segment is {exp['top1']}", first["result"].get("top1_key") == exp["top1"]))
    if "larger_effect" in exp:
        rows.append((f"{exp['larger_effect']} effect is larger", first["result"].get("larger_effect") == exp["larger_effect"]))
    for dim, want in (exp.get("cuts") or {}).items():
        cut = next((c for c in s["cuts"] if c["dimension"] == dim), None)
        rows.append((f"{dim}: top segment is {want['top1']}", bool(cut) and cut["result"]["top1_key"] == want["top1"]))
        if "larger_effect" in want:
            rows.append((f"{dim}: {want['larger_effect']} effect is larger",
                         bool(cut) and cut["result"].get("larger_effect") == want["larger_effect"]))
    for eid in exp.get("cites", []):
        rows.append((f"cites {eid}", eid in cited(s)))
    if "external_checks" in exp:
        st = [c["checks"]["status"] for sl in s["slots"] for c in sl["citations"] if c.get("external")]
        rows.append((f"outside event checks: {exp['external_checks']}", bool(st) and all(x == exp["external_checks"] for x in st)))
    if "gap_before_correction" in exp:
        g = exp["gap_before_correction"]
        rows.append((f"reports a gap at {g['dimension']}={g['value']}",
                     any(x["dimension"] == g["dimension"] and x["value"] == g["value"] for x in s["gaps"])))
    return rows


def planted_notes(exp: dict) -> list[str]:
    ids = exp["planted"] if isinstance(exp["planted"], list) else [exp["planted"]]
    return [EFFECTS[i]["note"] for i in ids]
