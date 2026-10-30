import math

from aib import judge, qualify


def approx(x, y):
    return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)


def test_unusualness_reports_numbers_not_verdicts():
    r = qualify.unusualness([0.01, 0.02, -0.01, 0.00, 0.03, 0.01], -0.12)
    assert r["history_n"] == 6
    assert r["robust_z"] < 0
    assert r["percentile"] == 0.0
    assert "verdict" not in r


def test_unusualness_short_history():
    assert qualify.unusualness([0.1], 0.2)["robust_z"] is None


def test_versus_market_is_exact():
    r = qualify.versus_market(own_base=100, own_cur=88, market_base=1000, market_cur=900)
    assert approx(r["market_part"], -10) and approx(r["own_part"], -2)
    assert approx(r["market_part"] + r["own_part"], -12)
    assert approx(r["market_share"], 10 / 12)


def test_calendar_alignment_detects_shifted_holiday():
    hol = [{"name": "autumn_break", "start": "2025-10-01", "end": "2025-10-07"},
           {"name": "autumn_break", "start": "2026-10-08", "end": "2026-10-14"}]
    r = qualify.calendar_alignment(hol, base=("2025-10-01", "2025-10-07"), current=("2026-10-01", "2026-10-07"))
    assert r["holiday_misaligned"] is True
    assert r["holidays"][0]["difference"] == -7


PARAMS = {"single_point_min_share": {"value": 0.5, "source": "test fixture"}}
TABLE = {
    "id": "stop.after_cut",
    "question": "drill or stop",
    "inputs": {"top1_abs_share": "additive.top1_abs_share"},
    "hit_policy": "FIRST",
    "rows": [
        {"when": {"top1_abs_share": {"gte": "param:single_point_min_share"}}, "then": {"action": "drill"}},
        {"when": {}, "then": {"action": "stop", "reason": "no_single_point"}},
    ],
}


def test_judge_valid_table_and_both_rows():
    assert judge.validate(TABLE, PARAMS) == []
    hit = judge.evaluate(TABLE, {"additive": {"top1_abs_share": 0.7}}, PARAMS)
    assert hit["then"]["action"] == "drill" and hit["row"] == 0
    miss = judge.evaluate(TABLE, {"additive": {"top1_abs_share": 0.3}}, PARAMS)
    assert miss["fallback"] and miss["then"]["action"] == "stop"


def test_judge_missing_input_falls_to_fallback():
    hit = judge.evaluate(TABLE, {"additive": {}}, PARAMS)
    assert hit["fallback"]


def test_judge_validate_catches_problems():
    bad = {
        "id": "bad",
        "inputs": {"x": "additive.no_such_field"},
        "rows": [
            {"when": {}, "then": {"action": "stop"}},
            {"when": {"y": {"gte": "param:missing"}}, "then": {"action": "drill"}},
            {"when": {"x": {"between": 1}}},
        ],
    }
    problems = " | ".join(judge.validate(bad, {}))
    for expected in ("last row must be the fallback", "can never fire", "not declared",
                     "param 'missing' is not defined", "unknown field", "unknown operator", "no 'then'"):
        assert expected in problems, expected


def test_judge_param_without_source_is_rejected():
    problems = judge.validate(TABLE, {"single_point_min_share": {"value": 0.5}})
    assert any("has no source" in p for p in problems)
