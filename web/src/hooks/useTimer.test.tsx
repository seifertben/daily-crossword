import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTimer } from "./useTimer";

function Harness({ initial }: { initial: number }) {
  const t = useTimer(initial);
  (window as unknown as { __timer: ReturnType<typeof useTimer> }).__timer = t;
  return null;
}

describe("useTimer", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["performance", "setInterval", "clearInterval", "Date"] });
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function mount(initial: number) {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    const timer = () => (window as unknown as { __timer: ReturnType<typeof useTimer> }).__timer;
    act(() => root.render(<Harness initial={initial} />));
    return { root, timer };
  }

  it("counts up while running and freezes on pause", () => {
    const { root, timer } = mount(0);
    act(() => timer().start());
    act(() => vi.advanceTimersByTime(3050));
    expect(timer().elapsed).toBe(3);

    act(() => timer().pause());
    const frozen = timer().elapsed;
    act(() => vi.advanceTimersByTime(5000));
    expect(timer().elapsed).toBe(frozen);

    act(() => timer().start());
    act(() => vi.advanceTimersByTime(2050));
    expect(timer().elapsed).toBe(frozen + 2);

    root.unmount();
  });

  it("resets to zero", () => {
    const { root, timer } = mount(0);
    act(() => timer().start());
    act(() => vi.advanceTimersByTime(5050));
    expect(timer().elapsed).toBe(5);

    act(() => timer().reset());
    expect(timer().elapsed).toBe(0);
    act(() => vi.advanceTimersByTime(1000));
    expect(timer().elapsed).toBe(0);

    root.unmount();
  });

  it("adopts a saved elapsed passed after mount", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    let timer = (): ReturnType<typeof useTimer> =>
      (window as unknown as { __timer: ReturnType<typeof useTimer> }).__timer;

    act(() => root.render(<Harness initial={0} />));
    expect(timer().elapsed).toBe(0);

    // puzzle loads after mount with 125s of previously banked solve time
    act(() => root.render(<Harness initial={125} />));
    expect(timer().elapsed).toBe(125);

    // a resumed puzzle keeps counting from the restored value
    act(() => timer().start());
    act(() => vi.advanceTimersByTime(2050));
    expect(timer().elapsed).toBe(127);

    root.unmount();
  });
});