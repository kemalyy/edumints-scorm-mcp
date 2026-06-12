import { describe, it, expect } from "vitest";
import { runRule, attachRules, evalCond, ACTIONS } from "../../components/engine/rules.js";
import { createEventBus } from "../../components/engine/eventbus.js";
import { createScore } from "../../components/engine/primitives/score.js";
import { createLives } from "../../components/engine/primitives/lives.js";

function ctxWith(extra = {}) {
  const bus = createEventBus();
  return { bus, vars: {}, mechanics: { score: createScore({}), lives: createLives({ start: 2 }), ...extra } };
}

describe("rule engine (when/if/then)", () => {
  it("runRule: koşul geçince aksiyonlar çalışır", () => {
    const ctx = ctxWith();
    const ok = runRule(
      { when: "choice.taken", if: { var: "lvl", cmp: ">=", value: 1 }, then: [{ do: "score.add", value: 50 }] },
      {}, { ...ctx, vars: { lvl: 3 } },
    );
    expect(ok).toBe(true);
    expect(ctx.mechanics.score.value).toBe(50);
  });

  it("runRule: koşul geçmezse çalışmaz", () => {
    const ctx = ctxWith();
    ctx.vars = { lvl: 0 };
    runRule({ when: "x", if: { var: "lvl", cmp: ">=", value: 2 }, then: [{ do: "score.add", value: 10 }] }, {}, ctx);
    expect(ctx.mechanics.score.value).toBe(0);
  });

  it("attachRules: olay yayılınca kural tetiklenir (when eşleşmesi)", () => {
    const ctx = ctxWith();
    attachRules([
      { when: "answer.correct", then: [{ do: "score.correct", points: 10 }] },
      { when: "answer.wrong", then: [{ do: "lives.lose", n: 1 }, { do: "score.wrong" }] },
    ], ctx);
    ctx.bus.emit("answer.correct");
    expect(ctx.mechanics.score.value).toBe(10);
    ctx.bus.emit("answer.wrong");
    expect(ctx.mechanics.lives.current).toBe(1);
    expect(ctx.mechanics.score.streak).toBe(0);
  });

  it("var.set / var.add + emit ile zincir", () => {
    const ctx = ctxWith();
    let chained = 0;
    ctx.bus.on("bonus", () => { chained++; });
    attachRules([
      { when: "start", then: [{ do: "var.set", var: "k", value: 0 }, { do: "var.add", var: "k", value: 5 }, { do: "emit", event: "bonus" }] },
    ], ctx);
    ctx.bus.emit("start");
    expect(ctx.vars.k).toBe(5);
    expect(chained).toBe(1);
  });

  it("bilinmeyen do güvenle yutulur + timer/hint mekaniği yoksa no-op", () => {
    const ctx = ctxWith({ score: null, lives: null });
    expect(() => runRule({ when: "x", then: [{ do: "WAT" }, { do: "score.correct", points: 5 }, { do: "timer.extend", sec: 5 }] }, {}, ctx)).not.toThrow();
  });

  it("detach abonelikleri kaldırır", () => {
    const ctx = ctxWith();
    const detach = attachRules([{ when: "e", then: [{ do: "score.add", value: 1 }] }], ctx);
    ctx.bus.emit("e");
    detach();
    ctx.bus.emit("e");
    expect(ctx.mechanics.score.value).toBe(1);
  });

  it("tüm aksiyonlar gerçek mekaniklerle çalışır", async () => {
    const { createTimer } = await import("../../components/engine/primitives/timer.js");
    const { createHintLadder } = await import("../../components/engine/primitives/hint.js");
    const bus = createEventBus();
    const ctx = {
      bus, vars: {},
      mechanics: {
        score: createScore({}), lives: createLives({ start: 1, max: 5 }),
        timer: createTimer({ duration_sec: 10 }), hints: createHintLadder({ hints: ["ipucu"] }),
      },
    };
    attachRules([
      { when: "e", then: [
        { do: "score.correct", points: 5 },
        { do: "lives.gain", n: 2 },
        { do: "timer.extend", sec: 5 },
        { do: "timer.disable" },
        { do: "hint.reveal" },
      ] },
    ], ctx);
    bus.emit("e");
    expect(ctx.mechanics.lives.current).toBe(3);
    expect(ctx.mechanics.timer.state().disabled).toBe(true);
    expect(ctx.mechanics.hints.state().revealed).toBe(1);
    expect(ctx.mechanics.score.value).toBe(5);
  });

  it("evalCond + ACTIONS doğrudan", () => {
    expect(evalCond(null)).toBe(true);
    expect(evalCond({ var: "a", cmp: "!=", value: 1 }, { a: 2 })).toBe(true);
    expect(typeof ACTIONS["score.correct"]).toBe("function");
  });

  it("attachRules bus yoksa hata", () => {
    expect(() => attachRules([], { vars: {}, mechanics: {} })).toThrow();
  });
});
