import { describe, it, expect } from "vitest";
import { createRng, seedFromString } from "../../components/engine/rng.js";

describe("rng (mulberry32, deterministik)", () => {
  it("aynı seed → BİT-DENK dizi (golden determinizm)", () => {
    const a = createRng("phishing-2026");
    const b = createRng("phishing-2026");
    const seqA = Array.from({ length: 8 }, () => a.float());
    const seqB = Array.from({ length: 8 }, () => b.float());
    expect(seqA).toEqual(seqB);
  });

  it("farklı seed → farklı dizi", () => {
    const a = createRng("seed-A");
    const b = createRng("seed-B");
    expect(a.float()).not.toEqual(b.float());
  });

  it("float [0,1) aralığında", () => {
    const r = createRng(42);
    for (let i = 0; i < 100; i++) {
      const v = r.float();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("int [min,max) sınırları", () => {
    const r = createRng(7);
    for (let i = 0; i < 200; i++) {
      const v = r.int(3, 9);
      expect(v).toBeGreaterThanOrEqual(3);
      expect(v).toBeLessThan(9);
      expect(Number.isInteger(v)).toBe(true);
    }
  });

  it("shuffle orijinali bozmaz + aynı seed → aynı sıra", () => {
    const src = [1, 2, 3, 4, 5, 6, 7, 8];
    const a = createRng("shuf").shuffle(src);
    const b = createRng("shuf").shuffle(src);
    expect(src).toEqual([1, 2, 3, 4, 5, 6, 7, 8]); // mutasyon yok
    expect(a).toEqual(b); // deterministik
    expect(a.slice().sort()).toEqual(src.slice().sort()); // permütasyon
  });

  it("pick + chance deterministik", () => {
    const r1 = createRng("c");
    const r2 = createRng("c");
    expect(r1.pick(["x", "y", "z"])).toEqual(r2.pick(["x", "y", "z"]));
    expect(r1.chance(0.5)).toEqual(r2.chance(0.5));
  });

  it("seed=0 → güvenli fallback (çökmesiz, deterministik)", () => {
    const a = createRng(0);
    const b = createRng(0);
    expect(a.float()).toEqual(b.float());
    expect(a.seed).toBeGreaterThan(0);
  });

  it("seedFromString deterministik + 32-bit", () => {
    expect(seedFromString("abc")).toEqual(seedFromString("abc"));
    expect(seedFromString("abc")).toBeGreaterThanOrEqual(0);
    expect(seedFromString("abc")).toBeLessThanOrEqual(0xffffffff);
  });
});
