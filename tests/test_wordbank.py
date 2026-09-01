"""Tests for the scored word bank and its pattern index."""

from __future__ import annotations

import pytest

from generator.wordbank import WordBank, get_bank, reset_cache


def _sample_bank() -> WordBank:
    entries = [
        # 5-letter
        ("APPLE", 95),
        ("BASTE", 90),
        ("CARVE", 80),
        ("PASTE", 70),
        # 4-letter
        ("RAVE", 60),
        ("CARE", 50),
        ("DATE", 40),
        ("DUNE", 30),
        ("AXLE", 20),
        ("BABE", 10),
        # 3-letter
        ("CAT", 70),
        ("DOG", 50),
        # dropped: digits / too short
        ("R2D2", 99),
        ("NO", 100),
    ]
    return WordBank(entries)


def test_filters_non_alpha_and_short():
    bank = _sample_bank()
    assert not bank.contains("R2D2")
    assert not bank.contains("NO")
    assert bank.contains("BASTE")


def test_words_of_length_sorted_by_score():
    bank = _sample_bank()
    fives = bank.words_of_length(5)
    assert fives[0] == "APPLE"  # highest score
    assert "BASTE" in fives and "CARVE" in fives and "PASTE" in fives


def test_candidates_full_wildcard_returns_bucket_ordered():
    bank = _sample_bank()
    fours = bank.candidates("????")
    assert fours[0] == "RAVE"  # score 60, highest among 4-letter words
    assert set(fours) == {"RAVE", "CARE", "DATE", "DUNE", "AXLE", "BABE"}


def test_candidates_with_fixed_letters():
    bank = _sample_bank()
    # ?A?E -> RAVE, CARE, DATE, BABE (DUNE has U at pos1; AXLE has X at pos1)
    hits = bank.candidates("?A?E")
    assert set(hits) == {"RAVE", "CARE", "DATE", "BABE"}
    # ordered by score: RAVE(60) > CARE(50) > DATE(40) > BABE(10)
    assert hits == ["RAVE", "CARE", "DATE", "BABE"]


def test_candidates_no_match_returns_empty():
    bank = _sample_bank()
    assert bank.candidates("ZZZZ") == []


def test_candidates_exclude():
    bank = _sample_bank()
    hits = bank.candidates("?A?E", exclude={"RAVE", "CARE"})
    assert hits == ["DATE", "BABE"]


def test_pool_size_and_has_length():
    bank = _sample_bank()
    assert bank.has_length(5)
    assert bank.pool_size(5) == 4
    assert not bank.has_length(99)


def test_dedup_keeps_highest_score():
    entries = [("CAT", 30), ("CAT", 70), ("DOG", 50)]
    bank = WordBank(entries)
    assert bank.score_of("CAT") == 70


def test_slot_candidates_uses_grid_pattern():
    from generator.models import Slot

    bank = _sample_bank()
    slot = Slot(0, 0, "across", 4, ((0, 0), (0, 1), (0, 2), (0, 3)))
    grid = {(0, 0): "C", (0, 2): "R"}  # C?R?
    hits = bank.slot_candidates(slot, grid)
    assert hits == ["CARE"]


def test_real_broda_loads_smoke():
    reset_cache()
    try:
        bank = get_bank()
    except FileNotFoundError:
        pytest.skip("broda_scored.txt not vendored")
    # the default quality floor keeps the bank large but cuts low-score junk
    assert len(bank) > 50_000
    assert bank.has_length(7)
    assert bank.pool_size(7) > 1_000
    # an A-Z 7-letter pattern with one fixed letter should return many matches
    hits = bank.candidates("S??????")
    assert len(hits) > 100
    assert all(w.startswith("S") and len(w) == 7 for w in hits)
    # ordered best-score first
    assert bank.score_of(hits[0]) >= bank.score_of(hits[-1])
    # quality floor: low-score junk is gone
    assert not bank.contains("DUAN")
    assert not bank.contains("NRACODE")


def test_min_score_threshold_filters_low_score_entries():
    reset_cache()
    full = get_bank(min_score=0)
    floor = get_bank(min_score=51)
    assert len(floor) < len(full)
    # the offending low-score fill words are excluded at the default floor
    assert not floor.contains("DUAN")
    assert not floor.contains("NRACODE")
    assert not floor.contains("VEINE")
    reset_cache()


def test_is_proper_classification():
    # fixture: names known to the census + common/dictionary words
    bank = WordBank(
        [
            ("SMITH", 80),
            ("PARK", 80),
            ("PARKER", 80),
        ],
        names={"SMITH", "PARK", "PARKER"},
        common_words={"PARK"},  # PARK is a common word homonym of the name
    )
    # a name with no common-word reading is proper
    assert bank.is_proper("SMITH")
    assert bank.is_proper("PARKER")
    # a name that is also a common word is NOT treated as a hard proper name
    assert not bank.is_proper("PARK")
    # a word not in the names list at all is not proper
    assert not bank.is_proper("CATS")


def test_default_bank_marks_real_names_proper():
    reset_cache()
    try:
        bank = get_bank()
    except FileNotFoundError:
        pytest.skip("broda_scored.txt not vendored")
    # common homonyms are not flagged as hard names
    assert not bank.is_proper("ROSE")
    assert not bank.is_proper("SEA")
    # celebrity/dictionary names pass through unrestricted (treated as words)
    assert not bank.is_proper("JAGGER")
    assert not bank.is_proper("EINSTEIN")
    assert not bank.is_proper("MADONNA")
    # purely surname-only entries are flagged (no common-word reading)
    assert bank.is_proper("NICOLAI")
    assert bank.is_proper("ARNETT")
    reset_cache()

