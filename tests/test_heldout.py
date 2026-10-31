"""The demo shop regenerated with seeds it was never tuned on: every planted cause must be found again,
or the run must show it was buried in noise, measured, and must then not name a different cause.

The gate's thresholds were set while looking at the shipped seed (planted.yaml). This file is the check that
they were not fitted to it. A miss is accepted only when the planted effect is smaller than
NOISE_SD robust standard deviations of that slice's own week-to-week swings (same history the gate uses).
"""

import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from aib import search
from aib.run import run
from aib.workspace import Workspace

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store"
sys.path.insert(0, str(DEMO))
import answer_key  # noqa: E402

SEEDS = (101, 102, 103, 104, 105, 106)
NOISE_SD = 2.0          # same as segment_z_min_when_unusual: below this the gate cannot tell a move from noise
RESULTS = []


@pytest.fixture(scope="module")
def shops(tmp_path_factory):
    out = {}
    for seed in SEEDS:
        d = tmp_path_factory.mktemp(f"seed{seed}") / "ws"
        shutil.copytree(DEMO / "workspace", d, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs", "data"))
        subprocess.run([sys.executable, str(DEMO / "generate.py"), "--seed", str(seed), "--out", str(d)], check=True, capture_output=True)
        out[seed] = Workspace(d)
    return out


def rain_effect_in_sd(ws, s):
    """Seed-specific size of the planted rain effect, in robust sd of the same-day slice's weekly residual."""
    f = s["filters"]
    h = search.segment_history(ws, "revenue", "delivery", f, s["history_pairs"]).get("same_day", [])
    med = statistics.median(h)
    sd = 1.4826 * statistics.median(abs(x - med) for x in h)
    o = ws.sources.frame("orders")
    sl = o[(o["region"] == "east") & (o["delivery"] == "same_day")]
    rain = sl[sl["order_date"].between("2026-10-21", "2026-10-23")]["revenue"].sum()
    before = sl[sl["order_date"].between("2026-10-14", "2026-10-16")]["revenue"].sum()
    return (rain - before) / sd, rain - before, sd


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("case", list(answer_key.CASES))
def test_planted_cause_found_on_unseen_seed(shops, seed, case):
    ws, c = shops[seed], answer_key.CASES[case]
    s = run(ws, {**c["run"], "id": case}, write=False)
    bad = [d for d, ok in answer_key.check(c, s) if not ok]
    row = {"seed": seed, "case": case, "found": not bad, "why": None}
    if bad and case == "east_last_week":
        k, effect, sd = rain_effect_in_sd(ws, s)
        row["why"] = f"rain effect {effect:+,.0f} = {k:+.2f} robust sd of the slice (sd {sd:,.0f})"
        assert abs(k) < NOISE_SD, (seed, row["why"], bad)
        # buried in noise: the run may say it cannot tell, but it must not name another cause as explained
        assert not any(x["status"] == "explained" for x in s["slots"]), [x["id"] for x in s["slots"]]
    else:
        assert not bad, (seed, case, bad)
    RESULTS.append(row)


def test_heldout_summary():
    if len(RESULTS) < len(SEEDS) * len(answer_key.CASES):
        pytest.skip("run the whole file to get the summary")
    found = sum(r["found"] for r in RESULTS)
    print(f"\nheld-out seeds: {found}/{len(RESULTS)} found; not found, with the measurement:")
    for r in RESULTS:
        if not r["found"]:
            print(f"  seed {r['seed']} {r['case']}: {r['why']}")
