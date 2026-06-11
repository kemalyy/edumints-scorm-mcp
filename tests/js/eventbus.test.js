import { describe, it, expect, vi } from "vitest";
import { createEventBus } from "../../components/engine/eventbus.js";

describe("eventbus (deklaratif trigger eşi)", () => {
  it("on/emit payload taşır", () => {
    const bus = createEventBus();
    const seen = [];
    bus.on("answer.correct", (p) => seen.push(p));
    bus.emit("answer.correct", { id: "q1", points: 10 });
    expect(seen).toEqual([{ id: "q1", points: 10 }]);
  });

  it("dinleyiciler kayıt SIRASINDA çalışır (determinizm)", () => {
    const bus = createEventBus();
    const order = [];
    bus.on("e", () => order.push("a"));
    bus.on("e", () => order.push("b"));
    bus.on("e", () => order.push("c"));
    bus.emit("e");
    expect(order).toEqual(["a", "b", "c"]);
  });

  it("off ile abonelik iptal", () => {
    const bus = createEventBus();
    const fn = vi.fn();
    const unsub = bus.on("e", fn);
    bus.emit("e");
    unsub();
    bus.emit("e");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("onAny tüm olayları görür (telemetri/stealth-assessment)", () => {
    const bus = createEventBus();
    const types = [];
    bus.onAny((evt) => types.push(evt.type));
    bus.emit("node.entered", { node: "n1" });
    bus.emit("timer.expired");
    expect(types).toEqual(["node.entered", "timer.expired"]);
  });

  it("bir dinleyici hatası diğerlerini engellemez (izolasyon)", () => {
    const bus = createEventBus();
    const ok = vi.fn();
    bus.on("e", () => { throw new Error("boom"); });
    bus.on("e", ok);
    expect(() => bus.emit("e")).not.toThrow();
    expect(ok).toHaveBeenCalledTimes(1);
  });

  it("off bilinmeyen tip/fn'de güvenli (no-op)", () => {
    const bus = createEventBus();
    expect(() => bus.off("yok", () => {})).not.toThrow();
    const fn = () => {};
    bus.on("e", fn);
    bus.off("e", () => {}); // kayıtlı olmayan fn
    expect(() => bus.emit("e")).not.toThrow();
  });

  it("payload undefined → null'a normalize", () => {
    const bus = createEventBus();
    let got;
    bus.on("e", (p) => { got = p; });
    bus.emit("e");
    expect(got).toBe(null);
  });

  it("clear tüm dinleyicileri temizler", () => {
    const bus = createEventBus();
    const fn = vi.fn();
    bus.on("e", fn);
    bus.onAny(fn);
    bus.clear();
    bus.emit("e");
    expect(fn).not.toHaveBeenCalled();
  });
});
