"""The order a person gave their dimensions in decides ties between equally good cuts, and a blank value reads as blank."""

import sys
from pathlib import Path

import pytest
import yaml

from aib import intake, search
from aib.run import run
from aib.validate import all_problems
from aib.workspace import Workspace

sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402

CUR = ["2026-10-19", "2026-10-25"]
SAID = {"kind": "user", "date": "2026-11-04", "note": "order of the user's selection"}


def _proposed(order):
    return {"revenue": {"order": order, "mode": "drill", "source": SAID, "status": "proposed"}}


def _scored(monkeypatch, scores):
    """Every candidate cut gets the score given for its dimension (default 0.0); everything else is computed."""
    real = search.candidate

    def fake(ws, metric, dim, base, cur, filters):
        c = real(ws, metric, dim, base, cur, filters)
        if "error" not in c:
            c["score"] = scores.get(dim, 0.0)
        return c
    monkeypatch.setattr(search, "candidate", fake)


def _first_cut(ws, extra=None):
    rec = run(ws, {"metric": "revenue", "current": CUR, "base": "pop", **(extra or {})}, write=False)
    return rec["cuts"][0]["dimension"]


@pytest.fixture(scope="module")
def df():
    return synth.orders(seed=11, start="2026-06-01", per_day=60)


def _ws(tmp_path, df, priorities):
    root = synth.workspace(tmp_path, df, priorities=priorities)
    ws = Workspace(root)
    assert all_problems(ws) == []
    return ws


# ---------- item 1: intake keeps the order the person gave ----------

def test_intake_writes_the_order_the_user_chose_as_a_proposed_priority(tmp_path, df):
    tables = tmp_path / "t"
    tables.mkdir()
    df.to_csv(tables / "orders.csv", index=False)
    ws = tmp_path / "ws"
    intake.init([tables], ws, lang="en")
    answers = {"main_table": "orders", "date_column": "order_date", "measure_columns": ["revenue"],
               "measure_roles": {"revenue": "amount"}, "order_id": "order_id", "template": "orders",
               "north_star": "revenue", "dimensions": ["region", "customer_type", "channel"],
               "single_point_share": 0.5, "reversal_column": "none"}
    intake.confirm(ws, answers)
    model = yaml.safe_load((ws / "model.yaml").read_text(encoding="utf-8"))
    pr = model["priorities"]["revenue"]
    assert pr["order"] == ["region", "customer_type", "channel"]       # not alphabetical
    assert pr["status"] == "proposed"
    assert all_problems(Workspace(ws)) == []


# ---------- item 2: when nothing moved, the user's order picks the first cut ----------

DIP = [{"where": {"region": "x"}, "start": "2026-10-19", "end": "2026-10-25", "orders": 0.5}]
ORDER = ["region", "customer_type", "channel"]


@pytest.fixture(scope="module")
def dip_df():
    return synth.orders(seed=11, start="2026-06-01", per_day=60, effects=DIP)


def _record(ws):
    return run(ws, {"metric": "revenue", "current": CUR, "base": "pop"}, write=False)


def _rule(rec):
    return next(n["first_cut"]["rule"] for n in rec["notes"] if "first_cut" in n)


def test_the_fixtures_are_quiet_and_not_quiet(tmp_path, df, dip_df):
    quiet = _record(_ws(tmp_path / "q", df, {}))
    moved = _record(_ws(tmp_path / "m", dip_df, {}))
    assert quiet["verdict_unusual"]["then"]["verdict"] == "within_usual_range"
    assert moved["verdict_unusual"]["then"]["verdict"] == "unusual_low"


def test_quiet_week_and_a_proposed_order_cut_its_first_dimension_first(tmp_path, df, monkeypatch):
    ws = _ws(tmp_path, df, _proposed(ORDER))
    _scored(monkeypatch, {"channel": 0.5, "customer_type": 0.2})          # others score higher; the scores say nothing
    rec = _record(ws)
    assert rec["cuts"][0]["dimension"] == "region"
    assert _rule(rec) == "quiet_user_order"


def test_quiet_week_keeps_the_scores_in_the_record(tmp_path, df, monkeypatch):
    ws = _ws(tmp_path, df, _proposed(ORDER))
    _scored(monkeypatch, {"channel": 0.5})
    cands = {c["dimension"]: c["score"] for c in _record(ws)["cuts"][0]["candidates"]}
    assert cands["channel"] == 0.5 and cands["region"] == 0.0


def test_a_week_that_moved_lets_the_higher_score_win(tmp_path, dip_df, monkeypatch):
    ws = _ws(tmp_path, dip_df, _proposed(ORDER))
    _scored(monkeypatch, {"channel": 0.01})
    rec = _record(ws)
    assert rec["cuts"][0]["dimension"] == "channel"
    assert _rule(rec) == "highest_score"


def test_a_week_that_moved_is_not_fixed_by_a_proposed_order(tmp_path, dip_df, monkeypatch):
    ws = _ws(tmp_path, dip_df, _proposed(ORDER))
    _scored(monkeypatch, {"customer_type": 0.5})
    rec = _record(ws)
    assert rec["cuts"][0]["dimension"] == "customer_type"
    assert _rule(rec) == "highest_score"


def test_quiet_week_without_an_order_follows_the_scores(tmp_path, df, monkeypatch):
    ws = _ws(tmp_path, df, {})
    _scored(monkeypatch, {"region": 0.5})
    rec = _record(ws)
    assert rec["cuts"][0]["dimension"] == "region"
    assert _rule(rec) == "highest_score"


def test_quiet_week_without_an_order_and_equal_scores_is_alphabetical(tmp_path, df, monkeypatch):
    ws = _ws(tmp_path, df, {})
    _scored(monkeypatch, {})
    rec = _record(ws)
    assert rec["cuts"][0]["dimension"] == "channel"
    assert _rule(rec) == "highest_score"


@pytest.mark.parametrize("which", ["quiet", "moved"])
def test_a_confirmed_order_still_fixes_the_first_cut(tmp_path, df, dip_df, monkeypatch, which):
    pr = _proposed(ORDER)
    pr["revenue"]["status"] = "confirmed"
    ws = _ws(tmp_path, df if which == "quiet" else dip_df, pr)
    _scored(monkeypatch, {"channel": 0.5})
    rec = _record(ws)
    assert rec["cuts"][0]["dimension"] == "region"
    assert _rule(rec) == "stated_order"


def test_dimensions_given_for_the_run_fix_the_first_cut(tmp_path, df, monkeypatch):
    ws = _ws(tmp_path, df, _proposed(ORDER))
    _scored(monkeypatch, {"region": 0.5})
    rec = run(ws, {"metric": "revenue", "current": CUR, "base": "pop", "dimensions": ["channel"]}, write=False)
    assert rec["cuts"][0]["dimension"] == "channel"
    assert _rule(rec) == "stated_order"


# ---------- item 3: a blank value is shown as blank ----------

@pytest.fixture(scope="module")
def blank_run(tmp_path_factory, df):
    d = df.copy()
    d["channel"] = d["channel"].replace({"c": "NULL"})
    root = synth.workspace(tmp_path_factory.mktemp("blank"), d)
    out = root / "out"
    rec = run(Workspace(root), {"metric": "revenue", "current": CUR, "base": "pop", "dimensions": ["channel"]}, out_dir=out)
    return rec, out


def test_blank_value_is_shown_as_blank_in_both_languages(blank_run):
    _, out = blank_run
    en = (out / "report.en.md").read_text(encoding="utf-8")
    zh = (out / "report.zh.md").read_text(encoding="utf-8")
    assert "| (blank) |" in en and "| NULL |" not in en
    assert "| (空) |" in zh and "| NULL |" not in zh


def test_the_blank_label_changes_no_number_or_group(blank_run):
    rec, _ = blank_run
    keys = {x["key"] for x in rec["cuts"][0]["result"]["segments"]}
    assert keys == {"a", "b", "NULL"}


def test_a_value_named_by_a_person_keeps_its_name():
    from aib import report

    class World:
        entities = {"agent:NULL": {"label": {"en": "Walk-in agent", "zh": "上门代理"}}}

        def entity_for(self, dim, key):
            return "agent:NULL" if (dim, str(key)) == ("agent", "NULL") else None

    assert report.seg_label(None, World(), "agent", "NULL", "en") == "Walk-in agent"
    assert report.seg_label(None, World(), "agent", "NULL", "zh") == "上门代理"
    assert report.seg_label(None, World(), "agent", "", "en") == "(blank)"
    assert report.seg_label(None, World(), "agent", "", "zh") == "(空)"
    assert report.seg_label(None, World(), "agent", "None", "en") == "None"
