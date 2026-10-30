"""First use: read a table, draft a workspace, and ask the user to confirm what every column means.

Column meaning is never guessed from a column name. The draft only looks at the shape of the data
(numbers or text, how many distinct values, unique per row or not) to decide which questions to ask
and which options to offer. Every role the workspace relies on comes from the user's answer.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import yaml

from .sources import LOADERS

ROLES = {
    "amount": {"en": "Money in (sales amount)", "zh": "收入金额（卖了多少钱）"},
    "profit": {"en": "Profit amount", "zh": "利润金额"},
    "cost": {"en": "Cost amount", "zh": "成本金额"},
    "quantity": {"en": "A count or quantity (items, visits)", "zh": "数量（件数、访问量）"},
    "skip": {"en": "Not a metric, ignore", "zh": "不是指标，忽略"},
}
TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "formulas"
MAX_DIM_VALUES = 50


ISO_DATE = r"^\d{4}-\d{1,2}-\d{1,2}([ T].*)?$"


def _kind(s: pd.Series, n: int) -> str:
    """Shape only: date, number, unique, category or text. Says nothing about what the column means."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"
    sample = s.dropna().astype(str).head(200)
    if len(sample) and not pd.api.types.is_numeric_dtype(s) and sample.str.match(ISO_DATE).all():
        return "date"
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        return "number"
    nun = s.nunique(dropna=True)
    if nun == n and n > 0:
        return "unique"
    return "category" if nun <= MAX_DIM_VALUES else "text"


def profile(df: pd.DataFrame) -> list[dict]:
    n = len(df)
    out = []
    for col in df.columns:
        s = df[col]
        k = _kind(s, n)
        item = {"column": col, "shape": k, "distinct": int(s.nunique(dropna=True)), "nulls": int(s.isna().sum()),
                "examples": [str(x) for x in s.dropna().unique()[:5]]}
        if k == "number":
            item["min"], item["max"] = float(s.min()), float(s.max())
        out.append(item)
    return out


def belongs_to_candidates(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    """child -> parent when every child value sits under exactly one parent value and the parent is coarser."""
    out = []
    for c in cols:
        for p in cols:
            if c == p:
                continue
            pairs = df[[c, p]].dropna().drop_duplicates()
            if len(pairs) and pairs[c].is_unique and pairs[p].nunique() < pairs[c].nunique():
                out.append({"child": c, "parent": p, "pairs": int(len(pairs))})
    return out


def questions(prof: list[dict], fds: list[dict], lang: str = "zh") -> list[dict]:
    zh = lang == "zh"
    qs = []
    dates = [p["column"] for p in prof if p["shape"] == "date"]
    if dates:
        qs.append({"id": "date_column", "ask": "按哪一列的日期统计？" if zh else "Which date column should the numbers be counted by?",
                   "options": dates})
    for p in prof:
        if p["shape"] == "number":
            qs.append({"id": f"role:{p['column']}", "column": p["column"],
                       "ask": (f"「{p['column']}」这一列是什么？例子：{', '.join(p['examples'][:3])}" if zh else
                               f"What is the column \"{p['column']}\"? Examples: {', '.join(p['examples'][:3])}"),
                       "options": [{"value": k, "label": v[lang]} for k, v in ROLES.items()]})
    rows = max((p["distinct"] + p["nulls"] for p in prof), default=0)
    ids = [p["column"] for p in prof if p["shape"] in ("unique", "text")
           or (p["shape"] == "number" and p["distinct"] == rows and float(p.get("min", 0)).is_integer())]
    if ids:
        qs.append({"id": "order_id", "ask": "哪一列是一笔订单（或一笔交易、一个订阅）的编号？" if zh else
                   "Which column identifies one order (or one transaction, one subscription)?",
                   "options": ids + ["none"]})
        qs.append({"id": "template", "ask": "这份数据按什么记？只影响叫法，不影响算法。" if zh else
                   "What does each row record? This only changes the names, not the arithmetic.",
                   "options": [{"value": "orders", "label": "订单（电商、零售、餐饮）" if zh else "Orders (e-commerce, retail, restaurants)"},
                               {"value": "subscription", "label": "订阅或会员" if zh else "Subscriptions or memberships"}]})
    nums = [p["column"] for p in prof if p["shape"] == "number"]
    if nums:
        qs.append({"id": "north_star", "ask": "这些数里，你最关心哪一个？" if zh else "Of these numbers, which matters most to you?",
                   "options": nums})
    cats = [p["column"] for p in prof if p["shape"] == "category" or (p["shape"] == "number" and p["distinct"] <= MAX_DIM_VALUES)]
    if cats:
        qs.append({"id": "dimensions", "multi": True,
                   "ask": "哪些列可以用来切分看（渠道、地区、品类这类）？" if zh else "Which columns can the numbers be cut by (channel, region, category and the like)?",
                   "options": cats})
    for f in fds:
        qs.append({"id": f"belongs:{f['child']}>{f['parent']}",
                   "ask": (f"数据里每个「{f['child']}」只出现在一个「{f['parent']}」下面。它是不是属于那个「{f['parent']}」？" if zh else
                           f"Every \"{f['child']}\" appears under exactly one \"{f['parent']}\". Does it belong to that \"{f['parent']}\"?"),
                   "options": ["yes", "no"]})
    qs.append({"id": "single_point_share",
               "ask": "一刀切下去，第一名占全部变动多少才算「单点」、值得往下钻？" if zh else
                      "After a cut, what share of all movement must the top segment carry to count as a single point worth drilling into?",
               "options": [0.5, 0.6, 0.7, "own value"]})
    return qs


def load_table(path: Path, sheet=None) -> tuple[pd.DataFrame, dict]:
    suffix = "".join(path.suffixes).lower()
    if suffix.endswith((".xlsx", ".xls")):
        spec = {"type": "excel", "path": path.name, **({"sheet": sheet} if sheet is not None else {})}
    elif suffix.endswith((".db", ".sqlite", ".sqlite3")):
        raise ValueError("for SQLite or DuckDB, write project.yaml by hand with a table or query (see the format reference)")
    else:
        spec = {"type": "csv", "path": path.name}
    return LOADERS[spec["type"]](spec, path.parent), spec


def init(data_path, workspace, lang: str = "zh") -> dict:
    """Profile the data and write draft.json with the questions. Nothing is decided yet."""
    data_path, ws = Path(data_path).resolve(), Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    df, spec = load_table(data_path)
    prof = profile(df)
    cats = [p["column"] for p in prof if p["shape"] == "category" or (p["shape"] == "number" and p["distinct"] <= MAX_DIM_VALUES)]
    fds = belongs_to_candidates(df, cats)
    draft = {"data": str(data_path), "source": spec, "language": lang, "rows": len(df), "profile": prof,
             "belongs_to": fds, "questions": questions(prof, fds, lang)}
    (ws / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    return draft


def _dump(p: Path, data):
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")


def _additive_dims(df, id_col, dims):
    """Distinct ids add up across a dimension only if each id has one value on it."""
    if not id_col:
        return list(dims)
    return [d for d in dims if df.groupby(id_col)[d].nunique().max() <= 1]


def confirm(workspace, answers: dict, today: dt.date | None = None) -> dict:
    """Turn the user's answers into project.yaml, model.yaml, rules.yaml and world.yaml."""
    ws = Path(workspace)
    draft = json.loads((ws / "draft.json").read_text(encoding="utf-8"))
    lang = draft["language"]
    today = (today or dt.date.today()).isoformat()
    said = {"kind": "user", "date": today}
    df, _ = load_table(Path(draft["data"]))
    date_cols = [p["column"] for p in draft["profile"] if p["shape"] == "date"]
    date_col = answers.get("date_column") or (date_cols[0] if len(date_cols) == 1 else None)
    if not date_col:
        raise ValueError("answer 'date_column' first: there is no single date column")
    dims = [d for d in answers.get("dimensions", [])]
    id_col = answers.get("order_id") if answers.get("order_id") not in (None, "none") else None
    roles = {q["column"]: answers.get(q["id"]) for q in draft["questions"] if q["id"].startswith("role:")}
    missing = [c for c, r in roles.items() if r is None]
    if missing:
        raise ValueError(f"answer what these columns are first: {', '.join(missing)}")

    source = {**draft["source"], "path": draft["data"], "date_columns": [date_col]}
    _dump(ws / "project.yaml", {"name": Path(draft["data"]).stem, "language": lang, "sources": {"data": source}})

    measures, metrics, identities = {}, {}, []
    by_role: dict = {}
    for col, role in roles.items():
        if role == "skip":
            continue
        mid = col
        measures[f"m_{col}"] = {"source": "data", "agg": "sum", "column": col, "date": date_col, "dimensions": dims}
        metrics[mid] = {"label": col, "measure": f"m_{col}", "unit": "count" if role == "quantity" else "currency",
                        "role": role, "source": said, "status": "confirmed"}
        by_role.setdefault(role, mid)
    tpl = yaml.safe_load((TEMPLATES / f"{answers.get('template', 'orders')}.yaml").read_text(encoding="utf-8"))
    names = tpl["names"]
    if id_col:
        add = _additive_dims(df, id_col, dims)
        measures["m_count"] = {"source": "data", "agg": "count_distinct", "column": id_col, "date": date_col,
                               "dimensions": add, "additive_over": add}
        metrics["id_count"] = {"label": names["id_count"], "measure": "m_count", "unit": "count",
                               "source": said, "status": "confirmed"}
        by_role["id_column"] = "id_count"
    for f in tpl["formulas"]:
        if not all(n in by_role for n in f["needs"]):
            continue
        resolve = lambda x: by_role.get(x, x)  # noqa: E731
        num, den = (resolve(x) for x in f["ratio"])
        metrics[f["metric"]] = {"label": names[f["metric"]], "kind": "ratio", "numerator": num, "denominator": den,
                                "unit": "ratio" if f["metric"] == "margin" else "currency",
                                "source": {"kind": "formula", "ref": f"templates/formulas/{tpl['id']}.yaml"}, "status": "confirmed"}
        identities.append({"id": f"{resolve(f['identity']['left'])}_by_{f['metric']}", "left": resolve(f["identity"]["left"]),
                           "factors": [resolve(x) for x in f["identity"]["factors"]], "operator": "multiply",
                           "source": {"kind": "formula"}, "status": "confirmed"})
    north = answers.get("north_star") if answers.get("north_star") in metrics else by_role.get("amount") or next(iter(metrics), None)
    model = {"north_star": north, "measures": measures, "metrics": metrics, "identities": identities,
             "dimensions": {d: {"label": d, "column": d} for d in dims},
             "priorities": {m: {"order": dims, "mode": "each", "source": {**said, "note": "order of the user's selection; not yet a priority"},
                                "status": "proposed"} for m in metrics},
             "comparisons": []}
    _dump(ws / "model.yaml", model)

    share = answers.get("single_point_share", 0.5)
    rules = {
        "params": {
            "single_point_min_share": {"value": float(share), "source": said, "status": "confirmed"},
            "unusual_z": {"value": 3.5, "status": "confirmed", "source": {"kind": "document", "ref": "Iglewicz & Hoaglin (1993), modified z-score cut-off"}},
            "unusual_z_low": {"value": -3.5, "status": "confirmed", "source": {"kind": "document", "ref": "Iglewicz & Hoaglin (1993), low side"}},
        },
        "tables": [
            {"id": "qualify.unusual", "inputs": {"robust_z": "qualify.robust_z"}, "hit_policy": "FIRST", "rows": [
                {"when": {"robust_z": {"gte": "param:unusual_z"}}, "then": {"verdict": "unusual_high"}},
                {"when": {"robust_z": {"lte": "param:unusual_z_low"}}, "then": {"verdict": "unusual_low"}},
                {"when": {}, "then": {"verdict": "within_usual_range"}}]},
            {"id": "stop.cut", "inputs": {"top1_abs_share": "result.top1_abs_share"}, "hit_policy": "FIRST", "rows": [
                {"when": {"top1_abs_share": {"gte": "param:single_point_min_share"}}, "then": {"action": "drill", "reason": "single_point"}},
                {"when": {}, "then": {"action": "stop", "reason": "spread"}}]},
        ],
    }
    _dump(ws / "rules.yaml", rules)

    entities, relations = [], []
    for d in dims:
        vals = df[d].dropna().unique()
        if len(vals) > MAX_DIM_VALUES:
            continue
        for v in sorted(map(str, vals)):
            entities.append({"id": f"{d}:{v}", "type": d, "dimension": d, "key": v, "label": v,
                             "source": {"kind": "data"}, "status": "confirmed"})
    ids = {e["id"] for e in entities}
    for f in draft["belongs_to"]:
        if answers.get(f"belongs:{f['child']}>{f['parent']}") != "yes" or f["child"] not in dims or f["parent"] not in dims:
            continue
        for c, p in df[[f["child"], f["parent"]]].dropna().drop_duplicates().itertuples(index=False):
            a, b = f"{f['child']}:{c}", f"{f['parent']}:{p}"
            if a in ids and b in ids:
                relations.append({"id": f"rel:{a}>{b}", "subject": a, "predicate": "belongs_to", "object": b,
                                  "source": {"kind": "data", "note": "confirmed by the user"}, "status": "confirmed"})
    _dump(ws / "world.yaml", {"entities": entities, "relations": relations, "mechanisms": [], "events": [], "actions": []})
    return {"north_star": north, "metrics": list(metrics), "dimensions": dims, "first_run": first_run(ws, north)}


def first_run(workspace, metric) -> dict:
    """The last complete Monday-to-Sunday week before the data's last day (which is often only partly loaded),
    compared with the same weekdays a year earlier if the data reaches back, else with the week before."""
    from .workspace import Workspace
    w = Workspace(workspace)
    m = w.measures[w.metric_measures(metric)[0]]
    dates = w.sources.frame(m["source"])[m["date"]]
    lo, hi = dates.min().date(), dates.max().date()
    end = hi - dt.timedelta(days=(hi.weekday() + 1) % 7 or 7)
    cur = (end - dt.timedelta(days=6), end)
    base = "yoy" if cur[0] - dt.timedelta(days=364) >= lo else "pop"
    mode = {"mode": "each"}
    return {"metric": metric, "current": [cur[0].isoformat(), cur[1].isoformat()], "base": base, **mode}
