import { describe, it, expect } from "vitest";
import { createItemBank } from "../../../components/engine/primitives/itembank.js";
import { createRng } from "../../../components/engine/rng.js";

describe("itembank primitifi (parametrik + seed-deterministik)", () => {
  it("aynı seed → aynı materyalize madde (denk zorluk, üretilebilir)", () => {
    const items = [{
      id: "add1", template: "{{a}} + {{b}} = ?",
      vars: { a: { min: 2, max: 9 }, b: { min: 2, max: 9 } },
      answer: { op: "add", operands: ["a", "b"] },
      distractors: { offsets: [-2, -1, 1, 2] },
    }];
    const a = createItemBank({ items }, createRng("seed-1")).draw(1)[0];
    const b = createItemBank({ items }, createRng("seed-1")).draw(1)[0];
    expect(a).toEqual(b); // bit-denk
    // doğru cevap gerçekten a+b
    const m = a.prompt.match(/(\d+) \+ (\d+)/);
    expect(Number(a.correct)).toBe(Number(m[1]) + Number(m[2]));
    expect(a.options).toContain(a.correct);
    expect(a.options.length).toBeGreaterThanOrEqual(3);
  });

  it("farklı seed → farklı değerler (parametrik çeşitlilik)", () => {
    const items = [{
      id: "x", template: "{{a}}", vars: { a: { min: 1, max: 1000 } },
      answer: { op: "add", operands: ["a"] },
    }];
    const a = createItemBank({ items }, createRng("A")).draw(1)[0];
    const b = createItemBank({ items }, createRng("B")).draw(1)[0];
    expect(a.prompt).not.toBe(b.prompt); // büyük aralıkta farklı
  });

  it("statik madde + get(id)", () => {
    const items = [{ id: "cap", prompt: "Türkiye başkenti?", answer: "Ankara", distractors: ["İstanbul", "İzmir"] }];
    const bank = createItemBank({ items }, createRng("s"));
    const it = bank.get("cap");
    expect(it.correct).toBe("Ankara");
    expect(it.options.sort()).toEqual(["Ankara", "İstanbul", "İzmir"].sort());
    expect(bank.get("yok")).toBe(null);
  });

  it("mul/sub op + draw n sınırı", () => {
    const items = [
      { id: "m", template: "{{a}}×{{b}}", vars: { a: { min: 3, max: 3 }, b: { min: 4, max: 4 } }, answer: { op: "mul", operands: ["a", "b"] } },
    ];
    const drawn = createItemBank({ items }, createRng("m")).draw(5); // sadece 1 var
    expect(drawn.length).toBe(1);
    expect(drawn[0].correct).toBe("12");
  });

  it("rng yoksa hata", () => {
    expect(() => createItemBank({ items: [] })).toThrow();
  });
});
