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
// S5 — suspend_data: kompakt v2 kodlaması + eski (v1 JSON) format migrasyonu
// --------------------------------------------------------------------------- //
// SCORM 1.2 suspend_data sınırı 4096 karakterdir; v1 (düz JSON.stringify) 60+ ekranlı kurslarda
// taşar ve history sessizce düşerdi. v2 biçimi ekran KİMLİKLERİ yerine `order` İNDEKSLERİNİ
// kullanır (base36), visited'ı hex bitfield'a paketler, results/ix'i minimal tutar.
//
// v2 alan düzeni ("|" ayraçlı, ilk alan sürüm etiketi "2"):
//   2 | cursorIdx36 | reachedEnd("1"|"") | visitedHex | history(i36,",") |
//   results(i36:puan:max:bayrak ",") | ix(i36:n36 ",") | inext36 | orderFp | tailJSON
// tailJSON (yalnız gerekliyse): { a: vars, c: order-dışı cursorId, v: [order-dışı visited],
//   r: {order-dışı results}, x: {order-dışı ix}, o: {bilinmeyen üst alanlar} } — kayıpsızlık garantisi.
// tail SON alandır ve içindeki "|" karakterleri decode'da yeniden birleştirilir (split-limit hilesi).
//
// orderFp — SÜRÜM GÜVENLİĞİ: cursor/visited/results/ix POZİSYONEL indekstir (order dizisindeki
// sıra). Kurs paketi güncellenip ekran eklenir/silinir/YENİDEN SIRALANIRSA eski payload YENİ order'a
// karşı çözülür ve visited/results YANLIŞ ekrana atfedilir (sessiz veri bozulması — yanlış puan,
// yanlış devam noktası). orderFp bu riski kapatır: encode ANINDAKİ order'ın djb2 özeti + uzunluğu
// zarfa gömülür; decode'da GÜNCEL order'ın özetiyle eşleşmezse state TEMİZ BAŞLANGIÇ (null) döner —
// devam noktasını kaybetmek, puanı/sonucu bozmaktan HER ZAMAN daha güvenlidir. Ekleme-sadece (append-only)
// düzenlemeler de reddedilir (basitlik için bilinçli tercih — bkz. _fp yorum).
//
// GERİYE UYUM: decodeSuspend eski v1 formatını ("{" ile başlayan düz JSON) tanır ve olduğu gibi
// döndürür — yayındaki kurslarda resume, paket güncellemesinden sağ çıkar. v1 KİMLİK-anahtarlıdır
// (screenId → değer), pozisyonel değildir → reorder/insert'e karşı ZATEN bağışıktır; orderFp KONTROLÜ
// v1'E UYGULANMAZ.

export const SUSPEND_LIMIT_12 = 4096;     // SCORM 1.2 cmi.suspend_data (SPM, karakter)
export const SUSPEND_LIMIT_2004 = 64000;  // SCORM 2004 4th Ed. cmi.suspend_data (SPM)

export function suspendLimit(is2004) {
  return is2004 ? SUSPEND_LIMIT_2004 : SUSPEND_LIMIT_12;
}

function _b36(n) { return Math.max(0, Math.floor(Number(n) || 0)).toString(36); }
function _p36(s) { var n = parseInt(s, 36); return isNaN(n) ? 0 : n; }
function _numStr(x) { var n = Number(x); return isFinite(n) ? String(n) : "0"; }

// order parmak izi (djb2, 32-bit işaretsiz — saf/deterministik, Date/random YOK). order.join(",")
// üzerinden: reorder AYNI elemanları farklı sırada içerse bile hash değişir (join dizesi değişir);
// insert/delete uzunluğu değiştirir; append de uzunluk+dizeyi değiştirir (append-only'yi de reddetmek
// bilinçli basitlik tercihi — bkz. dosya başı S5 yorumu). "_" ayracı base36 hash/uzunlukta oluşmaz.
function _fp(order) {
  var s = (order || []).join(",");
  var h = 5381;
  for (var i = 0; i < s.length; i++) h = ((h * 33) + s.charCodeAt(i)) >>> 0;
  return h.toString(36) + "_" + (order || []).length.toString(36);
}

var _V2_KNOWN = { visited: 1, results: 1, history: 1, vars: 1, ix: 1, inext: 1, cursorId: 1, reachedEnd: 1 };

export function encodeSuspend(state, order) {
  state = state || {}; order = order || [];
  var idx = {}, i;
  for (i = 0; i < order.length; i++) idx[order[i]] = i;
  var extra = {};

  var cur = "";
  if (state.cursorId != null) {
    if (idx[state.cursorId] != null) cur = _b36(idx[state.cursorId]);
    else extra.c = state.cursorId;
  }

  // visited → hex bitfield: bit i = order[i] ziyaret edildi (4 bit / hex hane, LSB ilk ekran)
  var nib = [];
  Object.keys(state.visited || {}).forEach(function (id) {
    if (!state.visited[id]) return;
    var j = idx[id];
    if (j == null) { (extra.v = extra.v || []).push(id); return; }
    nib[j >> 2] = (nib[j >> 2] || 0) | (1 << (j & 3));
  });
  var vis = "";
  for (i = 0; i < nib.length; i++) vis += (nib[i] || 0).toString(16);

  var hist = [];
  (state.history || []).forEach(function (id) {
    if (idx[id] != null) hist.push(_b36(idx[id]));   // order-dışı geçmiş girdisi zaten gezilemez → düşer
  });

  var res = [];
  Object.keys(state.results || {}).forEach(function (id) {
    var r = state.results[id] || {};
    if (idx[id] == null) { (extra.r = extra.r || {})[id] = r; return; }
    var f = (r.ok ? 1 : 0) | (r.answered ? 2 : 0);
    res.push(_b36(idx[id]) + ":" + _numStr(r.points) + ":" + _numStr(r.max) + ":" + f);
  });

  var ixs = [];
  Object.keys(state.ix || {}).forEach(function (id) {
    if (idx[id] == null) { (extra.x = extra.x || {})[id] = state.ix[id]; return; }
    ixs.push(_b36(idx[id]) + ":" + _b36(state.ix[id]));
  });

  if (state.vars && Object.keys(state.vars).length) extra.a = state.vars;
  Object.keys(state).forEach(function (k) {           // gelecekteki alanlar sessizce KAYBOLMASIN
    if (!_V2_KNOWN[k]) (extra.o = extra.o || {})[k] = state[k];
  });

  var tail = Object.keys(extra).length ? JSON.stringify(extra) : "";
  return ["2", cur, state.reachedEnd ? "1" : "", vis, hist.join(","),
          res.join(","), ixs.join(","), _b36(state.inext || 0), _fp(order), tail].join("|");
}

function _decodeV2(s, order) {
  try {
    var parts = s.split("|");
    // orderFp (parts[8]) GÜNCEL order'ın özetiyle eşleşmeli; eşleşmezse (paket reorder/insert/delete
    // edilmiş VEYA bu sürüm-öncesi/bozuk bir zarf) pozisyonel indeksler YANLIŞ ekrana atfeder →
    // temiz başlangıç (null) döndür. Kayıp puandan/yanlış atıftan güvenli.
    if (parts[8] !== _fp(order)) return null;
    var tail = parts.slice(9).join("|");               // tail JSON "|" içerebilir → yeniden birleştir
    var extra = tail ? JSON.parse(tail) : {};
    var st = { visited: {}, results: {}, history: [] };

    if (parts[1]) st.cursorId = order[_p36(parts[1])];
    if (extra.c != null) st.cursorId = extra.c;
    if (parts[2] === "1") st.reachedEnd = true;

    var vis = parts[3] || "";
    for (var j = 0; j < vis.length; j++) {
      var nib = parseInt(vis.charAt(j), 16) || 0;
      for (var k = 0; k < 4; k++) {
        if (nib & (1 << k)) { var id = order[j * 4 + k]; if (id != null) st.visited[id] = true; }
      }
    }
    (extra.v || []).forEach(function (vid) { st.visited[vid] = true; });

    if (parts[4]) parts[4].split(",").forEach(function (t) {
      var hid = order[_p36(t)]; if (hid != null) st.history.push(hid);
    });

    if (parts[5]) parts[5].split(",").forEach(function (t) {
      var f = t.split(":");
      var rid = order[_p36(f[0])]; if (rid == null) return;
      var flags = parseInt(f[3], 10) || 0;
      st.results[rid] = { points: parseFloat(f[1]) || 0, max: parseFloat(f[2]) || 0,
                          ok: !!(flags & 1), answered: !!(flags & 2) };
    });
    if (extra.r) Object.keys(extra.r).forEach(function (rid) { st.results[rid] = extra.r[rid]; });

    if (parts[6] || extra.x) {
      st.ix = {};
      if (parts[6]) parts[6].split(",").forEach(function (t) {
        var f = t.split(":"); var xid = order[_p36(f[0])];
        if (xid != null) st.ix[xid] = _p36(f[1]);
      });
      if (extra.x) Object.keys(extra.x).forEach(function (xid) { st.ix[xid] = extra.x[xid]; });
    }
    if (parts[7] != null && parts[7] !== "") st.inext = _p36(parts[7]);
    if (extra.a) st.vars = extra.a;                    // vars boşsa YOK say → runtime varsayılanları kurar
    if (extra.o) Object.keys(extra.o).forEach(function (ok_) { st[ok_] = extra.o[ok_]; });
    return st;
  } catch (e) { return null; }
}

// raw → state | null. v2 ("2|" öneki) ve v1 (düz JSON {visited:...}) formatlarını tanır.
export function decodeSuspend(raw, order) {
  if (raw == null || raw === "") return null;
  var s = String(raw);
  if (s.slice(0, 2) === "2|") return _decodeV2(s, order || []);
  try {                                                // v1 migrasyonu: eski JSON'u olduğu gibi kabul et
    var d = JSON.parse(s);
    if (d && typeof d === "object" && d.visited) {
      d.history = d.history || [];
      return d;
    }
  } catch (e) {}
  return null;
}

// Sığdırarak kodla: limit aşılırsa önce history düşer (v1'deki davranışın kayıpsız hâli — vars ve
// ix v2'de KORUNUR; v1 fallback ikisini de atardı → tekrar cevaplanan sorular kopya interaction
// üretirdi). Hâlâ sığmıyorsa veri OLDUĞU GİBİ döner + truncated bayrağı (görünürlük katmanı uyarır).
export function encodeSuspendFit(state, order, limit) {
  var lim = Number(limit) > 0 ? Number(limit) : SUSPEND_LIMIT_12;
  var data = encodeSuspend(state, order);
  var dropped = false;
  if (data.length > lim && state && state.history && state.history.length) {
    var slim = {}; for (var k in state) slim[k] = state[k];
    slim.history = [];
    data = encodeSuspend(slim, order);
    dropped = true;
  }
  return { data: data, truncated: data.length > lim, historyDropped: dropped };
}

// SCORM API Set çağrısının dönüşü başarı mı? 1.2 LMSSetValue ve 2004 SetValue CMIBoolean
// ("true"/"false") döndürür; bazı sahte/eksik API'ler gerçek boolean ya da boş döndürür.
// YALNIZ açık "false" başarısızlıktır — boş/bilinmeyen dönüşte uyarı spam'i istemeyiz.
export function setResultOk(r) {
  return !(r === false || String(r) === "false");
}

// persist sonrası görünürlük kararı (saf): hangi durumlar uyarı üretmeli?
// { ok, size, limit, truncated } → [{kind, size, limit}, ...]. Runtime bunları console.warn +
// (varsa) xAPI olayına çevirir; ASLA throw edilmez.
export function suspendWriteIssues(opts) {
  var out = [];
  if (!opts) return out;
  var size = Number(opts.size) || 0, limit = Number(opts.limit) || 0;
  if (opts.truncated) out.push({ kind: "truncated", size: size, limit: limit });
  if (opts.ok === false) out.push({ kind: "write_failed", size: size, limit: limit });
  return out;
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

// --------------------------------------------------------------------------- //
// S2 — cmi.objectives.*
// --------------------------------------------------------------------------- //
// Hedef toplama SAF ve deterministiktir: çıktı sırası HER ZAMAN kurs hedef sırasıdır
// (objectiveIds), ekran/cevap sırasından bağımsız. POLİTİKA: yalnız en az bir puanlı ekrana
// bağlı hedefler kayıt üretir — bağsız hedef yazarlık hatasıdır (antislop `unbound_objective`
// WARN'ı yakalar), LMS'e boş kayıt yazılmaz.
//
// Referans farklar (S1 tablosuyla aynı ilke — sürüm farkı TEK yerde, burada):
//   skor    1.2 .score.raw/min/max (0-100)  | 2004 .score.scaled (0-1)
//   durum   1.2 .status (tek alan)          | 2004 .success_status + .completion_status

// results: state.results ({screenId: {points,max,ok,answered}}); screenMap: {screenId: [objId,…]}.
// → kurs sırasında [{id, correct, total, answered, scaled}] (correct/answered/total EKRAN sayısıdır;
// bir ekran birden çok hedefe bağlıysa her birinde sayılır).
export function aggregateObjectives(objectiveIds, screenMap, results) {
  objectiveIds = objectiveIds || []; screenMap = screenMap || {}; results = results || {};
  var per = {};
  Object.keys(screenMap).forEach(function (sid) {
    var r = results[sid];
    (screenMap[sid] || []).forEach(function (oid) {
      var a = per[oid] || (per[oid] = { correct: 0, total: 0, answered: 0 });
      a.total++;
      if (r && r.answered) { a.answered++; if (r.ok) a.correct++; }
    });
  });
  var out = [];
  for (var i = 0; i < objectiveIds.length; i++) {
    var oid = objectiveIds[i], a = per[oid];
    if (!a) continue;                                  // bağsız hedef → kayıt yok (politika)
    out.push({ id: oid, correct: a.correct, total: a.total, answered: a.answered,
               scaled: a.total > 0 ? a.correct / a.total : 0 });
  }
  return out;
}

// LMS'te ÖNCEDEN var olan objective kayıtlarıyla (2004'te manifest imsss:objective'lerinden
// pre-populate edilebilir) çarpışmadan deterministik indeks ata: mevcut id kendi indeksini
// AYNEN korur (2004'te .id değiştirilemez), yeni id'ler sona sırayla eklenir.
export function objectiveIndices(existingIds, ids) {
  existingIds = existingIds || []; ids = ids || [];
  var pos = {}, i;
  for (i = 0; i < existingIds.length; i++) {
    if (pos[existingIds[i]] == null) pos[existingIds[i]] = i;
  }
  var map = {}, next = existingIds.length;
  for (i = 0; i < ids.length; i++) {
    map[ids[i]] = pos[ids[i]] != null ? pos[ids[i]] : next++;
  }
  return map;
}

// Bir hedef toplamını sSet ile yazılacak [anahtar, değer] çiftlerine çevirir (interactionElements
// deseni). agg: aggregateObjectives çıktısı; n: cmi.objectives.n; passingRatio: kurs geçme notu
// 0-1 (hedef başına ayrı eşik yok — S6 primaryObjective/minNormalizedMeasure ile tutarlı);
// includeId=false → .id çifti atlanır (LMS'te aynı indekste id zaten kayıtlıysa 2004 yeniden
// yazımı reddedebilir).
export function objectiveElements(agg, n, is2004, passingRatio, includeId) {
  var base = "cmi.objectives." + n + ".";
  var out = [];
  if (includeId !== false) out.push([base + "id", sanitizeId(agg.id)]);   // id İLK (S1 kuralı)

  var attempted = agg.answered > 0;
  var done = agg.total > 0 && agg.answered >= agg.total;
  var passed = agg.scaled >= (Number(passingRatio) || 0);

  if (attempted) {
    if (is2004) {
      out.push([base + "score.scaled", (Math.round(agg.scaled * 10000) / 10000).toFixed(4)]);
    } else {
      out.push([base + "score.raw", String(Math.round(agg.scaled * 100))]);
      out.push([base + "score.min", "0"]);
      out.push([base + "score.max", "100"]);
    }
  }

  if (is2004) {
    out.push([base + "success_status", done ? (passed ? "passed" : "failed") : "unknown"]);
    out.push([base + "completion_status",
      done ? "completed" : (attempted ? "incomplete" : "not attempted")]);
  } else {
    out.push([base + "status",
      done ? (passed ? "passed" : "failed") : (attempted ? "incomplete" : "not attempted")]);
  }
  return out;
}
