import { useEffect, useRef } from "react";

interface ConfettiProps {
  active: boolean;
  onDone?: () => void;
}

const COLORS = ["#f94144", "#f3722c", "#f9c74f", "#90be6d", "#43aa8b", "#577590", "#b388ff", "#f7d44a"];
const DURATION = 4200;
const COUNT = 160;

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  w: number;
  h: number;
  color: string;
  rot: number;
  vrot: number;
  ttl: number;
  decay: number;
}

function playJingle() {
  const AC: typeof AudioContext | undefined =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) return;
  const ctx = new AC();
  if (ctx.state === "suspended") void ctx.resume();
  const notes = [523.25, 659.25, 783.99, 1046.5];
  const start = ctx.currentTime + 0.06;
  notes.forEach((freq, i) => {
    const t = start + i * 0.12;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.2, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.5);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.55);
  });
  window.setTimeout(() => void ctx.close(), 2000);
}

function makeParticles(cx: number, cy: number): Particle[] {
  return Array.from({ length: COUNT }, () => {
    const angle = Math.random() * Math.PI * 2;
    const speed = 4 + Math.random() * 8;
    return {
      x: cx,
      y: cy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 7,
      w: 7 + Math.random() * 7,
      h: 4 + Math.random() * 5,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      rot: Math.random() * Math.PI,
      vrot: (Math.random() - 0.5) * 0.35,
      ttl: 1,
      decay: 0.006 + Math.random() * 0.008,
    };
  });
}

export function Confetti({ active, onDone }: ConfettiProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    playJingle();

    const particles = makeParticles(window.innerWidth / 2, window.innerHeight * 0.32);
    let raf = 0;
    const start = performance.now();

    const tick = (now: number) => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.clearRect(0, 0, w, h);
      let alive = false;
      for (const p of particles) {
        p.vy += 0.25;
        p.vx *= 0.99;
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vrot;
        p.ttl -= p.decay;
        if (p.ttl <= 0) continue;
        alive = true;
        ctx.save();
        ctx.globalAlpha = Math.max(0, p.ttl);
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      }
      if (alive && now - start < DURATION) {
        raf = requestAnimationFrame(tick);
      } else {
        ctx.clearRect(0, 0, w, h);
        onDoneRef.current?.();
      }
    };
    raf = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(raf);
  }, [active]);

  if (!active) return null;
  return <canvas ref={canvasRef} className="confetti" aria-hidden="true" />;
}