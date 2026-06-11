import { describe, it, expect, vi } from "vitest";
import { createTimer } from "../../../components/engine/primitives/timer.js";
import { createEventBus } from "../../../components/engine/eventbus.js";

describe("timer primitifi (deterministik tick + a11y 2.2.1)", () => {
  it("down mode: tick ile expire + olay", () => {
    const bus = createEventBus();
    const expired = vi.fn();
    bus.on("timer.expired", expired);
    const t = createTimer({ duration_sec: 2 }, bus);
    expect(t.tick(1000).remaining_ms).toBe(1000);
    expect(t.tick(1000).expired).toBe(true);
    expect(expired).toHaveBeenCalledTimes(1);
    expect(t.tick(1000).expired).toBe(true); // expire sonrası no-op
  });

  it("a11y: extend süreyi uzatır (expire'ı geri alır)", () => {
    const t = createTimer({ duration_sec: 1 });
    t.tick(1000);
    expect(t.state().expired).toBe(true);
    t.extend(5);
    expect(t.state().expired).toBe(false);
    expect(t.state().remaining_ms).toBe(5000);
  });

  it("a11y: disable → süresiz (asla expire)", () => {
    const t = createTimer({ duration_sec: 1 });
    t.disable();
    expect(t.tick(5000).expired).toBe(false);
    expect(t.state().remaining_ms).toBe(Infinity);
  });

  it("pause/resume + reset", () => {
    const t = createTimer({ duration_sec: 10 });
    t.pause();
    expect(t.tick(1000).elapsed_ms).toBe(0); // duraklatılmış
    t.resume();
    t.tick(3000);
    expect(t.value).toBe(7); // ceil((10000-3000)/1000)
    t.reset();
    expect(t.state().elapsed_ms).toBe(0);
  });

  it("up mode value = geçen saniye", () => {
    const t = createTimer({ duration_sec: 0, mode: "up", auto_expire: false });
    t.tick(4200);
    expect(t.value).toBe(4);
  });
});
