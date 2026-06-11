import { describe, it, expect, vi } from "vitest";
import { createHintLadder } from "../../../components/engine/primitives/hint.js";
import { createEventBus } from "../../../components/engine/eventbus.js";

describe("hint ladder primitifi (kademeli + maliyetli)", () => {
  it("reveal sırayla açar, maliyet biriktirir, olay yayar", () => {
    const bus = createEventBus();
    const revealed = vi.fn();
    bus.on("hint.revealed", revealed);
    const h = createHintLadder({ hints: [{ text: "Alan adına bak", cost: 5 }, { text: "URL'yi doğrula", cost: 10 }] }, bus);
    expect(h.reveal()).toEqual({ index: 0, text: "Alan adına bak", cost: 5 });
    expect(h.hasMore()).toBe(true);
    expect(h.reveal().index).toBe(1);
    expect(h.hasMore()).toBe(false);
    expect(h.reveal()).toBe(null); // tükendi
    expect(h.costSpent).toBe(15);
    expect(revealed).toHaveBeenCalledTimes(2);
  });

  it("string ipuçları (cost 0) + shown() resume", () => {
    const h = createHintLadder({ hints: ["ipucu A", "ipucu B"] });
    h.reveal();
    expect(h.shown()).toEqual([{ index: 0, text: "ipucu A", cost: 0 }]);
    expect(h.state().total).toBe(2);
  });

  it("reset", () => {
    const h = createHintLadder({ hints: ["x"] });
    h.reveal();
    h.reset();
    expect(h.state().revealed).toBe(0);
    expect(h.hasMore()).toBe(true);
  });
});
