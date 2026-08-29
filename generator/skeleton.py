"""Procedural crossword skeleton (block pattern) generation.

A skeleton is an N x N grid of white cells and black blocks that follows the
standard American conventions:

* 180-degree rotational symmetry (a block at (r, c) forces one at
  (size-1-r, size-1-c)).
* every maximal horizontal/vertical run of white cells is between MIN_RUN and
  ``max_run`` long (so every entry is a real, fillable word and every white
  cell is part of both an across and a down entry).
* no solid 2x2 block chunks.
* all white cells connected (one flood-fill component).
* a healthy slot count so the filler has room to work.

Construction starts fully open and adds mirrored block pairs one at a time,
rejecting any placement that would strand a run shorter than MIN_RUN (such a
run can never be repaired later). Over-long runs are split afterwards.

Pure stdlib, fully seed-deterministic.
"""

from __future__ import annotations

import random

from generator.models import Skeleton, Slot

MIN_RUN = 3
MIN_WORD = 3
DEFAULT_SIZE = 15


def _runs_along(fixed: int, size: int, blocks: frozenset[tuple[int, int]], axis: str) -> list[int]:
    """Open-cell run lengths along one row (axis='r') or column ('c')."""
    run = 0
    out: list[int] = []
    for i in range(size + 1):
        cell = (fixed, i) if axis == "r" else (i, fixed)
        if i < size and cell not in blocks:
            run += 1
        elif run:
            out.append(run)
            run = 0
    return out


def _touched_ok(
    blocks: frozenset[tuple[int, int]], lines: list[tuple[str, int]], size: int
) -> bool:
    """Incremental gate: no run shorter than MIN_RUN on the touched lines."""
    for axis, fixed in lines:
        for ln in _runs_along(fixed, size, blocks, axis):
            if ln < MIN_RUN and ln > 0:
                return False
    return True


def _all_runs_valid(blocks: frozenset[tuple[int, int]], size: int, max_run: int) -> bool:
    for fixed in range(size):
        for axis in ("r", "c"):
            for ln in _runs_along(fixed, size, blocks, axis):
                if not (MIN_RUN <= ln <= max_run):
                    return False
    return True


def _has_2x2_block(blocks: frozenset[tuple[int, int]], size: int) -> bool:
    return any(
        {(i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)} <= blocks
        for i in range(size - 1)
        for j in range(size - 1)
    )


def _connected(opens: set[tuple[int, int]]) -> bool:
    if not opens:
        return False
    start = next(iter(opens))
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (nr, nc) in opens and (nr, nc) not in seen:
                seen.add((nr, nc))
                stack.append((nr, nc))
    return len(seen) == len(opens)


def _count_slots(opens: set[tuple[int, int]], size: int) -> int:
    total = 0
    for fixed in range(size):
        for axis in ("r", "c"):
            run = 0
            for i in range(size + 1):
                cell = (fixed, i) if axis == "r" else (i, fixed)
                if i < size and cell in opens:
                    run += 1
                elif run:
                    total += 1
                    run = 0
    return total


def _split_long_runs(
    blocks: set[tuple[int, int]], size: int, max_run: int, rng: random.Random
) -> bool:
    """Add mirrored block pairs until no run exceeds max_run. True on success."""
    for _ in range(size * size):
        offender: list[tuple[int, int]] | None = None
        frozen_blocks = frozenset(blocks)
        for fixed in range(size):
            for axis in ("r", "c"):
                run: list[tuple[int, int]] = []
                for i in range(size + 1):
                    cell = (fixed, i) if axis == "r" else (i, fixed)
                    if i < size and cell not in frozen_blocks:
                        run.append(cell)
                    else:
                        if len(run) > max_run:
                            offender = run
                            break
                        run = []
                if offender:
                    break
            if offender:
                break
        if not offender:
            return True

        # try split positions near the middle, mirrored
        mids = sorted(
            range(len(offender)), key=lambda i: (abs(i - len(offender) / 2), rng.random())
        )
        placed = False
        for idx in mids[1:-1] or mids:
            cell = offender[idx]
            mirror = (size - 1 - cell[0], size - 1 - cell[1])
            if cell in blocks:
                continue
            cand = frozenset(blocks | {cell, mirror})
            touched = [("r", cell[0]), ("c", cell[1]), ("r", mirror[0]), ("c", mirror[1])]
            if not _touched_ok(cand, touched, size):
                continue
            if _has_2x2_block(cand, size):
                continue
            blocks |= {cell, mirror}
            placed = True
            break
        if not placed:
            return False
    return _all_runs_valid(frozenset(blocks), size, max_run)


def generate_skeleton(
    size: int = DEFAULT_SIZE,
    *,
    max_run: int = 9,
    block_ratio: float = 0.17,
    min_slots: int | None = None,
    attempts: int = 400,
    seed: int | None = None,
) -> Skeleton | None:
    """Generate one valid skeleton, or None if the budget ran out."""
    rng = random.Random(seed)
    target = round(size * size * block_ratio)
    if min_slots is None:
        min_slots = size * size // 4  # floor, not target
    cells = [(r, c) for r in range(size) for c in range(size)]
    max_rejects = max(80, size * 5)

    for _ in range(attempts):
        blocks: set[tuple[int, int]] = set()
        goal = target + rng.randint(-3, 3)
        rejects = 0
        guard = 0
        uncovered_rows = set(range(size))
        uncovered_cols = set(range(size))

        while len(blocks) < goal and rejects < max_rejects and guard < size * size * 2:
            guard += 1
            roll = rng.random()
            if uncovered_rows and (roll < 0.4 or not uncovered_cols):
                r = rng.choice(sorted(uncovered_rows))
                c = rng.randrange(size)
            elif uncovered_cols:
                c = rng.choice(sorted(uncovered_cols))
                r = rng.randrange(size)
            else:
                r, c = rng.choice(cells)
            pair = ((r, c), (size - 1 - r, size - 1 - c))
            if pair[0] in blocks:
                continue
            cand = frozenset(blocks | set(pair))
            touched = [("r", pair[0][0]), ("c", pair[0][1])]
            if pair[1] != pair[0]:
                touched.append(("r", pair[1][0]))
                touched.append(("c", pair[1][1]))
            if not _touched_ok(cand, touched, size):
                rejects += 1
                continue
            if _has_2x2_block(cand, size):
                rejects += 1
                continue
            blocks = set(cand)
            for br, bc in pair:
                uncovered_rows.discard(br)
                uncovered_cols.discard(bc)

        if not _split_long_runs(blocks, size, max_run, rng):
            continue
        frozen = frozenset(blocks)
        if not _all_runs_valid(frozen, size, max_run):
            continue
        opens = {(r, c) for r in range(size) for c in range(size)} - frozen
        density = len(opens) / (size * size)
        if not (0.72 <= density <= 0.90):
            continue
        if not _connected(opens):
            continue
        if _count_slots(opens, size) < min_slots:
            continue
        return Skeleton(size=size, blocks=frozen)

    return None


def extract_slots(skeleton: Skeleton, *, min_word: int = MIN_WORD) -> list[Slot]:
    """Decompose a skeleton into across and down slots (runs >= min_word)."""
    size = skeleton.size
    slots: list[Slot] = []

    # across
    for r in range(size):
        run: list[tuple[int, int]] = []
        for c in range(size + 1):
            cell = (r, c)
            if c < size and skeleton.is_open(r, c):
                run.append(cell)
            elif run:
                if len(run) >= min_word:
                    slots.append(Slot(r, run[0][1], "across", len(run), tuple(run)))
                run = []

    # down
    for c in range(size):
        run = []
        for r in range(size + 1):
            cell = (r, c)
            if r < size and skeleton.is_open(r, c):
                run.append(cell)
            elif run:
                if len(run) >= min_word:
                    slots.append(Slot(run[0][0], c, "down", len(run), tuple(run)))
                run = []

    return slots
