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
//   r: {order-dışı results}, x: {order-dışı ix}, p: xp (F2 exploration girdileri —
//   store_key anahtarlı, pozisyonel DEĞİL), o: {bilinmeyen üst alanlar} } — kayıpsızlık garantisi.
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

// Faz 4-ek — ÇALIŞMA BÜTÇESİ: sınırın tamamı kullanılmaz; kalan pay LMS tarafındaki
// kaçışlama/depolama ek yüküne REZERVE edilir (bazı LMS'ler suspend_data'yı SQL/XML
// kaçışlayarak saklar — 4096'ya dayanan payload orada taşar). TÜM ölçüm UTF-8 BAYTTIR,
// karakter değil (Türkçe ç/ğ/ı/ö/ş/ü 2 bayttır; .length ile ölçüm sessizce taşırırdı).
// Zarfın kendi alanları zaten ASCII'dir (kısa anahtar, id, base36/int) — Türkçe yalnız
// tail JSON'daki yazar değişkeni / öğrenen serbest metninde görülebilir.
export const SUSPEND_BUDGET_12 = 3500;    // 1.2 çalışma bütçesi (bayt); 4096-3500 rezerv

export function suspendBudget(is2004) {
  // 2004'te aynı rezerv ORANI uygulanır (kaçışlama ek yükü içerikle orantılıdır).
  return is2004
    ? Math.floor(SUSPEND_LIMIT_2004 * SUSPEND_BUDGET_12 / SUSPEND_LIMIT_12)
    : SUSPEND_BUDGET_12;
}

// UTF-8 bayt uzunluğu — saf, TextEncoder'sız (eski WebView'larda da deterministik).
// Surrogate çifti 4 bayt sayılır; eşleşmemiş surrogate U+FFFD gibi 3 bayt kabul edilir.
export function byteLen(s) {
  s = String(s == null ? "" : s);
  var n = 0;
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    if (c < 0x80) n += 1;
    else if (c < 0x800) n += 2;
    else if (c >= 0xd800 && c <= 0xdbff && i + 1 < s.length &&
             (s.charCodeAt(i + 1) & 0xfc00) === 0xdc00) { n += 4; i++; }
    else n += 3;
  }
  return n;
}

// s'yi en çok maxBytes UTF-8 baytına kırp — karakter ORTASINDAN kesmez (surrogate çifti bölünmez).
export function byteSlice(s, maxBytes) {
  s = String(s == null ? "" : s);
  var n = 0, i = 0;
  while (i < s.length) {
    var c = s.charCodeAt(i), w, step = 1;
    if (c < 0x80) w = 1;
    else if (c < 0x800) w = 2;
    else if (c >= 0xd800 && c <= 0xdbff && i + 1 < s.length &&
             (s.charCodeAt(i + 1) & 0xfc00) === 0xdc00) { w = 4; step = 2; }
    else w = 3;
    if (n + w > maxBytes) break;
    n += w; i += step;
  }
  return s.slice(0, i);
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

// g/e/t: Faz 4-ek merdiven alanları (aşağıda); z pozisyon kaydı state'e hiç yazılmaz ama
// savunmacı olarak listede (yanlışlıkla state.z konursa extra.o'ya yankılanmasın).
var _V2_KNOWN = { visited: 1, results: 1, history: 1, vars: 1, ix: 1, inext: 1, cursorId: 1,
                  reachedEnd: 1, xp: 1, g: 1, e: 1, t: 1, z: 1 };

// --------------------------------------------------------------------------- //
// F2 (#113) — exploration girdi saklama: state.xp = { store_key: değer }
// --------------------------------------------------------------------------- //
// Anahtarlar store_key'dir (ekran id'si DEĞİL) → pozisyonel indekse çevrilmez, v2 kuyruk
// JSON'unda (extra.p) kimlik-anahtarlı taşınır; paket reorder'ında bile anlamı bozulmaz
// (orderFp uyuşmazlığında zarfın tamamı temiz-başlangıca düşer — bilinçli güvenli taraf).
// Değer 500 UTF-8 BAYTTA kırpılır (Faz 4-ek: karakter değil bayt — Türkçe metin 2 bayt/harf):
// SCORM 1.2 suspend bütçesi (3500 bayt) birkaç keşif ekranını kaldırabilsin; sunucu tarafı
// tahmin (core/antislop.py estimate_suspend_size) AYNI sabiti kullanır — birlikte güncellenmeli.

export var EXPLORATION_VALUE_MAX = 500;

// state.xp[key] = String(value) (500 baytta kırp). Dönüş: { value, truncated } — çağıran
// (bindExploration) truncated'ı console.warn'a çevirir; burada ASLA loglanmaz (saf).
export function setExploration(state, key, value) {
  var v = value == null ? "" : String(value);
  var truncated = false;
  if (byteLen(v) > EXPLORATION_VALUE_MAX) { v = byteSlice(v, EXPLORATION_VALUE_MAX); truncated = true; }
  if (state) (state.xp = state.xp || {})[String(key)] = v;
  return { value: v, truncated: truncated };
}

export function getExploration(state, key) {
  var v = state && state.xp ? state.xp[String(key)] : null;
  return v == null ? "" : String(v);
}

// meta (Faz 4-ek, opsiyonel): { node: cursor ekranının outline düğüm id'si, cv: içerik
// sürümü (content_version, küçük int), t: kırpma basamağı (encodeSuspendFit yazar) }.
// meta verilirse tail'e `z` POZİSYON KAYDI eklenir: {s: ekranId, n: düğümId, v: içerikSürümü}.
// z KİMLİK-tabanlıdır (pozisyonel DEĞİL) → paket güncellenip order değişse (orderFp uyuşmasa)
// bile okunabilir kalır; resumeSuspend republish merdiveni bunun üzerinden çalışır.
export function encodeSuspend(state, order, meta) {
  state = state || {}; order = order || []; meta = meta || {};
  var idx = {}, i;
  for (i = 0; i < order.length; i++) idx[order[i]] = i;
  var extra = {};

  // z — pozisyon kaydı: konum + içerik sürümü. ASLA DÜŞMEZ (merdivenin tepesi).
  var z = {};
  if (state.cursorId != null) z.s = state.cursorId;
  if (meta.node != null) z.n = meta.node;
  if (meta.cv != null) z.v = meta.cv;
  if (z.s != null || z.v != null) extra.z = z;
  if (meta.t) extra.t = meta.t;                        // kırpma basamağı bayrağı
  if (state.g) extra.g = state.g;                      // hedef anlık görüntüsü (taban — rung 3)
  if (state.e != null) extra.e = state.e;              // toplam kazanılmış puan tabanı (rung 3)

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
  if (state.xp && Object.keys(state.xp).length) extra.p = state.xp;   // F2 — kimlik-anahtarlı
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
    if (extra.p) st.xp = extra.p;                      // F2 — exploration girdileri (store_key → değer)
    if (extra.o) Object.keys(extra.o).forEach(function (ok_) { st[ok_] = extra.o[ok_]; });
    // Faz 4-ek — merdiven alanları: t (kırpma basamağı), g/e (rung-3 skor/hedef tabanı).
    // z pozisyon kaydı state'e YAZILMAZ (konum zaten cursor'dan geldi; z resumeSuspend'in işi).
    if (extra.t) st.t = extra.t;
    if (extra.g) st.g = extra.g;
    if (extra.e != null) st.e = extra.e;
    // t=4 (yalnız-pozisyon): visited de düşmüştü → LİNEER YAKLAŞIM: cursor'a kadarki ekranlar
    // gezilmiş sayılır (kilit tuzağı/ilerleme sıfırlanması olmasın; menüden atlanmış ekranlar
    // için iyimser bir yaklaşıklıktır — belgeli). cursor'un kendisi visited SAYILMAZ (oynatıcı
    // gösterirken işaretler).
    if (st.t >= 4 && parts[1]) {
      var ci = _p36(parts[1]);
      for (var q = 0; q < ci && q < order.length; q++) st.visited[order[q]] = true;
    }
    return st;
  } catch (e) { return null; }
}

// raw → state | null. v2 ("2|" öneki) ve v1 (düz JSON {visited:...}) formatlarını tanır.
// NOT (Faz 4-ek): orderFp uyuşmazlığında null döner — bu TAM decode'un sözleşmesidir
// (pozisyonel alanlar güvensiz). Republish'ten sağ çıkan kimlik-tabanlı KISMİ resume için
// oynatıcı resumeSuspend kullanır (aşağıda) — null artık "her şeyi sıfırla" demek DEĞİLDİR.
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

// orderFp uyuşmayan v2 zarfından KİMLİK-tabanlı alanları kurtar: tail (extra.c/v/r/x/a/p/o,
// z, g, e, t) + inext (LMS interaction sayacı — order'dan bağımsız; eski satırların üzerine
// yazmayı önler). POZİSYONEL alanlar (cursor idx, visited bitfield, history, results/ix
// indeksleri) ATILIR — eski order bilinmediği için id'ye çevrilemezler; reachedEnd de atılır
// (yeni içerikte "sonu görmüş" sayılamaz). → {state, z} | null.
function _salvageV2(s) {
  try {
    var parts = s.split("|");
    if (parts[0] !== "2") return null;
    var tail = parts.slice(9).join("|");
    var extra = tail ? JSON.parse(tail) : {};
    var st = { visited: {}, results: {}, history: [] };
    (extra.v || []).forEach(function (vid) { st.visited[vid] = true; });
    if (extra.r) Object.keys(extra.r).forEach(function (rid) { st.results[rid] = extra.r[rid]; });
    if (extra.x) { st.ix = {}; Object.keys(extra.x).forEach(function (xid) { st.ix[xid] = extra.x[xid]; }); }
    if (parts[7] != null && parts[7] !== "") st.inext = _p36(parts[7]);
    if (extra.a) st.vars = extra.a;
    if (extra.p) st.xp = extra.p;
    if (extra.t) st.t = extra.t;
    if (extra.g) st.g = extra.g;
    if (extra.e != null) st.e = extra.e;
    if (extra.o) Object.keys(extra.o).forEach(function (ok_) { st[ok_] = extra.o[ok_]; });
    return { state: st, z: extra.z || null, c: extra.c != null ? extra.c : null };
  } catch (e) { return null; }
}

// Faz 4-ek — REPUBLISH-RESUME OKUMA MERDİVENİ. ctx: { cv: COURSE.content_version,
// screenNode: {ekranId: düğümId} }. Dönüş: { state, mode, target, notice }:
//   mode "none"   → veri yok/çözülemedi (temiz başlangıç, bildirim YOK — eski davranış)
//   mode "full"   → orderFp eşleşti (veya v1 kimlik-anahtarlı) → TAM resume, SESSİZ.
//                   İçerik sürümü v yalnız pozisyonel bütünlük bozulunca danışılır: fp
//                   eşleşiyorsa ekran kümesi ve sırası aynıdır → v farkı (yalnız düğüm
//                   kümesi değişimi) tam resume'u etkilemez (düğüm konumu statik konfigden).
//   mode "node"   → fp uyuşmadı ama pozisyon kaydındaki düğüm YAŞIYOR → düğüme devam
//                   (tam ekran hâlâ varsa o; yoksa düğümün yeni İLK ekranı) — SESSİZ (madde-2).
//   mode "screen" → düğüm gitmiş ama EKRAN yaşıyor → ekranın YENİ düğümünde devam + BİLDİRİM.
//   mode "start"  → ikisi de gitmiş (ya da pozisyon kaydı yok — eski payload) → kurs başı +
//                   BİLDİRİM (sessiz sıfırlama YOK).
// Fallback modlarında (node/screen) hedefe kadarki ekranlar LİNEER YAKLAŞIMLA visited
// işaretlenir (kilit tuzağı/ilerleme sıfırlanması olmasın — belgeli yaklaşıklık). Öğrenene
// ASLA teknik hata gösterilmez; bildirim dostu metindir (runtime i18n, aria-live).
export function resumeSuspend(raw, order, ctx) {
  ctx = ctx || {}; order = order || [];
  var none = { state: null, mode: "none", target: null, notice: false };
  if (raw == null || raw === "") return none;
  var s = String(raw);
  if (s.slice(0, 2) !== "2|") {
    var v1 = decodeSuspend(s, order);                  // v1 kimlik-anahtarlı → reorder'a bağışık
    return v1 ? { state: v1, mode: "full", target: v1.cursorId != null ? v1.cursorId : null,
                  notice: false } : none;
  }
  var full = _decodeV2(s, order);
  if (full) return { state: full, mode: "full",
                     target: full.cursorId != null ? full.cursorId : null, notice: false };
  var sv = _salvageV2(s);
  if (!sv) return none;
  var st = sv.state;
  var z = sv.z || {};
  if (z.s == null && sv.c != null) z.s = sv.c;         // eski payload: yalnız extra.c varsa o da konumdur
  var sn = ctx.screenNode || {};
  var idx = {}, i;
  for (i = 0; i < order.length; i++) idx[order[i]] = i;
  var nodeAlive = false;
  if (z.n != null) {
    for (i = 0; i < order.length; i++) if (sn[order[i]] === z.n) { nodeAlive = true; break; }
  }
  var mode, target = null, notice;
  if (nodeAlive) {
    mode = "node"; notice = false;
    if (z.s != null && idx[z.s] != null) target = z.s;
    else for (i = 0; i < order.length; i++) if (sn[order[i]] === z.n) { target = order[i]; break; }
  } else if (z.s != null && idx[z.s] != null) {
    mode = "screen"; notice = true; target = z.s;
  } else {
    mode = "start"; notice = true; target = order.length ? order[0] : null;
  }
  if (target != null && mode !== "start") {
    st.cursorId = target;
    for (i = 0; i < (idx[target] || 0); i++) st.visited[order[i]] = true;   // lineer yaklaşım
  }
  return { state: st, mode: mode, target: target, notice: notice };
}

function _shallow(st) { var o = {}; for (var k in st) o[k] = st[k]; return o; }

// rung-3 anlık görüntüsü: results düşmeden ÖNCE hedef toplamları + toplam kazanılmış puan
// tail'e taşınır (rung 2 sözleşmesi: hedef tamamlanma/skor durumu, sayfa-cevaplarından uzun
// yaşar). Mevcut taban (önceki kısmi resume'dan gelen g/e) korunur: canlı toplam yalnızca
// cevaplanmış hedeflerde tabanı EZER; toplam puanda büyük olan kazanır (çifte sayım yok).
function _snapshotScores(st, meta) {
  var g = {}, oid;
  if (st.g) for (oid in st.g) g[oid] = st.g[oid];
  if (meta && meta.objIds && meta.objMap) {
    var aggs = aggregateObjectives(meta.objIds, meta.objMap, st.results || {});
    for (var i = 0; i < aggs.length; i++) {
      var a = aggs[i];
      if (a.answered > 0) g[a.id] = [a.correct, a.total, a.answered];
    }
  }
  var e = 0;
  var res = st.results || {};
  for (var sid in res) e += Number(res[sid] && res[sid].points) || 0;
  if (st.e != null && Number(st.e) > e) e = Number(st.e);
  var out = {};
  if (Object.keys(g).length) out.g = g;
  if (e > 0) out.e = e;
  return out;
}

// Faz 4-ek — KIRPMA MERDİVENİ (taşma önceliği; üst korunur, alt önce düşer):
//   korunan tepe: pozisyon (z: ekran id + düğüm id + içerik sürümü) + cursor + reachedEnd
//                 + inext — ASLA düşmez.
//   rung 1: history (gezinme geri-yığını; en az değerli — geri tuşu lineere düşer)
//   rung 2: xp (öğrenen serbest metni — keşif girdileri; yer tutucuya düşer)
//   rung 3: sayfa-başına cevaplar (results/ix/vars) — düşmeden önce hedef toplamları + toplam
//           puan g/e olarak tail'e alınır (hedef tamamlanma/skor durumu cevaplardan uzun yaşar)
//   rung 4: g/e + visited de düşer → yalnız pozisyon (decode visited'ı lineer yaklaşımla kurar)
// Her basamaktan sonra YENİDEN ÖLÇÜLÜR (UTF-8 bayt), sığdığı anda durur. Basamak `t` kısa
// anahtarıyla zarfa yazılır — oynatıcı state'i KISMİ sayar (basamak-başına davranış runtime'da).
// limit = ÇALIŞMA BÜTÇESİ bayt (suspendBudget; 1.2'de 3500). meta: encodeSuspend meta'sı +
// {objIds, objMap} (rung-3 anlık görüntüsü için).
export function encodeSuspendFit(state, order, limit, meta) {
  var budget = Number(limit) > 0 ? Number(limit) : SUSPEND_BUDGET_12;
  meta = meta || {};
  var st = state || {};
  var rung = 0;
  var data = encodeSuspend(st, order, meta);
  while (byteLen(data) > budget && rung < 4) {
    rung++;
    st = _shallow(st);
    if (rung === 1) { st.history = []; }
    else if (rung === 2) { delete st.xp; }
    else if (rung === 3) {
      var snap = _snapshotScores(st, meta);
      delete st.results; delete st.ix; delete st.vars;
      delete st.g; delete st.e;
      if (snap.g) st.g = snap.g;
      if (snap.e != null) st.e = snap.e;
    } else if (rung === 4) { delete st.g; delete st.e; st.visited = {}; }
    var m = _shallow(meta); m.t = rung;
    data = encodeSuspend(st, order, m);
  }
  var bytes = byteLen(data);
  return { data: data, rung: rung, bytes: bytes, truncated: bytes > budget,
           historyDropped: rung >= 1 };
}

// rung-3 tabanını canlı toplamlarla birleştir (runtime writeObjectives yolu): hedef sırası
// objectiveIds'tir; CANLI toplamda cevap varsa canlı kazanır (öğrenen yeniden cevapladı),
// yoksa g tabanı kullanılır → kısmi resume'da LMS'e SIFIR yazılmaz (skor geriye gitmez).
export function mergeObjectiveSnapshot(aggs, objectiveIds, g) {
  if (!g) return aggs || [];
  var live = {};
  (aggs || []).forEach(function (a) { live[a.id] = a; });
  var out = [];
  (objectiveIds || []).forEach(function (oid) {
    var a = live[oid], snap = g[oid];
    if (a && a.answered > 0) { out.push(a); return; }
    if (snap) {
      var c = Number(snap[0]) || 0, t = Number(snap[1]) || 0, n = Number(snap[2]) || 0;
      out.push({ id: oid, correct: c, total: t, answered: n, scaled: t > 0 ? c / t : 0 });
      return;
    }
    if (a) out.push(a);
  });
  return out;
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
  // Faz 4-ek: "truncated" = merdivenin SONUNDA bile bütçeye sığmadı; "trimmed" = merdiven
  // veri düşürerek sığdırdı (rung>0) — kayıp OLDU, sessiz kalmaz (konsol + varsa xAPI).
  if (opts.truncated) out.push({ kind: "truncated", size: size, limit: limit });
  else if (Number(opts.rung) > 0) out.push({ kind: "trimmed", size: size, limit: limit });
  if (opts.ok === false) out.push({ kind: "write_failed", size: size, limit: limit });
  // kırpma basamağı (rung) verilmişse uyarılara eklenir: iz hangi veri katmanının düştüğünü
  // raporlar. Verilmezse alan hiç eklenmez (geriye uyum).
  if (opts.rung) for (var i = 0; i < out.length; i++) out[i].rung = Number(opts.rung);
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
