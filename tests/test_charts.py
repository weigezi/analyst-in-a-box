"""Charts must not mislead: honest bar heights, readable labels, signs that agree with the bars.
And the 'who should act' section must say something true when no owner is recorded."""

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from aib.report import DOWN, NEUTRAL, UP, bar_svg, daily_svg, waterfall_svg
from aib.run import run

ROOT = Path(__file__).absolute().parent.parent
DEMO = ROOT / "demo" / "store"
sys.path.insert(0, str(DEMO))
import answer_key  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"
WORLD = SimpleNamespace(entity_for=lambda dim, key: None)


def parse(svg):
    root = ET.fromstring(svg)
    rects = [(float(r.get("x")), float(r.get("y")), float(r.get("width")), float(r.get("height")), r.get("fill"))
             for r in root.iter(NS + "rect")]
    texts = [(float(t.get("x")), float(t.get("y")), t.get("text-anchor") or "start", t.text or "") for t in root.iter(NS + "text")]
    return rects, texts


# ---- waterfall: bar heights are in proportion to the real values -------------------------------------

def wf(base, steps, unit="currency"):
    cur = base + sum(v for _, v in steps)
    return {"base": base, "current": cur, "unit": unit,
            "steps": [{"dimension": "d", "label_key": k, "value": v} for k, v in steps]}


def test_waterfall_total_bars_keep_the_real_ratio():
    """Base 1,137,653 against current 1,809,325 is 1.59x. Before the fix the axis started near 1,023,887 and the
    base bar was drawn 6.9x shorter than the current one."""
    data = wf(1_137_653, [("a", 607_748), ("b", 62_725), ("c", 50_394), ("d", -50_223), ("e", 1_028)])
    rects, _ = parse(waterfall_svg(None, WORLD, data, "en"))
    totals = [r for r in rects if r[4] == NEUTRAL]
    assert len(totals) == 2
    base_h, cur_h = totals[0][3], totals[1][3]
    assert cur_h / base_h == pytest.approx(data["current"] / data["base"], rel=0.01)


def test_waterfall_axis_starts_at_zero_and_has_no_stray_axis_number():
    data = wf(1_137_653, [("a", 607_748), ("d", -50_223)])
    rects, texts = parse(waterfall_svg(None, WORLD, data, "en"))
    totals = [r for r in rects if r[4] == NEUTRAL]
    assert totals[0][1] + totals[0][3] == pytest.approx(totals[1][1] + totals[1][3])   # both stand on one baseline
    shown = [t[3] for t in texts]
    assert not any(re.fullmatch(r"1,023,887|1,137,65[0-9]", s) and t[1] > 280 for t, s in zip(texts, shown))
    assert "0" in shown


def test_waterfall_step_bars_share_the_scale_of_the_total_bars():
    data = wf(1000.0, [("a", 500.0), ("b", -250.0)])
    rects, _ = parse(waterfall_svg(None, WORLD, data, "en"))
    unit_px = [r for r in rects if r[4] == NEUTRAL][0][3] / 1000.0
    up = [r for r in rects if r[4] == UP][0]
    down = [r for r in rects if r[4] == DOWN][0]
    assert up[3] == pytest.approx(500 * unit_px, rel=0.01)
    assert down[3] == pytest.approx(250 * unit_px, rel=0.01)


def test_waterfall_ratio_with_a_negative_total_still_draws_from_zero():
    data = wf(-0.02, [("a", 0.05), ("b", -0.01)], unit="ratio")
    rects, _ = parse(waterfall_svg(None, WORLD, data, "en"))
    totals = [r for r in rects if r[4] == NEUTRAL]
    assert len(totals) == 2
    assert totals[0][3] > 0 and totals[1][3] > 0
    zero_line = totals[1][1] + totals[1][3]               # the positive current bar stands on the zero line
    assert totals[0][1] == pytest.approx(zero_line)       # the negative base hangs from it
    assert totals[0][1] + totals[0][3] > zero_line
    assert totals[0][3] / totals[1][3] == pytest.approx(abs(data["base"]) / abs(data["current"]), rel=0.01)


# ---- daily: labels do not sit on top of each other --------------------------------------------------

def daily(n, base=100.0, cur=130.0):
    days = [f"2016-08-{i + 1:02d}" for i in range(n)]
    return {"current": [{"day": d, "value": cur + (i % 5) * 7 - (20 if i == 9 else 0)} for i, d in enumerate(days)],
            "base": [{"day": d, "value": base + (i % 3) * 5} for i, d in enumerate(days)], "excluded_days": []}


def overlaps(texts, y_min=0):
    """Pairs of labels on one row whose estimated widths (7 px a character) overlap."""
    rows = {}
    for x, y, anchor, s in texts:
        w = 7 * len(s)
        a = x - w / 2 if anchor == "middle" else x - w if anchor == "end" else x
        rows.setdefault(round(y), []).append((a, a + w, s))
    bad = 0
    for items in rows.values():
        items.sort()
        bad += sum(1 for p, q in zip(items, items[1:]) if q[0] < p[1])
    return bad


def test_daily_thirty_one_days_do_not_overlap():
    _, texts = parse(daily_svg(daily(31), "en", "currency"))
    assert overlaps(texts) == 0
    dates = [s for *_, s in texts if re.fullmatch(r"\d\d-\d\d", s)]
    assert 4 <= len(dates) <= 12
    assert dates[0] == "08-01"
    assert "Current" in "".join(s for *_, s in texts) and "Base" in "".join(s for *_, s in texts)


def test_daily_value_labels_are_only_the_extremes_when_there_are_many_days():
    d = daily(31)
    _, texts = parse(daily_svg(d, "en", "currency"))
    signed = [s for *_, s in texts if re.match(r"[+\u2212]\d", s)]
    assert 1 <= len(signed) <= 4
    gaps = [c["value"] - b["value"] for c, b in zip(d["current"], d["base"])]
    biggest = max(gaps, key=abs)
    assert any(abs(float(s.replace(",", "").replace("\u2212", "-"))) == pytest.approx(abs(biggest), abs=1) for s in signed)


def test_daily_a_week_still_labels_every_day():
    _, texts = parse(daily_svg(daily(7), "en", "currency"))
    assert len([s for *_, s in texts if re.fullmatch(r"\d\d-\d\d", s)]) == 7
    assert len([s for *_, s in texts if re.match(r"[+\u2212]\d", s)]) == 7
    assert overlaps(texts) == 0


# ---- cut chart: a label never contradicts the bar ---------------------------------------------------

def label_of_bar(svg):
    rects, texts = parse(svg)
    out = []
    for x, y, w, h, fill in rects:
        row = [t for t in texts if abs(t[1] - (y - 5 + 17)) < 1 and t[2] in ("start", "end") and not t[3].isalpha()
               and re.search(r"\d", t[3])]
        out.append((fill, row[0][3] if row else ""))
    return out


def test_a_falling_bar_never_carries_a_plus_sign():
    """Groups fell by 52,078 and was labelled +14.0%, its share of all movement, next to a downward bar."""
    rows = [("Online TA", 275_300.0, 0.738), ("Groups", -52_078.0, 0.140), ("Direct", 35_770.0, 0.096)]
    svg = bar_svg(rows, "Market Segment", lambda v: ("+" if v >= 0 else "\u2212") + f"{abs(v):,.0f}")
    for fill, text in label_of_bar(svg):
        assert text, "every bar has a label"
        if fill == DOWN:
            assert text.startswith("\u2212") and "+" not in text
        else:
            assert text.startswith("+") and "\u2212" not in text
    assert any("52,078" in t for _, t in label_of_bar(svg))
    assert any("14.0%" in t and not t.startswith("+14") for _, t in label_of_bar(svg))


def test_cut_labels_in_a_real_report_agree_with_the_bars(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO / "workspace", ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    c = answer_key.CASES["revenue_last_week"]
    run(ws, {**c["run"], "id": "rev", "question": c["question"]}, out_dir=tmp_path / "out")
    for lang in ("zh", "en"):
        for f in sorted((tmp_path / "out" / "charts").glob(f"cut*.{lang}.svg")):
            for fill, text in label_of_bar(f.read_text(encoding="utf-8")):
                assert text
                assert (fill == DOWN) == text.startswith("\u2212"), (f.name, fill, text)


# ---- who should act: the first-run fallback -------------------------------------------------------

@pytest.fixture(scope="module")
def no_actions(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("noact")
    ws = tmp / "ws"
    shutil.copytree(DEMO / "workspace", ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    w = yaml.safe_load((ws / "world.yaml").read_text(encoding="utf-8"))
    w["actions"] = []
    (ws / "world.yaml").write_text(yaml.safe_dump(w, allow_unicode=True, sort_keys=False), encoding="utf-8")
    c = answer_key.CASES["revenue_last_week"]
    s = run(ws, {**c["run"], "id": "rev", "question": c["question"]}, out_dir=tmp / "out")
    return s, tmp / "out"


def who(md):
    return md.split("\n## ")[[h.split("\n")[0] for h in md.split("\n## ")].index(next(
        h.split("\n")[0] for h in md.split("\n## ") if h.startswith(("Who should act", "谁该做什么"))))]


def test_no_actions_names_the_slice_and_invites_an_owner(no_actions):
    s, out = no_actions
    assert s["actions"] == []
    en = who((out / "report.en.md").read_text(encoding="utf-8"))
    zh = who((out / "report.zh.md").read_text(encoding="utf-8"))
    assert "No actions recorded yet." not in en
    assert "Marketplace" in en and "no owner" in en.lower() and "tell me who" in en.lower()
    assert "没有登记" in zh and "负责人" in zh and "告诉我" in zh
    assert re.search(r"[+\u2212]\d", en) and re.search(r"[+\u2212]\d", zh)


def test_with_actions_the_section_is_unchanged(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO / "workspace", ws, ignore=shutil.ignore_patterns("runs", "regressions", "corrections.jsonl", "docs"))
    c = answer_key.CASES["revenue_last_week"]
    s = run(ws, {**c["run"], "id": "rev", "question": c["question"]}, out_dir=tmp_path / "out")
    assert s["actions"]
    en = who((tmp_path / "out" / "report.en.md").read_text(encoding="utf-8"))
    assert "Channel manager" in en and "no owner" not in en.lower()
