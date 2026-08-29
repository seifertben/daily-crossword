import { useState } from "react";
import type { Scope } from "../hooks/useCrossword";

interface ToolbarProps {
  elapsed: number;
  running: boolean;
  paused: boolean;
  autocheck: boolean;
  onPause: () => void;
  onResume: () => void;
  onCheck: (s: Scope) => void;
  onReveal: (s: Scope) => void;
  onClear: () => void;
  onToggleAutocheck: () => void;
}

export function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function Toolbar(props: ToolbarProps) {
  const { elapsed, running, paused, autocheck } = props;
  return (
    <div className="toolbar">
      <div className="timer">
        <span className="timer-display" aria-label="elapsed time">{formatTime(elapsed)}</span>
        {paused ? (
          <button className="btn" onClick={props.onResume}>Resume</button>
        ) : (
          <button className="btn" onClick={props.onPause} disabled={elapsed === 0 && !running}>
            Pause
          </button>
        )}
      </div>

      <div className="tool-group">
        <MenuButton label="Check" onPick={props.onCheck} />
        <MenuButton label="Reveal" onPick={props.onReveal} />
        <button
          className={`btn${autocheck ? " active" : ""}`}
          onClick={props.onToggleAutocheck}
          aria-pressed={autocheck}
        >
          Autocheck
        </button>
        <button className="btn" onClick={props.onClear}>Clear</button>
      </div>
    </div>
  );
}

function MenuButton({ label, onPick }: { label: string; onPick: (s: Scope) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="menu">
      <button className="btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {label} ▾
      </button>
      {open && (
        <>
          <div className="menu-backdrop" onClick={() => setOpen(false)} />
          <ul className="menu-list">
            {(["square", "word", "puzzle"] as Scope[]).map((s) => (
              <li
                key={s}
                onClick={() => {
                  onPick(s);
                  setOpen(false);
                }}
              >
                {s[0].toUpperCase() + s.slice(1)}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
