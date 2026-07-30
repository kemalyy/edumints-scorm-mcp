// components/engine/progress.js — Senaryo hattı Faz 4: oynatıcı konum/ilerleme/kilit — SAF, DOM'suz.
//
// NEDEN AYRI DOSYA (3.3 bayt-parite): scorm.js her pakete KOŞULSUZ inline edilir (S1/S3/S4).
// Faz 4 yardımcıları yalnız OUTLINE'LI kursta gerekir; scorm.js'e eklenmeleri outline'sız
// kursların çıktısını bayt düzeyinde değiştirirdi (tests/test_outline_menu.py fixture kilidi).
// Bu modül core/engine_bundle.load_progress_bundle() ile YALNIZ outline'lı pakete inline
// edilir → window.SCORMP. Vitest: tests/js/progress.test.js.

// --------------------------------------------------------------------------- //
// P — oynatıcı konum / ilerleme / kilit (Senaryo hattı Faz 4) — SAF, DOM'suz
// --------------------------------------------------------------------------- //
// Girdi biçimleri runtime kurs konfigürasyonuyla birebir:
//   nodes:      COURSE.outline → [{id, parent_id, title, unlock_rule?}] (unlock_rule yalnız
//               "sequential" iken serileşir; yokluk = "free")
//   screenNode: {screenId: nodeId} (COURSE.screens[].node_id'den kurulur)
//   order:      COURSE.id_order  ·  visited: state.visited ({screenId: true})
//
// TASARIM KARARI (plan 3.11 hiyerarşik suspend): {"n","s","st"} üçlüsü suspend zarfına
// EKLENMEZ — üçü de zaten karşılanıyor: s = cursor (pozisyonel), st = results/ix/xp,
// n = screens[cursor].node_id (STATİK konfig → çalışma anında türetilir; burada positionInfo).
// Kopya alan = drift riski + 1.2'nin 4096 bütçesinden çalınan bayt. Serbest metin (düğüm
// başlığı, kilit sebebi) suspend'e ASLA girmez. Menünün elle katla/aç durumu da persist
// edilmez (türetilen yol-açma yeterli; UI tercihi öğrenme durumu değildir).

// Düğüm zinciri (kök→yaprak) yürütücüsü — döngü/sarkan parent'ta sonlanır (savunmacı;
// validator bunları zaten sert hatayla keser ama render doğrulamasız da çağrılabilir).
function _nodeChain(byId, nid) {
  var chain = [], seen = {};
  var cur = nid == null ? null : byId[nid];
  while (cur && !seen[cur.id]) {
    seen[cur.id] = 1;
    chain.unshift(cur);
    cur = cur.parent_id == null ? null : byId[cur.parent_id];
  }
  return chain;
}

function _byId(nodes) {
  var m = {};
  (nodes || []).forEach(function (n) { if (n && n.id != null) m[n.id] = n; });
  return m;
}

// Konum göstergesi (§6.2): "Ünite 1 · Bölüm 1.1 · 2/4" için veri.
// → { chain: [başlıklar kök→yaprak], index: düğümün KENDİ ekranları içinde 1-tabanlı sıra,
//     total: düğümün kendi ekran sayısı } | null (outline yok / ekran order'da yok).
// Düğümsüz ekran (veya sarkan node_id — Faz 1 render kararıyla aynı): chain=[] +
// düğümsüz küme içindeki sıra. DOM katmanı chain'i i18n "düğümsüz" başlığıyla tamamlar.
export function positionInfo(nodes, screenNode, order, screenId) {
  if (!nodes || !nodes.length) return null;
  order = order || []; screenNode = screenNode || {};
  if (order.indexOf(screenId) < 0) return null;
  var byId = _byId(nodes);
  var raw = screenNode[screenId];
  var nid = raw != null && byId[raw] ? raw : null;   // sarkan node_id → düğümsüz say
  var members = [], i;
  for (i = 0; i < order.length; i++) {
    var m = screenNode[order[i]];
    if (m != null && !byId[m]) m = null;
    if ((m == null ? null : m) === nid) members.push(order[i]);
  }
  var chain = _nodeChain(byId, nid).map(function (n) { return String(n.title == null ? "" : n.title); });
  return { chain: chain, index: members.indexOf(screenId) + 1, total: members.length };
}

// Menü düğüm ilerlemesi (§6.2): düğüm başına {done, total} — ALT AĞAÇ kümülatif
// (kendi ekranları + tüm torun düğümlerin ekranları). total=0 → menüde n/m basılmaz.
export function nodeProgress(nodes, screenNode, visited) {
  nodes = nodes || []; screenNode = screenNode || {}; visited = visited || {};
  var byId = _byId(nodes);
  var acc = {};
  nodes.forEach(function (n) { acc[n.id] = { done: 0, total: 0 }; });
  Object.keys(screenNode).forEach(function (sid) {
    // ekranın sayımı, düğüm zincirindeki HER ataya işlenir (alt-ağaç kümülatifi)
    _nodeChain(byId, screenNode[sid]).forEach(function (n) {
      acc[n.id].total++;
      if (visited[sid]) acc[n.id].done++;
    });
  });
  return acc;
}

// Kilit kuralları (§6.1): unlock_rule="sequential" düğüm, ÖNCEKİ KARDEŞİNİN alt-ağacındaki
// TÜM bağlı ekranlar ziyaret edilmeden kilitlidir ("tamamlandı" = ziyaret; skor eşiği
// gezinmeyi kilitleyemez — erişilebilirlik zemini, sonuç kapıları results tarafındadır).
// Kilit alt ağaca YAYILIR (kilitli ünitenin bölümleri de kilitli; sebep kökteki engelleyici).
// → { nodeId: engelleyen_nodeId } (yalnız kilitliler). Kenarlar:
//   - ilk kardeşte sequential → engelleyen yok → açık
//   - önceki kardeşin alt-ağacında ekran yoksa runtime AÇIK bırakır (içerik tuzağı olmasın;
//     yazarlık hatasını validator UNREACHABLE_NODE sert hatasıyla keser)
export function lockedNodes(nodes, screenNode, visited) {
  nodes = nodes || [];
  var progress = nodeProgress(nodes, screenNode, visited);
  var byId = _byId(nodes);
  var self = {};                                     // düğümün KENDİ kuralından kilit
  nodes.forEach(function (n, i) {
    if (!n || n.unlock_rule !== "sequential") return;
    var prev = null;
    for (var j = i - 1; j >= 0; j--) {
      var pp = nodes[j] && nodes[j].parent_id == null ? null : nodes[j].parent_id;
      var np = n.parent_id == null ? null : n.parent_id;
      if (nodes[j] !== n && pp === np) { prev = nodes[j]; break; }
    }
    if (!prev) return;
    var pr = progress[prev.id] || { done: 0, total: 0 };
    if (pr.total > 0 && pr.done < pr.total) self[n.id] = prev.id;
  });
  var out = {};
  nodes.forEach(function (n) {                       // en yakın kilitli atadan yay (kök sebep)
    var chain = _nodeChain(byId, n.id);
    for (var k = 0; k < chain.length; k++) {
      if (self[chain[k].id]) { out[n.id] = self[chain[k].id]; break; }
    }
  });
  return out;
}

// results_breakdown bölüm tamamlanması (§6.2 hizası): AYNI screen_ids listesi üzerinden
// ziyaret sayımı — skor yüzdesiyle (renderResultsIfNeeded) aynı mekanizma, ikinci bir
// hedef-ilerleme makinesi YOK. → {done, total}.
export function sectionCompletion(ids, visited) {
  ids = ids || []; visited = visited || {};
  var done = 0;
  for (var i = 0; i < ids.length; i++) if (visited[ids[i]]) done++;
  return { done: done, total: ids.length };
}
