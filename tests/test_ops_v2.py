"""v0.2 item 10: growth accounting, price-volume-mix, shrinkage, and follow-up questions."""

import json
import math
import shutil
import sys
from pathlib import Path

import importlib

import pytest

from aib import cli
from aib.ops import shrink
from aib.run import run
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store" / "workspace"
sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402


def _mod(name):
    """Modules for later v0.2 items are imported per test, so this file is collected before they exist."""
    return importlib.import_module(name)


class _Lazy:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        return getattr(_mod(self._name), attr)


growth_accounting = _Lazy("aib.ops.growth_accounting")
pvm = _Lazy("aib.ops.pvm")
followup = _Lazy("aib.followup")


# ---------- growth accounting ----------

def test_growth_accounting_buckets_close_exactly():
    base = {"a": 10, "b": 10, "c": 5, "d": 7}
    cur = {"a": 12, "b": 8, "e": 4, "f": 3}
    earlier = {"f"}                                   # f bought before the base window, not in it
    r = growth_accounting.decompose(base, cur, earlier)
    b = r["buckets"]
    assert b == pytest.approx({"new": 4, "resurrected": 3, "retained": 18, "expansion": 2, "contraction": -2,
                               "churned": -12})
    assert r["closed"] and math.isclose(r["total_delta"], sum(cur.values()) - sum(base.values()))
    assert b["new"] + b["resurrected"] + b["expansion"] + b["contraction"] + b["churned"] == pytest.approx(r["total_delta"])
    assert r["quick_ratio"] == pytest.approx((4 + 3 + 2) / (12 + 2))
    assert r["gross_retention"] == pytest.approx(18 / 32)


def test_growth_accounting_in_a_run_reconciles_with_guests(tmp_path):
    df = synth.orders(seed=5, customers=4000)
    df.loc[df.index % 17 == 0, "customer_id"] = None
    ws = Workspace(synth.workspace(tmp_path, df))
    s = run(ws, {"metric": "revenue", "current": ["2026-10-01", "2026-10-25"], "base": "pop",
                 "growth_accounting": {"customer_column": "customer_id"}}, write=False)
    g = s["growth_accounting"]
    assert g["closed"]
    total = s["qualify"]["total_cur"] - s["qualify"]["total_base"]
    assert g["total_delta"] + g["no_customer_delta"] == pytest.approx(total)


# ---------- price-volume-mix ----------

def test_pvm_closes_and_splits_as_expected():
    seg = {"x": (100, 1000.0, 110, 1100.0),     # (qty_base, value_base, qty_cur, value_cur): volume only
           "y": (100, 2000.0, 100, 2400.0),     # price only
           "z": (0, 0.0, 10, 50.0)}             # new item
    r = pvm.decompose(seg)
    assert r["closed"]
    assert r["price_total"] == pytest.approx(400.0)
    assert r["new_total"] == pytest.approx(50.0)
    assert r["volume_total"] + r["mix_total"] == pytest.approx(100.0)
    assert r["volume_total"] + r["mix_total"] + r["price_total"] + r["new_total"] + r["gone_total"] == pytest.approx(r["delta"])


def test_pvm_pure_mix_shift():
    seg = {"cheap": (50, 500.0, 80, 800.0), "dear": (50, 1500.0, 20, 600.0)}
    r = pvm.decompose(seg)
    assert r["volume_total"] == pytest.approx(0.0)
    assert r["price_total"] == pytest.approx(0.0)
    assert r["mix_total"] == pytest.approx(-600.0)


# ---------- shrinkage ----------

def test_normal_normal_shrinks_small_groups_more():
    est = shrink.normal_normal(rates=[100, 102, 98, 300], variances=[1, 1, 1, 2500], prior_mean=100)
    assert est["shrunk"][3] < 200 and est["shrunk"][0] == pytest.approx(100, abs=2.5)
    assert est["weights"][3] < est["weights"][0]


def test_beta_binomial_pulls_three_out_of_three_down():
    est = shrink.beta_binomial(successes=[3, 50, 60], trials=[3, 1000, 1000])
    assert est["shrunk"][0] < 0.5


# ---------- follow-up ----------

def test_followup_inherits_filters_and_path(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO, ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    first = run(ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "filters": {"region": "east"},
                     "id": "first"}, out_dir=tmp_path / "first")
    slot = first["slots"][-1]["id"]
    cfg = followup.config(tmp_path / "first", slot, ["city"])
    assert cfg["filters"]["region"] == "east"
    for d, v in [*first["slots"][-1]["path"], (first["slots"][-1]["dimension"], first["slots"][-1]["value"])]:
        assert cfg["filters"][d] == v
    assert cfg["dimensions"] == ["city"] and cfg["parent_run"] == "first"
    rc = cli.main(["followup", "--workspace", str(ws), "--from", str(tmp_path / "first"), "--slot", slot,
                   "--dimensions", "city", "--out", str(tmp_path / "second")])
    assert rc in (0, 1)
    rec = json.loads((tmp_path / "second" / "record.json").read_text(encoding="utf-8"))
    assert rec["config"]["parent_run"] == "first"


def test_followup_rejects_an_unknown_slot(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO, ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    run(ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "id": "f"}, out_dir=tmp_path / "f")
    with pytest.raises(KeyError):
        followup.config(tmp_path / "f", "channel=nowhere")
