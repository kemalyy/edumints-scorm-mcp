import { describe, it, expect, vi } from "vitest";
import { createScore } from "../../../components/engine/primitives/score.js";
import { createEventBus } from "../../../components/engine/eventbus.js";

describe("score primitifi (streak + çarpan)", () => {
  it("correct streak çarpanı yükseltir", () => {
    const s = createScore({ streak_step: 3, max_multiplier: 3 });
    s.correct(10); // streak 1, x1 → 10
    s.correct(10); // streak 2, x1 → 20
    s.correct(10); // streak 3, x2 → 40
    expect(s.value).toBe(40);
    expect(s.streak).toBe(3);
  });

  it("wrong streak'i sıfırlar (çarpan düşer)", () => {
    const s = createScore({ streak_step: 2 });
    s.correct(10); s.correct(10); // streak 2 → x2
    s.wrong();
    expect(s.streak).toBe(0);
    s.correct(10); // x1 → +10
    expect(s.streak).toBe(1);
  });

  it("çarpan max_multiplier ile sınırlı", () => {
    const s = createScore({ streak_step: 1, max_multiplier: 2 });
    for (let i = 0; i < 10; i++) s.correct(0);
    expect(s.state().multiplier).toBe(2);
  });

  it("add/sub streak'e dokunmaz + olay", () => {
    const bus = createEventBus();
    const changed = vi.fn();
    bus.on("score.changed", changed);
    const s = createScore({ start: 5 }, bus);
    s.add(3); expect(s.value).toBe(8);
    s.sub(2); expect(s.value).toBe(6);
    expect(changed).toHaveBeenCalled();
    s.reset(); expect(s.value).toBe(5);
  });
});
