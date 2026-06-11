import { describe, it, expect, vi } from "vitest";
import { createBranchGraph, evalCondition } from "../../../components/engine/primitives/branchgraph.js";
import { createEventBus } from "../../../components/engine/eventbus.js";

const nodes = [
  { id: "start", choices: [
    { id: "safe", to: "win", effects: [{ var: "score", op: "add", value: 10 }] },
    { id: "risky", to: "boss", condition: { var: "level", cmp: ">=", value: 2 } },
  ] },
  { id: "boss", choices: [{ id: "fight", to: "win" }] },
  { id: "win", choices: [] },
];

describe("branchgraph primitifi (koşullu navigasyon)", () => {
  it("choose hedefe gider + effects applyFn ile uygulanır + olaylar", () => {
    const bus = createEventBus();
    const entered = vi.fn();
    bus.on("node.entered", entered);
    const applied = [];
    const g = createBranchGraph({ nodes, start: "start" }, bus);
    g.choose("safe", {}, (e) => applied.push(e));
    expect(g.current()).toBe("win");
    expect(applied).toEqual([{ var: "score", op: "add", value: 10 }]);
    // dinleyici (payload, evt) alır → payload'ı kontrol et
    expect(entered.mock.calls[0][0]).toEqual({ node: "win", via: "safe" });
    expect(g.isTerminal()).toBe(true);
  });

  it("kilitli seçim (koşul geçmez) → null, navigasyon yok", () => {
    const g = createBranchGraph({ nodes, start: "start" });
    expect(g.choose("risky", { level: 1 })).toBe(null); // level<2 kilitli
    expect(g.current()).toBe("start");
    expect(g.choose("risky", { level: 3 }).id || g.current()).toBe("boss"); // koşul geçti
  });

  it("available koşulu geçen seçenekleri verir", () => {
    const g = createBranchGraph({ nodes, start: "start" });
    expect(g.available({ level: 1 }).map((c) => c.id)).toEqual(["safe"]);
    expect(g.available({ level: 5 }).map((c) => c.id)).toEqual(["safe", "risky"]);
  });

  it("history + state + restore (resume)", () => {
    const g = createBranchGraph({ nodes, start: "start" });
    g.choose("risky", { level: 9 });
    g.choose("fight");
    expect(g.history()).toEqual(["start", "boss", "win"]);
    const snap = g.state();
    const g2 = createBranchGraph({ nodes, start: "start" }).restore(snap);
    expect(g2.current()).toBe("win");
  });

  it("evalCondition operatörleri + geçersiz seçim id", () => {
    expect(evalCondition(null)).toBe(true);
    expect(evalCondition({ var: "x", cmp: "==", value: 3 }, { x: 3 })).toBe(true);
    expect(evalCondition({ var: "x", cmp: "<", value: 3 }, { x: 5 })).toBe(false);
    const g = createBranchGraph({ nodes, start: "start" });
    expect(g.choose("yok")).toBe(null); // var olmayan seçim
  });
});
