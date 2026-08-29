import { useEffect, useRef } from "react";
import type { CrosswordState } from "../hooks/useCrossword";
import type { Direction, Puzzle } from "../types";

interface ClueListProps {
  puzzle: Puzzle;
  direction: Direction;
  state: CrosswordState;
  onSelect: (number: number, direction: Direction) => void;
}

export function ClueList({ puzzle, direction, state, onSelect }: ClueListProps) {
  const list = direction === "across" ? puzzle.across : puzzle.down;
  const activeRef = useRef<HTMLLIElement | null>(null);

  const activeNumber = activeClueNumber(puzzle, state);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeNumber, direction]);

  return (
    <section className="clue-list-section">
      <h2 className="clue-heading">{direction === "across" ? "Across" : "Down"}</h2>
      <ol className="clue-list">
        {list.map((w) => {
          const active = w.direction === state.dir && w.number === activeNumber;
          return (
            <li
              key={`${w.direction}-${w.number}`}
              ref={active ? activeRef : null}
              className={`clue-item${active ? " active" : ""}${w.themed ? " themed" : ""}`}
              onClick={() => onSelect(w.number, w.direction)}
            >
              <span className="clue-num">{w.number}</span>
              <span className="clue-text">
                {w.clue}
                {w.themed && <span className="themed-tag" aria-label="themed"> ★</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function activeClueNumber(puzzle: Puzzle, state: CrosswordState): number | null {
  const list = state.dir === "across" ? puzzle.across : puzzle.down;
  const w = list.find((x) => {
    if (state.dir === "across")
      return state.cursor.row === x.row && state.cursor.col >= x.col && state.cursor.col < x.col + x.length;
    return state.cursor.col === x.col && state.cursor.row >= x.row && state.cursor.row < x.row + x.length;
  });
  return w?.number ?? null;
}
