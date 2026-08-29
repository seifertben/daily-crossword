"""Standard American crossword numbering and puzzle finalization.

A white cell receives a number (scanning top-to-bottom, left-to-right) when it
begins an across entry (left neighbour blocked/off-grid, right neighbour open)
or a down entry (top neighbour blocked/off-grid, bottom neighbour open). The
same number serves both directions when a cell starts both.
"""

from __future__ import annotations

from generator.models import PlacedWord, Puzzle, Theme


def _is_white(open_cells: set[tuple[int, int]], r: int, c: int) -> bool:
    return (r, c) in open_cells


def _run_len(
    norm: set[tuple[int, int]],
    r: int,
    c: int,
    dr: int,
    dc: int,
) -> int:
    """Length of the open run starting at (r, c) going (dr, dc)."""
    n = 0
    rr, cc = r, c
    while (rr, cc) in norm:
        n += 1
        rr += dr
        cc += dc
    return n


def number_puzzle(
    open_cells: set[tuple[int, int]],
    placements: list[tuple[str, str, int, int, bool]],
    clues: dict[str, str],
    *,
    min_word: int = 3,
    theme: Theme | None = None,
    date: str | None = None,
) -> Puzzle:
    """Attach clue numbers to placements and build the final Puzzle.

    ``placements`` are ``(word, direction, row, col, themed)`` tuples from
    ``filler.realize``. ``clues`` maps an uppercase answer to its clue text.
    A cell is numbered only when it begins a real entry (run >= ``min_word``).
    """
    if not open_cells:
        raise ValueError("open_cells must be non-empty")

    min_r = min(r for r, _ in open_cells)
    min_c = min(c for _, c in open_cells)

    # normalize coordinates to 0-origin (skeletons are already 0-origin, but
    # this keeps numbering correct for any bbox)
    norm = open_cells
    if min_r != 0 or min_c != 0:
        norm = {(r - min_r, c - min_c) for r, c in open_cells}
        placements = [(w, d, r - min_r, c - min_c, t) for (w, d, r, c, t) in placements]
    max_r = max(r for r, _ in norm)
    max_c = max(c for _, c in norm)
    width = max_c + 1
    height = max_r + 1

    # assign numbers
    numbers: dict[tuple[int, int], int] = {}
    next_num = 1
    for r in range(height):
        for c in range(width):
            if (r, c) not in norm:
                continue
            left_blocked = c == 0 or (r, c - 1) not in norm
            above_blocked = r == 0 or (r - 1, c) not in norm
            starts_across = left_blocked and _run_len(norm, r, c, 0, 1) >= min_word
            starts_down = above_blocked and _run_len(norm, r, c, 1, 0) >= min_word
            if starts_across or starts_down:
                numbers[(r, c)] = next_num
                next_num += 1

    # build placed words (sorted by number for stable output)
    words: list[PlacedWord] = []
    for word, direction, row, col, themed in placements:
        number = numbers.get((row, col))
        if number is None:
            continue
        words.append(
            PlacedWord(
                answer=word,
                clue=clues.get(word.upper(), ""),
                direction=direction,
                row=row,
                col=col,
                number=number,
                themed=themed,
            )
        )
    words.sort(key=lambda w: (w.number, 0 if w.direction == "across" else 1))

    # solution letters (only cells covered by placed words)
    cells: dict[tuple[int, int], str] = {}
    for w in words:
        dr, dc = (0, 1) if w.direction == "across" else (1, 0)
        for i, ch in enumerate(w.answer):
            cells[(w.row + dr * i, w.col + dc * i)] = ch

    return Puzzle(
        width=width,
        height=height,
        cells=cells,
        words=words,
        theme=theme,
        date=date,
    )
