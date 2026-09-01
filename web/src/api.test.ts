import { describe, expect, it } from "vitest";
import { todayEastern } from "./api";

// Build a Date for a given America/New_York wall-clock time in Sept 2026
// (EDT = UTC-4). Returns epoch ms.
function et(y: number, m: number, d: number, hours: number, minutes = 0): number {
  return Date.UTC(y, m - 1, d, hours + 4, minutes);
}

describe("todayEastern (6 AM ET rollover)", () => {
  it("returns the new day from 6:00 AM onward", () => {
    expect(todayEastern(et(2026, 9, 2, 6))).toBe("2026-09-02");
    expect(todayEastern(et(2026, 9, 2, 17))).toBe("2026-09-02");
  });

  it("still shows the previous day before 6:00 AM", () => {
    expect(todayEastern(et(2026, 9, 2, 0))).toBe("2026-09-01");
    expect(todayEastern(et(2026, 9, 2, 4))).toBe("2026-09-01");
    expect(todayEastern(et(2026, 9, 2, 5))).toBe("2026-09-01");
  });

  it("rolls over exactly at 6:00 AM", () => {
    expect(todayEastern(et(2026, 9, 2, 5, 59))).toBe("2026-09-01");
  });
});