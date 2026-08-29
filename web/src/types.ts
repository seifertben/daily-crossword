export type Direction = "across" | "down";

export interface CellInfo {
  solution: string;
  number?: number;
}

export interface WordDTO {
  number: number;
  clue: string;
  answer: string;
  direction: Direction;
  row: number;
  col: number;
  length: number;
  themed: boolean;
}

export interface ThemeDTO {
  title: string;
  voice: string;
}

export interface Puzzle {
  date: string;
  width: number;
  height: number;
  grid: (CellInfo | null)[][];
  across: WordDTO[];
  down: WordDTO[];
  wordCount: number;
  theme?: ThemeDTO;
}

export interface Pos {
  row: number;
  col: number;
}
