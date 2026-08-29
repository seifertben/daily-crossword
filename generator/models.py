"""Core data structures shared across the generator pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Slot:
    """An open run of cells that must be filled with one word.

    A skeleton's white cells decompose into across slots (maximal horizontal
    runs) and down slots (maximal vertical runs). Each slot is a constraint
    the filler must satisfy.
    """

    row: int
    col: int
    direction: str  # "across" | "down"
    length: int
    cells: tuple[tuple[int, int], ...]

    @property
    def key(self) -> tuple[int, int, str]:
        return (self.row, self.col, self.direction)

    def pattern(self, grid: dict[tuple[int, int], str]) -> str:
        """Current pattern of this slot against a partial grid, '?' = empty."""
        return "".join(grid.get(cell, "?") if grid.get(cell) else "?" for cell in self.cells)


@dataclass(frozen=True)
class PlacedWord:
    answer: str
    clue: str
    direction: str  # "across" | "down"
    row: int
    col: int
    number: int | None = None
    themed: bool = False

    @property
    def length(self) -> int:
        return len(self.answer)


@dataclass
class Theme:
    title: str
    voice: str
    themed_answers: dict[str, str] = field(default_factory=dict)
    """Map of themed answer (uppercase A-Z) -> its themed clue text."""


@dataclass
class Skeleton:
    """A 15x15 (or N x N) pattern of white cells and black blocks."""

    size: int
    blocks: frozenset[tuple[int, int]]

    def is_open(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size and (r, c) not in self.blocks

    @property
    def open_cells(self) -> set[tuple[int, int]]:
        return {
            (r, c) for r in range(self.size) for c in range(self.size) if (r, c) not in self.blocks
        }

    def render(self) -> list[str]:
        return [
            "".join("." if self.is_open(r, c) else "#" for c in range(self.size))
            for r in range(self.size)
        ]


@dataclass
class Puzzle:
    width: int
    height: int
    cells: dict[tuple[int, int], str]
    """(row, col) -> solution letter for every white cell."""
    words: list[PlacedWord]
    theme: Theme | None = None
    date: str | None = None

    @property
    def word_count(self) -> int:
        return len(self.words)
