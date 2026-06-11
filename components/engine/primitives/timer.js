// components/engine/primitives/timer.js — W2 mekanik primitifi: süre.
// Deterministik: gerçek setInterval DEĞİL — runtime tick(deltaMs) çağırır (test edilebilir, seed-bağımsız).
// a11y SÖZLEŞMESİ (WCAG 2.2.1 Timing Adjustable): süre extend()/disable()/pause() ile ayarlanabilir/
// kapatılabilir OLMALI; süreli mekanik bunsuz build edilemez (oyun anti-slop kuralı, W6).
//
// Olaylar (bus verilirse): timer.tick {remaining_ms,elapsed_ms}, timer.expired {}.

export function createTimer({ duration_sec, mode = "down", auto_expire = true } = {}, bus = null) {
  let total = Math.max(0, Number(duration_sec) || 0) * 1000;
  let elapsed = 0;
  let running = true;
  let expired = false;
  let disabled = false; // a11y: süre kapatıldı → asla expire olmaz

  const emit = (type, payload) => { if (bus) bus.emit(type, payload); };
  const state = () => {
    const remaining = Math.max(0, total - elapsed);
    return { elapsed_ms: elapsed, remaining_ms: disabled ? Infinity : remaining, running, expired, disabled };
  };

  return {
    /** runtime her kare/saniye bunu çağırır; saf-deterministik */
    tick(deltaMs) {
      if (!running || expired || disabled) return state();
      elapsed += Math.max(0, Number(deltaMs) || 0);
      emit("timer.tick", { remaining_ms: Math.max(0, total - elapsed), elapsed_ms: elapsed });
      if (auto_expire && total > 0 && elapsed >= total) {
        expired = true; running = false;
        emit("timer.expired", {});
      }
      return state();
    },
    pause() { running = false; return state(); },
    resume() { if (!expired && !disabled) running = true; return state(); },
    /** a11y (2.2.1): süreyi uzat (sn) */
    extend(sec) { total += Math.max(0, Number(sec) || 0) * 1000; if (elapsed < total) expired = false; return state(); },
    /** a11y (2.2.1): süreyi tamamen kapat → mekanik süresiz */
    disable() { disabled = true; running = false; return state(); },
    reset() { elapsed = 0; running = true; expired = false; return state(); },
    state,
    get value() { return mode === "up" ? Math.floor(elapsed / 1000) : Math.ceil(Math.max(0, total - elapsed) / 1000); },
  };
}
