// components/engine/primitives/lives.js — W2 mekanik primitifi: can/deneme.
// Öz-belirleme: can = kalibre zorluk + net ilerleme; başarısızlık öğrenme fırsatı (ipucu merdiveniyle
// eşlenebilir), ceza-spam'i değil. Olaylar (bus): lives.changed {current,delta}, lives.depleted {}.

export function createLives({ start = 3, max = null } = {}, bus = null) {
  const cap = max == null ? Math.max(0, Number(start) || 0) : Math.max(0, Number(max) || 0);
  let current = Math.min(cap, Math.max(0, Number(start) || 0));

  const emit = (type, payload) => { if (bus) bus.emit(type, payload); };
  const state = () => ({ current, max: cap, depleted: current <= 0 });

  return {
    lose(n = 1) {
      const before = current;
      current = Math.max(0, current - (Math.max(0, Number(n) || 0)));
      if (current !== before) emit("lives.changed", { current, delta: current - before });
      if (current <= 0 && before > 0) emit("lives.depleted", {});
      return state();
    },
    gain(n = 1) {
      const before = current;
      current = Math.min(cap, current + (Math.max(0, Number(n) || 0)));
      if (current !== before) emit("lives.changed", { current, delta: current - before });
      return state();
    },
    reset() { current = Math.min(cap, Math.max(0, Number(start) || 0)); return state(); },
    state,
    get current() { return current; },
    get depleted() { return current <= 0; },
  };
}
