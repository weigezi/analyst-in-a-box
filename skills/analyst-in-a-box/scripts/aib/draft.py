"""First use: read a table, draft a workspace, and ask the user to confirm what every column means.

Column meaning is never guessed from a column name. The draft only looks at the shape of the data
(numbers or text, how many distinct values, unique per row or not) to decide which questions to ask
and which options to offer. Every role the workspace relies on comes from the user's answer.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from . import defaults
from .sources import LOADERS

ROLES = {
    "amount": {"en": "Money in (sales amount)", "zh": "收入金额（卖了多少钱）"},
    "profit": {"en": "Profit amount", "zh": "利润金额"},
    "cost": {"en": "Cost amount", "zh": "成本金额"},
    "quantity": {"en": "A count or quantity (items)", "zh": "数量（件数）"},
    "visits": {"en": "Visits or visitors (people who came, bought or not)", "zh": "访问量（来过的人，不管买没买）"},
    "skip": {"en": "Not a number to analyse (an ID, a code, a name), ignore", "zh": "不是要分析的数（编号、代码、名称），忽略"},
}
TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "formulas"
MAX_DIM_VALUES = 50


ISO_DATE = r"^\d{4}-\d{1,2}-\d{1,2}([ T].*)?$"
MONTH_NAMES = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
               "november", "december"}
MONTH_NAMES |= {m[:3] for m in MONTH_NAMES}


def is_identifier(s: pd.Series, share: float | None = None) -> bool:
    """A whole-number column (integer type) with mostly distinct values: an order, session or user number.
    Decimals are never identifiers; a column of a few distinct values is never one either."""
    share = defaults.PARAMS["intake_id_distinct_share"]["value"] if share is None else share
    if not pd.api.types.is_integer_dtype(s) or pd.api.types.is_bool_dtype(s) or len(s) == 0:
        return False
    return s.nunique(dropna=True) / len(s) >= share


def measure_columns(df: pd.DataFrame, number_columns: list[str]) -> list[str]:
    """Numeric columns that can be added up: not identifier-like, and with more than a flag's worth of distinct values."""
    lo = defaults.PARAMS["intake_measure_min_distinct"]["value"]
    return [c for c in number_columns if not is_identifier(df[c]) and df[c].nunique(dropna=True) >= lo]


def _int_between(s: pd.Series, lo: int, hi: int) -> bool:
    v = s.dropna()
    return bool(len(v)) and pd.api.types.is_numeric_dtype(s) and bool((v == v.round()).all()) and bool(v.between(lo, hi).all())


def composite_dates(df: pd.DataFrame) -> list[dict]:
    """Dates written over several columns, found by the values and by neighbouring columns, never by the names:
    year + month (1..12), year + month name + day, or a yyyymmdd whole number. Returns
    [{"name", "kind", "columns"}]; the name is the columns lowercased and joined with "+"."""
    cols, out = list(df.columns), []
    taken = set()
    def name(cs):
        return "+".join(re.sub(r"\W+", "_", str(c).strip().lower()) for c in cs)
    for i, c in enumerate(cols):
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) and _int_between(s, 1900, 2100) and s.nunique() >= 2 and i + 1 < len(cols):
            m = df[cols[i + 1]]
            if pd.api.types.is_object_dtype(m) or pd.api.types.is_string_dtype(m):
                if m.dropna().astype(str).str.strip().str.lower().isin(MONTH_NAMES).all() and len(m.dropna()):
                    day = next((cols[j] for j in range(i + 2, min(i + 4, len(cols))) if _int_between(df[cols[j]], 1, 31)
                                and df[cols[j]].max() > 12), None)
                    if day:
                        trio = [c, cols[i + 1], day]
                        out.append({"name": name(trio), "kind": "year_monthname_day", "columns": trio})
                        taken |= set(trio)
                        continue
            elif _int_between(m, 1, 12) and m.nunique() >= 2:
                nxt = cols[i + 2] if i + 2 < len(cols) else None
                if nxt is not None and _int_between(df[nxt], 1, 31) and df[nxt].max() > 12:
                    trio = [c, cols[i + 1], nxt]
                    out.append({"name": name(trio), "kind": "year_month_day", "columns": trio})
                    taken |= set(trio)
                else:
                    out.append({"name": name([c, cols[i + 1]]), "kind": "year_month", "columns": [c, cols[i + 1]]})
                    taken |= {c, cols[i + 1]}
    for c in cols:
        s = df[c]
        if c in taken or not pd.api.types.is_integer_dtype(s) or not _int_between(s, 19000101, 21001231):
            continue
        sample = s.dropna().astype("int64").astype(str).head(500)
        if sample.str.len().eq(8).all() and pd.to_datetime(sample, format="%Y%m%d", errors="coerce").notna().all():
            out.append({"name": name([c]), "kind": "yyyymmdd", "columns": [c]})
            taken.add(c)
    return out


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


# Readable names for columns. These are names, not meanings: what a column *means* is still asked as a question
# (role:<column>) and never taken from its name. A token missing from the table stays as it is, and the person
# answering can override any name with an answer "name:<column>" (a string, or {"zh": ..., "en": ...}).
TOKEN_ZH = {
    "id": "编号", "order": "订单", "date": "日期", "time": "时间", "datetime": "时间", "day": "日期", "week": "周",
    "month": "月份", "year": "年份", "customer": "客户", "client": "客户", "country": "国家", "region": "大区",
    "province": "省份", "city": "城市", "store": "门店", "shop": "门店", "group": "分组", "status": "状态",
    "market": "市场", "revenue": "营收", "gmv": "成交额", "amount": "金额", "value": "金额", "items": "件数",
    "lines": "行数", "invoice": "发票", "quantity": "数量", "qty": "数量", "price": "单价", "unit": "单价",
    "sku": "商品编号", "product": "商品", "channel": "渠道", "category": "品类", "type": "类型", "name": "名称",
    "delivery": "配送方式", "shipping": "配送", "promotion": "活动", "campaign": "活动", "start": "开始",
    "end": "结束", "weather": "天气", "rainfall": "降雨量", "rain": "降雨", "mm": "毫米", "visits": "访问量",
    "visit": "访问量", "traffic": "流量", "sessions": "会话数", "profit": "毛利", "margin": "毛利率",
    "cost": "成本", "gross": "毛利", "net": "净", "total": "合计", "average": "平均", "avg": "平均", "discount": "折扣", "refund": "退款", "return": "退货", "supplier": "供应商", "brand": "品牌",
    "spend": "花费", "clicks": "点击", "click": "点击", "impressions": "曝光", "conversion": "转化",
    "user": "用户", "member": "会员", "subscription": "订阅", "plan": "套餐", "list": "标价", "label": "名称",
    "zh": "中文", "en": "英文", "reason": "原因", "change": "变动", "sales": "销售额", "note": "备注",
}
UNITS = {"mm": "毫米", "pct": "%", "kg": "千克", "g": "克", "km": "公里"}
ACRONYMS = {"id": "ID", "sku": "SKU", "gmv": "GMV", "qty": "Qty", "mm": "mm", "url": "URL", "kpi": "KPI"}


COMPOUND = {
    "list_price": {"zh": "标价", "en": "List price"}, "unit_price": {"zh": "单价", "en": "Unit price"},
    "label_zh": {"zh": "名称（中文）", "en": "Name (Chinese)"}, "label_en": {"zh": "名称（英文）", "en": "Name (English)"},
}


def readable(column):
    """{"zh": ..., "en": ...} from the column's own tokens; not a statement about what the column means."""
    if str(column).lower() in COMPOUND:
        return dict(COMPOUND[str(column).lower()])
    tokens = [t for t in re.split(r"[_\-\s]+", str(column)) if t]
    parts, prev = [], None
    for i, t in enumerate(tokens):
        word = TOKEN_ZH.get(t.lower(), t)
        if t.lower() in UNITS and i:
            word = f"（{word}）"
        if word != prev:                      # "unit_price" must not read "单价单价"
            parts.append(word)
            prev = word
    en = " ".join(ACRONYMS.get(t.lower(), t[:1].upper() + t[1:].lower()) for t in tokens)
    return {"zh": "".join(parts) or str(column), "en": en or str(column)}


def profile(df: pd.DataFrame) -> list[dict]:
    n = len(df)
    out = []
    for col in df.columns:
        s = df[col]
        k = _kind(s, n)
        item = {"column": col, "name": readable(col), "shape": k, "distinct": int(s.nunique(dropna=True)),
                "nulls": int(s.isna().sum()), "filled": int(s.notna().sum()), "examples": [str(x) for x in s.dropna().unique()[:5]]}
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


def questions(prof: list[dict], fds: list[dict], lang: str = "zh", quiet: list[dict] | None = None,
              exclude: set | None = None, id_columns: set | None = None) -> list[dict]:
    """`exclude`: columns that are not amounts to add up (parts of a composite date, identifiers): no role question,
    and not offered as the number that matters most."""
    exclude = exclude or set()
    id_columns = id_columns or set()   # identifier-like whole numbers: asked about (suggested: not an amount), counted, never "the number that matters"
    zh = lang == "zh"
    qs = []
    dates = [p["column"] for p in prof if p["shape"] == "date"]
    if dates:
        qs.append({"id": "date_column", "ask": "按哪一列的日期统计？" if zh else "Which date column should the numbers be counted by?",
                   "options": [{"value": c, "label": (next(x for x in prof if x["column"] == c).get("name") or {}).get(lang) or c}
                               for c in dates]})
    def nm(item, lg):
        return (item.get("name") or {}).get(lg) or item["column"]

    for p in prof:
        if p["shape"] == "number" and p["column"] not in exclude:
            empty = p["nulls"] / max(p["nulls"] + p.get("filled", 0), 1) if "filled" in p else None
            note_zh = f"（有 {empty:.0%} 的格子是空的：空的不当 0 加，但这些单还在订单数里）" if empty else ""
            note_en = f" ({empty:.0%} of the cells are empty: they are not added as 0, yet those orders still count in the order total)" if empty else ""
            qs.append({"id": f"role:{p['column']}", "column": p["column"], **({"empty_share": empty} if empty else {}),
                       "ask": (f"「{nm(p, 'zh')}」这一列是什么？例子：{', '.join(p['examples'][:3])}{note_zh}" if zh else
                               f"What is the column \"{nm(p, 'en')}\"? Examples: {', '.join(p['examples'][:3])}{note_en}"),
                       "options": [{"value": k, "label": v[lang]} for k, v in ROLES.items()],
                       **({"suggested": "skip"} if p["column"] in id_columns else {})})
    rows = max((p["distinct"] + p["nulls"] for p in prof), default=0)
    ids = [p["column"] for p in prof if p["shape"] in ("unique", "text")
           or (p["shape"] == "number" and (p["column"] in id_columns
                                           or (p["distinct"] == rows and float(p.get("min", 0)).is_integer())))]
    if ids:
        qs.append({"id": "order_id", "ask": "哪一列是一笔订单（或一笔交易、一个订阅）的编号？" if zh else
                   "Which column identifies one order (or one transaction, one subscription)?",
                   "options": [{"value": c, "label": (next((x for x in prof if x["column"] == c), {}).get("name") or {}).get(lang) or c}
                               for c in ids] + ["none"]})
        qs.append({"id": "template", "ask": "这份数据按什么记？只影响叫法，不影响算法。" if zh else
                   "What does each row record? This only changes the names, not the arithmetic.",
                   "options": [{"value": "orders", "label": "订单（电商、零售、餐饮）" if zh else "Orders (e-commerce, retail, restaurants)"},
                               {"value": "subscription", "label": "订阅或会员" if zh else "Subscriptions or memberships"}]})
    nums = [p["column"] for p in prof if p["shape"] == "number" and p["column"] not in exclude | id_columns]
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
    if quiet:
        names = {"zh": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
                 "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}[lang]
        ev = "，".join(f"{names[q['weekday']]} {q['empty_weeks']}/{q['weeks']} 周没有记录" for q in quiet) if zh else \
            "; ".join(f"{names[q['weekday']]}: no rows in {q['empty_weeks']} of {q['weeks']} weeks" for q in quiet)
        qs.append({"id": "closed_weekdays", "multi": True,
                   "ask": (f"这几天几乎从来没有记录（{ev}）。是不营业吗？勾上的那几天，缺数据不算问题。" if zh else
                           f"These days almost never have rows ({ev}). Is the business closed then? "
                           "Days you tick are not reported as missing data."),
                   "options": [{"value": q["weekday"], "label": names[q["weekday"]]} for q in quiet]})
    qs.append({"id": "single_point_share",
               "ask": "一刀切下去，第一名占全部变动多少才算「单点」、值得往下钻？" if zh else
                      "After a cut, what share of all movement must the top segment carry to count as a single point worth drilling into?",
               "options": [0.5, 0.6, 0.7, "own value"]})
    return qs


def quiet_weekdays(df: pd.DataFrame, date_col: str, min_share: float = 0.9) -> list[dict]:
    """Weekdays with no rows in at least `min_share` of the weeks the data covers (evidence for a closing day).
    The 0.9 only decides whether to ask; the answer is the user's."""
    d = pd.to_datetime(df[date_col]).dt.normalize()
    if d.empty:
        return []
    full = pd.date_range(d.min(), d.max(), freq="D")
    seen = set(d.unique())
    out = []
    for wd in range(7):
        days = [x for x in full if x.weekday() == wd]
        empty = sum(1 for x in days if x not in seen)
        if days and empty / len(days) >= min_share:
            out.append({"weekday": wd, "weeks": len(days), "empty_weeks": empty})
    return out


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
    dates = [p["column"] for p in prof if p["shape"] == "date"]
    quiet = quiet_weekdays(df, dates[0]) if len(dates) == 1 else []
    draft = {"data": str(data_path), "source": spec, "language": lang, "rows": len(df), "profile": prof,
             "belongs_to": fds, "quiet_weekdays": quiet, "questions": questions(prof, fds, lang, quiet)}
    (ws / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    return draft


def closed_block(answers: dict, quiet: list, said: dict, today: str) -> dict | None:
    """project.yaml 'quality' block from the closed_weekdays answer, or None."""
    closed = answers.get("closed_weekdays") or []
    if isinstance(closed, dict):
        # {"days": [5], "basis": "inferred_from_data", "note": "..."}: the person answering did not know the opening
        # days and chose them from the evidence the question showed. Recorded as an inference, waiting to be confirmed.
        days, basis, note = closed.get("days") or [], closed.get("basis"), closed.get("note", "")
    else:
        days, basis, note = closed, None, ""
    if not days:
        return None
    evidence = {q["weekday"]: q for q in quiet}
    src = ({"kind": "data", "date": today, "note": note or "inferred from rows: " + ", ".join(
                f"weekday {d}: {evidence[d]['empty_weeks']}/{evidence[d]['weeks']} weeks empty" for d in days if d in evidence)}
           if basis == "inferred_from_data" else {**said, "note": "answer to the closed_weekdays question"})
    return {"closed_weekdays": sorted(int(x) for x in days), "source": src,
            "status": "proposed" if basis == "inferred_from_data" else "confirmed",
            "evidence": [evidence[d] for d in sorted(int(x) for x in days) if d in evidence]}


def proposed_priorities(measures: dict, metrics: dict, dims: list, said: dict) -> dict:
    """The user's dimension selection, per metric, keeping only the dimensions that metric's data can be cut by."""
    def cut_by(m):
        x = metrics[m]
        parts = [x["numerator"], x["denominator"]] if x.get("kind") == "ratio" else [m]
        sets = [set(measures[metrics[p]["measure"]].get("dimensions", [])) for p in parts]
        return set.intersection(*sets) if sets else set()
    out = {}
    for m in metrics:
        order = [d for d in dims if d in cut_by(m)]
        if order:
            out[m] = {"order": order, "mode": "drill", "source": {**said, "note": "order of the user's selection; not yet a priority, "
                                                                  "so every layer is chosen by score until the user confirms one"},
                      "status": "proposed"}
    return out


def _as_name(v):
    if isinstance(v, dict):
        return {"zh": v.get("zh") or v.get("en"), "en": v.get("en") or v.get("zh")}
    return {"zh": v, "en": v}


def name_map(profile: list, answers: dict) -> dict:
    """Readable name per column: the answer "name:<column>" if given, else the one read from the column name."""
    out = {}
    for it in profile:
        given = answers.get(f"name:{it['column']}")
        out[it["column"]] = _as_name(given) if given else it.get("name") or readable(it["column"])
    return out


def build_metrics(specs: list, id_spec: dict | None, template: str, said: dict, names: dict | None = None):
    """Measures, metrics and identities from the columns whose meaning the user confirmed.

    specs: [{column, role, source, date, dimensions[, columns]}]; id_spec: the order-id column, if any.
    The template only names formulas (arithmetic); which columns fill them comes from the user's roles."""
    measures, metrics, identities, by_role = {}, {}, [], {}
    nm = lambda c: (names or {}).get(c) or _as_name(c)  # noqa: E731
    for sp in specs:
        if sp["role"] == "skip":
            continue
        col = sp["column"]
        m = {"label": nm(col), "source": sp["source"], "agg": "sum", "column": col, "date": sp["date"],
             "dimensions": list(sp["dimensions"])}
        if sp.get("columns"):
            m["columns"] = dict(sp["columns"])
        measures[f"m_{col}"] = m
        metrics[col] = {"label": nm(col), "measure": f"m_{col}", "unit": "count" if sp["role"] in ("quantity", "visits") else "currency",
                        "role": sp["role"], "source": said, "status": "confirmed"}
        by_role.setdefault(sp["role"], col)
    tpl = yaml.safe_load((TEMPLATES / f"{template}.yaml").read_text(encoding="utf-8"))
    names = tpl["names"]
    if id_spec:
        d = list(id_spec["dimensions"])
        measures["m_count"] = {"source": id_spec["source"], "agg": "count_distinct", "column": id_spec["column"],
                               "date": id_spec["date"], "dimensions": d, "additive_over": d}
        metrics["id_count"] = {"label": names["id_count"], "measure": "m_count", "unit": "count", "source": said, "status": "confirmed"}
        by_role["id_column"] = "id_count"
    for f in tpl["formulas"]:
        if not all(n in by_role for n in f["needs"]):
            continue
        resolve = lambda x: by_role.get(x, x)  # noqa: E731
        num, den = (resolve(x) for x in f["ratio"])
        metrics[f["metric"]] = {"label": names[f["metric"]], "kind": "ratio", "numerator": num, "denominator": den,
                                "unit": f.get("unit", "currency"),
                                "source": {"kind": "formula", "ref": f"templates/formulas/{tpl['id']}.yaml"}, "status": "confirmed"}
        identities.append({"id": f"{resolve(f['identity']['left'])}_by_{f['metric']}", "left": resolve(f["identity"]["left"]),
                           "factors": [resolve(x) for x in f["identity"]["factors"]], "operator": "multiply",
                           "source": {"kind": "formula"}, "status": "confirmed"})
    return measures, metrics, identities, by_role


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
    if id_col and df[id_col].notna().all() and df[id_col].is_unique:
        # the user named the column as the order id, and the data confirms one row per value: a key to check
        source["key"] = id_col
    project = {"name": Path(draft["data"]).stem, "language": lang, "sources": {"data": source}}
    q = closed_block(answers, draft.get("quiet_weekdays", []), said, today)
    if q:
        project["quality"] = q
    _dump(ws / "project.yaml", project)

    specs = [{"column": col, "role": role, "source": "data", "date": date_col, "dimensions": dims}
             for col, role in roles.items()]
    id_spec = None
    if id_col:
        add = _additive_dims(df, id_col, dims)
        id_spec = {"column": id_col, "source": "data", "date": date_col, "dimensions": add}
    names = name_map(draft["profile"], answers)
    project["columns"] = {c: n for c, n in names.items()}
    _dump(ws / "project.yaml", project)
    measures, metrics, identities, by_role = build_metrics(specs, id_spec, answers.get("template", "orders"), said, names)
    north = answers.get("north_star") if answers.get("north_star") in metrics else by_role.get("amount") or next(iter(metrics), None)
    model = {"north_star": north, "measures": measures, "metrics": metrics, "identities": identities,
             "dimensions": {d: {"label": names.get(d) or _as_name(d), "column": d} for d in dims},
             "priorities": proposed_priorities(measures, metrics, dims, said),
             "comparisons": []}
    _dump(ws / "model.yaml", model)

    share = answers.get("single_point_share", 0.5)
    rules = defaults.rules()
    rules["params"]["single_point_min_share"] = {"value": float(share), "source": said, "status": "confirmed"}
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
    if (dates.dt.day == 1).all():
        # dates that are all the first of a month (year + month): compare the last full month with the one before
        # it, or with the same month a year earlier when the data reaches back that far
        last = dates.max()
        cur = (last.date(), (last + pd.offsets.MonthEnd(0)).date())
        yoy = (last - pd.DateOffset(years=1)).date()
        base = "yoy" if yoy >= lo else "pop"
        return {"metric": metric, "current": [cur[0].isoformat(), cur[1].isoformat()], "base": base}
    end = hi - dt.timedelta(days=(hi.weekday() + 1) % 7 or 7)
    cur = (end - dt.timedelta(days=6), end)
    base = "yoy" if cur[0] - dt.timedelta(days=364) >= lo else "pop"
    return {"metric": metric, "current": [cur[0].isoformat(), cur[1].isoformat()], "base": base}
