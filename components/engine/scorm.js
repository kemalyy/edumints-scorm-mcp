// components/engine/scorm.js — SCORM runtime veri sözleşmesi: interactions (S1), seat time (S3),
// exit/entry (S4). Saf-mantık, DOM'suz, AĞSIZ, deterministik (zaman DIŞARIDAN enjekte → vitest'te sabit).
//
// DRİFT RİSKİ: 1.2 ile 2004 arasındaki eleman adı / sözlük / ayraç farkları TEK yerde burada tutulur;
// templates.py ENGINE_JS bu mantığı KOPYALAMAZ, window.SCORMRT üzerinden çağırır.
//
// Referans farklar (bilerek ayrı tutuldu):
//   sonuç       1.2 "wrong"            | 2004 "incorrect"
//   cevap alanı 1.2 student_response   | 2004 learner_response
//   zaman       1.2 .time (CMITime, günün saati) | 2004 .timestamp (ISO 8601 tarih-saat)
//   süre        1.2 CMITimespan HHHH:MM:SS.SS    | 2004 ISO 8601 PT#H#M#S
//   doğru/yanlış 1.2 "1"/"0"           | 2004 "true"/"false"
//   çoklu ayraç 1.2 "a,b" / "a.b"      | 2004 "a[,]b" / "a[.]b"

// --------------------------------------------------------------------------- //
// Süre / zaman biçimleme (S3 + interactions.latency)
// --------------------------------------------------------------------------- //

function _pad(n, w) {
  var s = String(Math.floor(Math.abs(n)));
  while (s.length < w) s = "0" + s;
  return s;
}

// SCORM 1.2 CMITimespan: HHHH:MM:SS.SS (saat 2-4 hane; 4'e sabitliyoruz — ADL örnekleriyle birebir).
export function duration12(ms) {
  var t = Math.max(0, Math.floor(Number(ms) || 0));
  var cs = Math.floor(t / 10) % 100;          // yüzde-saniye
  var sec = Math.floor(t / 1000) % 60;
  var min = Math.floor(t / 60000) % 60;
  var hr = Math.min(9999, Math.floor(t / 3600000));
  return _pad(hr, 4) + ":" + _pad(min, 2) + ":" + _pad(sec, 2) + "." + _pad(cs, 2);
}

// SCORM 2004 ISO 8601 süresi: PT#H#M#S (sıfır bileşenler düşer; tamamen sıfırsa PT0S).
export function duration2004(ms) {
  var t = Math.max(0, Math.floor(Number(ms) || 0));
  var hr = Math.floor(t / 3600000);
  var min = Math.floor(t / 60000) % 60;
  var sec = (Math.floor(t / 10) % 6000) / 100;   // saniye + yüzde-saniye
  var out = "PT";
  if (hr) out += hr + "H";
  if (min) out += min + "M";
  if (sec || out === "PT") out += sec + "S";
  return out;
}

export function sessionTime(ms, is2004) {
  return is2004 ? duration2004(ms) : duration12(ms);
}

// SCORM 1.2 CMITime: HH:MM:SS.SS — GÜNÜN SAATİ (tarih yok). date: Date | epoch ms.
export function timestamp12(date) {
  var d = date instanceof Date ? date : new Date(Number(date) || 0);
  return _pad(d.getUTCHours(), 2) + ":" + _pad(d.getUTCMinutes(), 2) + ":" +
    _pad(d.getUTCSeconds(), 2) + "." + _pad(Math.floor(d.getUTCMilliseconds() / 10), 2);
}

// SCORM 2004: ISO 8601 tarih-saat (UTC).
export function timestamp2004(date) {
  var d = date instanceof Date ? date : new Date(Number(date) || 0);
  return d.getUTCFullYear() + "-" + _pad(d.getUTCMonth() + 1, 2) + "-" + _pad(d.getUTCDate(), 2) +
    "T" + _pad(d.getUTCHours(), 2) + ":" + _pad(d.getUTCMinutes(), 2) + ":" +
    _pad(d.getUTCSeconds(), 2) + "Z";
}

// --------------------------------------------------------------------------- //
// S4 — exit / entry
// --------------------------------------------------------------------------- //

// Tamamlanmamış kurstan çıkış "suspend" olmalı: 1.2'de BOŞ exit *normal* çıkış demektir ve LMS
// suspend_data'yı korumak zorunda değildir → "kaldığın yerden devam" sessizce bozulur.
export function exitValue(complete) {
  return complete ? "normal" : "suspend";
}

// entry: "" | "ab-initio" | "resume". Yalnız "ab-initio" kesin olarak SIFIRDAN başlat demektir.
// Boş/bilinmeyen değerde eski davranışı koru (suspend_data varsa geri yükle) — bazı LMS entry'yi
// hiç doldurmaz, katı "sadece resume" kuralı bu LMS'lerde devam etmeyi bozar.
export function shouldRestore(entry, hasSuspendData) {
  var e = String(entry == null ? "" : entry).trim().toLowerCase();
  if (e === "resume") return true;
  if (e === "ab-initio") return false;
  return !!hasSuspendData;
}

// --------------------------------------------------------------------------- //
// S1 — cmi.interactions.*
// --------------------------------------------------------------------------- //

// Ekran tipi → SCORM etkileşim tipi. 1.2 ve 2004 sözlükleri bu alt küme için aynı.
export const INTERACTION_TYPES = {
  mcq: "choice",
  true_false: "true-false",
  fill_blank: "fill-in",
  drag_drop: "matching",
  hotspot: "choice",
  matching: "matching",
  sorting: "sequencing",
  labeled_diagram: "matching",
  simulation: "performance",
  decision_scenario: "performance",
  term_match_race: "matching",
  escape_room: "performance",
  game: "performance",
  adaptive_practice: "choice",
};

export function interactionType(screenType) {
  return INTERACTION_TYPES[screenType] || "other";
}

// CMIIdentifier: boşluksuz, sınırlı alfabe, ≤255. Ekran id'leri genelde uygun; yine de temizle.
export function sanitizeId(id) {
  var s = String(id == null ? "" : id).replace(/[^A-Za-z0-9_.-]/g, "_");
  if (!s) s = "item";
  return s.slice(0, 255);
}

export function resultValue(ok, is2004) {
  if (ok === "neutral" || ok === "unanticipated") return ok;
  if (ok) return "correct";
  return is2004 ? "incorrect" : "wrong";
}

function _bool(v, is2004) {
  var t = v === true || v === "true" || v === "1" || v === 1;
  return is2004 ? (t ? "true" : "false") : (t ? "1" : "0");
}

// Çok değerli cevaplarda ayraçlar sürüme göre değişir.
function _sep(is2004) { return is2004 ? "[,]" : ","; }
function _pairSep(is2004) { return is2004 ? "[.]" : "."; }

// value → SCORM cevap deseni. Kabul edilen girdiler:
//   choice/sequencing : dizi | tek değer
//   matching          : {kaynak: hedef} nesnesi | [[kaynak,hedef],…] | dizi
//   true-false        : bool benzeri
//   fill-in           : string | dizi (çoklu boşluk → ayraçla birleştirilir)
//   performance/other : string
export function formatResponse(type, value, is2004) {
  if (value == null) return "";
  if (type === "true-false") return _bool(value, is2004);

  if (type === "matching") {
    var pairs = [];
    if (Array.isArray(value)) {
      value.forEach(function (p) {
        if (Array.isArray(p) && p.length >= 2) pairs.push([p[0], p[1]]);
      });
    } else if (typeof value === "object") {
      Object.keys(value).forEach(function (k) { pairs.push([k, value[k]]); });
    }
    return pairs
      .map(function (p) { return sanitizeId(p[0]) + _pairSep(is2004) + sanitizeId(p[1]); })
      .join(_sep(is2004));
  }

  if (type === "choice" || type === "sequencing") {
    var arr = Array.isArray(value) ? value : [value];
    return arr.map(sanitizeId).join(_sep(is2004));
  }

  // fill-in / performance / other — serbest metin
  var text = Array.isArray(value) ? value.join(_sep(is2004)) : String(value);
  return text.slice(0, is2004 ? 250 : 255);
}

// Bir etkileşim kaydını, sSet ile yazılacak [anahtar, değer] çiftlerine çevirir.
// rec: { id, screenType | type, response, correct, ok, latencyMs?, time?, description?, weighting? }
// n:   cmi.interactions.n indeksi
export function interactionElements(rec, n, is2004) {
  var t = rec.type || interactionType(rec.screenType);
  var base = "cmi.interactions." + n + ".";
  var out = [];

  out.push([base + "id", sanitizeId(rec.id)]);
  out.push([base + "type", t]);

  // Sıra önemli: 1.2'de bazı LMS'ler .id yazılmadan alt elemanları reddeder → id ilk.
  if (rec.correct != null) {
    var pattern = formatResponse(t, rec.correct, is2004);
    if (pattern !== "") out.push([base + "correct_responses.0.pattern", pattern]);
  }

  if (rec.weighting != null) out.push([base + "weighting", String(rec.weighting)]);

  var resp = formatResponse(t, rec.response, is2004);
  out.push([base + (is2004 ? "learner_response" : "student_response"), resp]);

  if (rec.ok != null) out.push([base + "result", resultValue(rec.ok, is2004)]);

  if (rec.latencyMs != null) {
    out.push([base + "latency", is2004 ? duration2004(rec.latencyMs) : duration12(rec.latencyMs)]);
  }

  if (rec.time != null) {
    out.push([base + (is2004 ? "timestamp" : "time"),
      is2004 ? timestamp2004(rec.time) : timestamp12(rec.time)]);
  }

  // 1.2'de .description YOKTUR — yalnız 2004'te yaz.
  if (is2004 && rec.description) {
    out.push([base + "description", String(rec.description).slice(0, 250)]);
  }

  return out;
}
