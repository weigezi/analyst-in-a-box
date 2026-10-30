"""Decision tables: stop conditions and routing written one rule per row, read by a program.

Structure borrowed from the OMG DMN decision table (one row per rule, a hit policy, a fallback row),
without its XML or expression language. Source: Object Management Group, Decision Model and Notation.

Table format (YAML):
  id: stop.after_dimension_cut
  question: After cutting by a dimension, drill into the top segment or stop here?
  inputs: {top1_abs_share: additive.top1_abs_share, same_direction_share: additive.same_direction_share}
  hit_policy: FIRST
  rows:
    - when: {top1_abs_share: {gte: "param:single_point_min_share"}}
      then: {action: drill, target: top1}
    - when: {}
      then: {action: stop, reason: no_single_point}
Thresholds never live in the table; they are named params with a source, so changing one is one line.
"""

from __future__ import annotations

from .ops import OUTPUT_FIELDS
from .qualify import OUTPUT_FIELDS as QUALIFY_FIELDS

KNOWN_FIELDS = {**{k: set(v) for k, v in OUTPUT_FIELDS.items()}, "qualify": set(QUALIFY_FIELDS)}
# "result" means "the cut just computed, whichever operator produced it", so one table can serve every operator.
KNOWN_FIELDS["result"] = set().union(*(set(v) for v in OUTPUT_FIELDS.values()))
OPS = ("gte", "gt", "lte", "lt", "eq", "ne", "in", "not_null")


def _resolve(value, params):
    if isinstance(value, str) and value.startswith("param:"):
        name = value[len("param:"):]
        if name not in params:
            raise KeyError(f"unknown param {name}")
        return params[name]["value"]
    return value


def _test(op, actual, expected):
    if op == "not_null":
        return (actual is not None) == bool(expected)
    if actual is None:
        return False
    return {
        "gte": lambda: actual >= expected, "gt": lambda: actual > expected,
        "lte": lambda: actual <= expected, "lt": lambda: actual < expected,
        "eq": lambda: actual == expected, "ne": lambda: actual != expected,
        "in": lambda: actual in expected,
    }[op]()


def _match(cond: dict, ctx: dict, params: dict) -> bool:
    if not cond:
        return True
    for key, spec in cond.items():
        if key == "all":
            if not all(_match(c, ctx, params) for c in spec):
                return False
        elif key == "any":
            if not any(_match(c, ctx, params) for c in spec):
                return False
        else:
            for op, expected in spec.items():
                if not _test(op, ctx.get(key), _resolve(expected, params)):
                    return False
    return True


def gather_inputs(table: dict, results: dict) -> dict:
    """results: {'additive': {...}, 'divisive': {...}, 'qualify': {...}} -> {input_name: value}."""
    ctx = {}
    for name, path in table.get("inputs", {}).items():
        op, field = path.split(".", 1)
        ctx[name] = (results.get(op) or {}).get(field)
    return ctx


def evaluate(table: dict, results: dict, params: dict) -> dict:
    ctx = gather_inputs(table, results)
    for i, row in enumerate(table["rows"]):
        if _match(row.get("when", {}), ctx, params):
            return {"table": table["id"], "row": i, "then": row["then"], "inputs": ctx,
                    "fallback": not row.get("when")}
    raise RuntimeError(f"table {table['id']} has no matching row; validate() should have caught this")


def _fields_in(cond: dict, out: set):
    for key, spec in cond.items():
        if key in ("all", "any"):
            for c in spec:
                _fields_in(c, out)
        else:
            out.add(key)
            for op, expected in spec.items():
                if op not in OPS:
                    out.add(f"!bad_op:{op}")


def _params_in(cond: dict, out: set):
    for key, spec in cond.items():
        if key in ("all", "any"):
            for c in spec:
                _params_in(c, out)
        else:
            for v in spec.values():
                if isinstance(v, str) and v.startswith("param:"):
                    out.add(v[len("param:"):])


def validate(table: dict, params: dict) -> list[str]:
    """Return a list of problems; empty means the table is safe for a program to run."""
    problems = []
    tid = table.get("id", "?")
    rows = table.get("rows") or []
    if not rows:
        return [f"{tid}: no rows"]
    if rows[-1].get("when"):
        problems.append(f"{tid}: last row must be the fallback (empty 'when')")
    for i, row in enumerate(rows[:-1]):
        if not row.get("when"):
            problems.append(f"{tid}: row {i} has an empty 'when'; every row after it can never fire")
    seen = []
    for i, row in enumerate(rows):
        w = row.get("when", {})
        if w and w in seen:
            problems.append(f"{tid}: row {i} repeats an earlier condition and can never fire")
        seen.append(w)
        if "then" not in row:
            problems.append(f"{tid}: row {i} has no 'then'")
    declared = set(table.get("inputs", {}))
    for row in rows:
        used = set()
        _fields_in(row.get("when", {}), used)
        for f in used:
            if f.startswith("!bad_op:"):
                problems.append(f"{tid}: unknown operator {f[8:]}")
            elif f not in declared:
                problems.append(f"{tid}: condition uses '{f}' which is not declared in inputs")
        refs = set()
        _params_in(row.get("when", {}), refs)
        for p in refs:
            if p not in params:
                problems.append(f"{tid}: param '{p}' is not defined")
            elif not params[p].get("source"):
                problems.append(f"{tid}: param '{p}' has no source")
    for name, path in table.get("inputs", {}).items():
        op, _, field = path.partition(".")
        if op not in KNOWN_FIELDS or field not in KNOWN_FIELDS[op]:
            problems.append(f"{tid}: input '{name}' points to unknown field '{path}'")
    if table.get("hit_policy", "FIRST") != "FIRST":
        problems.append(f"{tid}: only hit_policy FIRST is supported")
    return problems
