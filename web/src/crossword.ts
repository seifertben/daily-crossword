import type { Direction, Pos, Puzzle, WordDTO } from "./types";

export type Grid = (string | null)[][];

export function createEmptyGrid(puzzle: Puzzle): Grid {
  return Array.from({ length: puzzle.height }, () =>
    Array.from({ length: puzzle.width }, () => null as string | null),
  );
}

export function isOpen(puzzle: Puzzle, r: number, c: number): boolean {
  return r >= 0 && r < puzzle.height && c >= 0 && c < puzzle.width && puzzle.grid[r][c] !== null;
}

export function wordCells(w: WordDTO): Pos[] {
  const cells: Pos[] = [];
  for (let i = 0; i < w.length; i++) {
    cells.push({
      row: w.row + (w.direction === "down" ? i : 0),
      col: w.col + (w.direction === "across" ? i : 0),
    });
  }
  return cells;
}

export function indexInWord(w: WordDTO, r: number, c: number): number {
  return w.direction === "across" ? c - w.col : r - w.row;
}

export function wordAt(puzzle: Puzzle, r: number, c: number, dir: Direction): WordDTO | null {
  const list = dir === "across" ? puzzle.across : puzzle.down;
  return (
    list.find((w) => {
      if (w.direction === "across") {
        return r === w.row && c >= w.col && c < w.col + w.length;
      }
      return c === w.col && r >= w.row && r < w.row + w.length;
    }) ?? null
  );
}

export function supportsBothDirections(puzzle: Puzzle, r: number, c: number): boolean {
  return Boolean(wordAt(puzzle, r, c, "across") && wordAt(puzzle, r, c, "down"));
}

export function firstOpenCell(puzzle: Puzzle): Pos | null {
  for (let r = 0; r < puzzle.height; r++) {
    for (let c = 0; c < puzzle.width; c++) {
      if (isOpen(puzzle, r, c)) return { row: r, col: c };
    }
  }
  return null;
}

/** Step one cell in (dr, dc), skipping blocks. Returns the new pos or the original. */
export function moveCursor(puzzle: Puzzle, from: Pos, dr: number, dc: number): Pos {
  let { row, col } = from;
  do {
    row += dr;
    col += dc;
  } while (
    row >= 0 &&
    row < puzzle.height &&
    col >= 0 &&
    col < puzzle.width &&
    !isOpen(puzzle, row, col)
  );
  if (isOpen(puzzle, row, col)) return { row, col };
  return from;
}

/** Next square of the active word, or null if past the end. */
export function nextInWord(w: WordDTO, idx: number, delta: number): Pos | null {
  const next = idx + delta;
  if (next < 0 || next >= w.length) return null;
  return wordCells(w)[next];
}

export function allClues(puzzle: Puzzle): WordDTO[] {
  return [...puzzle.across, ...puzzle.down];
}

/** First blank cell of a word (for "jump to first blank" behaviour). */
export function firstBlankInWord(grid: Grid, w: WordDTO): Pos | null {
  for (const p of wordCells(w)) {
    if (!grid[p.row][p.col]) return p;
  }
  return null;
}

export function isSolved(grid: Grid, puzzle: Puzzle): boolean {
  for (let r = 0; r < puzzle.height; r++) {
    for (let c = 0; c < puzzle.width; c++) {
      const info = puzzle.grid[r][c];
      if (!info) continue;
      if (grid[r][c] !== info.solution) return false;
    }
  }
  return true;
}

export function cloneGrid(grid: Grid): Grid {
  return grid.map((row) => [...row]);
}
