import { describe, it, expect, vi } from "vitest";
import { createLives } from "../../../components/engine/primitives/lives.js";
import { createEventBus } from "../../../components/engine/eventbus.js";

describe("lives primitifi", () => {
  it("lose → depleted olayı bir kez", () => {
    const bus = createEventBus();
    const depleted = vi.fn();
    bus.on("lives.depleted", depleted);
    const l = createLives({ start: 2 }, bus);
    l.lose(); expect(l.current).toBe(1);
    l.lose(); expect(l.depleted).toBe(true);
    expect(depleted).toHaveBeenCalledTimes(1);
    l.lose(); // 0'da no extra depleted
    expect(depleted).toHaveBeenCalledTimes(1);
  });

  it("gain max ile sınırlı", () => {
    const l = createLives({ start: 1, max: 3 });
    l.gain(5);
    expect(l.current).toBe(3);
  });

  it("lose 0'ın altına inmez + reset", () => {
    const l = createLives({ start: 1 });
    l.lose(5);
    expect(l.current).toBe(0);
    l.reset();
    expect(l.current).toBe(1);
  });

  it("değişmeyen lose/gain olay yaymaz", () => {
    const bus = createEventBus();
    const changed = vi.fn();
    bus.on("lives.changed", changed);
    const l = createLives({ start: 0, max: 0 }, bus);
    l.gain(1); // cap 0 → değişmez
    l.lose(1); // zaten 0
    expect(changed).not.toHaveBeenCalled();
  });
});
