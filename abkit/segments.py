"""Segment-cut guards — pure constants + classifiers shared by the backend
(request enforcement, chart_data) and mirrored in the frontend TS
(frontend/src/pages/experiment/segmentGuard.ts) for the live selection-time
guard. Kept dependency-free so both the analyze request path and the
cardinality endpoint can import it without pulling in pandas/statistics.

Segment combinations (country × platform × ...) explode combinatorially — with
5-6 stratum columns the full space is huge — so ABSet never precomputes
everything: the analyst declares the cuts, and a cell-count guard keeps a
declared cut from turning into noise.
"""

from __future__ import annotations

from typing import Literal

# Cell-count (= product of the cut columns' distinct values) thresholds for a
# single segment cut. Above WARN we nudge; above MAX we refuse to add it
# ("this many segments is noise, not analysis").
SEGMENT_WARN_CELLS = 30
SEGMENT_MAX_CELLS = 200

# A rendered segment CELL with fewer than this many users PER GROUP is
# underpowered — shown greyed with an "underpowered" badge instead of a lift,
# rather than inviting a decision off a handful of users.
UNDERPOWERED_MIN_N_PER_GROUP = 100

SegmentCardinalityStatus = Literal["ok", "warn", "refuse"]


def segment_cardinality_status(n_cells: int) -> SegmentCardinalityStatus:
    """Classify a cut by its cell count: ok (<=30), warn (31..200), refuse
    (>200). Boundaries: 30->ok, 31->warn, 200->warn, 201->refuse."""
    if n_cells > SEGMENT_MAX_CELLS:
        return "refuse"
    if n_cells > SEGMENT_WARN_CELLS:
        return "warn"
    return "ok"
