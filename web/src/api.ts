import type { Puzzle } from "./types";

// Two serving modes, chosen at build time:
//   "api"    (default) — the FastAPI app serves the SPA and reads puzzle blobs
//   "static"           — puzzles are static files shipped next to the SPA
const STATIC = import.meta.env.VITE_PUZZLE_MODE === "static";
const PUZZLE_DIR = `${import.meta.env.BASE_URL}puzzles`;

// A new puzzle is published each Eastern Time day, so "today" is computed in
// America/New_York regardless of the viewer's own timezone.
function todayEastern(): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const byType = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${byType("year")}-${byType("month")}-${byType("day")}`;
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
  if (STATIC) return fetchPuzzle(todayEastern());
  return fetchJson("/api/puzzle");
}
