import { useEffect, useMemo, useRef, useState } from "react";
import { Grid } from "./components/Grid";
import { ClueBar } from "./components/ClueBar";
import { ClueList } from "./components/ClueList";
import { Confetti } from "./components/Confetti";
import { Toolbar, formatTime } from "./components/Toolbar";
import { useCrossword } from "./hooks/useCrossword";
import { useTimer } from "./hooks/useTimer";
import { loadProgress, saveProgress } from "./hooks/useProgress";
import { useCoarsePointer, useIsMobile } from "./hooks/useMedia";
import { fetchPuzzle, fetchToday } from "./api";
import type { Direction, Puzzle } from "./types";

function todayStr(): string {
  return new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

export default function App() {
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [won, setWon] = useState(false);
  const [wonDismissed, setWonDismissed] = useState(false);
  const [celebrate, setCelebrate] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const isMobile = useIsMobile();
  const coarse = useCoarsePointer();
  const [mobileTab, setMobileTab] = useState<"grid" | "clues">("grid");
  const [clueDir, setClueDir] = useState<Direction>("across");

  const dateParam = useMemo(
    () => new URLSearchParams(window.location.search).get("date"),
    [],
  );

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const p = dateParam ? await fetchPuzzle(dateParam) : await fetchToday();
        if (!alive) return;
        setPuzzle(p);
        setError(null);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load puzzle");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [dateParam]);

  const initial = useMemo(() => {
    if (!puzzle) return null;
    const saved = loadProgress(puzzle.date, puzzle);
    if (!saved) return null;
    return { grid: saved.grid, dir: "across" as Direction };
  }, [puzzle]);

  const cw = useCrossword(puzzle, initial);
  const initialElapsed = useMemo(() => {
    if (!puzzle) return 0;
    return loadProgress(puzzle.date, puzzle)?.elapsed ?? 0;
  }, [puzzle]);
  const timer = useTimer(initialElapsed);

  const hasInput = useMemo(
    () => cw.state.grid.some((row) => row.some((c) => c !== null)),
    [cw.state.grid],
  );

  // start the timer on first input; stop when solved
  useEffect(() => {
    if (!puzzle || paused) return;
    if (cw.state.solved) {
      timer.pause();
      if (!wonDismissed) setWon(true);
      return;
    }
    if (hasInput && !timer.running) timer.start();
  }, [puzzle, paused, cw.state.solved, hasInput, timer, wonDismissed]);

  const wasSolvedRef = useRef(false);
  useEffect(() => {
    if (cw.state.solved && !wasSolvedRef.current) {
      wasSolvedRef.current = true;
      setCelebrate(true);
    } else if (!cw.state.solved) {
      wasSolvedRef.current = false;
    }
  }, [cw.state.solved]);

  // persist progress
  useEffect(() => {
    if (!puzzle) return;
    saveProgress(puzzle.date, {
      grid: cw.state.grid,
      elapsed: timer.elapsed,
      solved: cw.state.solved,
    });
  }, [puzzle, cw.state.grid, cw.state.solved, timer.elapsed]);

  // keep focus on the hidden input for keyboard capture
  useEffect(() => {
    if (puzzle && !paused && !coarse) inputRef.current?.focus({ preventScroll: true });
  }, [puzzle, paused, cw.state.cursor, coarse]);

  if (loading) return <div className="state-msg">Loading today’s crossword…</div>;
  if (error)
    return (
      <div className="state-msg">
        <p>{error}</p>
        <p className="hint">Run <code>make gen-stub</code> to generate a puzzle first.</p>
      </div>
    );
  if (!puzzle) return null;

  const onSelectClue = (number: number, direction: Direction) => {
    const list = direction === "across" ? puzzle.across : puzzle.down;
    const w = list.find((x) => x.number === number);
    if (w) {
      cw.selectWord(w);
      if (isMobile) setMobileTab("grid");
      inputRef.current?.focus({ preventScroll: true });
    }
  };

  const onInput = (e: React.FormEvent<HTMLInputElement>) => {
    const v = (e.target as HTMLInputElement).value;
    (e.target as HTMLInputElement).value = "";
    if (v && /[a-zA-Z]/.test(v.slice(-1))) cw.typeChar(v.slice(-1));
  };

  const resume = () => {
    setPaused(false);
    if (hasInput && !cw.state.solved) timer.start();
  };

  return (
    <div className="app">
      <header className="masthead">
        <h1>Daily Crossword</h1>
        <p className="date">{todayStr()}</p>
        {puzzle.theme && <p className="theme">{puzzle.theme.title}</p>}
      </header>

      <input
        ref={inputRef}
        className="hidden-input"
        type="text"
        autoComplete="off"
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
        aria-label="Crossword letter input"
        onKeyDown={cw.handleKey}
        onInput={onInput}
        onBlur={(e) => {
          if (!paused && !coarse) {
            const t = e.relatedTarget as HTMLElement | null;
            if (!t || !t.closest(".app")) window.setTimeout(() => inputRef.current?.focus(), 0);
          }
        }}
      />

      <Toolbar
        elapsed={timer.elapsed}
        running={timer.running}
        paused={paused}
        autocheck={cw.state.autocheck}
        onPause={() => {
          setPaused(true);
          timer.pause();
        }}
        onResume={resume}
        onCheck={cw.check}
        onReveal={cw.reveal}
        onClear={() => {
          cw.clear();
          timer.reset();
          setWon(false);
          setWonDismissed(false);
        }}
        onToggleAutocheck={cw.toggleAutocheck}
      />

      <ClueBar word={cw.currentWord} />

      {isMobile && (
        <nav className="view-tabs" aria-label="Puzzle view">
          <button
            className={`tab${mobileTab === "grid" ? " active" : ""}`}
            onClick={() => setMobileTab("grid")}
            aria-pressed={mobileTab === "grid"}
          >
            Grid
          </button>
          <button
            className={`tab${mobileTab === "clues" ? " active" : ""}`}
            onClick={() => setMobileTab("clues")}
            aria-pressed={mobileTab === "clues"}
          >
            Clues
          </button>
        </nav>
      )}

      <div className="play-area">
        {(!isMobile || mobileTab === "grid") && (
          <div className="grid-wrap">
            {!paused && (
              <Grid
                puzzle={puzzle}
                state={cw.state}
                currentWord={cw.currentWord}
                onCellClick={(p) => {
                  cw.clickCell(p);
                  inputRef.current?.focus({ preventScroll: true });
                }}
              />
            )}
            {paused && (
              <div className="pause-overlay">
                <button className="btn big" onClick={resume}>Resume</button>
              </div>
            )}
            <p className="hint small">
              {isMobile
                ? "Tap a cell to type · tap again to flip direction"
                : "Type to fill · arrows move · space flips direction · tab next clue"}
            </p>
          </div>
        )}

        {(!isMobile || mobileTab === "clues") && (
          <div className="clues">
            {isMobile && (
              <nav className="clue-tabs" aria-label="Clue direction">
                <button
                  className={`tab${clueDir === "across" ? " active" : ""}`}
                  onClick={() => setClueDir("across")}
                  aria-pressed={clueDir === "across"}
                >
                  Across
                </button>
                <button
                  className={`tab${clueDir === "down" ? " active" : ""}`}
                  onClick={() => setClueDir("down")}
                  aria-pressed={clueDir === "down"}
                >
                  Down
                </button>
              </nav>
            )}
            {isMobile ? (
              <ClueList puzzle={puzzle} direction={clueDir} state={cw.state} onSelect={onSelectClue} />
            ) : (
              <>
                <ClueList puzzle={puzzle} direction="across" state={cw.state} onSelect={onSelectClue} />
                <ClueList puzzle={puzzle} direction="down" state={cw.state} onSelect={onSelectClue} />
              </>
            )}
          </div>
        )}
      </div>

      {won && (
        <div className="win-overlay" role="dialog" aria-modal="true">
          <div className="win-card">
            <h2>Solved!</h2>
            <p>You finished in {formatTime(timer.elapsed)}.</p>
            <p className="muted">{puzzle.wordCount} words</p>
            <button className="btn" onClick={() => { setWon(false); setWonDismissed(true); }}>Close</button>
          </div>
        </div>
      )}

      <Confetti active={celebrate} onDone={() => setCelebrate(false)} />
    </div>
  );
}
