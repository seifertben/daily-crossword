import type { Puzzle } from "./types";

// Two serving modes, chosen at build time:
//   "api"    (default) — the FastAPI app serves the SPA and reads puzzle blobs
//   "static"           — puzzles are static files shipped next to the SPA
const STATIC = import.meta.env.VITE_PUZZLE_MODE === "static";
const PUZZLE_DIR = `${import.meta.env.BASE_URL}puzzles`;

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

async function fetchJson(url: string): Promise<Puzzle> {
  const res = await fetch(url);
  if (!res.ok) {
    if (STATIC) throw new Error(`Failed to load puzzle (${res.status})`);
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to load puzzle (${res.status})`);
  }
  return (await res.json()) as Puzzle;
}

export async function fetchPuzzle(date: string): Promise<Puzzle> {
  return fetchJson(STATIC ? `${PUZZLE_DIR}/${date}.json` : `/api/puzzle/${date}`);
}

export async function fetchToday(): Promise<Puzzle> {
  if (STATIC) return fetchPuzzle(todayUtc());
  return fetchJson("/api/puzzle");
}
