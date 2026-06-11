// components/engine/primitives/score.js — W2 mekanik primitifi: skor + streak + çarpan.
// Mekanik-bağımsız tek skor çekirdeği. İçsel-bütünleşme: çarpan/streak öğrenme davranışını ödüllendirir
// (örn. ardışık doğru → ustalık sinyali), dışsal süs değil.
//
// Olaylar (bus): score.changed {value,delta,streak,multiplier}.

export function createScore(
  { start = 0, streak_step = 3, max_multiplier = 3 } = {},
  bus = null,
) {
  let value = Number(start) || 0;
  let streak = 0;

  const multiplier = () =>
    Math.min(max_multiplier, 1 + Math.floor(streak / Math.max(1, streak_step)));
  const emit = (delta) =>
    bus && bus.emit("score.changed", { value, delta, streak, multiplier: multiplier() });
  const state = () => ({ value, streak, multiplier: multiplier() });

  return {
    /** doğru cevap → streak artar, puan çarpanla eklenir */
    correct(points = 10) {
      streak += 1;
      const delta = Math.round((Number(points) || 0) * multiplier());
      value += delta;
      emit(delta);
      return state();
    },
    /** yanlış → streak sıfırlanır (çarpan düşer) */
    wrong() {
      streak = 0;
      emit(0);
      return state();
    },
    /** doğrudan ekle/çıkar (streak'e dokunmaz) */
    add(n) { const d = Number(n) || 0; value += d; emit(d); return state(); },
    sub(n) { const d = Number(n) || 0; value -= d; emit(-d); return state(); },
    reset() { value = Number(start) || 0; streak = 0; emit(0); return state(); },
    state,
    get value() { return value; },
    get streak() { return streak; },
  };
}
