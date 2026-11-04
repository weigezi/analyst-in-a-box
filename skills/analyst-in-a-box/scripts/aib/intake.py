"""Intake: from a folder of tables (and the shop's documents) to a workspace, with every inference confirmed.

What it reads is the shape of each table, never what a column is called:
  main table       has a date, the most rows, and numbers
  lookup tables    one row per key (no date); their other columns are attributes of that key
  links            every value of a column in one table appears among the keys (or values) of a column in another;
                   the share of rows that find a match is the coverage, shown to the user
  event records    two dates per row (start and end, start never after end) plus words or groups: campaigns,
                   price changes, holidays
  daily series     one number per date (or per date and one group): visits, weather, a market index
Each of these is a suggestion with its evidence. `confirm` turns only the answered ones into the workspace.

Documents are read by the user's AI tool, not by this script (a script reading prose would be guessing). The tool
proposes mechanisms and events with the sentence they came from; `propose` accepts a proposal only if that
sentence appears in the document, and records it as 'from a document, to confirm'.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import defaults, draft
from .sources import apply_derived_columns, derive_dates

TABLE_SUFFIXES = (".csv", ".csv.gz", ".xlsx", ".xls")


class NoTimeAxis(ValueError):
    """No table has dates together with an amount to add up, so there is no 'this period against that one'."""


class NeedsAnswers(ValueError):
    """`confirm` was given a main table other than the suggested one, re-read the tables for it, and found questions
    that only exist for that table. They are saved in draft.json; answer them and run `confirm` again."""

    def __init__(self, message, ids, questions):
        super().__init__(message)
        self.ids, self.questions = ids, questions


# Thresholds are named params (defaults.PARAMS, with their reasons); a workspace's rules.yaml may override them.
def _param(name, ws_dir=None):
    if ws_dir is not None:
        rules_path = Path(ws_dir) / "rules.yaml"
        if rules_path.exists():
            p = ((yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}).get("params") or {}).get(name)
            if p is not None:
                return p["value"]
    return defaults.PARAMS[name]["value"]


def _suffix(p: Path) -> str:
    return "".join(p.suffixes).lower()


def find_tables(paths) -> list[Path]:
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(x for x in p.iterdir() if x.is_file() and _suffix(x).endswith(TABLE_SUFFIXES))
        elif p.is_file():
            out.append(p)
        else:
            raise FileNotFoundError(p)
    return out


def _name(p: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", p.name.split(".")[0]) or "table"


def _is_key(s: pd.Series) -> bool:
    """One row per value, no gaps, and not a measured number (a float with decimals is a measurement)."""
    if len(s) == 0 or s.isna().any() or not s.is_unique:
        return False
    if pd.api.types.is_float_dtype(s):
        return False
    return not pd.api.types.is_bool_dtype(s)


def _table_facts(name, path, df):
    prof = draft.profile(df)
    shape = {p["column"]: p["shape"] for p in prof}
    dates = [c for c, k in shape.items() if k == "date"]
    comps = draft.composite_dates(df)
    parts = {c for cd in comps for c in cd["columns"]}
    nums = [c for c, k in shape.items() if k == "number" and c not in parts]
    words = [c for c, k in shape.items() if k in ("category", "text", "unique")]
    # Keys are looked for only in tables without dates: in a two-row campaign table every column is "unique".
    keys = [c for c in df.columns if not dates and _is_key(df[c])]
    # A dated table also has keys of its own (a session id, an order id): a child table can point at them. Only
    # whole numbers and words, never a measured amount, and only when the table is big enough for "unique" to mean something.
    row_keys = [c for c in df.columns if dates and c not in dates and len(df) >= 30 and _is_key(df[c])]
    facts = {"name": name, "path": str(path), "rows": len(df), "profile": prof, "date_columns": dates,
             "composite_dates": comps, "number_columns": nums, "measure_columns": draft.measure_columns(df, nums),
             "id_columns": [c for c in nums if draft.is_identifier(df[c])],
             "duplicate_rows": int(df.duplicated().sum()), "row_keys": row_keys,
             "word_columns": words, "keys": keys}
    if len(dates) >= 2:
        a, b = dates[:2]
        da, db = pd.to_datetime(df[a]), pd.to_datetime(df[b])
        # Two dates in order on every row are a start and an end only for a small table or one with no amounts.
        # An orders table (ordered, shipped) passes the order test too, but it is a fact table with two dates.
        small = len(df) <= _param("intake_event_table_max_rows") or not facts["measure_columns"]
        if small and (da <= db).all():
            facts["start_end"] = [a, b]
        elif small and (db <= da).all():
            facts["start_end"] = [b, a]
    if len(dates) == 1:
        d = dates[0]
        groups = [c for c in words if c not in keys and shape[c] == "category"]
        for g in ([], *[[c] for c in groups]):
            if not df.duplicated([d, *g]).any():
                facts["per_date"] = g
                break
    return facts


def _suggest_kind(t, main, links, df, grain=()):
    if t["name"] == main:
        return "main"
    linked = any(lk["left_table"] == t["name"] for lk in links)
    # The detail of the main table (its items) is already added up in the main table: using it too would count twice.
    if any(g["child"] == t["name"] and g["parent"] == main for g in grain):
        return "ignore"
    # A dated table that the main table reaches by its own key, with the link suggested, describes the main table's
    # rows (a session gives the order its channel; an item reaches the session through its order). It is joined in as a
    # lookup; its own dates stay out of the way.
    if t["name"] in {lk["right_table"] for lk in _chain(links, main)} and t["date_columns"] and not t.get("start_end"):
        return "lookup"
    if not t["date_columns"] and not t["composite_dates"]:
        return "lookup" if t["keys"] else "ignore"
    if not t["date_columns"]:   # dated only by a composite (year + month)
        if any(lk["right_table"] == t["name"] and lk["right_is_key"] for lk in links):
            return "lookup"     # other tables point at its key: it describes them (a member list with an enrolment month)
        return "business" if t["measure_columns"] else "ignore"
    if t.get("start_end"):
        return "events" if linked else "calendar"
    if "per_date" in t and t["number_columns"]:
        if not t["per_date"]:
            return "series"
        # grouped daily numbers: whole counts linked to the main table's groups read like business data (visits);
        # measurements (decimals) read like outside data (rainfall). A suggestion only.
        integer = all(float(x).is_integer() for x in df[t["number_columns"]].iloc[:200].stack())
        return "business" if (linked and integer) else "series"
    return "business" if t["number_columns"] else "ignore"


def _child_not_before_parent(frames, tables, left, lcol, right, rcol):
    """Share of matched rows whose child date is not earlier than the parent's date, or None when either table has no
    ordinary date to compare."""
    ld, rd = tables[left]["date_columns"], tables[right]["date_columns"]
    if not ld or not rd or tables[left].get("start_end") or tables[right].get("start_end"):
        return None
    a = frames[left][[lcol, ld[0]]].dropna().astype({lcol: str})
    b = frames[right][[rcol, rd[0]]].dropna().astype({rcol: str}).rename(columns={rcol: lcol, rd[0]: "_parent"})
    m = a.merge(b, on=lcol)
    if m.empty:
        return None
    return float((pd.to_datetime(m[ld[0]]) >= pd.to_datetime(m["_parent"])).mean())


def _range_use(frames, left, lcol, right, rcol):
    """How much of the parent's range of whole-number ids the child's ids span (1.0 = all of it), or None when the
    columns are not whole numbers."""
    a, b = frames[left][lcol].dropna(), frames[right][rcol].dropna()
    if not (pd.api.types.is_integer_dtype(a) and pd.api.types.is_integer_dtype(b)) or b.max() == b.min():
        return None
    return float(a.max() - a.min()) / float(b.max() - b.min())


def _links(tables, frames, main):
    """Candidate links: left column values found among a right column's values.

    Right side: keys of tables without dates (lookups), the own keys of dated tables (a session id), and grouping
    columns of the main table and of lookups. Left side: words and whole numbers, but not amounts. For each left column
    only the best parent is kept: the one whose rows do not come after the child's, then the best coverage."""
    rights = []
    for t in tables.values():
        df = frames[t["name"]]
        dated = bool(t["date_columns"])
        for c in df.columns:
            if c in t["date_columns"]:
                continue
            is_key = c in t["keys"] or c in t["row_keys"]
            if c in t["number_columns"] and not is_key:
                continue
            if is_key or (not dated or t["name"] == main) and df[c].nunique() <= draft.MAX_DIM_VALUES:
                rights.append((t["name"], c, is_key, set(df[c].dropna().astype(str).unique())))
    out = []
    for t in tables.values():
        df = frames[t["name"]]
        is_lookup = not t["date_columns"] and bool(t["keys"])
        for c in df.columns:
            if c in t["date_columns"] or is_lookup:
                continue
            if c in t["number_columns"] and not draft.is_identifier(df[c]) and df[c].nunique() > draft.MAX_DIM_VALUES:
                continue          # an amount, not a pointer
            if c in t["row_keys"] and not t["date_columns"]:
                continue
            vc = df[c].dropna().astype(str).value_counts()
            if vc.empty:
                continue
            best = None
            for rt, rc, rkey, vals in rights:
                if rt == t["name"]:
                    continue
                cov = float(vc[vc.index.isin(vals)].sum() / vc.sum())
                if cov < _param("intake_link_ask_min"):
                    continue
                order = _child_not_before_parent(frames, tables, t["name"], c, rt, rc) if rkey else None
                spread = _range_use(frames, t["name"], c, rt, rc) if rkey else None
                ok = (order is None or order >= _param("intake_link_order_min")) and (spread is None or spread >= _param("intake_link_range_min"))
                cand = {"left_table": t["name"], "left_column": c, "right_table": rt, "right_column": rc,
                        "right_is_key": rkey, "coverage": cov, "matched_rows": int(vc[vc.index.isin(vals)].sum()),
                        "rows": int(vc.sum()),
                        "suggested": "yes" if (cov >= _param("intake_link_suggest_min") and ok) else "no"}
                if order is not None:
                    cand["child_not_before_parent"] = order
                if spread is not None:
                    cand["id_range_used"] = spread
                rank = (ok, cov, rkey and t["name"] == main, rt == main)
                if best is None or rank > best[0]:
                    best = (rank, cand)
            if best:
                out.append(best[1])
    return out


def _chain(links, main, use=lambda lk: lk["suggested"] == "yes"):
    """The links that bring other tables' columns onto the main table, in the order they are applied: first the tables the
    main table points at by key, then the tables those point at (order_items -> orders -> sessions). A table is joined once."""
    have, hops, grew = {main}, [], True
    while grew:
        grew = False
        for lk in links:
            if lk["left_table"] in have and lk["right_table"] not in have and lk["right_is_key"] and use(lk):
                hops.append(lk)
                have.add(lk["right_table"])
                grew = True
    return hops


def _joined(main_df, links, frames, main, use=lambda lk: lk["suggested"] == "yes"):
    """The main table with the attributes of every lookup it reaches by key, directly or through another lookup.

    A column whose name the table already has is not brought in, and its name is kept in `skipped_same_name`: a
    parent's own amount repeated on every row of its detail would be added up once per row."""
    df, joins = main_df.copy(), []
    for lk in _chain(links, main, use):
        if lk["left_column"] not in df.columns:
            continue          # the column it points from was itself left out for a name clash
        other = frames[lk["right_table"]]
        rest = [c for c in other.columns if c != lk["right_column"]]
        cols = [c for c in rest if c not in df.columns]
        look = other[[lk["right_column"], *cols]].rename(columns={lk["right_column"]: lk["left_column"]})
        look[lk["left_column"]] = look[lk["left_column"]].astype(df[lk["left_column"]].dtype)
        df = df.merge(look, on=lk["left_column"], how="left")
        join = {"source": lk["right_table"], "on": {lk["left_column"]: lk["right_column"]}, "columns": cols}
        if len(cols) < len(rest):
            join["skipped_same_name"] = [c for c in rest if c not in cols]
        joins.append(join)
    return df, joins


def _grain(tables, frames, links):
    """Detail tables: a table with more rows than the table it points at, whose numbers add up (per key) to the parent's
    numbers. Found from the values only, for each pair of a child column and a parent column:
    {child, parent, child_link, parent_link, child_rows, parent_rows, sums: [{child_column, parent_column,
    parent_rows_matching, child_total, parent_total}]}. A pair counts when the sum agrees on at least
    `intake_grain_match_min` of the parent's rows that have a value."""
    need, tol = _param("intake_grain_match_min"), _param("intake_grain_tolerance")
    out = []
    for lk in links:
        c, p = lk["left_table"], lk["right_table"]
        ct, pt = tables[c], tables[p]
        if not (lk["right_is_key"] and lk["suggested"] == "yes" and ct["rows"] > pt["rows"] and ct["date_columns"] and pt["date_columns"]
                and ct["measure_columns"] and pt["measure_columns"]):
            continue
        cf, pf = frames[c], frames[p]
        parent_key = pf[lk["right_column"]].astype(str)
        child_key = cf[lk["left_column"]].astype(str)
        sums = []
        for cc in ct["measure_columns"]:
            per = cf[cc].groupby(child_key).sum(min_count=1).reindex(parent_key.values)
            for pc in pt["measure_columns"]:
                have = pf[pc].notna().values
                if not have.any():
                    continue
                agree = np.isclose(per.values[have], pf[pc].values[have], rtol=tol, atol=tol)
                share = float(agree.mean())
                if share >= need:
                    sums.append({"child_column": cc, "parent_column": pc, "parent_rows_matching": share,
                                 "child_total": float(cf[cc].sum()), "parent_total": float(pf[pc].sum())})
        if sums:
            out.append({"child": c, "parent": p, "child_link": lk["left_column"], "parent_link": lk["right_column"],
                        "child_rows": ct["rows"], "parent_rows": pt["rows"], "sums": sums})
    return out


def _climb(main, grain):
    """The table to analyse: the main table, or its parent when its rows are the parent's detail, and so on upwards."""
    seen = {main}
    while True:
        up = next((g for g in grain if g["child"] == main and g["parent"] not in seen), None)
        if up is None:
            return main
        main = up["parent"]
        seen.add(main)


def _one_row(t, grain, lang):
    """What one row of the table is, said from the columns that never repeat, and for a detail table how often the
    column that points at its parent repeats."""
    keys = t["row_keys"] or t["keys"]
    zh = lang == "zh"
    if keys:
        said = ("每行一个 " if zh else "one row per ") + (" / ".join(keys[:3]))
    else:
        said = "没有一列能唯一标识一行" if zh else "no column identifies one row"
    for g in grain:
        if g["child"] == t["name"]:
            per = g["child_rows"] / max(g["parent_rows"], 1)
            said += (f"；{g['child_link']} 会重复，平均每个 {per:.2f} 行" if zh else
                     f"; {g['child_link']} repeats, {per:.2f} rows for each")
    return said


def _candidates(tables, grain, main, lang):
    """The tables that can be the one to analyse, with what the user needs to choose: rows, what one row is, and the
    totals that were found to agree."""
    names = list(dict.fromkeys([main, *[x for g in grain for x in (g["parent"], g["child"])]]))
    out = []
    for n in names:
        sums = {}
        for g in grain:
            for s in g["sums"]:
                if g["child"] == n:
                    sums[s["child_column"]] = s["child_total"]
                if g["parent"] == n:
                    sums[s["parent_column"]] = s["parent_total"]
        out.append({"table": n, "rows": tables[n]["rows"], "one_row": _one_row(tables[n], grain, lang), "sums": sums})
    return out


def _main_evidence(tables, grain, main, lang):
    zh = lang == "zh"
    t = tables[main]
    text = (f"「{main}」{t['rows']:,} 行（{_one_row(t, grain, lang)}）。" if zh else
            f"\"{main}\" has {t['rows']:,} rows ({_one_row(t, grain, lang)}). ")
    for g in grain:
        s = g["sums"][0]
        c, p = g["child"], g["parent"]
        if zh:
            text += (f"「{c}」{g['child_rows']:,} 行，按 {g['child_link']} 把「{s['child_column']}」加起来，"
                     f"在「{p}」的 {s['parent_rows_matching']:.1%} 的行上等于「{s['parent_column']}」，"
                     f"总数也相同（{s['child_total']:,.2f} 与 {s['parent_total']:,.2f}）。所以「{c}」是「{p}」的明细，一行一行加就会重复算；"
                     f"建议以「{p}」为主表。要按订单里面的东西（商品、每件价格）切，才选「{c}」。")
        else:
            text += (f"\"{c}\" has {g['child_rows']:,} rows; adding up \"{s['child_column']}\" per {g['child_link']} gives "
                     f"\"{s['parent_column']}\" of \"{p}\" on {s['parent_rows_matching']:.1%} of its rows, and the totals are equal "
                     f"({s['child_total']:,.2f} and {s['parent_total']:,.2f}). So \"{c}\" is the detail of \"{p}\": its rows add up to "
                     f"the parent's. \"{p}\" is suggested as the main table. Choose \"{c}\" only to cut by what is inside an order.")
    return text.strip()


def _no_time_axis(tables, lang) -> str:
    """Plain words for data that cannot answer 'why did this number change': no dates, or dates with nothing to add up."""
    dated = [n for n, t in tables.items() if t["date_columns"] or t["composite_dates"]]
    if lang == "zh":
        why = ("这些表里没有日期列" if not dated else f"有日期的表（{'、'.join(dated)}）里既没有可以加总的数（金额、数量），也没有能数个数的编号列")
        return (f"这份数据回答不了「这个数为什么变了」：{why}，没法把这一期和另一期放在一起比。"
                "如果你有按天、按周或按月的记录，请把它们一起给我。")
    why = ("none of the tables has a date column" if not dated else
           f"the tables with dates ({', '.join(dated)}) have no amount to add up and no identifier column to count")
    return (f"This data cannot answer \"why did this number change\": {why}, so there is no period to set against another. "
            "If you have records by day, week or month, give them to me as well.")


def _rn(col, lang):
    """Readable name of a column, for question text (the ids keep the raw names)."""
    return draft.readable(col)[lang]


def _q(qid, zh, en, options, lang, **extra):
    return {"id": qid, "ask": zh if lang == "zh" else en, "options": options, **extra}


def _derived_questions(main_qs, t, df, lang):
    """A rate is never the number to analyse: ask which decimal column is a unit price and what it multiplies, and whether a
    whole-number column is the sum of two others. Only when the table has both kinds of column. The role question of a
    decimal column then offers 'a unit price' first."""
    zh = lang == "zh"
    decimals = [c for c in t["measure_columns"] if pd.api.types.is_float_dtype(df[c])]
    wholes = [c for c in t["measure_columns"] if pd.api.types.is_integer_dtype(df[c])]
    if not decimals or not wholes:
        return main_qs
    ex = lambda c: ", ".join(draft.profile(df[[c]])[0]["examples"][:3])   # noqa: E731
    new = [
        _q("unit_price", "有没有哪一列是单价（每一晚、每一件的价格），不能直接加起来、要乘上数量才是金额？" + "；".join(f"「{c}」例如 {ex(c)}" for c in decimals),
           "Is any column a unit price (a price for one night, one item) that cannot be added up and must be multiplied by a quantity to give an amount? "
           + "; ".join(f"\"{c}\" e.g. {ex(c)}" for c in decimals), [*decimals, "none"], lang, suggested="none"),
        _q("sum_columns", "有没有一个数量其实是两列相加（比如周末晚数 + 工作日晚数 = 总晚数）？选两列，没有就不选。",
           "Is a quantity the sum of two columns (weekend nights + week nights = nights)? Pick two, or none.", wholes, lang),
        _q("unit_price_times", "单价乘以哪一列才是金额？（sum_columns = 上一题选的两列之和）",
           "Which column does the unit price multiply to give an amount? (sum_columns = the sum picked in the previous question)",
           ["sum_columns", *wholes], lang),
    ]
    new[1]["multi"] = True
    for q in main_qs:
        if q["id"].startswith("role:") and q.get("column") in decimals:
            q["options"] = [{"value": "unit_price", "label": "单价（每一晚、每一件的价格，要乘上数量才是金额）" if zh else
                             "A unit price (for one night, one item): multiplied by a quantity to give an amount"}, *q["options"]]
    i = next((k for k, q in enumerate(main_qs) if q["id"].startswith("role:")), len(main_qs))
    return [*main_qs[:i], *new, *main_qs[i:]]


def init(paths, workspace, lang="zh", main=None) -> dict:
    """Read every table, propose what each one is and how they connect, and write draft.json with the questions."""
    d = _derive(paths, workspace, lang, main)
    (Path(workspace) / "draft.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return d


def _derive(paths, workspace, lang="zh", main=None) -> dict:
    files = find_tables(paths)
    if not files:
        raise ValueError("no tables found (csv, csv.gz, xlsx)")
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    frames, tables = {}, {}
    for f in files:
        df, _ = draft.load_table(f.resolve())
        n = _name(f)
        while n in frames:
            n += "_2"
        frames[n] = df
        tables[n] = _table_facts(n, os.path.relpath(f.resolve(), ws.resolve()), df)
    dated = [t for t in tables.values() if (t["date_columns"] or t["composite_dates"]) and (t["measure_columns"] or t["id_columns"])]
    # A table whose two dates are in order on every row looks like a start and an end (a campaign, a holiday). It is
    # passed over for a real fact table, but when it is the only table with something to analyse (a small orders
    # table: ordered, shipped) it is the main table: the row-count line between the two cannot be drawn reliably.
    facts = [t for t in dated if not t.get("start_end")] or dated
    given = main is not None
    if main is None:
        if not facts:
            raise NoTimeAxis(_no_time_axis(tables, lang))
        # amounts first, size second: an event log of keys only (page views) is a main table only when nothing has amounts
        main = max(facts, key=lambda t: (bool(t["measure_columns"]), t["rows"]))["name"]
    elif main not in tables:
        raise ValueError(f"--main {main}: no table of that name; the tables are {', '.join(tables)}")
    links = _links(tables, frames, main)
    grain = _grain(tables, frames, links)
    if not given:
        # A table whose rows add up to the totals of the table it points at is that table's detail: analyse the parent.
        up = _climb(main, grain)
        if up != main:
            main = up
            links = _links(tables, frames, main)
            grain = _grain(tables, frames, links)
    for t in tables.values():
        t["suggested_kind"] = _suggest_kind(t, main, links, frames[t["name"]], grain)
    joined, joins = _joined(frames[main], links, frames, main)

    zh = lang == "zh"
    mq = _q("main_table", f"主表（每行一笔交易、要分析的那张）是「{main}」吗？它有日期、有数字（{tables[main]['rows']:,} 行）。",
            f"Is \"{main}\" the main table (one row per transaction, the one to analyse)? It has dates and numbers "
            f"({tables[main]['rows']:,} rows).", [main, *[t for t in tables if t != main]], lang, suggested=main)
    if grain:
        mq["evidence"] = _main_evidence(tables, grain, main, lang)
        mq["candidates"] = _candidates(tables, grain, main, lang)
    qs = [mq]
    kinds = {"lookup": ("查找表（一行一个编号，其余是属性）", "a lookup table (one row per key, the rest are attributes)"),
             "business": ("另一份业务数据（要拿来算数的，比如访问量）", "more business data (to compute with, e.g. visits)"),
             "events": ("事件记录（活动、调价之类，每行一件事、有起止日期）", "event records (campaigns, price changes: one per row, with start and end)"),
             "calendar": ("节假日日历", "a holiday calendar"),
             "series": ("外部的连续数据（天气之类）", "outside daily data (weather and the like)"),
             "market": ("行业大盘", "a market benchmark"),
             "ignore": ("不用", "not used")}
    for t in tables.values():
        if t["name"] == main:
            continue
        date_names = ", ".join(_rn(c, lang) for c in t["date_columns"]) or ("无" if zh else "none")
        key_names = ", ".join(_rn(c, lang) for c in t["keys"]) or ("无" if zh else "none")
        ev = (f"{t['rows']:,} 行；日期列 {date_names}；唯一编号列 {key_names}" if zh else
              f"{t['rows']:,} rows; date columns {date_names}; one-per-row columns {key_names}")
        if t.get("start_end"):
            ev += (f"；每行「{_rn(t['start_end'][0], lang)}」都不晚于「{_rn(t['start_end'][1], lang)}」，像是起止日期" if zh else
                   f"; on every row \"{_rn(t['start_end'][0], lang)}\" is not after \"{_rn(t['start_end'][1], lang)}\", like a start and an end")
        if "per_date" in t:
            ev += (f"；每个日期{'和「' + t['per_date'][0] + '」' if t['per_date'] else ''}只有一行" if zh else
                   f"; one row per date{' and ' + t['per_date'][0] if t['per_date'] else ''}")
        for g in grain:
            if g["child"] == t["name"]:
                s = g["sums"][0]
                ev += (f"；按 {g['child_link']} 把「{s['child_column']}」加起来，等于「{g['parent']}」的「{s['parent_column']}」"
                       f"（{s['parent_rows_matching']:.1%} 的行相同），是它的明细，已经加在「{g['parent']}」里了" if zh else
                       f"; its \"{s['child_column']}\" add up per {g['child_link']} to \"{s['parent_column']}\" of \"{g['parent']}\" "
                       f"({s['parent_rows_matching']:.1%} of rows), so it is the detail of \"{g['parent']}\" and already added up there")
        qs.append({"id": f"kind:{t['name']}", "ask": (f"「{t['name']}」这张表是什么？（{ev}）" if zh else f"What is the table \"{t['name']}\"? ({ev})"),
                   "options": [{"value": k, "label": v[0] if zh else v[1]} for k, v in kinds.items()],
                   "suggested": t["suggested_kind"], "evidence": ev})
    for lk in links:
        cov = f"{lk['coverage']:.1%}"
        qs.append(_q(f"link:{lk['left_table']}.{lk['left_column']}>{lk['right_table']}.{lk['right_column']}",
                     f"「{lk['left_table']}」的「{lk['left_column']}」和「{lk['right_table']}」的「{lk['right_column']}」是同一个东西吗？"
                     f"{lk['matched_rows']:,}/{lk['rows']:,} 行能对上（覆盖 {cov}）。",
                     f"Are \"{lk['left_column']}\" in \"{lk['left_table']}\" and \"{lk['right_column']}\" in \"{lk['right_table']}\" the same thing? "
                     f"{lk['matched_rows']:,} of {lk['rows']:,} rows match ({cov}).", ["yes", "no"], lang,
                     suggested=lk["suggested"], coverage=lk["coverage"]))
    for t in tables.values():
        if t["name"] == main:
            continue
        if t["suggested_kind"] in ("events", "calendar"):
            texts = [c for c in t["word_columns"] if not any(lk["left_table"] == t["name"] and lk["left_column"] == c for lk in links)]
            qs.append(_q(f"event_text:{t['name']}", f"「{t['name']}」里哪一列说的是这件事是什么？", f"Which column of \"{t['name']}\" says what happened?",
                         texts or t["word_columns"], lang, suggested=(texts or t["word_columns"] or [None])[0]))
        if t["suggested_kind"] == "events":
            qs.append(_q(f"event_kind:{t['name']}", f"「{t['name']}」里记的是你们自己做的事，还是外面发生的事？",
                         f"Does \"{t['name']}\" record things you did, or things that happened to you?",
                         ["internal", "external"], lang, suggested="internal"))
        if t["suggested_kind"] in ("business", "series", "market"):
            for c in t["number_columns"]:
                qs.append({"id": f"role:{t['name']}.{c}", "column": c, "table": t["name"],
                           "ask": (f"「{t['name']}」的「{c}」这一列是什么？" if zh else f"What is the column \"{c}\" of \"{t['name']}\"?"),
                           "options": [{"value": k, "label": v[lang]} for k, v in draft.ROLES.items()]})
        if t["suggested_kind"] in ("series", "market"):
            qs.append(_q(f"market_compares:{t['name']}", f"如果「{t['name']}」是行业大盘，拿它和主表的哪一列比？不是大盘就选 none。",
                         f"If \"{t['name']}\" is a market benchmark, which main-table column does it compare with? none if it is not one.",
                         ["none", *tables[main]["number_columns"]], lang, suggested="none"))
    comps = tables[main]["composite_dates"]
    for cd in comps:
        joined[cd["name"]] = derive_dates(joined, cd)
    prof = draft.profile(joined)
    # "belongs to" is between groups; a measured number (a list price) is an attribute, not a group to belong to
    cats = [p["column"] for p in prof if p["shape"] in ("category", "unique") and p["distinct"] <= draft.MAX_DIM_VALUES]
    fds = draft.belongs_to_candidates(joined, cats)
    only_date = (tables[main]["date_columns"] + [cd["name"] for cd in comps])
    quiet = draft.quiet_weekdays(joined, only_date[0]) if len(only_date) == 1 else []
    parts = {c for cd in comps for c in cd["columns"]}
    ids = {c for c in tables[main]["number_columns"] if c in joined.columns and draft.is_identifier(joined[c])}
    attributes = {c for j in joins for c in j["columns"] if c in joined.columns}
    row_keys = {c for c in ids if joined[c].is_unique and not joined[c].isna().any()}   # asked as "which column identifies one record"
    main_qs = draft.questions(prof, fds, lang, quiet, exclude=parts | row_keys | attributes, id_columns=ids - row_keys | row_keys)
    dups = tables[main]["duplicate_rows"]
    if dups and not row_keys:
        # asked on its own: a table with copies and no key often has no identifier column to hang the warning on
        main_qs.append(_q("duplicate_rows",
                          f"这张表有 {dups:,} 行与别的行完全相同，而且没有一列能唯一标识一行，没法判断它们是重复录入还是真的发生了两次。保留还是去掉这些重复的行？",
                          f"{dups:,} rows are exact copies of other rows and no column identifies one row, so there is no telling "
                          "whether they are double entries or two real events. Keep the copies or drop them?",
                          [{"value": "keep", "label": "保留（当作真的发生了两次）" if zh else "Keep (two real events)"},
                           {"value": "drop", "label": "去掉（当作重复录入）" if zh else "Drop (double entries)"}], lang, suggested="keep"))
    # a column of a few words could say that a row was cancelled or refunded: ask, never assume
    # a few words, or a two-valued number (0/1): either can mark a reversed row. Asked, never assumed.
    flag_cols = [p["column"] for p in prof if p["column"] in joined.columns and p["column"] not in parts
                 and ((p["shape"] == "category" and 2 <= p["distinct"] <= 12) or (p["shape"] == "number" and p["distinct"] == 2))]
    if flag_cols:
        main_qs.append(_q("reversal_column", "有没有一列说明这一行是被取消、退款或作废的？（选了的话，下一步选哪些取值算。）",
                          "Is there a column that says a row was cancelled, refunded or voided? (If so, the next question lists its values.)",
                          [*flag_cols, "none"], lang, suggested="none"))
        for c in flag_cols:
            vals = [str(v) for v in joined[c].dropna().unique()]
            q = _q(f"reversal_values:{c}", f"「{c}」的哪些取值表示这一行是被取消、退款或作废的？这些行会从所有数字里去掉。",
                   f"Which values of \"{c}\" mean the row was cancelled, refunded or voided? Those rows are left out of every number.",
                   [{"value": v, "label": v} for v in sorted(vals)], lang)
            q["multi"] = True
            main_qs.append(q)
    for q in main_qs:
        if q["id"] == "date_column":
            # composite dates are offered as composite:<name>; the single derived column is not offered twice
            q["options"] = [o for o in q["options"] if (o["value"] if isinstance(o, dict) else o) not in {cd["name"] for cd in comps}]
            for cd in comps:
                label = " + ".join(_rn(c, lang) for c in cd["columns"])
                q["options"].append({"value": f"composite:{cd['name']}", "label": label + (("（合起来是一个日期）" if zh else " (together one date)"))})
            if len(q["options"]) == 1:
                q["suggested"] = q["options"][0]["value"] if isinstance(q["options"][0], dict) else q["options"][0]
    for q in main_qs:
        if q["id"].startswith("role:"):
            q["table"] = main
    main_qs = _derived_questions(main_qs, tables[main], frames[main], lang)
    qs += main_qs
    return {"kind": "tables", "language": lang, "main": main, "tables": tables, "links": links, "joins": joins, "grain": grain,
            "belongs_to": fds, "quiet_weekdays": quiet, "joined_profile": prof, "questions": qs}


# ---------------------------------------------------------------- confirm

def _rel(path, root):
    return os.path.relpath(Path(root, path).resolve(), Path(root).resolve())


def _abs(path, root) -> Path:
    """draft.json keeps table paths relative to the workspace, so a workspace can be moved or shared."""
    return Path(root, path).resolve()


def _spec(t, root):
    suf = _suffix(Path(t["path"]))  # t["path"] is relative to the workspace (see init)
    return {"type": "excel" if suf.endswith((".xlsx", ".xls")) else "csv", "path": _rel(t["path"], root)}


def _yes(answers, lk):
    return answers.get(f"link:{lk['left_table']}.{lk['left_column']}>{lk['right_table']}.{lk['right_column']}") == "yes"


def confirm(workspace, answers: dict, today: dt.date | None = None) -> dict:
    ws = Path(workspace)
    d = json.loads((ws / "draft.json").read_text(encoding="utf-8"))
    lang, main, tables = d["language"], d["main"], d["tables"]
    chosen = answers.get("main_table", main)
    if chosen != main:
        if chosen not in tables:
            raise ValueError(f"main_table was answered as '{chosen}', but there is no table of that name; the tables are {', '.join(tables)}")
        return _confirm_other_main(ws, d, chosen, answers, today)
    today_s = (today or dt.date.today()).isoformat()
    said = {"kind": "user", "date": today_s}
    kind = {n: (answers.get(f"kind:{n}") or "ignore") if n != main else "main" for n in tables}
    unanswered = [n for n in tables if n != main and f"kind:{n}" not in answers]
    frames = {n: draft.load_table(_abs(t["path"], ws))[0] for n, t in tables.items() if kind[n] != "ignore"}
    links = [lk for lk in d["links"] if _yes(answers, lk) and kind.get(lk["left_table"]) != "ignore"
             and kind.get(lk["right_table"]) != "ignore"]
    joined, joins = _joined(frames[main], links, frames, main, use=lambda lk: True)
    for j in joins:
        if kind[j["source"]] != "lookup":
            raise ValueError(f"'{j['source']}' is linked to the main table by key but was not answered as a lookup table")

    mt = tables[main]
    date_col = answers.get("date_column") or (mt["date_columns"][0] if len(mt["date_columns"]) == 1 else None)
    derive = []
    if date_col and str(date_col).startswith("composite:"):
        cd = next((c for c in mt["composite_dates"] if f"composite:{c['name']}" == date_col), None)
        if cd is None:
            raise ValueError(f"'{date_col}' is not a date found in '{main}'")
        derive, date_col = [cd], cd["name"]
        joined[date_col] = derive_dates(joined, cd)
    if not date_col:
        raise ValueError("answer 'date_column' first")
    derived, price_col, per_unit = _derived_specs(answers, frames[main], joined)
    if derived:
        joined = apply_derived_columns(joined, derived)
    wanted = list(answers.get("dimensions") or [])
    dims = [x for x in wanted if x in joined.columns]
    problems = [(f"「{x}」不能用来切分：从主表「{main}」出发，没有一条确认过的链接能走到这一列。" if lang == "zh" else
                 f"\"{x}\" cannot be used to cut the numbers: no confirmed link leads from the main table \"{main}\" to a column of that name.")
                for x in wanted if x not in joined.columns]
    id_col = answers.get("order_id") if answers.get("order_id") not in (None, "none") else None

    sources, external = {}, {}
    main_src = _spec(mt, ws)
    if derive:
        main_src["derive_dates"] = derive
    if derived:
        main_src["derive_columns"] = derived
    if answers.get("duplicate_rows") == "drop":
        main_src["drop_duplicates"] = True
        joined = joined.drop_duplicates()
    rc = answers.get("reversal_column")
    rv = answers.get(f"reversal_values:{rc}") if rc and rc != "none" else None
    if rv:
        main_src["exclude_rows"] = {rc: list(rv)}
        joined = joined[~joined[rc].astype(str).isin([str(v) for v in rv])]
    if joins:
        sources[f"{main}_rows"] = main_src
        for j in joins:
            sources[j["source"]] = {**_spec(tables[j["source"]], ws), "key": j["on"][next(iter(j["on"]))]}
        sources[main] = {"type": "join", "base": f"{main}_rows", "joins": joins}
    else:
        sources[main] = main_src
    sources[main]["date_columns"] = [date_col]
    if id_col and joined[id_col].notna().all() and joined[id_col].is_unique:
        sources[main]["key"] = id_col

    specs = [{"column": q["column"], "role": answers.get(q["id"]), "source": main, "date": date_col, "dimensions": dims}
             for q in d["questions"] if q["id"].startswith("role:") and q.get("table") == main and q["column"] in joined.columns]
    for s_ in specs:
        if s_["column"] == price_col:
            s_["role"] = "skip"           # a unit price is multiplied, never added up
        elif s_["role"] == "unit_price":
            s_["role"] = "skip"
        elif per_unit and s_["column"] == per_unit["quantity_source"] and s_["role"] in (None, "skip"):
            s_["role"] = "quantity"
    for dc in derived:
        specs.append({"column": dc["name"], "role": "amount" if dc["name"] == (per_unit or {}).get("amount") else "quantity",
                      "source": main, "date": date_col, "dimensions": dims})
    missing = [s["column"] for s in specs if s["role"] is None]
    if missing:
        raise ValueError(f"answer what these columns are first: {', '.join(missing)}")
    id_spec = {"column": id_col, "source": main, "date": date_col, "dimensions": draft._additive_dims(joined, id_col, dims)} if id_col else None

    events, skipped, intake_log = [], [], []
    for n, t in tables.items():
        k = kind[n]
        if k in ("main", "lookup", "ignore"):
            continue
        df = frames[n]
        mine = [lk for lk in links if lk["left_table"] == n and lk["right_column"] in dims]
        if k == "business":
            cd = None if t["date_columns"] else t["composite_dates"][0]
            date = t["date_columns"][0] if cd is None else cd["name"]
            cols = {lk["right_column"]: lk["left_column"] for lk in mine}
            src = {**_spec(t, ws), "date_columns": [date], **({"derive_dates": [cd]} if cd else {})}
            if t.get("per_date") is not None:
                src["key"] = [date, *t["per_date"]]
            sources[n] = src
            for c in t["number_columns"]:
                specs.append({"column": c, "role": answers.get(f"role:{n}.{c}") or "skip", "source": n, "date": date,
                              "dimensions": list(cols), "columns": {dm: lc for dm, lc in cols.items() if dm != lc}})
        elif k in ("series", "market"):
            date = t["date_columns"][0]
            comp = answers.get(f"market_compares:{n}")
            ext = {**_spec(t, ws), "date_columns": [date], "value": t["number_columns"][0], "date": date,
                   "role": "market" if (k == "market" or (comp and comp != "none")) else "series"}
            if ext["role"] == "market":
                ext["compares_with"] = comp if comp and comp != "none" else next((s["column"] for s in specs if s["role"] == "amount"), None)
            if mine:
                ext["dimension_columns"] = {lk["right_column"]: lk["left_column"] for lk in mine}
            external[n] = ext
        elif k == "calendar":
            a, b = t["start_end"]
            text = answers.get(f"event_text:{n}") or (t["word_columns"] or [None])[0]
            ren = {text: "name", a: "start", b: "end"}
            # the calendar reader needs exactly these three names; a column already called that is moved aside
            for target in ("name", "start", "end"):
                clash = next((c for c in frames[n].columns if c == target and ren.get(c) != target and c not in ren), None)
                if clash:
                    ren[clash] = f"{clash}_original"
            external[n] = {**_spec(t, ws), "role": "calendar", "rename": ren}
        elif k == "events":
            a, b = t["start_end"]
            text = answers.get(f"event_text:{n}") or (t["word_columns"] or [None])[0]
            ek = answers.get(f"event_kind:{n}") or "internal"
            for i, row in df.reset_index(drop=True).iterrows():
                ents = [f"{lk['right_column']}:{row[lk['left_column']]}" for lk in mine if pd.notna(row[lk["left_column"]])
                        and str(row[lk["left_column"]]) != ""]
                details = {c: (None if pd.isna(row[c]) else row[c]) for c in df.columns if c not in (a, b, text)}
                if not ents:
                    skipped.append({"table": n, "row": i + 2, "reason": "no column of this row names a group in the data"})
                    continue
                events.append({"id": f"ev_{n}_{i + 1}", "kind": ek, "start": str(pd.to_datetime(row[a]).date()),
                               "end": str(pd.to_datetime(row[b]).date()), "entities": ents,
                               "what": {lang: str(row[text])}, "details": {k2: (float(v) if isinstance(v, (int, float)) else v)
                                                                            for k2, v in details.items() if v is not None},
                               "source": {"kind": "system_record", "ref": f"{_rel(t['path'], ws)} row {i + 2}",
                                          "note": "imported from an event table at intake; the table was confirmed, each row is to confirm"},
                               "status": "proposed"})
    every_column = list(dict.fromkeys([c for f in frames.values() for c in f.columns] + list(joined.columns)))
    names = draft.name_map([{"column": c, "name": draft.readable(c)} for c in every_column], answers)
    measures, metrics, identities, by_role = draft.build_metrics(specs, id_spec, answers.get("template", "orders"), said, names,
                                                                 per_unit=per_unit)
    north = answers.get("north_star") if answers.get("north_star") in metrics else by_role.get("amount") or next(iter(metrics), None)

    project = {"name": _abs(mt["path"], ws).parent.name, "language": lang, "sources": sources}
    if external:
        project["external"] = external
    q = draft.closed_block(answers, d.get("quiet_weekdays", []), said, today_s)
    if q:
        project["quality"] = q
    draft._dump(ws / "project.yaml", project)
    model = {"north_star": north, "measures": measures, "metrics": metrics, "identities": identities,
             "dimensions": {x: {"label": names.get(x) or draft._as_name(x), "column": x} for x in dims},
             "priorities": draft.proposed_priorities(measures, metrics, dims, said),
             "comparisons": []}
    draft._dump(ws / "model.yaml", model)
    rules = defaults.rules()
    rules["params"]["single_point_min_share"] = {"value": float(answers.get("single_point_share", 0.5)), "source": said, "status": "confirmed"}
    draft._dump(ws / "rules.yaml", rules)

    entities, relations = [], []
    for x in dims:
        vals = joined[x].dropna().unique()
        if len(vals) > draft.MAX_DIM_VALUES:
            continue
        for v in sorted(map(str, vals)):
            entities.append({"id": f"{x}:{v}", "type": x, "dimension": x, "key": v, "label": v, "source": {"kind": "data"}, "status": "confirmed"})
    ids = {e["id"] for e in entities}
    for f in d["belongs_to"]:
        if answers.get(f"belongs:{f['child']}>{f['parent']}") != "yes" or f["child"] not in dims or f["parent"] not in dims:
            continue
        for c, p in joined[[f["child"], f["parent"]]].dropna().drop_duplicates().itertuples(index=False):
            a, b = f"{f['child']}:{c}", f"{f['parent']}:{p}"
            if a in ids and b in ids:
                relations.append({"id": f"rel:{a}>{b}", "subject": a, "predicate": "belongs_to", "object": b,
                                  "source": {"kind": "data", "note": "confirmed by the user"}, "status": "confirmed"})
    good = []
    for e in events:
        if all(x in ids for x in e["entities"]):
            good.append(e)
        else:
            skipped.append({"table": e["id"], "reason": f"names a group that is not a chosen dimension value: {e['entities']}"})
    draft._dump(ws / "world.yaml", {"entities": entities, "relations": relations, "mechanisms": [], "events": good, "actions": []})
    asked = [x["id"] for x in d["questions"]]
    record = {"date": today_s, "main": main, "kinds": kind, "unanswered_tables": unanswered,
              "links_confirmed": [f"{lk['left_table']}.{lk['left_column']}>{lk['right_table']}.{lk['right_column']}" for lk in links],
              "joins": joins, "events_imported": len(good), "events_skipped": skipped,
              "questions": len(asked), "answered": sum(1 for x in asked if x in answers)}
    (ws / "intake.json").write_text(json.dumps({"draft": "draft.json", "answers": answers, "confirmed": record},
                                               ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"north_star": north, "metrics": list(metrics), "dimensions": dims, "intake": record, "problems": problems,
            "first_run": draft.first_run(ws, north)}


def _derived_specs(answers, main_df, joined):
    """derive_columns from the answers: a sum of two columns, and a unit price times a quantity. Returns
    (specs, the unit price column or None, {'amount', 'quantity', 'quantity_source'} for the average price per unit or None)."""
    specs, price, per_unit = [], answers.get("unit_price"), None
    if price in (None, "none"):
        price = next((k[5:] for k, v in answers.items() if k.startswith("role:") and v == "unit_price"), None)
    pair = answers.get("sum_columns") or []
    pair = pair if isinstance(pair, list) else [pair]
    pair = [c for c in pair if c != "none"]
    if pair and len(pair) != 2:
        raise ValueError(f"sum_columns takes exactly two columns, got {len(pair)}: {pair}")
    sum_name = None
    if pair:
        sum_name = f"{pair[0]}_plus_{pair[1]}"
        specs.append({"name": sum_name, "op": "add", "columns": pair})
    if price:
        if answers.get(f"role:{price}") not in (None, "skip", "unit_price"):
            raise ValueError(f"'{price}' was named a unit price, so it cannot be 'money in' as well: it is multiplied by a quantity, never added up "
                             "(adding up rates gives a meaningless number)")
        times = answers.get("unit_price_times")
        if times in (None, "none"):
            raise ValueError(f"'{price}' is a unit price, but the column it multiplies was not named (unit_price_times): a unit price on its own is not an amount")
        if times == "sum_columns":
            if not sum_name:
                raise ValueError("unit_price_times is sum_columns, but no two columns were given in sum_columns")
            times = sum_name
        amount = f"{price}_times_{times}"
        specs.append({"name": amount, "op": "mul", "columns": [price, times]})
        per_unit = {"amount": amount, "quantity": times, "quantity_source": times, "price": price}
    for sp in specs:
        for c in sp["columns"]:
            if c not in main_df.columns and c not in {x["name"] for x in specs}:
                raise ValueError(f"derived column '{sp['name']}' needs '{c}', which is not a column of the main table")
    return specs, price, per_unit


def _confirm_other_main(ws, d, chosen, answers, today):
    """The user chose a main table other than the suggested one. Read the tables again for that table, keep the answers
    that still fit the new questions, and either confirm or say which questions only exist now."""
    files = [_abs(t["path"], ws) for t in d["tables"].values()]
    new = _derive(files, ws, d["language"], chosen)
    new["main_changed_from"] = d["main"]
    (ws / "draft.json").write_text(json.dumps(new, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    asked_before = {q["id"] for q in d["questions"]}
    fit = {}
    for q in new["questions"]:
        if q["id"] not in answers:
            continue
        vals = [o["value"] if isinstance(o, dict) else o for o in q["options"]]
        v = answers[q["id"]]
        if not vals or all(x in vals for x in (v if isinstance(v, list) else [v])):
            fit[q["id"]] = v
    fresh = [q for q in new["questions"] if q["id"] not in fit and q["id"].startswith(("kind:", "link:", "role:", "order_id"))
             and (q["id"] not in asked_before or q["id"] in answers)]
    stale = [q for q in fresh if q["id"].startswith("link:") and q.get("suggested") != "yes" and q["id"] not in answers]
    fresh = [q for q in fresh if q not in stale]
    rest = {k: v for k, v in answers.items() if k not in {q["id"] for q in new["questions"]} or k in fit}
    rest["main_table"] = chosen
    if fresh:
        ids = [q["id"] for q in fresh]
        raise NeedsAnswers(f"the main table is now '{chosen}' (it was '{d['main']}'). {len(ids)} questions are new or no longer fit your earlier "
                           f"answers: {', '.join(ids)}. They are saved in draft.json; answer them and run confirm again.", ids, fresh)
    return confirm(ws, rest, today)


# ---------------------------------------------------------------- propose

def _norm(text: str) -> str:
    """Whitespace, line breaks and Markdown emphasis are ignored; every other character must match."""
    return re.sub(r"[\s*`]+", "", text)


def quote_in(doc_text: str, quote: str, min_chars: int | None = None) -> bool:
    q = _norm(quote or "")
    n = _param("intake_quote_min_chars") if min_chars is None else min_chars
    return len(q) >= n and q in _norm(doc_text)


def propose(workspace, doc, items: list, today: dt.date | None = None) -> dict:
    """Record mechanisms and events an AI tool proposes from a document. Each needs the sentence it came from;
    a sentence not found in the document is refused. Accepted entries are 'from a document, to confirm'."""
    from .evolve import _next_id, _hint
    ws = Path(workspace)
    doc = Path(doc)
    text = doc.read_text(encoding="utf-8")
    world = yaml.safe_load((ws / "world.yaml").read_text(encoding="utf-8")) or {}
    ents = {e["id"] for e in world.get("entities", [])}
    today_s = (today or dt.date.today()).isoformat()
    accepted, rejected = [], []
    min_chars = _param("intake_quote_min_chars", ws)
    for it in items:
        kind = it.get("type")
        entry = dict(it.get("entry") or {})
        why = None
        if kind not in ("mechanism", "event"):
            why = "type must be mechanism or event"
        elif not quote_in(text, it.get("quote", ""), min_chars):
            why = "the quote is not in the document (whitespace aside, it must match word for word)" \
                if len(_norm(it.get("quote", ""))) >= min_chars else f"the quote is shorter than {min_chars} characters"
        elif not entry.get("entities"):
            why = "say which groups it touches (entities)"
        elif [x for x in entry["entities"] if x not in ents]:
            why = f"unknown entities: {[x for x in entry['entities'] if x not in ents]}"
        elif kind == "event" and not entry.get("start"):
            why = "an event needs a start date"
        elif kind == "mechanism" and not entry.get("claim"):
            why = "a mechanism needs a claim"
        elif kind == "event" and not entry.get("what"):
            why = "an event needs a what"
        if why:
            rejected.append({"quote": it.get("quote"), "type": kind, "reason": why})
            continue
        bucket = world.setdefault("mechanisms" if kind == "mechanism" else "events", [])
        entry["id"] = entry.get("id") or _next_id({x["id"] for x in bucket}, "mech" if kind == "mechanism" else "ev", _hint(entry))
        entry.pop("hint", None)
        if kind == "event":
            entry.setdefault("kind", "internal")
        entry["source"] = {"kind": "document", "ref": os.path.relpath(doc.resolve(), ws.resolve()), "quote": it["quote"], "date": today_s,
                           "note": "proposed by the user's AI tool after reading the document"}
        entry["status"] = "proposed"
        bucket.append(entry)
        accepted.append({"id": entry["id"], "type": kind, "quote": it["quote"]})
    draft._dump(ws / "world.yaml", world)
    with open(ws / "proposals.jsonl", "a", encoding="utf-8") as f:
        at = today.isoformat() if today else dt.datetime.now().isoformat(timespec="seconds")
        f.write(json.dumps({"at": at, "doc": os.path.relpath(doc.resolve(), ws.resolve()),
                            "accepted": accepted, "rejected": rejected}, ensure_ascii=False) + "\n")
    return {"accepted": accepted, "rejected": rejected}


# ---------------------------------------------------------------- where each part came from

def formation(workspace) -> dict:
    """Every part of the workspace grouped by where it came from: the data, the user's answers, a document,
    or nobody yet (what only a person can add)."""
    from .workspace import Workspace
    w = Workspace(workspace)
    rec = {}
    p = Path(workspace) / "intake.json"
    if p.exists():
        rec = json.loads(p.read_text(encoding="utf-8"))
    world = w.world
    by = {"from_data": [], "user_answers": [], "from_documents": [], "needs_a_person": []}
    for e in world.get("entities", []):
        if (e.get("source") or {}).get("kind") == "data":
            by["from_data"].append({"kind": "entity", "id": e["id"]})
    for r in world.get("relations", []):
        by["from_data"].append({"kind": "relation", "id": r["id"], "confirmed_by_user": True})
    for name, m in w.metrics.items():
        k = (m.get("source") or {}).get("kind")
        by["from_data" if k == "formula" else "user_answers"].append({"kind": "metric", "id": name, "via": k})
    for i in w.model.get("identities", []):
        by["from_data"].append({"kind": "identity", "id": i["id"], "via": "formula"})
    for name, s in w.sources.specs.items():
        if s.get("type") == "join":
            by["from_data"].append({"kind": "lookup", "id": name, "joins": [j["source"] for j in s["joins"]]})
    for name, s in w.external.specs.items():
        by["from_data"].append({"kind": f"outside_{s.get('role')}", "id": name})
    for k in ("events", "mechanisms", "actions"):
        for x in world.get(k, []):
            src = (x.get("source") or {}).get("kind")
            item = {"kind": k[:-1], "id": x["id"], "status": x.get("status"), "source": x.get("source", {}).get("ref")}
            if src == "document":
                by["from_documents"].append({**item, "quote": x["source"].get("quote")})
            elif src == "system_record" and "intake" in (x["source"].get("note") or ""):
                by["from_data"].append(item)
            elif src == "user":
                by["user_answers"].append(item)
            else:
                by["from_data" if src in ("data", "system_record") else "user_answers"].append(item)
    ans = rec.get("answers") or {}
    for qid, v in ans.items():
        by["user_answers"].append({"kind": "answer", "id": qid, "answer": v})
    # What tables cannot show. Mechanisms are always listed: a document may give some, but why a group is
    # naturally different (a commission, a cheaper category) is mostly in people's heads.
    confirmed_mech = [x for x in world.get("mechanisms", []) if x.get("status") == "confirmed"]
    by["needs_a_person"].append({"kind": "mechanism", "reason": "mechanisms", "have": len(world.get("mechanisms", [])),
                                 "confirmed": len(confirmed_mech)})
    if not world.get("actions"):
        by["needs_a_person"].append({"kind": "action", "reason": "actions"})
    pr = w.model.get("priorities") or {}
    if not any(x.get("status") == "confirmed" for x in pr.values()):
        by["needs_a_person"].append({"kind": "priority", "reason": "priorities"})
    if not w.model.get("comparisons"):
        by["needs_a_person"].append({"kind": "comparison", "reason": "comparisons"})
    if not w.model.get("pvm"):
        by["needs_a_person"].append({"kind": "pvm", "reason": "pvm"})
    if all(str(e.get("label")) == str(e.get("key")) for e in world.get("entities", [])):
        by["needs_a_person"].append({"kind": "labels", "reason": "labels"})
    pending = [x for x in world.get("events", []) + world.get("mechanisms", []) if x.get("status") == "proposed"]
    return {"counts": {k: len(v) for k, v in by.items()}, "items": by, "pending_confirmation": [x["id"] for x in pending],
            "intake": rec.get("confirmed")}
