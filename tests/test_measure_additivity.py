"""Measure additivity: columns get `additivity` ("additive", "distinct_count", "non_additive") based on table grain.

A per_date table (one row per date × groups) has daily totals: sum them, never count distinct.
A per_event table (one row per session, order, etc.) may have identifiers: count distinct, never sum.
Validation checks that agg and additivity agree.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from aib import draft, intake
from aib.validate import all_problems, model_problems
from aib.workspace import Workspace


def build_per_date_table(folder: Path) -> pd.DataFrame:
    """A traffic table: one row per date × channel, with daily visit counts."""
    rows = []
    for day in pd.date_range("2025-01-01", "2025-02-28"):
        for ch in ("app", "web", "marketplace"):
            visits = int(np.random.default_rng(hash((str(day), ch)) % 2**32).integers(1000, 5000))
            rows.append({"date": day.date(), "channel": ch, "visits": visits})
    df = pd.DataFrame(rows)
    df.to_csv(folder / "traffic.csv", index=False)
    return df


def build_per_event_table(folder: Path) -> pd.DataFrame:
    """A sessions table: one row per session, with timestamps."""
    rows = []
    sid = 0
    for day in pd.date_range("2025-01-01", "2025-01-31"):
        for k in range(50):
            sid += 1
            t = day + pd.Timedelta(hours=8, minutes=k)
            rows.append({"session_id": sid, "created_at": t, "channel": "app" if k % 2 else "web"})
    df = pd.DataFrame(rows)
    df.to_csv(folder / "sessions.csv", index=False)
    return df


class TestGrainDetection:
    """Grain is detected from table shape: per_date tables have dates without time, per_event have timestamps."""
    
    def test_per_date_table_has_grain_per_date(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_date_table(folder)
        facts = intake._table_facts("traffic", folder / "traffic.csv", pd.read_csv(folder / "traffic.csv"))
        assert facts["grain"] == "per_date"
    
    def test_per_event_table_has_grain_per_event(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_event_table(folder)
        facts = intake._table_facts("sessions", folder / "sessions.csv", pd.read_csv(folder / "sessions.csv"))
        assert facts["grain"] == "per_event"
    
    def test_datetime_with_time_forces_per_event(self, tmp_path):
        """Even if no duplicates on date+groups, timestamps mean per_event grain."""
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_event_table(folder)
        df_read = pd.read_csv(folder / "sessions.csv")
        facts = intake._table_facts("sessions", folder / "sessions.csv", df_read)
        assert facts["grain"] == "per_event"


class TestClassifyMeasure:
    """classify_measure returns additivity based on grain and column characteristics."""
    
    def test_per_date_integer_is_additive(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_date_table(folder)
        cls = draft.classify_measure(df, "visits", "per_date", [])
        assert cls["additivity"] == "additive"
        assert cls["confidence"] == "sure"
    
    def test_per_date_decimal_is_additive(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_date_table(folder)
        df["revenue"] = df["visits"] * 1.5
        cls = draft.classify_measure(df, "revenue", "per_date", [])
        assert cls["additivity"] == "additive"
    
    def test_per_event_identifier_returns_none_additivity(self, tmp_path):
        """Identifiers in per_event tables get additivity=None so the user can choose the role."""
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_event_table(folder)
        cls = draft.classify_measure(df, "session_id", "per_event", [])
        assert cls["additivity"] is None
        assert "identifier" in cls["why"].lower() or "sequence" in cls["why"].lower()
    
    def test_per_event_low_uniqueness_is_additive(self, tmp_path):
        """Integer columns with many repeats in per_event tables are typical measures, thus additive."""
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_event_table(folder)
        df["item_count"] = [i % 5 + 1 for i in range(len(df))]
        cls = draft.classify_measure(df, "item_count", "per_event", [])
        assert cls["additivity"] == "additive"


class TestIsIdentifier:
    """is_identifier respects grain: per_date tables have no identifiers by definition."""
    
    def test_identifier_in_per_event(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_event_table(folder)
        assert draft.is_identifier(df["session_id"], grain="per_event")
    
    def test_no_identifier_in_per_date(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        df = build_per_date_table(folder)
        assert not draft.is_identifier(df["visits"], grain="per_date")
    
    def test_per_date_skips_identifier_check(self):
        """Even a highly unique integer column is not an identifier in a per_date table."""
        s = pd.Series(range(1, 101))
        assert draft.is_identifier(s, grain=None)
        assert draft.is_identifier(s, grain="per_event")
        assert not draft.is_identifier(s, grain="per_date")


def _make_ws(tmp_path, measures: dict):
    """Create a minimal workspace with the given measures."""
    ws_path = tmp_path / "ws"
    ws_path.mkdir()
    (ws_path / "project.yaml").write_text("language: en")
    (ws_path / "model.yaml").write_text(yaml.dump({
        "measures": {name: {"source": "main", "date": "date", "dimensions": [], **spec} for name, spec in measures.items()},
        "metrics": {},
        "dimensions": {}
    }))
    (ws_path / "rules.yaml").write_text(yaml.dump({"tables": [{"id": "main", "path": "data.csv", "type": "file"}]}))
    (ws_path / "world.yaml").write_text("{}")
    return Workspace(ws_path)


class TestAdditivityValidation:
    """Validation catches mismatches between additivity and agg."""
    
    def test_valid_additive_sum(self, tmp_path):
        ws = _make_ws(tmp_path, {"m_revenue": {"column": "revenue", "agg": "sum", "additivity": "additive"}})
        problems = model_problems(ws)
        assert all("additivity" not in p for p in problems)
    
    def test_invalid_additive_count_distinct(self, tmp_path):
        ws = _make_ws(tmp_path, {"m_visits": {"column": "visits", "agg": "count_distinct", "additivity": "additive"}})
        problems = model_problems(ws)
        assert any("additivity 'additive' does not match agg 'count_distinct'" in p for p in problems)
    
    def test_valid_distinct_count_count_distinct(self, tmp_path):
        ws = _make_ws(tmp_path, {"m_sessions": {"column": "session_id", "agg": "count_distinct", "additivity": "distinct_count"}})
        problems = model_problems(ws)
        assert all("additivity" not in p for p in problems)
    
    def test_missing_additivity_is_ok(self, tmp_path):
        """Backward compatibility: missing additivity field should not cause validation errors."""
        ws = _make_ws(tmp_path, {"m_revenue": {"column": "revenue", "agg": "sum"}})
        problems = model_problems(ws)
        assert all("additivity" not in p for p in problems)


class TestWorkspaceAdditivity:
    """Workspace.measure_additivity infers additivity from agg when not explicit."""
    
    def test_explicit_additivity(self, tmp_path):
        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "project.yaml").write_text("language: en")
        (ws_path / "model.yaml").write_text(yaml.dump({
            "measures": {"m_revenue": {"column": "revenue", "agg": "sum", "additivity": "additive"}},
            "metrics": {}, "dimensions": {}
        }))
        (ws_path / "rules.yaml").write_text("{}")
        (ws_path / "world.yaml").write_text("{}")
        ws = Workspace(ws_path)
        assert ws.measure_additivity("m_revenue") == "additive"
    
    def test_inferred_from_sum(self, tmp_path):
        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "project.yaml").write_text("language: en")
        (ws_path / "model.yaml").write_text(yaml.dump({
            "measures": {"m_revenue": {"column": "revenue", "agg": "sum"}},
            "metrics": {}, "dimensions": {}
        }))
        (ws_path / "rules.yaml").write_text("{}")
        (ws_path / "world.yaml").write_text("{}")
        ws = Workspace(ws_path)
        assert ws.measure_additivity("m_revenue") == "additive"
    
    def test_inferred_from_count_distinct(self, tmp_path):
        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "project.yaml").write_text("language: en")
        (ws_path / "model.yaml").write_text(yaml.dump({
            "measures": {"m_sessions": {"column": "session_id", "agg": "count_distinct"}},
            "metrics": {}, "dimensions": {}
        }))
        (ws_path / "rules.yaml").write_text("{}")
        (ws_path / "world.yaml").write_text("{}")
        ws = Workspace(ws_path)
        assert ws.measure_additivity("m_sessions") == "distinct_count"
    
    def test_inferred_from_mean(self, tmp_path):
        ws_path = tmp_path / "ws"
        ws_path.mkdir()
        (ws_path / "project.yaml").write_text("language: en")
        (ws_path / "model.yaml").write_text(yaml.dump({
            "measures": {"m_avg_price": {"column": "price", "agg": "mean"}},
            "metrics": {}, "dimensions": {}
        }))
        (ws_path / "rules.yaml").write_text("{}")
        (ws_path / "world.yaml").write_text("{}")
        ws = Workspace(ws_path)
        assert ws.measure_additivity("m_avg_price") == "non_additive"
