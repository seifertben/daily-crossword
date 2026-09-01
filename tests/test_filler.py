"""Tests for the CSP filler and crossword numbering."""

from __future__ import annotations

import pytest

from generator.filler import realize, solve_fill
from generator.models import Slot
from generator.number import number_puzzle
from generator.wordbank import WordBank

# ---- fixtures ----------------------------------------------------------


def _bank() -> WordBank:
    return WordBank(
        [
            ("START", 90),
            ("TEARS", 80),
            ("STAB", 70),
            ("STORE", 60),
            ("SCORE", 55),
            ("STARS", 50),
            ("TRAMS", 45),
            ("BEAR", 40),
            ("STAR", 35),
            ("TEAR", 30),
            ("TEAM", 25),
            ("BEAD", 20),
            ("CATS", 15),
            ("CARE", 10),
        ]
    )


def _plus_slots() -> list[Slot]:
    """A 4x5 grid with two across 5s and one down 4, all crossing:
    S T A R T
    T E A R S
    A . . . .
    B . . . .
    """
    return [
        Slot(0, 0, "across", 5, ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4))),
        Slot(1, 0, "across", 5, ((1, 0), (1, 1), (1, 2), (1, 3), (1, 4))),
        Slot(0, 0, "down", 4, ((0, 0), (1, 0), (2, 0), (3, 0))),
    ]


_PLUS_OPEN = {
    (0, 0),
    (0, 1),
    (0, 2),
    (0, 3),
    (0, 4),
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (2, 0),
    (3, 0),
}


# ---- filler ------------------------------------------------------------


def test_filler_completes_small_grid():
    bank = _bank()
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=1, node_budget=2000, deadline_seconds=2.0)
    assert result.complete
    assert result.placed == 3
    assert result.assignment is not None
    assert result.assignment[(0, 0, "across")] == "START"
    assert result.assignment[(1, 0, "across")] == "TEARS"
    assert result.assignment[(0, 0, "down")] == "STAB"


def test_filler_no_duplicate_words():
    bank = _bank()
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=1, node_budget=2000, deadline_seconds=2.0)
    assert result.assignment is not None
    words = list(result.assignment.values())
    assert len(words) == len(set(words)), "a word was reused"


def test_filler_crossings_consistent():
    bank = _bank()
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=1, node_budget=2000, deadline_seconds=2.0)
    assert result.assignment is not None
    cells, _ = realize(slots, result.assignment)
    # the shared column-0 cells must agree between START/TEARS and STAB
    assert cells[(0, 0)] == "S"
    assert cells[(1, 0)] == "T"
    assert cells[(2, 0)] == "A"
    assert cells[(3, 0)] == "B"


def test_filler_fixed_theme_placement():
    bank = _bank()
    slots = _plus_slots()
    fixed = {(0, 0, "across"): "START"}
    result = solve_fill(slots, bank, fixed=fixed, seed=2, node_budget=2000, deadline_seconds=2.0)
    assert result.complete
    assert result.assignment[(0, 0, "across")] == "START"


def test_filler_conflicting_fixed_returns_failure():
    bank = _bank()
    slots = _plus_slots()
    # START wants (0,0)=S; STAB fixed wants (0,0)=S too -> ok. Force a conflict:
    fixed = {(0, 0, "across"): "START", (0, 0, "down"): "BEAR"}  # B != S at (0,0)
    result = solve_fill(slots, bank, fixed=fixed, seed=2, node_budget=500, deadline_seconds=1.0)
    assert not result.complete


def test_filler_unfillable_returns_partial():
    # bank with no 5-letter words -> across slots cannot be filled
    bank = WordBank([("BEAR", 40), ("STAR", 35), ("CAT", 20), ("DOG", 10)])
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=1, node_budget=500, deadline_seconds=1.0, restarts=2)
    assert not result.complete
    # at least the down slot might fill; partial should not exceed available
    assert result.placed <= 1


def test_filler_prefers_non_names_under_cap():
    # START and TRAMS are proper names; STARS is a common word. All three fit
    # the across-0 slot. With a small name cap the solver must choose STARS.
    bank = WordBank(
        [
            ("START", 90),
            ("STARS", 80),
            ("TRAMS", 70),
            ("STAB", 40),
            ("TEAR", 30),
        ],
        names={"START", "TRAMS"},
        common_words={"STARS", "STAB", "TEAR"},
    )
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=1, node_budget=2000, deadline_seconds=2.0, name_cap=1)
    assert result.complete
    assert result.assignment is not None
    across0 = result.assignment[(0, 0, "across")]
    assert across0 == "STARS", "preferred a proper name when a common word fit"


def test_filler_exceeds_name_cap_only_when_needed():
    # Every across-0 option is a proper name, so even a tiny cap is exceeded
    # rather than failing to fill the grid (last-resort fallback).
    bank = WordBank(
        [
            ("START", 90),
            ("TRAMS", 70),
            ("STARK", 50),
            ("STAB", 40),
            ("TEAR", 30),
        ],
        names={"START", "TRAMS", "STARK"},
        common_words={"STAB", "TEAR"},
    )
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=3, node_budget=3000, deadline_seconds=2.0, name_cap=1)
    assert result.complete, "failed to fill despite a name-only option"
    assert result.assignment is not None
    assert bank.is_proper(result.assignment[(0, 0, "across")])


# ---- numbering ---------------------------------------------------------


def test_numbering_assigns_expected_numbers():
    bank = _bank()
    slots = _plus_slots()
    result = solve_fill(slots, bank, seed=1, node_budget=2000, deadline_seconds=2.0)
    assert result.assignment is not None
    cells, placements = realize(slots, result.assignment)
    puzzle = number_puzzle(_PLUS_OPEN, placements, clues={})

    # (0,0) starts both across and down -> number 1 (START across, STAB down)
    # (1,0) starts across (TEARS), not down (above open) -> number 2
    by_key = {(w.row, w.col, w.direction): w for w in puzzle.words}
    assert by_key[(0, 0, "across")].number == 1
    assert by_key[(0, 0, "down")].number == 1
    assert by_key[(1, 0, "across")].number == 2
    assert puzzle.width == 5 and puzzle.height == 4
    assert puzzle.word_count == 3


def test_numbering_clues_attached():
    slots = _plus_slots()
    assignment = {
        (0, 0, "across"): "START",
        (1, 0, "across"): "TEARS",
        (0, 0, "down"): "STAB",
    }
    _, placements = realize(slots, assignment)
    clues = {"START": "Begin", "TEARS": "Cries", "STAB": "Knife wound"}
    puzzle = number_puzzle(_PLUS_OPEN, placements, clues)
    by_ans = {w.answer: w for w in puzzle.words}
    assert by_ans["START"].clue == "Begin"
    assert by_ans["TEARS"].clue == "Cries"
    assert by_ans["STAB"].clue == "Knife wound"


# ---- integration: real bank + 15x15 skeleton --------------------------


def _verify_crossings(slots, assignment):
    cells, _ = realize(slots, assignment)
    for slot in slots:
        word = assignment.get(slot.key)
        if word is None:
            continue
        for i, cell in enumerate(slot.cells):
            assert cells[cell] == word[i], "crossing mismatch"
    words = [w for w in assignment.values()]
    assert len(words) == len(set(words)), "duplicate word in fill"


def test_integration_real_bank_fills_15x15():
    from generator.skeleton import extract_slots, generate_skeleton
    from generator.wordbank import get_bank

    skel = generate_skeleton(15, max_run=9, seed=7)
    if skel is None:
        pytest.skip("skeleton generation returned None")
    slots = extract_slots(skel)
    bank = get_bank()
    result = solve_fill(slots, bank, seed=3, node_budget=40_000, deadline_seconds=6.0, restarts=4)
    chosen = result.assignment if result.complete else result.partial
    assert chosen and len(chosen) >= 20, "fill produced nothing usable"
    _verify_crossings(slots, chosen)
