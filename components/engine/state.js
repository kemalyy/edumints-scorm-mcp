// components/engine/state.js — versiyonlu oyun durumu serileştirici + bütçe-bilinçli sıkıştırma.
// Hedef-bilinçli: SCORM 1.2 suspend_data SERT sınır 4096 karakter (kırmızı çizgi, CI'da test).
// 2004 ~64K, cmi5 state API ~sınırsız. Saf-mantık, bağımlılıksız ESM.

// SCORM 1.2 suspend_data karakter sınırı (CONTRACTS — kırmızı çizgi).
export const SCORM12_SUSPEND_MAX = 4096;

// UTF-8 byte uzunluğu (suspend_data byte/karakter bütçesi için).
export function byteLength(str) {
  return typeof TextEncoder !== "undefined"
    ? new TextEncoder().encode(str).length
    : Buffer.byteLength(str, "utf8");
}

export function fitsScorm12(str) {
  return byteLength(str) <= SCORM12_SUSPEND_MAX;
}

// Versiyonlu zarf: {v: şemaVersiyonu, d: durum}. Minified (whitespace yok).
export function encodeState(state, version = 1) {
  return JSON.stringify({ v: version, d: state });
}

// Çöz + ileri-göç (migration). migrations: { [fromVersion]: (data)=>newData }.
// Eski sürüm state'i en güncele taşır (geriye uyumluluk).
export function decodeState(str, migrations = {}) {
  const o = JSON.parse(str);
  let v = o.v;
  let d = o.d;
  while (migrations[v]) {
    d = migrations[v](d);
    v += 1;
  }
  return { version: v, state: d };
}

// Şema-bilinçli anahtar kısaltma (binary-pack lite): uzun anahtarları kısa kodlara çevir.
// alias: { uzunAnahtar: "kısa" }. Tekrarlanan anahtarlarda büyük tasarruf, LZ'siz.
export function packKeys(obj, alias) {
  if (Array.isArray(obj)) return obj.map((x) => packKeys(x, alias));
  if (obj && typeof obj === "object") {
    const out = {};
    for (const k of Object.keys(obj)) {
      out[alias[k] || k] = packKeys(obj[k], alias);
    }
    return out;
  }
  return obj;
}

export function unpackKeys(obj, alias) {
  const inv = {};
  for (const k of Object.keys(alias)) inv[alias[k]] = k;
  const walk = (o) => {
    if (Array.isArray(o)) return o.map(walk);
    if (o && typeof o === "object") {
      const out = {};
      for (const k of Object.keys(o)) out[inv[k] || k] = walk(o[k]);
      return out;
    }
    return o;
  };
  return walk(obj);
}

// Yüksek seviye: paketle + kodla; hedefe sığıyor mu raporla (runtime degrade kararı için).
// target: "scorm12" | "scorm2004" | "cmi5".
export function serializeForTarget(state, { version = 1, alias = {}, target = "scorm12" } = {}) {
  const packed = Object.keys(alias).length ? packKeys(state, alias) : state;
  const str = encodeState(packed, version);
  const bytes = byteLength(str);
  const limit = target === "scorm12" ? SCORM12_SUSPEND_MAX : target === "scorm2004" ? 64000 : Infinity;
  return { str, bytes, limit, fits: bytes <= limit };
}

export function deserialize(str, { alias = {}, migrations = {} } = {}) {
  const { version, state } = decodeState(str, migrations);
  const unpacked = Object.keys(alias).length ? unpackKeys(state, alias) : state;
  return { version, state: unpacked };
}
