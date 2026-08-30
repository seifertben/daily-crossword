import { useCallback, useEffect, useRef, useState } from "react";

export interface TimerState {
  elapsed: number;
  running: boolean;
  start: () => void;
  pause: () => void;
  reset: () => void;
  setElapsed: (s: number) => void;
}

export function useTimer(initial = 0): TimerState {
  const [elapsed, setElapsed] = useState(initial);
  const [running, setRunning] = useState(false);
  // Live mirror of `elapsed` so stable callbacks never close over a stale value.
  const elapsedRef = useRef(initial);
  elapsedRef.current = elapsed;
  // Monotonic anchor (performance.now()) behind the current elapsed figure.
  const anchorRef = useRef(0);
  const runningRef = useRef(false);
  runningRef.current = running;
  const prevInitialRef = useRef(initial);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setElapsed(Math.max(0, Math.floor((performance.now() - anchorRef.current) / 1000)));
    }, 250);
    return () => window.clearInterval(id);
  }, [running]);

  // Adopt a saved elapsed once it becomes known after mount (e.g. the puzzle
  // loads async while we already rendered with initial 0).
  useEffect(() => {
    if (initial === prevInitialRef.current) return;
    prevInitialRef.current = initial;
    if (initial >= 0 && !runningRef.current) {
      elapsedRef.current = initial;
      setElapsed(initial);
    }
  }, [initial]);

  const start = useCallback(() => {
    anchorRef.current = performance.now() - elapsedRef.current * 1000;
    setRunning(true);
  }, []);

  const pause = useCallback(() => setRunning(false), []);

  const reset = useCallback(() => {
    elapsedRef.current = 0;
    setElapsed(0);
    setRunning(false);
  }, []);

  const setElapsedCb = useCallback((s: number) => {
    elapsedRef.current = s;
    anchorRef.current = performance.now() - s * 1000;
    setElapsed(s);
  }, []);

  return { elapsed, running, start, pause, reset, setElapsed: setElapsedCb };
}