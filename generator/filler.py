"""Backtracking CSP grid filler.

Given a skeleton's slots and a scored word bank, assign a word to every slot so
that all crossings agree and no word is reused. Themed answers may be locked
into chosen slots before the search starts.

The solver combines three standard CSP techniques that make a 15x15 tractable
in pure Python:

* **Most-constrained-variable (MRV):** at each node pick the unfilled slot
  with the fewest remaining candidates, so dead-ends surface early.
* **Forward checking:** whenever a word is placed, recompute the candidate
  domains of only the crossing slots; if any becomes empty, prune immediately.
* **Randomized restarts:** on node/time-budget exhaustion, restart with a new
  seed (different tie-breaks / candidate orders), keeping the best partial.

Pure stdlib, fully seed-deterministic.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from generator.models import Slot
from generator.wordbank import WordBank


@dataclass
class FillResult:
    assignment: dict[tuple[int, int, str], str] | None
    """Complete slot->word map, or None if no full fill was found."""

    partial: dict[tuple[int, int, str], str] = field(default_factory=dict)
    """The deepest partial fill reached (best effort when no full fill)."""

    complete: bool = False
    placed: int = 0
    nodes: int = 0
    restarts_used: int = 0


@dataclass
class _Best:
    """Mutable holder for the deepest partial assignment seen during search."""

    depth: int
    assignment: dict[tuple[int, int, str], str]


def _build_crossings(
    slots: list[Slot],
) -> dict[tuple[int, int, str], list[tuple[Slot, int, int]]]:
    """For each slot, the (other_slot, pos_in_self, pos_in_other) of crossings."""
    cell_to_slot: dict[tuple[int, int], list[tuple[Slot, int]]] = {}
    for slot in slots:
        for i, cell in enumerate(slot.cells):
            cell_to_slot.setdefault(cell, []).append((slot, i))

    crossings: dict[tuple[int, int, str], list[tuple[Slot, int, int]]] = {}
    for slot in slots:
        related: list[tuple[Slot, int, int]] = []
        for i, cell in enumerate(slot.cells):
            for other, j in cell_to_slot[cell]:
                if other.key != slot.key:
                    related.append((other, i, j))
        crossings[slot.key] = related
    return crossings


def _backtrack(
    slots: list[Slot],
    crossings: dict[tuple[int, int, str], list[tuple[Slot, int, int]]],
    bank: WordBank,
    rng: random.Random,
    grid: dict[tuple[int, int], str],
    cell_count: dict[tuple[int, int], int],
    assignment: dict[tuple[int, int, str], str],
    domains: dict[tuple[int, int, str], frozenset[str]],
    placed: set[str],
    nodes: list[int],
    node_budget: int,
    deadline: float,
    best: _Best,
) -> bool:
    if nodes[0] >= node_budget or time.monotonic() > deadline:
        return False
    if len(assignment) == len(slots):
        return True  # all slots filled

    # MRV: unfilled slot with the fewest candidates (random tie-break)
    best_slot: Slot | None = None
    best_size = 10**9
    for slot in slots:
        if slot.key in assignment:
            continue
        size = len(domains[slot.key])
        if size < best_size:
            best_size = size
            best_slot = slot
        elif size == best_size and rng.random() < 0.5:
            best_slot = slot
    if best_slot is None:
        return True
    if best_size == 0:
        return False  # dead-end (forward checking already pruned)

    # track deepest partial
    if len(assignment) > best.depth:
        best.depth = len(assignment)
        best.assignment = dict(assignment)

    slot = best_slot
    # commit to this slot: build the authoritative ordered candidate list,
    # excluding all placed words, sorted best-score first. (Domains are kept as
    # unsorted frozensets for cheap MRV sizing; only the chosen slot is sorted.)
    rank = bank.rank_of(slot.length)
    fallback = len(rank)
    candidates = sorted(domains[slot.key] - placed, key=lambda w: rank.get(w, fallback))
    # light randomization among the top-scoring options to diversify restarts
    if len(candidates) > 8:
        top = candidates[: max(4, len(candidates) // 8)]
        rng.shuffle(top)
        candidates = top + candidates[len(top) :]

    for word in candidates:
        nodes[0] += 1
        if nodes[0] >= node_budget:
            break
        # tentatively place (reference-counted so undoing a slot never wipes
        # a letter still needed by an earlier-placed crossing slot)
        for i, cell in enumerate(slot.cells):
            grid[cell] = word[i]
            cell_count[cell] = cell_count.get(cell, 0) + 1
        assignment[slot.key] = word
        placed.add(word)

        # forward check: refresh domains of crossing unfilled slots (unsorted)
        snapshot: list[tuple[tuple[int, int, str], frozenset[str]]] = []
        conflict = False
        for other, _i, _j in crossings[slot.key]:
            if other.key in assignment:
                continue
            new_dom = bank.candidates_set(other.pattern(grid), exclude=placed)
            snapshot.append((other.key, domains[other.key]))
            domains[other.key] = new_dom
            if not new_dom:
                conflict = True
                break

        if not conflict and _backtrack(
            slots,
            crossings,
            bank,
            rng,
            grid,
            cell_count,
            assignment,
            domains,
            placed,
            nodes,
            node_budget,
            deadline,
            best,
        ):
            return True

        # undo
        for cell in slot.cells:
            cell_count[cell] -= 1
            if cell_count[cell] <= 0:
                grid.pop(cell, None)
                cell_count.pop(cell, None)
        del assignment[slot.key]
        placed.discard(word)
        for key, old_dom in snapshot:
            domains[key] = old_dom

    return False


def solve_fill(
    slots: list[Slot],
    bank: WordBank,
    *,
    fixed: dict[tuple[int, int, str], str] | None = None,
    ban: set[str] | None = None,
    seed: int = 0,
    node_budget: int = 60_000,
    deadline_seconds: float = 8.0,
    restarts: int = 6,
) -> FillResult:
    """Fill all slots. Returns a FillResult (complete or best partial).

    ``deadline_seconds`` is a *total* time budget shared across all restarts
    (not a per-restart allowance), so the call never runs longer than it. A
    fresh random seed is used per restart so each explores a different path.

    ``ban`` is a persistent set of words that may never be used (e.g. words the
    clue provider could not clue); it is excluded from every candidate query.
    """
    crossings = _build_crossings(slots)
    fixed = fixed or {}
    ban = ban or set()

    # validate fixed (theme) placements are mutually consistent
    grid0: dict[tuple[int, int], str] = {}
    count0: dict[tuple[int, int], int] = {}
    placed0: set[str] = set()
    for slot in slots:
        word = fixed.get(slot.key)
        if word is None:
            continue
        for i, cell in enumerate(slot.cells):
            if cell in grid0 and grid0[cell] != word[i]:
                return FillResult(None, placed=len(fixed))  # theme conflict
            grid0[cell] = word[i]
            count0[cell] = count0.get(cell, 0) + 1
        placed0.add(word)

    best_overall: tuple[int, dict[tuple[int, int, str], str]] = (len(fixed), dict(fixed))
    complete_assignment: dict[tuple[int, int, str], str] | None = None
    nodes_total = 0
    restarts_used = 0
    # ``deadline_seconds`` is a TOTAL budget shared across all restarts (not a
    # per-restart allowance), so solve_fill honors the time the caller reserved.
    deadline = time.monotonic() + deadline_seconds

    for r in range(restarts):
        rng = random.Random(seed + r * 7919)
        grid = dict(grid0)
        cell_count = dict(count0)
        assignment = dict(fixed)
        placed = set(placed0) | ban
        # initial domains for unfilled slots (unsorted frozensets for MRV size)
        domains: dict[tuple[int, int, str], frozenset[str]] = {}
        for slot in slots:
            if slot.key in assignment:
                continue
            domains[slot.key] = bank.candidates_set(slot.pattern(grid), exclude=placed)

        # if any initial domain is empty, this restart is hopeless
        if any(not d for d in domains.values()):
            restarts_used += 1
            continue

        best = _Best(len(assignment), dict(assignment))
        nodes = [0]
        ok = _backtrack(
            slots,
            crossings,
            bank,
            rng,
            grid,
            cell_count,
            assignment,
            domains,
            placed,
            nodes,
            node_budget,
            deadline,
            best,
        )
        nodes_total += nodes[0]
        restarts_used += 1

        if ok and len(assignment) == len(slots):
            complete_assignment = dict(assignment)
            best_overall = (len(assignment), dict(assignment))
            break
        if best.depth > best_overall[0]:
            best_overall = (best.depth, dict(best.assignment))

    placed_count = len(complete_assignment) if complete_assignment is not None else best_overall[0]
    return FillResult(
        assignment=complete_assignment,
        partial=best_overall[1],
        complete=complete_assignment is not None,
        placed=placed_count,
        nodes=nodes_total,
        restarts_used=restarts_used,
    )


def realize(
    slots: list[Slot],
    assignment: dict[tuple[int, int, str], str],
    *,
    themed_keys: set[tuple[int, int, str]] | None = None,
) -> tuple[dict[tuple[int, int], str], list[tuple[str, str, int, int, bool]]]:
    """Materialize letters and raw placements from a slot->word assignment.

    Returns (cells, placements) where placements are
    ``(word, direction, row, col, themed)`` tuples ready for numbering.
    """
    themed_keys = themed_keys or set()
    cells: dict[tuple[int, int], str] = {}
    placements: list[tuple[str, str, int, int, bool]] = []
    for slot in slots:
        word = assignment.get(slot.key)
        if word is None:
            continue
        for i, cell in enumerate(slot.cells):
            cells[cell] = word[i]
        placements.append((word, slot.direction, slot.row, slot.col, slot.key in themed_keys))
    return cells, placements
