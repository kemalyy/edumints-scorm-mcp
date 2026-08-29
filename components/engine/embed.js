// components/engine/embed.js — embed_html köprüsü: iframe artifact'inin postMessage'ını cmi
// yazımlarına çevirir (SAF; DOM yok, vitest'le test edilir). templates.py EMBED_JS bunu
// window.SCORMEMBED üzerinden çağırır.
// AYRI MODÜL (scorm.js DEĞİL): scorm.js her pakete koşulsuz inline edilir → oraya eklemek
// embed'siz kursların baytlarını değiştirirdi (bkz. engine_bundle.py progress.js notu).
//
// fix round 2 / VERİ MODELİ: köprünün kalıcı kaydı KOMPAKT ve ANLAMSALdır — state.eb:
//   { s: skor 0..100 (sayı), c: tamamlanma/lesson durumu (dize), k: success durumu (2004),
//     d: { ekranId: 1 } eşiği aşılmış time_threshold ekranları,
//     m: { ekranId: 1 } artifact'i {scorm:'complete'} bildirmiş on_message ekranları (fix round 3) }
// cmi anahtarları ASLA state'te saklanmaz; her zaman embedWrites(eb, is2004) ile TÜRETİLİR.
// Nedenleri: (1) suspend_data bütçesi (1.2'de 3500 bayt çalışma bütçesi; "cmi.core.lesson_status"
// tek başına 22 bayt), (2) suspend_data'dan geri okunan kayıt yeniden doğrulanır → yalnız beyaz
// listedeki cmi anahtarları yazılabilir, (3) 1.2'de lesson_status tek kanaldır (c) → "son yazan
// kazanır" sırası korunur; 2004'te completion_status (c) ile success_status (k) ayrışır.

var STATUS_1_2 = ["completed", "incomplete", "passed", "failed", "browsed", "not attempted"];
// 2004: cmi.completion_status YALNIZ bunları kabul eder (passed/failed → success_status, 406 riski).
var COMPLETION_2004 = ["completed", "incomplete", "not attempted", "unknown"];

/**
 * postMessage mesajını KOMPAKT eb yamasına çevirir (cmi anahtarı ÜRETMEZ).
 * Geçersiz/bilinmeyen mesaj → null.
 */
export function embedStateFromMsg(msg, is2004) {
  if (!msg || typeof msg !== "object" || typeof msg.scorm !== "string") return null;
  var cmd = msg.scorm;
  if (cmd === "complete") return { c: "completed" };
  if (cmd === "setScore") {
    // fix round 1 / MINOR 4: yalnız gerçek `number` kabul edilir — Number(null)===0,
    // Number("")===0, Number([])===0, Number(true)===1 gibi zımni tür dönüşümleri (ve Infinity)
    // geçersiz sayılır.
    if (typeof msg.value !== "number" || !isFinite(msg.value)) return null;
    return { s: Math.max(0, Math.min(100, msg.value)) };
  }
  if (cmd === "passed" || cmd === "failed") return is2004 ? { k: cmd } : { c: cmd };
  if (cmd === "setStatus" && typeof msg.value === "string") {
    if (STATUS_1_2.indexOf(msg.value) < 0) return null;
    if (!is2004) return { c: msg.value };
    // fix round 1 / IMPORTANT 1: 2004'te passed/failed success_status'a gider; browsed
    // 2004 sözlüğünde YOKTUR → reddedilir (1.2'de geçerli, orada değişmedi).
    if (msg.value === "passed" || msg.value === "failed") return { k: msg.value };
    if (msg.value === "browsed") return null;
    return { c: msg.value };
  }
  return null;
}

/**
 * Kompakt eb kaydından cmi yazımlarını TÜRETİR → [{key, value}, ...].
 * Beyaz liste dışındaki her şey sessizce düşer (suspend_data'dan gelen kayıt da buradan geçer).
 */
export function embedWrites(eb, is2004) {
  var out = [];
  if (!eb || typeof eb !== "object") return out;
  if (typeof eb.s === "number" && isFinite(eb.s)) {
    var n = Math.max(0, Math.min(100, eb.s));
    if (is2004) {
      out.push({ key: "cmi.score.raw", value: String(n) });
      out.push({ key: "cmi.score.scaled", value: (n / 100).toFixed(4) });
    } else {
      out.push({ key: "cmi.core.score.raw", value: String(n) });
    }
  }
  if (typeof eb.c === "string") {
    if (!is2004) {
      if (STATUS_1_2.indexOf(eb.c) >= 0) out.push({ key: "cmi.core.lesson_status", value: eb.c });
    } else if (COMPLETION_2004.indexOf(eb.c) >= 0) {
      out.push({ key: "cmi.completion_status", value: eb.c });
    }
  }
  if (is2004 && (eb.k === "passed" || eb.k === "failed")) {
    out.push({ key: "cmi.success_status", value: eb.k });
  }
  return out;
}

/**
 * Tek mesajın doğrudan cmi karşılığı (kompozisyon; sözleşme dokümanının referansı).
 * Geçersiz/bilinmeyen mesaj → [].
 *
 * fix round 3 / FINDING F — BİLEREK KORUNUYOR (runtime'da çağrılmıyor): CONTRACTS.md §9 artifact
 * yazarına köprünün eşlemesini BU imza üzerinden anlatır ve testlerin çoğu (round 0/1) bunun
 * üzerinden yazılmıştır. İki canlı fonksiyonun kompozisyonu olduğu için ayrıca bakım yükü yok ve
 * paket maliyeti ~3 satır. NOT: paketin inline edildiğini kanıtlayan test işareti artık CANLI bir
 * sembol (`embedStateFromMsg`) — bkz. tests/test_embed_html.py.
 */
export function bridgeToScorm(msg, is2004) {
  return embedWrites(embedStateFromMsg(msg, is2004), is2004);
}

/**
 * fix round 3 / KAPI DURUMU — round 2'nin `gateVisited`'ı (state.visited'ı geri çekmek) YERİNE.
 * Neden değişti: motorun `viewedAll()`'ı `state.reachedEnd`'i de kabul ettiğinden visited'ı geri
 * çekmek son ekranda (ve TEK ekranlı kursta — bu özelliğin amiral gemisi biçimi) tamamlanmayı
 * HİÇ geciktirmiyordu (FINDING A); ayrıca ilerleme çubuğunu ve history-pop yolunu bozuyordu
 * (FINDING C/D). Artık motorun girdisine DOKUNULMAZ; tamamlanma evaluate() SONRASI geri çekilir
 * (holdBackWrites).
 *
 * @param gates [{id, mode}] — kapılı ekranlar. mode: "time_threshold" | "on_message"
 *        (çağıran, o an ERİŞİLEBİLİR olmayan — visible_if false — ekranları ELEMİŞ olmalıdır:
 *        erişilemeyen bir kapı kursu sonsuza dek kilitlerdi).
 * @param eb state.eb — `d` (eşiği aşılmış time_threshold ekranları) + `m` (artifact'i
 *        {scorm:'complete'} bildirmiş on_message ekranları) defterleri.
 * @returns true → EN AZ BİR kapı bekliyor (tamamlanma geri çekilmeli).
 */
export function gatesPending(gates, eb) {
  gates = gates || [];
  eb = eb || {};
  for (var i = 0; i < gates.length; i++) {
    var g = gates[i];
    if (!g || !g.id) continue;
    var ledger = g.mode === "on_message" ? eb.m : eb.d;
    if (!(ledger && ledger[g.id])) return true;
  }
  return false;
}

/**
 * fix round 3 / TAMAMLANMA KİLİDİ (yalnız GERİ ÇEKME): bekleyen kapı varsa motorun hesapladığı
 * tamamlanma "tamamlanmadı"ya düşürülür. ASLA yükseltmez (hiçbir girdi için "completed"/"passed"
 * üretemez) ve skora/success_status'a HİÇ dokunmaz — F1 değişmezi: köprü bir kursu tamamlanmış
 * YAPAMAZ; yanlış sonuç yalnız "henüz tamamlanmadı" yönünde olabilir.
 *
 * `exit` de geri çekilir (ayrı karar, fix round 3 raporunda gerekçeli): motor
 * `exit = complete ? "normal" : "suspend"` yazar; kilit tam olarak "motor complete diyor ama kapı
 * bekliyor" durumunda devreye girdiği için aksi hâlde `status=incomplete` + `exit=normal` çifti
 * oluşur ve katı bir 1.2 LMS'i suspend_data'yı atmakta serbest kalır (kurs ortasında veri kaybı).
 * "suspend" her iki sürümde de geçerli vokabülerdir.
 */
export function holdBackWrites(pending, is2004) {
  if (!pending) return [];
  return [
    { key: is2004 ? "cmi.completion_status" : "cmi.core.lesson_status", value: "incomplete" },
    { key: is2004 ? "cmi.exit" : "cmi.core.exit", value: "suspend" },
  ];
}

/**
 * fix round 4 / FIX 1+2 — TAMAMLANMA İDDİASI: "bu cmi yazımı kursu TAMAMLANMIŞ ilan eder mi?"
 * Kapı beklerken bastırılacak TEK yüklem budur; `wrapSet` (motorun kendi yazımları) ve
 * `isGatedCompletionWrite` üzerinden `EMBED_SHIM_JS` bunu kullanır — kural tek yerde durur.
 * (task-5 / FIX 3: ayrı bir artifact pin süzgeci — `suppressCompletionWrites` — VARDI; wrapSet
 *  onu tamamen kapsadığı için silindi. Bkz. CONTRACTS.md §9.)
 *
 * Kapsam BİLEREK dar:
 *   - 1.2 `cmi.core.lesson_status`: "completed" VE "passed". 1.2'de bu anahtar TEK başarı
 *     kanalıdır ve "passed" tamamlanmayı İMA EDER (LMS raporlaması onu tamamlanmış sayar).
 *   - 2004 `cmi.completion_status`: yalnız "completed" ("passed" bu anahtarın vokabülerinde YOK;
 *     2004'te başarı AYRI kanaldır → `cmi.success_status`).
 *   - `cmi.success_status`, skor anahtarları, `cmi.suspend_data` (sSetChecked ile yazılır, bu
 *     sarmalayıcıdan HİÇ geçmez) ve "failed"/"incomplete"/"browsed"/"not attempted" gibi
 *     tamamlanma İMA ETMEYEN değerler ASLA bastırılmaz.
 *
 * TAM eşitlik (`===`) şarttır, alt-dize/regex DEĞİL: `scorm.js:objectiveElements` aynı `sSet`
 * üzerinden `cmi.objectives.N.completion_status` / `.status` = "completed" yazar ve bunlar kapı
 * beklerken de yazılmalıdır (hedef bazlı ilerleme, kursun tamamlanma iddiası değildir).
 */
export function isCompletionAssertion(key, value, is2004) {
  var v = String(value);
  if (is2004) return key === "cmi.completion_status" && v === "completed";
  return key === "cmi.core.lesson_status" && (v === "completed" || v === "passed");
}

/**
 * fix round 5 — GEÇİCİ `exit=normal`. AYRI bir yüklem (isCompletionAssertion'a KATILMAZ:
 * CONTRACTS.md §9'un kapsam tablosu o yüklemin yalnız-tamamlanma kalmasına dayanır).
 *
 * NEDEN: motor `exit = complete ? "normal" : "suspend"` yazar (scorm.js:exitValue) ve bunu
 * `evaluate()` içinde, `persist()` → `sCommit()`'ten ÖNCE yapar. Kapı beklerken motor
 * "complete" hesapladığı için her evaluate()'te önce geçici bir `exit=normal` COMMIT ediliyor,
 * ancak ondan sonra kilidin `exit=suspend`'i geliyordu — FIX 1'in kapattığı kusurun `exit`
 * anahtarındaki aynı biçimi. İlk commit edilen `exit`e göre davranan bir LMS'te (suspend_data'yı
 * atmakta serbest kalır) bu veri kaybı demektir.
 *
 * KAPSAM: yalnız "normal". `suspend`/`logout`/`time-out`/`""` ASLA bastırılmaz — kilit zaten
 * `suspend` yazar ve kapanış vokabülerinin geri kalanı motorun/LMS'in işidir.
 * (AYRI BİLET, burada DEĞİL: "normal" 1.2 `cmi.core.exit` vokabülerinde HİÇ yoktur —
 * 1.2 `time-out | suspend | logout | ""` kabul eder. Düzeltmesi `components/engine/scorm.js`'te,
 * yani koşulsuz inline edilen bundle'da → bayt-parite yüzünden bu turun dışında.)
 */
export function isTransientExit(key, value, is2004) {
  return key === (is2004 ? "cmi.exit" : "cmi.core.exit") && String(value) === "normal";
}

/**
 * fix round 5 — kapı beklerken bastırılan yazımların TEK kapısı: tamamlanma iddiası VEYA ona
 * eşlik eden geçici `exit=normal`. Hem `wrapSet` (motorun kendi yazımları) hem `EMBED_SHIM_JS`
 * (bootstrap penceresi, LMS adaptör vekili) bunu kullanır → kural tek yerde durur.
 */
export function isGatedCompletionWrite(key, value, is2004) {
  return isCompletionAssertion(key, value, is2004) || isTransientExit(key, value, is2004);
}

/**
 * fix round 4 / FIX 1 — `sSet` SARMALAYICISI: kapı beklerken tamamlanma iddiası içeren yazımı
 * cmi'ye HİÇ göndermez.
 *
 * NEDEN gerekliydi (round 3'ün ölçülmüş kusuru): kilit `origEvaluate()`'ten SONRA çalışıyordu, ama
 * `origEvaluate` → `persist()` → `sCommit()` motorun "completed"ini kilit devreye girmeden ÖNCE
 * COMMIT ediyordu. Yani geçici "completed" yalnız açılışta değil, kapı beklerken HER evaluate()'te
 * LMS'e gidiyordu. Tamamlanmayı ilk commit'te MANDALLAYAN bir LMS'te (1.2 raporlaması, 2004 rollup)
 * kapı özelliği sessizce hiç çalışmıyordu. Geri çekme (holdBackWrites) KALIR — ikisi birlikte
 * "yazılmadı, dolayısıyla geri çekmeye de gerek kalmadı ama yine de tutarlı" durumunu üretir.
 *
 * @param origSet motorun `sSet(k, v)`'si
 * @param pending () => boolean — HER yazımda taze sorulur (kapı açılınca sarmalayıcı şeffaflaşır)
 */
export function wrapSet(origSet, pending, is2004) {
  return function (key, value) {
    // fix round 5: yüklem isCompletionAssertion'dan isGatedCompletionWrite'a genişledi →
    // geçici `exit=normal` de kapı beklerken cmi'ye HİÇ gitmez (bkz. isTransientExit).
    if (pending() && isGatedCompletionWrite(key, value, is2004)) return;
    origSet(key, value);
  };
}

// fix round 1 / CRITICAL: motorun kendi evaluate() döngüsü (templates.py ENGINE_JS — her showAt +
// exit'te) skoru/durumu COURSE'tan YENİDEN hesaplayıp cmi'yi ezer → artifact'in setScore(85)'i bir
// sonraki evaluate()'te sıfırlanırdı. ENGINE_JS gövdesine dokunmadan (bayt-parite) çözüm: EMBED_JS
// `evaluate` bağlamasını bu sarmalayıcıyla DEĞİŞTİRİR.
// fix round 2:
//   - getWrites DİZİ döndürür (kompakt eb'den türetilmiş).
//   - FINDING 3: yeniden yazım persist() içindeki sCommit'ten SONRA olduğundan, yazım varsa
//     ayrıca commit edilir (yalnız Terminate'in örtük kalıcılığına güvenilmez).
// fix round 3:
//   - `before` (round-2 kapı düzeltmesi) KALDIRILDI — kapı artık motorun girdisini değiştirmiyor.
//   - getWrites SIRASI: önce holdBackWrites (kilit, yalnız geri çekme), SONRA eb'den türetilen
//     artifact yazımları. Böylece "son yazan kazanır" kuralıyla artifact'in KENDİ komutu (F1'in
//     izin verdiği tek ezme) kilidin üstünde kalır; kilit yalnız MOTORUN hesapladığı tamamlanmayı
//     geri çeker (1.2'de tek kanal olan lesson_status'ta artifact'in passed/failed'ı ezilmez).
// fix round 4 / FIX 2 — YUKARIDAKİ SIRA KORUNUR ama artık "artifact her şeyi ezer" DEMEK DEĞİLDİR:
//     bu sarmalayıcıya verilen `sSet` `wrapSet` ile sarmalanmıştır, yani kapı beklerken TAMAMLANMA
//     İDDİASI içeren yazım (1.2 completed/passed, 2004 completed) — motorunki de artifact pini de —
//     LMS'e HİÇ gitmez. Sıra hâlâ anlamlıdır: `failed`, `browsed`, skor ve 2004 `success_status`
//     pinleri kilidin üstünde kalmaya devam eder.
// task-5 / FIX 3: round 4'ün AYRI pin süzgeci (`suppressCompletionWrites`) SİLİNDİ — `wrapSet`
//     yüklemi (isGatedCompletionWrite) onun yükleminin (isCompletionAssertion) katı üst kümesi ve
//     her iki yazım yolu (wrapEvaluate + message/applyWrites) sSet'ten geçiyor → tam kapsanıyordu.
export function wrapEvaluate(origEvaluate, sSet, getWrites, commit) {
  return function () {
    origEvaluate();
    var writes = getWrites() || [];
    for (var i = 0; i < writes.length; i++) sSet(writes[i].key, writes[i].value);
    if (writes.length && commit) commit();
  };
}
