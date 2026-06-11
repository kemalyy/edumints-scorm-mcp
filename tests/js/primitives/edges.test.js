import { describe, it, expect } from "vitest";
import { createTimer } from "../../../components/engine/primitives/timer.js";
import { createScore } from "../../../components/engine/primitives/score.js";
import { createLives } from "../../../components/engine/primitives/lives.js";
import { createHintLadder } from "../../../components/engine/primitives/hint.js";
import { createItemBank } from "../../../components/engine/primitives/itembank.js";
import { createBranchGraph } from "../../../components/engine/primitives/branchgraph.js";
import { createRng } from "../../../components/engine/rng.js";

// no-bus + varsayılan argüman + sınır yolları (dal kapsamı için)
describe("primitif kenar-durumları (bus'sız + varsayılanlar)", () => {
  it("hepsi bus OLMADAN çalışır (emit no-op)", () => {
    expect(() => {
      createTimer({ duration_sec: 1 }).tick(500);
      const s = createScore({}); s.correct(); s.wrong();
      const l = createLives({}); l.lose(); l.gain();
      createHintLadder({ hints: ["x"] }).reveal();
    }).not.toThrow();
  });

  it("timer varsayılan args + geçersiz delta + extend reset etkisi", () => {
    const t = createTimer();          // duration_sec undefined → 0
    expect(t.tick(-5).elapsed_ms).toBe(0); // negatif delta → 0
    const t2 = createTimer({ duration_sec: 1 });
    t2.tick(1000); t2.extend(0);      // expire'da extend 0
    expect(t2.state().expired).toBe(true);
  });

  it("lives varsayılan (start 3, max=start)", () => {
    const l = createLives();
    expect(l.state().max).toBe(3);
    l.gain(10); expect(l.current).toBe(3); // cap = start
  });

  it("score reset olayı + bus", () => {
    const s = createScore({ start: 0 });
    s.reset(); expect(s.value).toBe(0);
  });

  it("branchgraph: boş graf + to'suz seçim + geçersiz restore", () => {
    const empty = createBranchGraph({ nodes: [], start: null });
    expect(empty.current()).toBe(null);
    expect(empty.choose("x")).toBe(null);   // node null
    expect(empty.available()).toEqual([]);
    expect(empty.isTerminal()).toBe(true);
    // to'suz seçim → aynı düğümde kalır ama olay yayar
    const g = createBranchGraph({ nodes: [{ id: "n", choices: [{ id: "stay" }] }], start: "n" });
    g.choose("stay");
    expect(g.current()).toBe("n");
    g.restore(null);                        // geçersiz restore → no-op
    g.restore({ current: "yok" });          // var olmayan düğüm → no-op
    expect(g.current()).toBe("n");
  });

  it("branchgraph: effects var ama applyFn yok → çökmez", () => {
    const g = createBranchGraph({ nodes: [
      { id: "a", choices: [{ id: "go", to: "b", effects: [{ var: "x", op: "add", value: 1 }] }] },
      { id: "b", choices: [] },
    ], start: "a" });
    expect(() => g.choose("go")).not.toThrow(); // applyFn null
    expect(g.current()).toBe("b");
  });

  it("itembank: distractors config'siz varsayılan offsetler + tek-operand", () => {
    const items = [{
      id: "q", template: "{{a}}", vars: { a: { min: 50, max: 50 } },
      answer: { op: "add", operands: ["a"] }, // tek operand → değer
    }];
    const it = createItemBank({ items }, createRng("s")).draw(1)[0];
    expect(it.correct).toBe("50");
    expect(it.options).toContain("50");
    expect(it.options.length).toBeGreaterThanOrEqual(3); // varsayılan offsetlerden çeldirici
  });

  it("lives/score: sayı-olmayan girdi güvenli (||0 fallback)", () => {
    const l = createLives({ start: "x", max: "y" }); // NaN → 0
    expect(l.state().max).toBe(0);
    l.lose("z"); l.gain(undefined); // 0 delta → no-op
    expect(l.current).toBe(0);
    const s = createScore({ start: "q" }); // NaN → 0
    s.sub("w"); s.add(null);
    expect(s.value).toBe(0);
  });

  it("itembank: statik madde distractors'sız", () => {
    const items = [{ id: "s", prompt: "X?", answer: "Y" }]; // distractors yok
    const it = createItemBank({ items }, createRng("s")).draw(1)[0];
    expect(it.correct).toBe("Y");
    expect(it.options).toEqual(["Y"]);
  });

  it("itembank: bilinmeyen op → add'e düşer", () => {
    const items = [{
      id: "u", template: "{{a}}+{{b}}", vars: { a: { min: 2, max: 2 }, b: { min: 3, max: 3 } },
      answer: { op: "WAT", operands: ["a", "b"] },
    }];
    const it = createItemBank({ items }, createRng("s")).draw(1)[0];
    expect(it.correct).toBe("5"); // fallback add
  });
});
