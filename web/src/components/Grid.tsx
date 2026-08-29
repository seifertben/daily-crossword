import { memo } from "react";
import type { CrosswordState } from "../hooks/useCrossword";
import { wordCells } from "../crossword";
import { useViewportWidth } from "../hooks/useMedia";
import type { Direction, Pos, Puzzle, WordDTO } from "../types";

interface GridProps {
  puzzle: Puzzle;
  state: CrosswordState;
  currentWord: WordDTO | null;
  onCellClick: (p: Pos) => void;
}

function buildSelectedSet(currentWord: WordDTO | null): Set<string> {
  if (!currentWord) return new Set();
  return new Set(wordCells(currentWord).map((p) => `${p.row}-${p.col}`));
}

export const Grid = memo(function Grid({ puzzle, state, currentWord, onCellClick }: GridProps) {
  const selected = buildSelectedSet(currentWord);
  const viewport = useViewportWidth();
  const available = Math.min(560, viewport - 32);
  const px = Math.max(18, Math.min(44, Math.floor(available / puzzle.width)));
  const style = { "--cell": `${px}px`, gridTemplateColumns: `repeat(${puzzle.width}, var(--cell))` } as React.CSSProperties;

  return (
    <div className="grid" style={style} role="grid" aria-label="Crossword grid">
      {puzzle.grid.map((row, r) =>
        row.map((info, c) => {
          if (!info) return <div key={`${r}-${c}`} className="cell block" role="presentation" />;
          const key = `${r}-${c}`;
          const isCurrent = state.cursor.row === r && state.cursor.col === c;
          const isSelected = selected.has(key);
          const isWrong = state.wrong.has(key);
          const letter = state.grid[r][c];
          const classes = ["cell"];
          if (isCurrent) classes.push("current");
          else if (isSelected) classes.push("selected");
          if (isWrong) classes.push("wrong");
          return (
            <button
              key={key}
              className={classes.join(" ")}
              onClick={() => onCellClick({ row: r, col: c })}
              role="gridcell"
              aria-label={`row ${r + 1} column ${c + 1}`}
            >
              {info.number != null && <span className="num">{info.number}</span>}
              <span className="letter">{letter ?? ""}</span>
            </button>
          );
        }),
      )}
    </div>
  );
});

export function dirLabel(d: Direction): string {
  return d === "across" ? "Across" : "Down";
}
