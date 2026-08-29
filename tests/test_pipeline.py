"""Integration tests for the generation pipeline (stub provider, no network)."""

from __future__ import annotations

import asyncio
import re

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
