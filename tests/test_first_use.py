"""First use with nothing but a table: profile, ask, confirm, and get a first attribution."""

from pathlib import Path

import pandas as pd

from aib import draft
from aib.run import run
from aib.validate import all_problems
from aib.workspace import Workspace

ORDERS = Path(__file__).resolve().parents[1] / "demo" / "store" / "workspace" / "data" / "orders.csv.gz"


def small_table(tmp_path) -> Path:
    df = pd.read_csv(ORDERS)
    df = df[df["order_date"] >= "2025-09-01"].drop(columns=["cost", "commission"])
    p = tmp_path / "my_shop.csv"
    df.to_csv(p, index=False)
    return p


def test_profile_reads_shape_not_names(tmp_path):
    df = pd.DataFrame({"a": ["2026-01-01", "2026-01-02"], "b": [1.5, 2.5], "c": ["x", "y"], "d": ["u1", "u2"]})
    shapes = {p["column"]: p["shape"] for p in draft.profile(df)}
    assert shapes == {"a": "date", "b": "number", "c": "unique", "d": "unique"}


def test_belongs_to_is_found_from_data():
    df = pd.DataFrame({"city": ["s", "h", "b", "s"], "region": ["e", "e", "n", "e"]})
    assert draft.belongs_to_candidates(df, ["city", "region"]) == [{"child": "city", "parent": "region", "pairs": 3}]


def test_init_asks_and_confirm_builds_a_runnable_workspace(tmp_path):
    data = small_table(tmp_path)
    ws_dir = tmp_path / "ws"
    d = draft.init(data, ws_dir, lang="zh")
    ids = {q["id"] for q in d["questions"]}
    assert {"date_column", "role:revenue", "role:gross_profit", "order_id", "dimensions", "single_point_share"} <= ids
    assert any(q["id"] == "belongs:city>region" for q in d["questions"])
    assert not any(q["id"].startswith("role:order_id") for q in d["questions"]), "an id column is not offered as a metric"

    answers = {"date_column": "order_date", "role:revenue": "amount", "role:gross_profit": "profit",
               "order_id": "order_id", "template": "orders", "north_star": "revenue",
               "dimensions": ["channel", "category", "region", "city", "delivery", "customer_type"],
               "belongs:city>region": "yes", "single_point_share": 0.5}
    out = draft.confirm(ws_dir, answers)
    ws = Workspace(ws_dir)
    assert all_problems(ws) == []
    assert {"revenue", "gross_profit", "id_count", "per_id", "margin"} <= set(ws.metrics)
    assert len(ws.world["relations"]) == 8
    s = run(ws, out["first_run"], out_dir=tmp_path / "first")
    assert not s["blocked"], [c for c in s["checks"] if not c["pass"]]
    assert s["cuts"] and (tmp_path / "first" / "report.zh.md").exists()
