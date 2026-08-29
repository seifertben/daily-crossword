import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import {
  allClues,
  cloneGrid,
  createEmptyGrid,
  firstBlankInWord,
  firstOpenCell,
  indexInWord,
  isSolved,
  isOpen,
  moveCursor,
  nextInWord,
  supportsBothDirections,
  wordAt,
  type Grid,
} from "../crossword";
import type { Direction, Pos, Puzzle, WordDTO } from "../types";

export type Scope = "square" | "word" | "puzzle";

export interface CrosswordState {
  grid: Grid;
  cursor: Pos;
  dir: Direction;
  wrong: Set<string>; // "r-c" cells flagged incorrect by Check/Autocheck
  solved: boolean;
  autocheck: boolean;
}

type Action =
  | { type: "type"; ch: string }
  | { type: "backspace" }
  | { type: "toggleDir" }
  | { type: "move"; dr: number; dc: number; axis: Direction }
  | { type: "nextClue"; delta: number }
  | { type: "selectWord"; word: WordDTO }
  | { type: "clickCell"; pos: Pos }
  | { type: "check"; scope: Scope }
  | { type: "reveal"; scope: Scope }
  | { type: "clear" }
  | { type: "setAutocheck"; on: boolean }
  | { type: "load"; grid: Grid; cursor: Pos; dir: Direction };

function cellKey(p: Pos): string {
  return `${p.row}-${p.col}`;
}

function makeReducer(puzzle: Puzzle) {
  function reduce(state: CrosswordState, action: Action): CrosswordState {
    switch (action.type) {
      case "type": {
        const grid = cloneGrid(state.grid);
        grid[state.cursor.row][state.cursor.col] = action.ch;
        const wrong = new Set(state.wrong);
        wrong.delete(cellKey(state.cursor));
        const w = wordAt(puzzle, state.cursor.row, state.cursor.col, state.dir);
        let cursor = state.cursor;
        if (w) {
          const idx = indexInWord(w, state.cursor.row, state.cursor.col);
          const nxt = nextInWord(w, idx, 1);
          if (nxt) cursor = nxt;
        }
        let wrongSet = wrong;
        if (state.autocheck) {
          const sol = puzzle.grid[state.cursor.row][state.cursor.col]?.solution;
          if (sol && action.ch !== sol) wrongSet = new Set(wrong).add(cellKey(state.cursor));
          else wrongSet = new Set(wrong);
          wrongSet.delete(cellKey(state.cursor));
          if (sol && action.ch !== sol) wrongSet.add(cellKey(state.cursor));
        }
        return { ...state, grid, cursor, wrong: wrongSet, solved: isSolved(grid, puzzle) };
      }
      case "backspace": {
        const grid = cloneGrid(state.grid);
        const here = grid[state.cursor.row][state.cursor.col];
        let cursor = state.cursor;
        if (here) {
          grid[state.cursor.row][state.cursor.col] = null;
        } else {
          const w = wordAt(puzzle, state.cursor.row, state.cursor.col, state.dir);
          if (w) {
            const idx = indexInWord(w, state.cursor.row, state.cursor.col);
            const prev = nextInWord(w, idx, -1);
            if (prev) {
              cursor = prev;
              grid[prev.row][prev.col] = null;
            }
          }
        }
        const wrong = new Set(state.wrong);
        wrong.delete(cellKey(cursor));
        return { ...state, grid, cursor, wrong, solved: isSolved(grid, puzzle) };
      }
      case "toggleDir": {
        if (!supportsBothDirections(puzzle, state.cursor.row, state.cursor.col)) return state;
        return { ...state, dir: state.dir === "across" ? "down" : "across" };
      }
      case "move": {
        if (state.dir !== action.axis) return { ...state, dir: action.axis };
        return { ...state, cursor: moveCursor(puzzle, state.cursor, action.dr, action.dc) };
      }
      case "nextClue": {
        const clues = allClues(puzzle);
        const cur = wordAt(puzzle, state.cursor.row, state.cursor.col, state.dir);
        const idx = cur ? clues.findIndex((w) => w === cur) : -1;
        const next = clues[(idx + action.delta + clues.length) % clues.length];
        return selectWordState(state, next);
      }
      case "selectWord":
        return selectWordState(state, action.word);
      case "clickCell": {
        const { row, col } = action.pos;
        const same = state.cursor.row === row && state.cursor.col === col;
        let dir = state.dir;
        if (same && supportsBothDirections(puzzle, row, col)) {
          dir = dir === "across" ? "down" : "across";
        } else if (!same) {
          if (!wordAt(puzzle, row, col, dir)) {
            dir = dir === "across" ? "down" : "across";
          }
        }
        return { ...state, cursor: { row, col }, dir };
      }
      case "check": {
        const wrong = checkAction(state, puzzle, action.scope);
        return { ...state, wrong };
      }
      case "reveal": {
        const grid = cloneGrid(state.grid);
        const wrong = new Set(state.wrong);
        for (const p of scopeCells(puzzle, state, action.scope)) {
          grid[p.row][p.col] = puzzle.grid[p.row][p.col]!.solution;
          wrong.delete(cellKey(p));
        }
        return { ...state, grid, wrong, solved: isSolved(grid, puzzle) };
      }
      case "clear": {
        return {
          ...state,
          grid: createEmptyGrid(puzzle),
          wrong: new Set(),
          solved: false,
        };
      }
      case "setAutocheck":
        return { ...state, autocheck: action.on };
      case "load":
        return {
          ...state,
          grid: action.grid,
          cursor: action.cursor,
          dir: action.dir,
          wrong: new Set<string>(),
          solved: isSolved(action.grid, puzzle),
        };
      default:
        return state;
    }
  }
  return reduce;
}

function selectWordState(state: CrosswordState, w: WordDTO): CrosswordState {
  const blank = firstBlankInWord(state.grid, w);
  const cursor = blank ?? { row: w.row, col: w.col };
  return { ...state, cursor, dir: w.direction };
}

function scopeCells(puzzle: Puzzle, state: CrosswordState, scope: Scope): Pos[] {
  if (scope === "square") return [state.cursor];
  if (scope === "puzzle") {
    const out: Pos[] = [];
    for (let r = 0; r < puzzle.height; r++)
      for (let c = 0; c < puzzle.width; c++) if (isOpen(puzzle, r, c)) out.push({ row: r, col: c });
    return out;
  }
  const w = wordAt(puzzle, state.cursor.row, state.cursor.col, state.dir);
  return w ? cellsOf(w) : [state.cursor];
}

function cellsOf(w: WordDTO): Pos[] {
  const out: Pos[] = [];
  for (let i = 0; i < w.length; i++)
    out.push({ row: w.row + (w.direction === "down" ? i : 0), col: w.col + (w.direction === "across" ? i : 0) });
  return out;
}

function checkAction(state: CrosswordState, puzzle: Puzzle, scope: Scope): Set<string> {
  const wrong = new Set(state.wrong);
  for (const p of scopeCells(puzzle, state, scope)) {
    const sol = puzzle.grid[p.row][p.col]?.solution;
    const g = state.grid[p.row][p.col];
    if (g && sol && g !== sol) wrong.add(cellKey(p));
    else wrong.delete(cellKey(p));
  }
  return wrong;
}

export interface UseCrossword {
  state: CrosswordState;
  currentWord: WordDTO | null;
  handleKey: (e: ReactKeyboardEvent) => void;
  typeChar: (ch: string) => void;
  clickCell: (p: Pos) => void;
  selectWord: (w: WordDTO) => void;
  check: (scope: Scope) => void;
  reveal: (scope: Scope) => void;
  clear: () => void;
  toggleAutocheck: () => void;
}

function initialPos(p: Puzzle): { cursor: Pos; dir: Direction } {
  const cursor = firstOpenCell(p) ?? { row: 0, col: 0 };
  const dir = wordAt(p, cursor.row, cursor.col, "across") ? "across" : "down";
  return { cursor, dir };
}

const EMPTY_PUZZLE: Puzzle = {
  date: "",
  width: 10,
  height: 10,
  grid: Array.from({ length: 10 }, () =>
    Array.from({ length: 10 }, () => null),
  ) as Puzzle["grid"],
  across: [],
  down: [],
  wordCount: 0,
};

export function useCrossword(
  puzzle: Puzzle | null,
  initial?: { grid: Grid; dir: Direction } | null,
): UseCrossword {
  const p = puzzle ?? EMPTY_PUZZLE;
  const reducer = useMemo(() => makeReducer(p), [p]);
  const start = useMemo(() => initialPos(p), [p]);
  const [state, dispatch] = useReducer(reducer, {
    grid: initial?.grid ?? createEmptyGrid(p),
    cursor: start.cursor,
    dir: initial?.dir ?? start.dir,
    wrong: new Set<string>(),
    solved: initial ? isSolved(initial.grid, p) : false,
    autocheck: false,
  });

  const startedRef = useRef(false);

  const puzzleRef = useRef(p);
  useEffect(() => {
    if (puzzleRef.current === p) return;
    puzzleRef.current = p;
    dispatch({
      type: "load",
      grid: initial?.grid ?? createEmptyGrid(p),
      cursor: start.cursor,
      dir: initial?.dir ?? start.dir,
    });
  }, [p, initial, start]);

  const handleKey = useCallback((e: ReactKeyboardEvent) => {
    const k = e.key;
    if (/^[a-zA-Z]$/.test(k)) {
      e.preventDefault();
      startedRef.current = true;
      dispatch({ type: "type", ch: k.toUpperCase() });
    } else if (k === "Backspace") {
      e.preventDefault();
      dispatch({ type: "backspace" });
    } else if (k === " ") {
      e.preventDefault();
      dispatch({ type: "toggleDir" });
    } else if (k === "Tab" || k === "Enter") {
      e.preventDefault();
      dispatch({ type: "nextClue", delta: e.shiftKey ? -1 : 1 });
    } else {
      switch (k) {
        case "ArrowRight":
          e.preventDefault();
          dispatch({ type: "move", dr: 0, dc: 1, axis: "across" });
          break;
        case "ArrowLeft":
          e.preventDefault();
          dispatch({ type: "move", dr: 0, dc: -1, axis: "across" });
          break;
        case "ArrowDown":
          e.preventDefault();
          dispatch({ type: "move", dr: 1, dc: 0, axis: "down" });
          break;
        case "ArrowUp":
          e.preventDefault();
          dispatch({ type: "move", dr: -1, dc: 0, axis: "down" });
          break;
        default:
          break;
      }
    }
  }, []);

  const typeChar = useCallback((ch: string) => {
    startedRef.current = true;
    dispatch({ type: "type", ch: ch.toUpperCase() });
  }, []);

  const currentWord = wordAt(p, state.cursor.row, state.cursor.col, state.dir);

  return {
    state,
    currentWord,
    handleKey,
    typeChar,
    clickCell: (p) => dispatch({ type: "clickCell", pos: p }),
    selectWord: (w) => dispatch({ type: "selectWord", word: w }),
    check: (scope) => dispatch({ type: "check", scope }),
    reveal: (scope) => dispatch({ type: "reveal", scope }),
    clear: () => dispatch({ type: "clear" }),
    toggleAutocheck: () => dispatch({ type: "setAutocheck", on: !state.autocheck }),
  };
}
