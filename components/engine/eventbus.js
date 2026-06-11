// components/engine/eventbus.js — saf olay veriyolu (Storyline trigger modelinin deklaratif eşi).
// Mekanikler olay yayar (answer.correct, timer.expired, node.entered…), kurallar dinler.
// Senkron, deterministik (dinleyici kayıt sırasına göre), bağımlılıksız ESM.

export function createEventBus() {
  const listeners = new Map(); // type -> [fn,...]
  const any = []; // tüm olayları dinleyenler (telemetri/stealth-assessment için)

  function on(type, fn) {
    if (!listeners.has(type)) listeners.set(type, []);
    listeners.get(type).push(fn);
    return () => off(type, fn); // unsubscribe
  }
  function off(type, fn) {
    const arr = listeners.get(type);
    if (!arr) return;
    const i = arr.indexOf(fn);
    if (i >= 0) arr.splice(i, 1);
  }
  function onAny(fn) {
    any.push(fn);
    return () => {
      const i = any.indexOf(fn);
      if (i >= 0) any.splice(i, 1);
    };
  }
  // Olayı senkron yayınla. payload değişmez kabul edilir. Dinleyiciler kayıt sırasında çalışır
  // (determinizm). Bir dinleyicinin hatası diğerlerini engellemez.
  function emit(type, payload) {
    const evt = { type, payload: payload === undefined ? null : payload, t: Date.now };
    const arr = listeners.get(type);
    if (arr) {
      for (const fn of arr.slice()) {
        try { fn(evt.payload, evt); } catch (e) { /* dinleyici izolasyonu */ }
      }
    }
    for (const fn of any.slice()) {
      try { fn(evt); } catch (e) { /* yut */ }
    }
    return evt;
  }
  function clear() {
    listeners.clear();
    any.length = 0;
  }
  return { on, off, onAny, emit, clear };
}
