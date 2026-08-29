import { describe, expect, it } from "vitest";
import {
  allClues,
  createEmptyGrid,
  indexInWord,
  isSolved,
  isOpen,
  moveCursor,
  nextInWord,
  supportsBothDirections,
  wordAt,
  wordCells,
} from "./crossword";
import type { Puzzle } from "./types";

const puzzle: Puzzle = {
  date: "2026-01-01",
  width: 3,
  height: 3,
  grid: [
    [null, { solution: "A", number: 1 }, null],
    [{ solution: "D", number: 2 }, { solution: "E" }, { solution: "F" }],
    [null, { solution: "G" }, null],
  ],
  across: [
    { number: 2, clue: "row", answer: "DEF", direction: "across", row: 1, col: 0, length: 3, themed: false },
  ],
  down: [
    { number: 1, clue: "col", answer: "AEG", direction: "down", row: 0, col: 1, length: 3, themed: false },
  ],
  wordCount: 2,
};

describe("crossword helpers", () => {
  it("wordAt finds across and down", () => {
    expect(wordAt(puzzle, 1, 0, "across")?.answer).toBe("DEF");
    expect(wordAt(puzzle, 0, 1, "down")?.answer).toBe("AEG");
    expect(wordAt(puzzle, 0, 1, "across")).toBeNull();
  });

  it("wordCells and indexInWord", () => {
    const w = puzzle.down[0];
    expect(wordCells(w)).toEqual([{ row: 0, col: 1 }, { row: 1, col: 1 }, { row: 2, col: 1 }]);
    expect(indexInWord(w, 2, 1)).toBe(2);
  });

  it("supportsBothDirections only at intersections", () => {
    expect(supportsBothDirections(puzzle, 1, 1)).toBe(true);
    expect(supportsBothDirections(puzzle, 1, 0)).toBe(false); // only across
  });

  it("moveCursor skips blocks and stops at edges", () => {
    expect(moveCursor(puzzle, { row: 1, col: 0 }, 0, 1)).toEqual({ row: 1, col: 1 });
    expect(moveCursor(puzzle, { row: 1, col: 2 }, 0, 1)).toEqual({ row: 1, col: 2 }); // edge
  });

  it("nextInWord honours word bounds", () => {
    const w = puzzle.across[0];
    expect(nextInWord(w, 0, 1)).toEqual({ row: 1, col: 1 });
    expect(nextInWord(w, 2, 1)).toBeNull();
    expect(nextInWord(w, 0, -1)).toBeNull();
  });

  it("isSolved checks every white cell", () => {
    const g = createEmptyGrid(puzzle);
    expect(isSolved(g, puzzle)).toBe(false);
    g[0][1] = "A"; g[1][0] = "D"; g[1][1] = "E"; g[1][2] = "F"; g[2][1] = "G";
    expect(isSolved(g, puzzle)).toBe(true);
    g[1][1] = "X";
    expect(isSolved(g, puzzle)).toBe(false);
  });

  it("isOpen respects bounds and blocks", () => {
    expect(isOpen(puzzle, 0, 0)).toBe(false);
    expect(isOpen(puzzle, 1, 1)).toBe(true);
    expect(isOpen(puzzle, 5, 5)).toBe(false);
  });

  it("allClues returns across then down", () => {
    expect(allClues(puzzle).map((w) => w.answer)).toEqual(["DEF", "AEG"]);
  });
});
