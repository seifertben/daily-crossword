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
  const baseRef = useRef(0); // monotonic anchor when running

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setElapsed(Math.floor((performance.now() - baseRef.current) / 1000));
    }, 250);
    return () => window.clearInterval(id);
  }, [running]);

  const start = useCallback(() => {
    setRunning(true);
    baseRef.current = performance.now() - elapsed * 1000;
  }, [elapsed]);

  const pause = useCallback(() => setRunning(false), []);
  const reset = useCallback(() => {
    setRunning(false);
    setElapsed(0);
    baseRef.current = performance.now();
  }, []);
  const setElapsedCb = useCallback((s: number) => {
    setElapsed(s);
    baseRef.current = performance.now() - s * 1000;
  }, []);

  return { elapsed, running, start, pause, reset, setElapsed: setElapsedCb };
}
