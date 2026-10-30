"""Shared helpers for decomposition operators."""

from __future__ import annotations

import math
from typing import Iterable

# Floating-point tolerance for "terms sum to the total". This is about binary
# arithmetic error, not a business threshold.
REL_TOL = 1e-9


def closure_gap(total: float, terms: Iterable[float]) -> float:
    """Return total - sum(terms). Zero (within tolerance) means the decomposition is exact."""
    return float(total) - math.fsum(float(t) for t in terms)


def is_closed(total: float, terms: Iterable[float]) -> bool:
    terms = list(terms)
    scale = max(1.0, abs(float(total)), *(abs(float(t)) for t in terms)) if terms else max(1.0, abs(float(total)))
    return abs(closure_gap(total, terms)) <= REL_TOL * scale


def share(part: float, total: float) -> float | None:
    """Signed share of a total change. None when the total change is zero, because a share of nothing is undefined."""
    if total == 0 or not math.isfinite(total):
        return None
    return float(part) / float(total)


def safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return float(a) / float(b)


def top_fields(rows: list, field: str) -> dict:
    """rows sorted by |field| descending -> top1 key and the top segments' share of all movement."""
    abs_sum = math.fsum(abs(r[field]) for r in rows)
    out = {"top1_key": rows[0]["key"] if rows else None, "top1_abs_share": None, "top2_cum_abs_share": None}
    if rows and abs_sum:
        out["top1_abs_share"] = abs(rows[0][field]) / abs_sum
        out["top2_cum_abs_share"] = math.fsum(abs(r[field]) for r in rows[:2]) / abs_sum
    return out


def key_str(key) -> str:
    if isinstance(key, tuple):
        return " / ".join(str(k) for k in key)
    return str(key)
