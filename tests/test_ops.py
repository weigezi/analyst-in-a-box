"""Every operator must split its total exactly. Hand-checked cases plus random cases."""

import math
import random

import pytest

from aib.ops import additive, divisive, multiplicative, second_order


def approx(x, y):
    return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)


# ---------- additive ----------

def test_additive_hand_case():
    r = additive.decompose({"a": (100, 80), "b": (50, 55), "c": (10, 10)})
    assert approx(r["total_delta"], -15)
    assert r["top1_key"] == "a"
    assert approx(r["top1_share"], 20 / 15)  # a fell 20 while the total fell 15
    assert r["closed"]
    assert approx(sum(s["share"] for s in r["segments"]), 1.0)


def test_additive_zero_total_has_no_shares():
    r = additive.decompose({"a": (10, 12), "b": (10, 8)})
    assert r["total_delta"] == 0
    assert all(s["share"] is None for s in r["segments"])
    assert r["closed"]


# ---------- multiplicative ----------

def test_multiplicative_shapley_hand_case():
    r = multiplicative.decompose({"x": 10, "z": 2}, {"x": 12, "z": 3}, method="shapley")
    c = {f["factor"]: f["contribution"] for f in r["factors"]}
    assert approx(c["x"], 5.0) and approx(c["z"], 11.0)
    assert r["closed"]


def test_multiplicative_lmdi_exact_and_auto_fallback():
    r = multiplicative.decompose({"uv": 1000, "cr": 0.05, "aov": 80}, {"uv": 1200, "cr": 0.04, "aov": 85})
    assert r["method"] == "lmdi" and r["closed"]
    z = multiplicative.decompose({"x": 0, "z": 2}, {"x": 3, "z": 2})
    assert z["method"] == "shapley" and z["closed"]
    with pytest.raises(ValueError):
        multiplicative.decompose({"x": 0, "z": 2}, {"x": 3, "z": 2}, method="lmdi")


# ---------- divisive ----------

def test_divisive_kitagawa_hand_case():
    # weights 0.5/0.5 -> 0.3/0.7 ; rates A 0.10->0.12, B 0.20->0.20
    seg = {"A": (5, 50, 3.6, 30), "B": (10, 50, 14, 70)}
    r = divisive.decompose(seg, relative=False)
    assert approx(r["rate_base"], 0.15) and approx(r["rate_cur"], 0.176)
    assert approx(r["structure_total"], 0.02)
    assert approx(r["rate_total"], 0.01)
    assert approx(r["interaction_total"], -0.004)
    assert r["closed"] and r["larger_effect"] == "structure"
    rel = divisive.decompose(seg, relative=True)
    assert approx(rel["structure_total"], 0.02)  # relative form changes per-segment split, not the total


def test_divisive_segment_in_one_period_only():
    r = divisive.decompose({"old": (5, 50, 0, 0), "new": (0, 0, 9, 40), "keep": (10, 50, 12, 60)})
    assert r["closed"]


# ---------- second order ----------

def test_second_order_sides_hand_case():
    a = {"p": (60, 72), "q": (40, 43)}
    b = {"p": (30, 30), "q": (70, 70)}
    r = second_order.across_sides(a, b)
    # A: p +20% (w .6), q +7.5% (w .4) -> 15% ; B: flat -> 0%
    # mix = (.6-.3)*(.2+0)/2 + (.4-.7)*(.075+0)/2 = .03 - .01125
    # performance = (.2-0)*(.6+.3)/2 + (.075-0)*(.4+.7)/2 = .09 + .04125
    assert approx(r["gap"], 0.15)
    assert approx(r["mix_total"], 0.01875)
    assert approx(r["performance_total"], 0.13125)
    assert r["closed"] and r["larger_effect"] == "performance"


def test_second_order_time_hand_case():
    w1 = {"x": (100, 120), "y": (100, 100)}
    w2 = {"x": (100, 80), "y": (100, 110)}
    r = second_order.across_time(w1, w2)
    # window 1 growth = +20/200 = +10% ; window 2 = (-20 + 10)/200 = -5%
    assert approx(r["growth_change"], -0.15)
    assert r["top1_key"] == "x" and r["closed"]


# ---------- random: every operator closes ----------

@pytest.mark.parametrize("seed", range(25))
def test_random_closure(seed):
    rnd = random.Random(seed)
    segs = {f"s{i}": (rnd.uniform(0, 500), rnd.uniform(0, 500)) for i in range(rnd.randint(1, 12))}
    segs["anchor"] = (rnd.uniform(1, 500), rnd.uniform(1, 500))
    assert additive.decompose(segs)["closed"]

    base = {f"f{i}": rnd.uniform(0.01, 100) for i in range(rnd.randint(2, 4))}
    cur = {k: rnd.uniform(0.01, 100) for k in base}
    assert multiplicative.decompose(base, cur, method="lmdi")["closed"]
    assert multiplicative.decompose(base, cur, method="shapley")["closed"]

    rate_segs = {f"s{i}": (rnd.uniform(0, 50), rnd.uniform(1, 100), rnd.uniform(0, 50), rnd.uniform(1, 100))
                 for i in range(rnd.randint(1, 10))}
    for mode in ("three_term", "two_term"):
        for rel in (True, False):
            assert divisive.decompose(rate_segs, mode=mode, relative=rel)["closed"]

    other = {k: (rnd.uniform(1, 500), rnd.uniform(0, 500)) for k in segs}
    assert second_order.across_time(segs, other)["closed"]
    assert second_order.across_sides(segs, other)["closed"]

    rate_other = {k: (rnd.uniform(0, 50), rnd.uniform(1, 100), rnd.uniform(0, 50), rnd.uniform(1, 100)) for k in rate_segs}
    assert second_order.across_time_rate(rate_segs, rate_other)["closed"]
