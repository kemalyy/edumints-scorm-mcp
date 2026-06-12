import { describe, it, expect } from "vitest";
import { createElo, createBkt, createEstimator, pickByTargetSuccess } from "../../components/engine/adaptive.js";
import { createRng } from "../../components/engine/rng.js";

describe("Elo-lite yetenek tahmincisi", () => {
  it("doğru → yetenek artar, yanlış → azalır", () => {
    const e = createElo({ ability: 0 });
    const after = e.observe(0, true);
    expect(after).toBeGreaterThan(0);
    const back = e.observe(0, false);
    expect(back).toBeLessThan(after);
  });

  it("expected (0,1) aralığında ve zorlukla azalır", () => {
    const e = createElo({ ability: 1 });
    expect(e.pCorrect(-2)).toBeGreaterThan(e.pCorrect(2));
    expect(e.pCorrect(0)).toBeGreaterThan(0);
    expect(e.pCorrect(0)).toBeLessThan(1);
  });

  it("deterministik: aynı dizi → bit-denk yetenek", () => {
    const seq = [[0, true], [1, false], [-1, true], [2, true]];
    const run = () => { const e = createElo({ ability: 0.5, k: 0.3 }); seq.forEach(([d, c]) => e.observe(d, c)); return e.ability; };
    expect(run()).toBe(run());
  });

  it("zorlukları sürekli doğru bilirse yetenek o zorluğun üstüne yakınsar", () => {
    const e = createElo({ ability: 0, k: 0.4 });
    for (let i = 0; i < 50; i++) e.observe(2, true);
    expect(e.ability).toBeGreaterThan(2); // ustalık zorluğun üstüne çıkar
  });

  it("state serileştirilebilir + reset", () => {
    const e = createElo({ ability: 1.5 });
    expect(e.state()).toEqual({ strategy: "elo", ability: 1.5 });
    e.observe(0, true); e.reset(); expect(e.ability).toBe(1.5);
  });
});

describe("BKT-lite ustalık tahmincisi", () => {
  it("doğru gözlemler ustalığı artırır, yanlış düşürür", () => {
    const b = createBkt({ p_init: 0.3 });
    const up = b.observe(true);
    expect(up).toBeGreaterThan(0.3);
    const down = b.observe(false);
    expect(down).toBeLessThan(up);
  });

  it("ardışık doğru → ustalık 1'e yakınsar, [0,1] sınırlı", () => {
    const b = createBkt({ p_init: 0.2 });
    for (let i = 0; i < 30; i++) b.observe(true);
    expect(b.mastery).toBeGreaterThan(0.95);
    expect(b.mastery).toBeLessThanOrEqual(1);
  });

  it("pCorrect slip/guess ile sınırlı (asla 0/1 değil)", () => {
    const b = createBkt({ p_init: 1, p_slip: 0.1, p_guess: 0.2 });
    expect(b.pCorrect()).toBeLessThanOrEqual(0.9); // tam ustalıkta bile slip
    const b0 = createBkt({ p_init: 0, p_slip: 0.1, p_guess: 0.2 });
    expect(b0.pCorrect()).toBeGreaterThanOrEqual(0.2); // sıfır ustalıkta bile guess
  });

  it("deterministik + state/reset", () => {
    const run = () => { const b = createBkt({ p_init: 0.4 }); [true, false, true].forEach((c) => b.observe(c)); return b.mastery; };
    expect(run()).toBe(run());
    const b = createBkt({ p_init: 0.4 }); b.observe(true); b.reset(); expect(b.mastery).toBeCloseTo(0.4);
    expect(b.state().strategy).toBe("bkt");
  });
});

describe("createEstimator (strateji yönlendirme)", () => {
  it("strategy=bkt → BKT, diğer/eksik → Elo", () => {
    expect(createEstimator({ strategy: "bkt" }).strategy).toBe("bkt");
    expect(createEstimator({ strategy: "elo" }).strategy).toBe("elo");
    expect(createEstimator({}).strategy).toBe("elo");
  });
});

describe("pickByTargetSuccess (akış/ZPD seçici)", () => {
  it("hedef başarıya EN YAKIN adayı seçer", () => {
    const items = [{ d: 0.2 }, { d: 0.7 }, { d: 0.95 }];
    const pick = pickByTargetSuccess((it) => it.d, items, { target: 0.7 });
    expect(pick.d).toBe(0.7);
  });

  it("eşitlikte seed'li rng ile üretilebilir tie-break", () => {
    const items = [{ id: "a", d: 0.6 }, { id: "b", d: 0.8 }]; // ikisi de 0.7'den 0.1 uzak
    const p1 = pickByTargetSuccess((it) => it.d, items, { target: 0.7 }, createRng(42));
    const p2 = pickByTargetSuccess((it) => it.d, items, { target: 0.7 }, createRng(42));
    expect(p1.id).toBe(p2.id); // aynı seed → aynı seçim
    expect(["a", "b"]).toContain(p1.id);
  });

  it("boş aday → null", () => {
    expect(pickByTargetSuccess(() => 0.5, [], {})).toBe(null);
  });

  it("Elo tahmincisiyle uçtan uca: yetenek arttıkça daha zor öğe seçilir", () => {
    const bank = [{ d: -1 }, { d: 0 }, { d: 1 }, { d: 2 }];
    const novice = createElo({ ability: -1 });
    const expert = createElo({ ability: 2 });
    const easyPick = pickByTargetSuccess((it) => novice.pCorrect(it.d), bank, { target: 0.7 });
    const hardPick = pickByTargetSuccess((it) => expert.pCorrect(it.d), bank, { target: 0.7 });
    expect(hardPick.d).toBeGreaterThan(easyPick.d);
  });
});
