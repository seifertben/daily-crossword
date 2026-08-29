"""Serialize a filled :class:`Puzzle` into the JSON shape the frontend expects.

The solution letters are included so Check/Reveal run client-side (per the
agreed design); the puzzle is immutable and CDN-cacheable.
"""

from __future__ import annotations

from typing import Any

from generator.models import PlacedWord, Puzzle


def puzzle_to_dict(puzzle: Puzzle) -> dict[str, Any]:
    grid: list[list[dict[str, Any] | None]] = []
    for r in range(puzzle.height):
        row: list[dict[str, Any] | None] = []
        for c in range(puzzle.width):
            letter = puzzle.cells.get((r, c))
            if letter is None:
                row.append(None)
                continue
            entry: dict[str, Any] = {"solution": letter}
            number = next(
                (w.number for w in puzzle.words if w.row == r and w.col == c),
                None,
            )
            if number is not None:
                entry["number"] = number
            row.append(entry)
        grid.append(row)

    def word_dto(w: PlacedWord) -> dict[str, Any]:
        return {
            "number": w.number,
            "clue": w.clue,
            "answer": w.answer,
            "direction": w.direction,
            "row": w.row,
            "col": w.col,
            "length": len(w.answer),
            "themed": bool(w.themed),
        }

    across = sorted(
        (word_dto(w) for w in puzzle.words if w.direction == "across"),
        key=lambda d: d["number"],
    )
    down = sorted(
        (word_dto(w) for w in puzzle.words if w.direction == "down"),
        key=lambda d: d["number"],
    )

    payload: dict[str, Any] = {
        "date": puzzle.date,
        "width": puzzle.width,
        "height": puzzle.height,
        "grid": grid,
        "across": across,
        "down": down,
        "wordCount": len(puzzle.words),
    }
    if puzzle.theme:
        payload["theme"] = {
            "title": puzzle.theme.title,
            "voice": puzzle.theme.voice,
        }
    return payload
