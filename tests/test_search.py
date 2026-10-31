"""v0.2 items 2 and 3: tell noise from a cause, and choose which dimension to cut instead of a fixed order."""

import datetime as dt
import sys
from pathlib import Path

import pytest

from aib import search
from aib.run import run
from aib.workspace import Workspace

sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402


@pytest.fixture(scope="module")
def noise_ws(tmp_path_factory):
    root = tmp_path_factory.mktemp("noise")
    return Workspace(synth.workspace(root, synth.orders(seed=7)))


def weeks(n, end=dt.date(2026, 10, 25)):
    for i in range(n):
        e = end - dt.timedelta(days=7 * i)
        yield [(e - dt.timedelta(days=6)).isoformat(), e.isoformat()]


def test_pure_noise_rarely_drills(noise_ws):
    drilled = sum(bool(run(noise_ws, {"metric": "revenue", "current": w, "base": "yoy"}, write=False)["slots"]) for w in weeks(30))
    assert drilled <= 3, drilled


@pytest.mark.parametrize("metric", ["revenue", "aov"])
def test_pure_noise_false_drill_rate_across_unseen_seeds(tmp_path, metric):
    """Ten noise shops the gate was never tuned on, 30 weeks each: at most 5% of weeks may be drilled into."""
    drilled = 0
    for seed in range(201, 211):
        ws = Workspace(synth.workspace(tmp_path / str(seed), synth.orders(seed=seed)))
        drilled += sum(bool(run(ws, {"metric": metric, "current": w, "base": "yoy"}, write=False)["slots"]) for w in weeks(30))
    print(f"\n{metric}: {drilled}/300 pure-noise weeks drilled into")
    assert drilled <= 15, f"{metric}: {drilled}/300 noise weeks drilled into"


def test_run_of_days_is_held_to_a_two_test_bar():
    one = search.p_for_z(3.0)
    assert abs(search.p_for_z(search.z_for_p(2 * one, -3.0)) - 2 * one) < 1e-9
    assert -3.0 < search.z_for_p(2 * one, -3.0) < -2.7


def test_quiet_week_on_a_two_value_dimension_does_not_drill(noise_ws):
    s = run(noise_ws, {"metric": "revenue", "current": ["2026-08-03", "2026-08-09"], "base": "pop",
                       "dimensions": ["customer_type"], "mode": "fixed"}, write=False)
    assert not s["slots"]
    cut = s["cuts"][0]
    assert cut["decision"]["then"]["action"] == "stop"
    assert cut["gate"]["n_groups"] == 2 and cut["gate"]["top1_excess"] is not None


def test_every_segment_reports_its_own_z_and_size(noise_ws):
    s = run(noise_ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "mode": "fixed",
                       "dimensions": ["channel"]}, write=False)
    seg = s["cuts"][0]["result"]["segments"]
    assert all("z" in x and "n" in x for x in seg)
    assert all(x["n"] > 0 for x in seg)


def test_excess_over_an_even_split():
    assert search.excess(0.5, 2) == 0.0
    assert search.excess(1.0, 2) == 1.0
    assert search.excess(0.55, 3) == pytest.approx((0.55 - 1 / 3) / (1 - 1 / 3))


def test_js_divergence_is_zero_for_identical_and_symmetric():
    assert search.js([0.5, 0.5], [0.5, 0.5]) == 0
    assert search.js([0.9, 0.1], [0.1, 0.9]) == pytest.approx(search.js([0.1, 0.9], [0.9, 0.1]))
    assert search.js([1, 0], [0, 1]) == pytest.approx(1.0)


@pytest.fixture(scope="module")
def cross_ws(tmp_path_factory):
    """One cause, visible on two dimensions: channel b in region y loses 80% of orders from 2026-10-12."""
    root = tmp_path_factory.mktemp("cross")
    df = synth.orders(seed=3, effects=[{"where": {"channel": "b", "region": "y"}, "start": "2026-10-12", "orders": 0.2}])
    return Workspace(synth.workspace(root, df))


def test_one_cause_on_two_dimensions_is_reported_once(cross_ws):
    s = run(cross_ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    leaves = [x for x in s["slots"] if x.get("leaf", True)]
    assert len(leaves) == 1, [x["id"] for x in s["slots"]]
    ids = leaves[0]["id"]
    assert "channel=b" in ids and "region=y" in ids
    assert any(c.get("role") == "cross_check" for c in s["cuts"])


def test_layer_choice_is_scored_and_recorded(cross_ws):
    s = run(cross_ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    first = s["cuts"][0]
    assert first["role"] == "layer"
    cands = first["candidates"]
    assert {c["dimension"] for c in cands} >= {"channel", "region"}
    assert all({"explanatory_power", "surprise", "score"} <= set(c) for c in cands)
    assert cands[0]["dimension"] == first["dimension"]
    assert s["config_used"]["max_depth"] <= 3


def test_depth_is_bounded(cross_ws):
    s = run(cross_ws, {"metric": "revenue", "current": ["2026-10-19", "2026-10-25"], "base": "yoy"}, write=False)
    assert max(len(c["path"]) for c in s["cuts"]) < 3


def test_small_group_does_not_rank_first_after_shrinkage(tmp_path):
    """A category with a handful of orders and wild prices must not be named the main cause of an AOV change."""
    dims = {"category": {"big1": 0.45, "big2": 0.45, "tiny": 0.0015}, "region": {"x": 0.6, "y": 0.4}}
    df = synth.orders(seed=11, dims=dims, per_day=400, sigma=0.3,
                      effects=[{"where": {"category": "tiny"}, "start": "2026-10-19", "price": 25.0},
                               {"where": {"category": "big1"}, "start": "2026-10-12", "price": 0.95}])
    ws = Workspace(synth.workspace(tmp_path, df, dims=["category", "region"]))
    cfg = {"metric": "aov", "current": ["2026-10-19", "2026-10-25"], "base": "yoy", "mode": "fixed", "dimensions": ["category"]}
    raw = run(ws, {**cfg, "shrink": False}, write=False)["cuts"][0]["result"]
    shrunk = run(ws, cfg, write=False)["cuts"][0]["result"]
    assert raw["top1_key"] == "tiny"
    assert shrunk["top1_key"] == "big1"
    tiny = next(x for x in shrunk["segments"] if x["key"] == "tiny")
    assert tiny["den_cur"] < 10
    assert abs(tiny["total_shrunk"]) < abs(tiny["total"])
