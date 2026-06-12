// components/engine/adaptive.js — W4 adaptif katman: yeterlilik tahmini + akış/ZPD zorluk kalibrasyonu.
// Saf-mantık, DOM'suz, deterministik (vitest). İki tahminci ortak arayüz arkasında (Elo-vs-BKT — spec seçer);
// her ikisi de KÜÇÜK durum (SCORM 1.2 4096B bütçesi) ve SUNUCUDA LLM YOK — zekâ burada, spec'te.
//
// Ortak arayüz:  observe(...) → durumu günceller ;  pCorrect(difficulty?) → tahmini P(doğru) ;
//                state() → {strategy, ...} (serileştirilebilir) ;  reset().
// ECD bağlantısı: tahminci = yeterlilik modeli değişkeni (gizli ustalık); observe = kanıt kuralı.

const _sig = (x) => 1 / (1 + Math.exp(-x));
const _clamp01 = (x) => Math.min(1, Math.max(0, Number(x) || 0));

// --- Elo-lite (Rasch-benzeri 1-parametre lojistik) -----------------------------
// Tek float `ability` (logit ölçeği). Zorluk eşleştirmeye doğal yatkın (akış). Beceriden bağımsız
// öğeler için tek genel yetenek; çok-beceri için öğe-başına ayrı Elo örneği kullan.
export function createElo({ ability = 0, k = 0.24 } = {}) {
  let a = Number(ability) || 0;
  const expected = (difficulty) => _sig(a - (Number(difficulty) || 0)); // P(doğru | zorluk)
  return {
    strategy: "elo",
    /** bir gözlem: verilen zorlukta doğru/yanlış → yeteneği güncelle (döner: yeni ability) */
    observe(difficulty, correct) {
      const e = expected(difficulty);
      a += k * ((correct ? 1 : 0) - e);
      return a;
    },
    pCorrect(difficulty = 0) { return expected(difficulty); },
    expected,
    get ability() { return a; },
    state() { return { strategy: "elo", ability: a }; },
    reset(v = ability) { a = Number(v) || 0; },
  };
}

// --- BKT-lite (Bayesian Knowledge Tracing) -------------------------------------
// Tek float ustalık olasılığı P(L) + slip/guess/transit parametreleri. ECD yeterlilik modeline
// doğrudan eşlenir (P(ustalık)). Beceri-başına bir örnek (stealth assessment raporlaması için okunaklı).
export function createBkt({ p_init = 0.2, p_transit = 0.15, p_slip = 0.1, p_guess = 0.2 } = {}) {
  const slip = _clamp01(p_slip), guess = _clamp01(p_guess), transit = _clamp01(p_transit);
  let pL = _clamp01(p_init);
  return {
    strategy: "bkt",
    /** bir gözlem: doğru/yanlış → Bayes posterior + öğrenme geçişi (döner: yeni P(ustalık)) */
    observe(correct) {
      const pObsL = correct ? (1 - slip) : slip;              // P(gözlem | ustalık)
      const pObsNotL = correct ? guess : (1 - guess);         // P(gözlem | ustalık değil)
      const num = pL * pObsL;
      const post = num / (num + (1 - pL) * pObsNotL || 1e-9); // posterior P(L | gözlem)
      pL = post + (1 - post) * transit;                        // öğrenme: ustalığa geçiş
      return pL;
    },
    /** sıradaki denemede doğru olasılığı (slip/guess hesaba katılır) */
    pCorrect() { return pL * (1 - slip) + (1 - pL) * guess; },
    get mastery() { return pL; },
    state() { return { strategy: "bkt", mastery: pL }; },
    reset() { pL = _clamp01(p_init); },
  };
}

// Spec'ten tahminci kur (strategy ayrımı). Bilinmeyen strateji → Elo (güvenli varsayılan).
export function createEstimator(spec = {}) {
  return (spec.strategy === "bkt") ? createBkt(spec) : createElo(spec);
}

// --- Akış/ZPD seçici -----------------------------------------------------------
// Arzu edilen zorluk (Bjork): hedef başarı olasılığına EN YAKIN adayı seç (vars. 0.7 — ne çok kolay
// ne çok zor). predict(aday) → tahmini P(doğru). Eşitlikte seed'li rng ile tie-break (üretilebilir).
export function pickByTargetSuccess(predict, candidates, { target = 0.7 } = {}, rng = null) {
  let bestGap = Infinity, ties = [];
  for (const c of candidates || []) {
    const gap = Math.abs(predict(c) - target);
    if (gap < bestGap - 1e-9) { bestGap = gap; ties = [c]; }
    else if (Math.abs(gap - bestGap) <= 1e-9) ties.push(c);
  }
  if (ties.length <= 1) return ties.length ? ties[0] : null;
  return rng && rng.pick ? rng.pick(ties) : ties[0];
}
