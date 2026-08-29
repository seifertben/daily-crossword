import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { useCrossword } from "./hooks/useCrossword";
import { Grid } from "./components/Grid";
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

describe("useCrossword initial highlight", () => {
  it("highlights a valid word even when the first open cell is down-only", async () => {
    let cw: ReturnType<typeof useCrossword> | null = null;
    function Harness() {
      cw = useCrossword(puzzle, null);
      return (
        <Grid
          puzzle={puzzle}
          state={cw!.state}
          currentWord={cw!.currentWord}
          onCellClick={() => {}}
        />
      );
    }
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => root.render(<Harness />));

    expect(cw!.currentWord).not.toBeNull();
    const cells = Array.from(host.querySelectorAll(".cell"));
    expect(cells.filter((c) => c.classList.contains("current")).length).toBe(1);
    expect(cells.filter((c) => c.classList.contains("selected")).length).toBeGreaterThan(0);

    await act(async () => cw!.clear());
    expect(cw!.currentWord).not.toBeNull();

    root.unmount();
  });
});
