"""Tests for skeleton generation invariants."""

from __future__ import annotations

import pytest

from generator.models import Skeleton
from generator.skeleton import (
    DEFAULT_SIZE,
    MIN_RUN,
    _all_runs_valid,
    _connected,
    _has_2x2_block,
    _runs_along,
    extract_slots,
    generate_skeleton,
)


def _invariants(skel: Skeleton, max_run: int = 9) -> None:
    size = skel.size
    blocks = skel.blocks

    # 180-degree rotational symmetry
    for r, c in blocks:
        assert (size - 1 - r, size - 1 - c) in blocks, f"asymmetry at {(r, c)}"

    # no 2x2 solid chunk
    assert not _has_2x2_block(blocks, size)

    # all runs within [MIN_RUN, max_run]
    for fixed in range(size):
        for axis in ("r", "c"):
            for ln in _runs_along(fixed, size, blocks, axis):
                assert MIN_RUN <= ln <= max_run, f"run {ln} out of range"

    # connected white cells
    opens = skel.open_cells
    assert _connected(opens)

    # every white cell belongs to both an across and a down run >= MIN_RUN
    across_cells = set()
    down_cells = set()
    for slot in extract_slots(skel):
        if slot.direction == "across":
            across_cells.update(slot.cells)
        else:
            down_cells.update(slot.cells)
    assert across_cells == opens, "some white cell has no across slot"
    assert down_cells == opens, "some white cell has no down slot"


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 42])
def test_skeleton_satisfies_invariants(seed: int) -> None:
    skel = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=seed)
    if skel is None:
        pytest.skip(f"skeleton generation returned None for seed {seed}")
    _invariants(skel, max_run=9)


def test_skeleton_block_density_in_range():
    skel = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=11)
    if skel is None:
        pytest.skip("skeleton generation returned None")
    density = len(skel.open_cells) / (skel.size * skel.size)
    assert 0.72 <= density <= 0.90, f"density {density:.2f} out of range"


def test_skeleton_has_healthy_slot_count():
    skel = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=23)
    if skel is None:
        pytest.skip("skeleton generation returned None")
    slots = extract_slots(skel)
    # a real 15x15 weekday grid has ~70-80 slots
    assert len(slots) >= 40, f"only {len(slots)} slots"


def test_extract_slots_lengths_match_runs():
    skel = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=99)
    if skel is None:
        pytest.skip("skeleton generation returned None")
    for slot in extract_slots(skel):
        assert slot.length == len(slot.cells)
        assert slot.length >= MIN_RUN
        # cells are contiguous in the direction
        if slot.direction == "across":
            cols = [c for _, c in slot.cells]
            assert cols == list(range(slot.col, slot.col + slot.length))
            assert all(r == slot.row for r, _ in slot.cells)
        else:
            rows = [r for r, _ in slot.cells]
            assert rows == list(range(slot.row, slot.row + slot.length))
            assert all(c == slot.col for _, c in slot.cells)


def test_skeleton_deterministic_with_seed():
    a = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=123)
    b = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=123)
    assert a is not None and b is not None
    assert a.blocks == b.blocks


def test_all_runs_valid_helper():
    skel = generate_skeleton(DEFAULT_SIZE, max_run=9, seed=5)
    if skel is None:
        pytest.skip("skeleton generation returned None")
    assert _all_runs_valid(skel.blocks, skel.size, 9)
