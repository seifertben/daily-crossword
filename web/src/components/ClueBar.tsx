import { dirLabel } from "./Grid";
import type { WordDTO } from "../types";

interface ClueBarProps {
  word: WordDTO | null;
}

export function ClueBar({ word }: ClueBarProps) {
  if (!word) return <div className="clue-bar empty" aria-live="polite" />;
  return (
    <div className="clue-bar" aria-live="polite">
      <span className="clue-bar-num">
        {word.number}
        <span className="clue-bar-dir">{word.direction === "across" ? "A" : "D"}</span>
      </span>
      <span className="clue-bar-text">{word.clue}</span>
    </div>
  );
}

export { dirLabel };
