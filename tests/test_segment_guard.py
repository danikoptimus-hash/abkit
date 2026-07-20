"""Segment cardinality guard classifier (abkit/segments.py) — the boundaries
the frontend live guard mirrors."""

from __future__ import annotations

from abkit.segments import (
    SEGMENT_MAX_CELLS,
    SEGMENT_WARN_CELLS,
    UNDERPOWERED_MIN_N_PER_GROUP,
    segment_cardinality_status,
)


def test_thresholds():
    assert SEGMENT_WARN_CELLS == 30
    assert SEGMENT_MAX_CELLS == 200
    assert UNDERPOWERED_MIN_N_PER_GROUP == 100


def test_ok_at_and_below_warn_boundary():
    assert segment_cardinality_status(29) == "ok"
    assert segment_cardinality_status(30) == "ok"


def test_warn_just_above_30_and_up_to_200():
    assert segment_cardinality_status(31) == "warn"
    assert segment_cardinality_status(199) == "warn"
    assert segment_cardinality_status(200) == "warn"


def test_refuse_above_200():
    assert segment_cardinality_status(201) == "refuse"
    assert segment_cardinality_status(5000) == "refuse"
