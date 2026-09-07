// components/engine/rng.js — deterministik, seed'li PRNG (mulberry32).
// W1 oyun çekirdeği: aynı seed → aynı dizi → golden-test edilebilir oynanış.
// Saf-mantık, DOM'suz, bağımlılıksız ESM. Runtime'da inline edilir, vitest'le test edilir.

// 32-bit string seed'i deterministik integer'a çevir (FNV-1a benzeri).
export function seedFromString(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < String(str).length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// mulberry32 — küçük, hızlı, iyi dağılımlı 32-bit PRNG.
// Bir RNG nesnesi döndürür.
//
// KURALIN KAPSAMI (#159 — eskiden koşulsuz "Math.random YASAK" yazıyordu, kapsam belirsizdi):
// Bu kural MOTOR BUNDLE'ını (components/engine/**) yönetir. Oradaki her rastgelelik buradan
// türer, çünkü bundle'ın işi ölçme: aynı seed → aynı dizi → golden-test edilebilir oynanış
// (GameScreen.seed / AdaptivePracticeScreen.seed; ikisi de boşken ekran id'sinden türer).
// Bundle'da `Math.random(` HİÇ geçmez ve tests/test_rng_rule.py bunu kapı olarak tutar.
//
// BELGELENMİŞ İKİ İSTİSNA — inline motorda (components/templates.py ENGINE_JS), ikisi de
// SUNUM karıştırması, ölçme değil:
//   1) term_match_race — <select> seçeneklerinin sırası
//   2) sorting         — maddelerin başlangıç sırası
// Neden buraya taşınmadılar (ölçüldü, tembellikten değil):
//   - `createRng` yalnız `window.SCORMGame` üzerinden erişilebilir ve bundle YALNIZ
//     game/adaptive_practice ekranı olan ya da xAPI açık kurslara inline edilir
//     (renderer._uses_engine_bundle). Sadece sorting/term_match_race içeren kurs bundle'ı
//     hiç yüklemez — bilinçli "zero-load" kararı.
//   - Taşımak ya mulberry32'yi ENGINE_JS'e İKİNCİ kez yazmayı (tam da bu dosyanın önlediği
//     tekrar) ya da o kurslara bundle'ı zorlamayı (zero-load'un iptali) gerektirirdi.
//   - Ayrıca bu iki ekranın `seed` alanı YOK: ekran id'sine tohumlamak sırayı her öğrencide
//     ve her denemede aynı yapardı — sunum çeşitliliği için istenen bu değil.
// Bu iki yüzeye tohum vermek istenirse önce `seed` alanı ve tohumun neye bağlanacağı
// (öğrenci? oturum? deneme?) karara bağlanmalı; o ayrı bir iştir.
export function createRng(seed) {
  let a = (typeof seed === "string" ? seedFromString(seed) : (seed >>> 0)) || 1;
  const next = () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296; // [0,1)
  };
  return {
    seed: a >>> 0,
    /** [0,1) float */
    float: next,
    /** [min,max) tamsayı */
    int(min, max) {
      return Math.floor(next() * (max - min)) + min;
    },
    /** dizi içinden bir öğe */
    pick(arr) {
      return arr[Math.floor(next() * arr.length)];
    },
    /** Fisher-Yates — yeni karıştırılmış kopya (orijinali bozmaz) */
    shuffle(arr) {
      const a2 = arr.slice();
      for (let i = a2.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        const tmp = a2[i];
        a2[i] = a2[j];
        a2[j] = tmp;
      }
      return a2;
    },
    /** olasılık p ile true */
    chance(p) {
      return next() < p;
    },
  };
}
