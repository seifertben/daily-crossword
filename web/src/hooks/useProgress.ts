import { useCallback } from "react";
import type { Grid } from "../crossword";
import type { Puzzle } from "../types";

export interface Progress {
  grid: Grid;
  elapsed: number;
  solved: boolean;
}

export function loadProgress(date: string, puzzle: Puzzle): Progress | null {
  try {
    const raw = localStorage.getItem(key(date));
    if (!raw) return null;
    const p = JSON.parse(raw) as Progress;
    if (!Array.isArray(p.grid) || p.grid.length !== puzzle.height) return null;
    return p;
  } catch {
    return null;
  }
}

export function saveProgress(date: string, progress: Progress): void {
  try {
    localStorage.setItem(key(date), JSON.stringify(progress));
  } catch {
    /* storage full or unavailable */
  }
}

export function clearProgress(date: string): void {
  try {
    localStorage.removeItem(key(date));
  } catch {
    /* ignore */
  }
}

export function key(date: string): string {
  return `daily-crossword:${date}`;
}

export function useProgress(puzzle: Puzzle | null) {
  return useCallback(
    (grid: Grid, elapsed: number, solved: boolean) => {
      if (!puzzle) return;
      saveProgress(puzzle.date, { grid, elapsed, solved });
    },
    [puzzle],
  );
}
