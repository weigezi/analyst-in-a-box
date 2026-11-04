"""The counting rule of a table of visits, at the level of the draft: a role "records", and an identifier that is counted
and never summed."""

from aib import draft


def test_records_is_a_role_next_to_visits():
    assert {"visits", "records"} <= set(draft.ROLES)
    assert "count the rows" in draft.ROLES["records"]["en"] and draft.ROLES["records"]["zh"]


def test_build_metrics_counts_instead_of_summing_an_identifier():
    specs = [{"column": "sid", "role": "visits", "source": "s", "date": "d", "dimensions": [], "count": {"column": "sid"}},
             {"column": "amt", "role": "amount", "source": "o", "date": "d", "dimensions": []}]
    idsp = {"column": "oid", "source": "o", "date": "d", "dimensions": []}
    measures, metrics, identities, by_role = draft.build_metrics(specs, idsp, "orders", {"kind": "user"})
    assert measures["m_sid"]["agg"] == "count_distinct" and measures["m_sid"]["column"] == "sid"
    assert metrics["conversion"]["denominator"] == "sid" and by_role["visits"] == "sid"
    specs[0].update(role="records", count={"column": None})
    measures, metrics, _, by_role = draft.build_metrics(specs, idsp, "orders", {"kind": "user"})
    assert measures["m_sid"]["agg"] == "count" and "column" not in measures["m_sid"]
    assert metrics["conversion"]["denominator"] == "sid"


def test_count_basis():
    assert draft.count_basis("amount", "x", True, None) is None
    assert draft.count_basis("visits", "n", False, None) is None            # a column of visit counts per day: added up
    assert draft.count_basis("visits", "sid", True, None) == {"column": "sid"}
    assert draft.count_basis("records", "sid", True, "k") == {"column": "sid"}
    assert draft.count_basis("records", "n", False, "k") == {"column": "k"}
    assert draft.count_basis("records", "n", False, None) == {"column": None}
