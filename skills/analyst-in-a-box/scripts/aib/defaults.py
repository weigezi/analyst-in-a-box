"""The starting rules every new workspace gets: named params with their source, and the decision tables that read them.

Values marked "example default" are not business knowledge; they are a reasonable place to start and the user
is expected to confirm or change them (`correct` with `set_param`). Values with a document source come from
the literature named in the source.
"""

from __future__ import annotations

import copy

IH = "B. Iglewicz & D. Hoaglin (1993), How to Detect and Handle Outliers, ASQC"
EXAMPLE = "example default, waiting for the user to confirm"


def _p(value, ref=None, note=None):
    src = {"kind": "document", "ref": ref} if ref else {"kind": "demo_setting", "note": note or EXAMPLE}
    return {"value": value, "source": src, "status": "confirmed" if ref else "proposed"}


def _maint(value, note):
    """A default the project maintainer decided (docs/decisions, 2026-10-31). Still a default: a user may change it."""
    return {"value": value, "source": {"kind": "user", "date": "2026-10-31", "note": "project maintainer decided: " + note},
            "status": "confirmed"}


PARAMS = {
    "unusual_z": _p(3.5, IH + ": modified z-scores beyond 3.5 are labelled potential outliers"),
    "unusual_z_low": _p(-3.5, IH + ", applied to the low side"),
    "single_point_min_share": _p(0.5, note="Kept from 0.1 for reading old runs; the cut table now uses single_point_min_excess. " + EXAMPLE),
    "single_point_min_excess": _p(0.25, note="The top group must carry at least 25% more of the movement than an even split "
                                             "(0 = even, 1 = all of it). " + EXAMPLE),
    "single_point_min_excess_no_history": _p(0.6, note="Without a history to judge noise, demand a much clearer single point. " + EXAMPLE),
    "segment_z_min": _p(3.0, note="A group's own change must be this far from its own history (robust z, "
                                  "same method as unusual_z, one notch lower because it is a second test). " + EXAMPLE),
    "segment_z_min_when_unusual": _p(2.0, note="When the whole number is already unusual (or we are inside a group already "
                                               "drilled into), the question is where it came from; a group's own z only has "
                                               "to rule out ordinary noise. " + EXAMPLE),
    "segment_min_n": _p(30, note="Groups with fewer rows than this are not named as a single point. " + EXAMPLE),
    "drill_when_usual": _p(False, note="When the whole number is within its usual range, report and do not drill, unless one "
                                       "group stands out (drill_quiet_total_when_group_stands_out). True drills always. " + EXAMPLE),
    "search_max_depth": _p(3, note="At most three cuts deep. " + EXAMPLE),
    "search_top_k": _p(3, note="Candidates shown per layer. " + EXAMPLE),
    "same_cause_min_share": _p(0.6, note="Two slots are one cause when their shared cell carries at least 60% of each. " + EXAMPLE),
    "shrink_ratio_segments": _p(True, note="Rank ratio groups by empirically-Bayes-shrunk rates (James & Stein 1961; "
                                           "Efron & Morris 1975). " + EXAMPLE),
    "own_share_min": _p(0.5, note="If at least half of the change is our own, break it down internally. " + EXAMPLE),
    "external_slice_min_share": _p(0.5, note="An outside event must touch the slice that carries at least half of the change. " + EXAMPLE),
    "external_size_min_share": _p(0.6, note="At least 60% of that slice's change must fall on the event's days. " + EXAMPLE),
    "quality_missing_days_max": _p(0, note="Any expected day with no rows makes the data suspect. " + EXAMPLE),
    "quality_duplicate_key_max_share": _p(0.0, note="A declared key is unique by definition."),
    "quality_jump_high": _p(1.8, note="A day with 1.8x the rows of the same weekday's recent median looks loaded twice. " + EXAMPLE),
    "quality_jump_low": _p(0.25, note="A day with a quarter of the usual rows looks partly loaded. " + EXAMPLE),
    "quality_value_jump": _p(5.0, note="A day whose total is 5x (or 1/5) the usual looks like a unit or definition change. " + EXAMPLE),
    "quality_jump_lookback_weeks": _p(8, note="Weeks of the same weekday used as the reference. " + EXAMPLE),
    "quality_row_ratio_max": _p(3.0, note="Rows in one period more than 3x the other is worth a warning. " + EXAMPLE),
    "quality_single_row_max_share": _p(0.2, note="One row carrying 20% of the change is named. " + EXAMPLE),
    "quality_single_row_fail_share": _p(0.5, note="One row carrying half of the change makes the data suspect. " + EXAMPLE),
    "quality_top_rows": _p(5, note="How many extreme rows to list. " + EXAMPLE),
    "quality_extreme_row_times": _p(20, note="A row is extreme when its effect is at least 20x the median row's; "
                                             "ordinary rows never count, however small the change. " + EXAMPLE),
    "quality_check_levels": _maint(
        {"key_unique": "block", "calendar_complete": "block", "row_ratio": "block", "daily_value_steady": "block",
         "daily_volume_steady": "warn", "dimension_values_stable": "warn", "no_single_row_dominates": "warn"},
        "Checks that would make the numbers wrong stop the report (repeated order ids, whole days missing outside closing "
        "days, a period with no rows to compare); the others are named at the top of the report and the conclusions are "
        "given. daily_value_steady (a day's total several times the usual, as after a unit change) is placed with "
        "'block' by the skill, not by the maintainer's list: it changes every amount after it."),
    "group_stands_out_z": _maint(3.5, "When the whole number is within its usual range, drill only into a group whose own "
                                      "change is at least this far from its own history (robust z; same cut-off as unusual_z)."),
    "drill_quiet_total_when_group_stands_out": _maint(True, "Whole number within its usual range but one group stands far "
                                                            "out from its own past swings: drill into it."),
    "onset_lookback_weeks": _p(8, note="Weeks of daily data searched for the day the main group's gap shifted. " + EXAMPLE),
    "onset_min_shift_sd": _p(2.0, note="A start date is named only when the shift is at least 2 residual sd. " + EXAMPLE),
    "history_skip_misaligned_holidays": _p(True, note="A past period whose two windows hold different holidays is left out "
                                                      "of the history the z-score is judged against, and named. " + EXAMPLE),
    "quality_row_ratio_block": _p(20.0, note="One period with 20x the rows of the other (or none) cannot be compared. " + EXAMPLE),
    "quality_new_value_min_share": _p(0.1, note="A value that appears from nothing while another of similar size disappears, "
                                                "each at least 10% of the total, looks like a rename. " + EXAMPLE),
    # intake: how sure the reader must be before it even asks, and what counts as a quote
    "intake_link_ask_min": _p(0.5, note="Two columns are offered as a link only when at least half the rows of one find a "
                                        "match in the other; below that it is a coincidence of codes, not a link. " + EXAMPLE),
    "intake_link_suggest_min": _p(0.95, note="At or above this share of matching rows the suggested answer is 'yes'; below "
                                             "it 'no'. Only the suggestion: the user answers every link. " + EXAMPLE),
    "intake_id_distinct_share": _p(0.3, note="A whole-number column whose distinct values are at least 30% of the rows reads as an "
                                             "identifier (an order, a session, a user), not as an amount: a measure repeats "
                                             "its values far more than that. A heuristic that only decides which tables may be "
                                             "offered as the main one; the user still answers every column. " + EXAMPLE),
    "intake_measure_min_distinct": _p(3, note="A numeric column with fewer than 3 distinct values is a flag or a code (0/1), not an "
                                              "amount to add up. Same limit: it only steers the offered main table. " + EXAMPLE),
    "intake_event_table_max_rows": _p(200, note="Two dates in order on every row make a start and an end (a campaign, a holiday) "
                                                "only when the table is small or has no amounts; a large table with amounts is a "
                                                "fact table that carries two dates (ordered, shipped). " + EXAMPLE),
    "intake_quote_min_chars": _p(8, note="A quote shorter than this (spaces aside) proves nothing about where a claim came "
                                         "from, so a proposal citing it is refused. " + EXAMPLE),
}

TABLES = [
    {"id": "qualify.unusual", "question": {"en": "Is this period unusual against its own history?", "zh": "这一期和自己的历史比，算不算异常？"},
     "inputs": {"robust_z": "qualify.robust_z"}, "hit_policy": "FIRST", "rows": [
         {"when": {"robust_z": {"gte": "param:unusual_z"}}, "then": {"verdict": "unusual_high"}},
         {"when": {"robust_z": {"lte": "param:unusual_z_low"}}, "then": {"verdict": "unusual_low"}},
         {"when": {}, "then": {"verdict": "within_usual_range"}}]},
    {"id": "qualify.market", "question": {"en": "Did the market move us, or did we move ourselves?", "zh": "是大盘带着走，还是自己的问题？"},
     "inputs": {"own_share": "qualify.own_share"}, "hit_policy": "FIRST", "rows": [
         {"when": {"own_share": {"gte": "param:own_share_min"}}, "then": {"verdict": "own", "next": "break_down_internally"}},
         {"when": {"own_share": {"not_null": True}}, "then": {"verdict": "market", "next": "report_market_first"}},
         {"when": {}, "then": {"verdict": "no_market_data"}}]},
    {"id": "stop.cut", "question": {"en": "After a cut, drill into the top segment or stop here?", "zh": "切完这一刀，往第一名下钻，还是停在这一层？"},
     "inputs": {"overall_quiet": "cut.overall_quiet", "top1_beats_quiet": "cut.top1_beats_quiet",
                "context_unusual": "cut.context_unusual", "top1_abs_share": "cut.top1_abs_share",
                "top1_excess": "cut.top1_excess", "top1_abs_z": "cut.top1_abs_z",
                "top1_n": "cut.top1_n", "has_history": "cut.has_history", "order": "cut.order"},
     "hit_policy": "FIRST", "rows": [
         {"when": {"all": [{"overall_quiet": {"eq": True}}, {"top1_beats_quiet": {"eq": False}}]},
          "then": {"action": "stop", "reason": "whole_number_within_usual_range"}},
         {"when": {"top1_n": {"lt": "param:segment_min_n"}}, "then": {"action": "stop", "reason": "top_group_too_small"}},
         {"when": {"all": [{"order": {"eq": "second"}}, {"top1_abs_share": {"gte": "param:single_point_min_share"}},
                           {"top1_excess": {"gte": "param:single_point_min_excess"}}]},
          "then": {"action": "drill", "reason": "single_point"}},
         {"when": {"all": [{"overall_quiet": {"eq": True}}, {"top1_beats_quiet": {"eq": True}},
                           {"top1_excess": {"gte": "param:single_point_min_excess"}},
                           {"top1_abs_share": {"gte": "param:single_point_min_share"}}]},
          "then": {"action": "drill", "reason": "single_point_inside_a_quiet_total"}},
         {"when": {"all": [{"context_unusual": {"eq": True}}, {"top1_abs_share": {"gte": "param:single_point_min_share"}},
                           {"top1_excess": {"gte": "param:single_point_min_excess"}},
                           {"top1_abs_z": {"gte": "param:segment_z_min_when_unusual"}}]},
          "then": {"action": "drill", "reason": "single_point"}},
         {"when": {"all": [{"top1_abs_share": {"gte": "param:single_point_min_share"}},
                           {"top1_excess": {"gte": "param:single_point_min_excess"}},
                           {"top1_abs_z": {"gte": "param:segment_z_min"}}]},
          "then": {"action": "drill", "reason": "single_point"}},
         {"when": {"all": [{"has_history": {"eq": False}}, {"order": {"eq": "first"}},
                           {"top1_excess": {"gte": "param:single_point_min_excess_no_history"}}]},
          "then": {"action": "drill", "reason": "single_point_without_history"}},
         {"when": {}, "then": {"action": "stop", "reason": "spread_or_noise"}}]},
]


def rules() -> dict:
    return {"params": copy.deepcopy(PARAMS), "tables": copy.deepcopy(TABLES)}


def param(ws, name):
    """A param from the workspace, else the default. Missing ones are reported by run as 'defaults used'."""
    p = ws.params.get(name)
    return p["value"] if p is not None else PARAMS[name]["value"]
