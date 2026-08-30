"""Integration tests for the generation pipeline (stub provider, no network)."""

from __future__ import annotations

import asyncio
import json
import re

import pytest

from generator.gemini import GeminiError, StubProvider
from generator.pipeline import generate_puzzle
from generator.store import LocalStore


def _assert_valid_payload(p) -> None:
    assert p["width"] == p["height"]  # square grid
    assert p["wordCount"] == len(p["across"]) + len(p["down"])
    assert p["wordCount"] >= 10
    assert "theme" not in p

    # every clue present, answers pure A-Z, lengths consistent
    for w in p["across"] + p["down"]:
        assert w["clue"], f"missing clue for {w['answer']}"
        assert re.fullmatch(r"[A-Z]+", w["answer"])
        assert w["length"] == len(w["answer"])
        assert w["length"] <= 9  # nothing longer than max_run


def test_pipeline_stub_produces_valid_puzzle(tmp_path):
    store = LocalStore(tmp_path)
    result = asyncio.run(
        generate_puzzle(
            "2026-01-01",
            size=10,
            skeleton_attempts=2,
            fill_node_budget=12_000,
            fill_seconds=4.0,
            fill_restarts=3,
            provider=StubProvider(seed=1),
            store=store,
        )
    )
    assert result.complete
    p = result.payload
    _assert_valid_payload(p)

    # grid solutions agree with answers at every crossing
    grid = p["grid"]
    mism = 0
    for w in p["across"]:
        for i in range(w["length"]):
            if grid[w["row"]][w["col"] + i]["solution"] != w["answer"][i]:
                mism += 1
    for w in p["down"]:
        for i in range(w["length"]):
            if grid[w["row"] + i][w["col"]]["solution"] != w["answer"][i]:
                mism += 1
    assert mism == 0

    # the puzzle was persisted to the store
    assert store.exists("2026-01-01")
    assert store.get("2026-01-01") is not None


def test_pipeline_never_ships_incomplete_or_unclued(tmp_path):
    """Regression: only complete, fully-clued grids are shipped.

    The clue writer skips rare-letter words (J/X/Z/Q, a realistic Gemini
    miss), so those get blacklisted and the filler must re-fill a grid that
    avoids them. A shipped puzzle must never be partial and never carry an
    empty clue.
    """

    class PickyClueProvider:
        async def generate_theme(self, *, seed: int):
            raise AssertionError("theme must not be requested")

        async def generate_clues(self, words, *, voice, difficulty):
            return {
                w.upper(): f"clue {w.upper()}"
                for w in words
                if not any(ch in "JXZQ" for ch in w.upper())
            }

    store = LocalStore(tmp_path)
    result = asyncio.run(
        generate_puzzle(
            "2026-10-10",
            size=10,
            provider=PickyClueProvider(),
            store=store,
        )
    )
    assert result.complete, "pipeline shipped an incomplete grid"
    p = result.payload
    _assert_valid_payload(p)
    assert p["wordCount"] >= 16, f"grid too sparse: {p['wordCount']} words"
    white = sum(1 for row in p["grid"] for c in row if c)
    assert white >= 60, f"grid too sparse: {white}/100 white cells"


def test_pipeline_fallback_recycles_existing_puzzle(tmp_path):
    """A day that can't generate recycles a random existing puzzle.

    When generation gives up (zero time budget) but the store already holds a
    puzzle for another date, the pipeline copies that puzzle, restamps its date,
    persists it, and reports it as a fallback rather than raising.
    """
    store = LocalStore(tmp_path)
    old = {
        "date": "2025-12-31",
        "width": 3,
        "height": 3,
        "grid": [
            [None, {"solution": "A", "number": 1}, None],
            [{"solution": "D", "number": 2}, {"solution": "E"}, {"solution": "F"}],
            [None, {"solution": "G"}, None],
        ],
        "across": [
            {
                "number": 2,
                "clue": "DEF clue",
                "answer": "DEF",
                "direction": "across",
                "row": 1,
                "col": 0,
                "length": 3,
                "themed": False,
            }
        ],
        "down": [
            {
                "number": 1,
                "clue": "AEG clue",
                "answer": "AEG",
                "direction": "down",
                "row": 0,
                "col": 1,
                "length": 3,
                "themed": False,
            }
        ],
        "wordCount": 2,
    }
    store.put("2025-12-31", json.dumps(old, ensure_ascii=False))

    result = asyncio.run(
        generate_puzzle(
            "2026-02-02",
            size=10,
            provider=StubProvider(seed=1),
            store=store,
            total_seconds=0.0,
        )
    )
    assert result.fallback
    assert result.complete
    assert result.payload["date"] == "2026-02-02"
    assert result.payload["width"] == 3
    assert store.exists("2026-02-02")
    assert store.get("2026-02-02") is not None


def test_pipeline_no_fallback_raises_on_empty_store(tmp_path):
    """With nothing to recycle, a failed day still raises."""
    store = LocalStore(tmp_path)
    with pytest.raises(RuntimeError):
        asyncio.run(
            generate_puzzle(
                "2026-02-03",
                size=10,
                provider=StubProvider(seed=1),
                store=store,
                total_seconds=0.0,
            )
        )


def test_pipeline_retries_transient_clue_error(tmp_path):
    """A transient clue-provider error must not blacklist the whole fill.

    Regression: a Gemini network/API blip used to yield ``got = {}``, which
    blacklisted every word in the fill and poisoned all re-fill attempts, so
    the whole run failed even though the outage was momentary.
    """

    class FlakyProvider(StubProvider):
        def __init__(self) -> None:
            self._calls = 0

        async def generate_clues(self, words, *, voice, difficulty):
            self._calls += 1
            if self._calls == 1:
                raise GeminiError("simulated transient outage", status=503)
            return await super().generate_clues(words, voice=voice, difficulty=difficulty)

    store = LocalStore(tmp_path)
    result = asyncio.run(
        generate_puzzle(
            "2026-03-03",
            size=10,
            provider=FlakyProvider(),
            store=store,
        )
    )
    assert result.complete
    _assert_valid_payload(result.payload)


def test_pipeline_second_pass_clues_missing_words(tmp_path):
    """Words skipped on the first clue pass get one more shot, alone.

    A provider that returns nothing on its first call (but clues everything it
    is asked on the second) must not blacklist any word: the second pass bumps
    the stragglers, their clues are used, and the original fill still ships.
    Without the second pass, every word would be blacklisted and the pipeline
    would fail after exhausting its re-fill rounds.
    """

    class ColdStartProvider(StubProvider):
        def __init__(self) -> None:
            self._calls = 0

        async def generate_clues(self, words, *, voice, difficulty):
            self._calls += 1
            if self._calls == 1:
                return {}
            return {w.upper(): f"clue {w.upper()}" for w in words}

    store = LocalStore(tmp_path)
    result = asyncio.run(
        generate_puzzle(
            "2026-01-05",
            size=10,
            provider=ColdStartProvider(),
            store=store,
            total_seconds=30.0,
        )
    )
    assert result.complete
    _assert_valid_payload(result.payload)
