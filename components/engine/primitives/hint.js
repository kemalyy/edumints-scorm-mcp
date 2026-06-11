// components/engine/primitives/hint.js — W2 mekanik primitifi: kademeli ipucu merdiveni.
// Scaffolding: yanlış arttıkça kademeli destek; maliyet (puan/zaman) ile dengeli (bedava ipucu
// öğrenmeyi baltalar). a11y SÖZLEŞMESİ: ipuçları METİN (ekran-okuyucu erişilebilir), görsel-yalnız değil.
// Olaylar (bus): hint.revealed {index,cost,remaining}.

export function createHintLadder({ hints = [] } = {}, bus = null) {
  const ladder = hints.map((h) => (typeof h === "string" ? { text: h, cost: 0 } : { text: h.text, cost: Number(h.cost) || 0 }));
  let revealed = 0; // kaç ipucu açıldı

  const emit = (payload) => { if (bus) bus.emit("hint.revealed", payload); };
  const state = () => ({ revealed, total: ladder.length, cost_spent: ladder.slice(0, revealed).reduce((s, h) => s + h.cost, 0) });

  return {
    /** sıradaki ipucunu aç; hepsi açıldıysa null döner */
    reveal() {
      if (revealed >= ladder.length) return null;
      const h = ladder[revealed];
      revealed += 1;
      emit({ index: revealed - 1, text: h.text, cost: h.cost, remaining: ladder.length - revealed });
      return { index: revealed - 1, text: h.text, cost: h.cost };
    },
    /** açılmış ipuçları (resume için) */
    shown() { return ladder.slice(0, revealed).map((h, i) => ({ index: i, text: h.text, cost: h.cost })); },
    hasMore() { return revealed < ladder.length; },
    reset() { revealed = 0; return state(); },
    state,
    get costSpent() { return ladder.slice(0, revealed).reduce((s, h) => s + h.cost, 0); },
  };
}
