"""End-to-end daily puzzle generation pipeline.

skeleton selection -> CSP fill -> fresh clues (with ephemeral blacklist +
re-fill) -> number -> serialize -> store.

No theme: the grid is filled purely from the word bank. The same ``date``
always yields the same seed, and only a COMPLETE, fully-clued grid is ever
shipped (partial fills and empty clues are never persisted).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
from dataclasses import dataclass
from typing import Any

from generator import gemini
from generator.filler import realize, solve_fill
from generator.models import Puzzle, Slot
from generator.number import number_puzzle
from generator.serialize import puzzle_to_dict
from generator.skeleton import extract_slots, generate_skeleton
from generator.store import PuzzleStore, get_store
from generator.wordbank import WordBank, get_bank

_SIZE = 10  # a 10x10 solves comfortably in well under 10 minutes
_MAX_RUN = 9  # every entry is at most 9 letters, keeping fills short and easy
_DIFFICULTY = 3  # Standard: balanced, fair clues calibrated for a ~10-minute solve
_SKELETON_ATTEMPTS = 8
_FILL_RETRIES = 3  # clue-blacklist re-fill rounds (initial fill + 2 re-fills)
_FILL_NODE_BUDGET = 200_000
_FILL_SECONDS = 6.0
_FILL_RESTARTS = 6
_CLUE_RETRIES = 3  # clue-call attempts before blaming the words
_CLUE_BACKOFF = 1.0  # base seconds for exponential backoff between clue calls
_VOICE = "neutral, simple, friendly"  # plain-fill clue voice (no theme)


@dataclass
class GenResult:
    puzzle: Puzzle
    payload: dict[str, Any]
    complete: bool


@dataclass
class _Scenario:
    """A skeleton ready to be filled."""

    slots: list[Slot]
    open_cells: set[tuple[int, int]]
    seed: int


def _date_seed(date: str) -> int:
    y, m, d = (int(x) for x in date.split("-"))
    return y * 10000 + m * 100 + d


async def _fill_one(
    slots: list[Slot],
    bank: WordBank,
    open_cells: set[tuple[int, int]],
    date: str,
    *,
    seed: int,
    difficulty: int,
    provider: gemini.ClueProvider,
    node_budget: int,
    deadline_seconds: float,
    restarts: int,
) -> dict[str, Any] | None:
    """Fill one grid and return its serialized payload, or None.

    Only a grid that is BOTH fully filled AND fully clued is accepted. Words
    the clue provider cannot clue are blacklisted and the fill is retried with
    a fresh seed, so unclueable words never appear in a shipped puzzle.
    """
    ban: set[str] = set()
    for attempt in range(_FILL_RETRIES):
        result = solve_fill(
            slots,
            bank,
            ban=ban,
            seed=seed + attempt * 104729,
            node_budget=node_budget,
            deadline_seconds=deadline_seconds,
            restarts=restarts,
        )
        if not result.complete or not result.assignment:
            return None  # never ship a partial grid; move to the next skeleton
        chosen = result.assignment
        words = list(chosen.values())

        # Retry the clue call before concluding the words are unclueable: a
        # transient network/API error must NOT blacklist the whole fill (that
        # would poison every re-fill attempt). Only a successful response that
        # omits words (or flags them INVALID) is evidence against the words.
        got: dict[str, str] = {}
        provider_error = False
        for backoff in range(_CLUE_RETRIES):
            try:
                got = await provider.generate_clues(
                    words,
                    voice=_VOICE,
                    difficulty=difficulty,
                )
                break
            except gemini.GeminiError:
                provider_error = True
                got = {}
                await asyncio.sleep(_CLUE_BACKOFF * (2**backoff))
        if not got and provider_error:
            continue  # provider is down; don't grow the ban, just try a fresh fill
        missing = [w for w in words if w not in got]

        if missing:
            ban |= set(missing)  # blacklist unclueable words and re-fill
            continue

        _, placements = realize(slots, chosen)
        puzzle = number_puzzle(open_cells, placements, got, date=date)
        return puzzle_to_dict(puzzle)
    return None


async def generate_puzzle(
    date: str | None = None,
    *,
    seed: int | None = None,
    difficulty: int = _DIFFICULTY,
    size: int = _SIZE,
    skeleton_attempts: int = _SKELETON_ATTEMPTS,
    fill_node_budget: int = _FILL_NODE_BUDGET,
    fill_seconds: float = _FILL_SECONDS,
    fill_restarts: int = _FILL_RESTARTS,
    total_seconds: float = 60.0,
    provider: gemini.ClueProvider | None = None,
    bank: WordBank | None = None,
    store: PuzzleStore | None = None,
) -> GenResult:
    """Generate and persist one day's puzzle. Returns the GenResult.

    ``seed`` overrides the deterministic date-derived seed, so a caller can
    request a completely original puzzle for a given (or any) date.
    """
    date = date or dt.datetime.now(dt.UTC).date().strftime("%Y-%m-%d")
    seed = seed if seed is not None else _date_seed(date)
    start = time.monotonic()

    provider = provider or gemini.get_provider()
    bank = bank or get_bank()
    store = store or get_store()

    for attempt in range(skeleton_attempts):
        if time.monotonic() - start > total_seconds:
            break
        skel = generate_skeleton(
            size,
            max_run=_MAX_RUN,
            seed=(seed * 17 + attempt) % (2**31),
        )
        if skel is None:
            continue
        slots = extract_slots(skel)
        sc = _Scenario(slots, skel.open_cells, seed + attempt * 5)
        remaining = total_seconds - (time.monotonic() - start)
        if remaining <= 0:
            break
        payload = await _fill_one(
            sc.slots,
            bank,
            sc.open_cells,
            date,
            seed=sc.seed,
            difficulty=difficulty,
            provider=provider,
            node_budget=fill_node_budget,
            deadline_seconds=min(fill_seconds, max(0.5, remaining)),
            restarts=fill_restarts,
        )
        if payload is None:
            continue
        store.put(date, json.dumps(payload, ensure_ascii=False, indent=2))
        puzzle = _payload_to_puzzle(payload, date)
        return GenResult(puzzle=puzzle, payload=payload, complete=True)

    raise RuntimeError(
        f"could not generate a puzzle for {date}; try a different seed or check the word bank."
    )


def _payload_to_puzzle(payload: dict[str, Any], date: str) -> Puzzle:
    """Reconstruct a lightweight Puzzle from the serialized payload (for return)."""
    from generator.models import PlacedWord

    cells: dict[tuple[int, int], str] = {}
    for r, row in enumerate(payload["grid"]):
        for c, info in enumerate(row):
            if info:
                cells[(r, c)] = info["solution"]
    words = [
        PlacedWord(
            answer=w["answer"],
            clue=w["clue"],
            direction=w["direction"],
            row=w["row"],
            col=w["col"],
            number=w["number"],
            themed=False,
        )
        for w in payload["across"] + payload["down"]
    ]
    return Puzzle(
        width=payload["width"],
        height=payload["height"],
        cells=cells,
        words=words,
        theme=None,
        date=date,
    )


def main() -> None:
    import argparse
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Generate one daily crossword.")
    parser.add_argument("date", nargs="?", help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--difficulty", type=int, default=_DIFFICULTY, choices=range(1, 6))
    parser.add_argument(
        "--seed",
        type=int,
        help="override the date-derived seed for a completely fresh puzzle",
    )
    args = parser.parse_args()

    result = asyncio.run(
        generate_puzzle(
            args.date,
            difficulty=args.difficulty,
            seed=args.seed,
        )
    )
    p = result.puzzle
    print(
        f"Generated {p.date}: {p.word_count} words "
        f"on a {p.width}x{p.height} grid "
        f"(difficulty {args.difficulty})"
    )


if __name__ == "__main__":
    main()
