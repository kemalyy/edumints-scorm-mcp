import { describe, it, expect } from "vitest";
import {
  duration12, duration2004, sessionTime, timestamp12, timestamp2004,
  exitValue, shouldRestore,
  INTERACTION_TYPES, interactionType, sanitizeId, resultValue, formatResponse,
  interactionElements,
  SUSPEND_LIMIT_12, SUSPEND_LIMIT_2004, suspendLimit,
  SUSPEND_BUDGET_12, suspendBudget, byteLen, byteSlice,
  encodeSuspend, decodeSuspend, encodeSuspendFit, resumeSuspend, mergeObjectiveSnapshot,
  setResultOk, suspendWriteIssues,
  EXPLORATION_VALUE_MAX, setExploration, getExploration,
  aggregateObjectives, objectiveIndices, objectiveElements,
} from "../../components/engine/scorm.js";

// --------------------------------------------------------------------------- //
// S3 — süre biçimleme
// --------------------------------------------------------------------------- //
describe("S3 süre biçimleme (seat time)", () => {
  it("1.2 CMITimespan HHHH:MM:SS.SS", () => {
    expect(duration12(0)).toBe("0000:00:00.00");
    expect(duration12(1000)).toBe("0000:00:01.00");
    expect(duration12(90_000)).toBe("0000:01:30.00");
    expect(duration12(3_661_250)).toBe("0001:01:01.25");
  });

  it("1.2 negatif/çöp girdi 0'a düşer, saat 9999'da doyar", () => {
    expect(duration12(-5)).toBe("0000:00:00.00");
    expect(duration12(NaN)).toBe("0000:00:00.00");
    expect(duration12(undefined)).toBe("0000:00:00.00");
    expect(duration12(1e13)).toMatch(/^9999:/);
  });

  it("2004 ISO 8601 PT#H#M#S — sıfır bileşenler düşer", () => {
    expect(duration2004(0)).toBe("PT0S");
    expect(duration2004(1000)).toBe("PT1S");
    expect(duration2004(90_000)).toBe("PT1M30S");
    expect(duration2004(3_600_000)).toBe("PT1H");
    expect(duration2004(3_661_250)).toBe("PT1H1M1.25S");
  });

  it("sessionTime sürüme göre doğru biçimi seçer", () => {
    expect(sessionTime(90_000, false)).toBe("0000:01:30.00");
    expect(sessionTime(90_000, true)).toBe("PT1M30S");
  });

  it("1.2 zamanı GÜNÜN SAATİ, 2004 tam ISO tarih-saat", () => {
    const d = Date.UTC(2026, 6, 24, 9, 5, 3, 250); // 2026-07-24T09:05:03.250Z
    expect(timestamp12(d)).toBe("09:05:03.25");
    expect(timestamp2004(d)).toBe("2026-07-24T09:05:03Z");
  });
});

// --------------------------------------------------------------------------- //
// S4 — exit / entry
// --------------------------------------------------------------------------- //
describe("S4 exit/entry ile resume garantisi", () => {
  it("tamamlanmamış kurs suspend, tamamlanan normal çıkar", () => {
    expect(exitValue(false)).toBe("suspend");
    expect(exitValue(true)).toBe("normal");
  });

  it("resume → geri yükle, ab-initio → yükleme", () => {
    expect(shouldRestore("resume", true)).toBe(true);
    expect(shouldRestore("resume", false)).toBe(true);
    expect(shouldRestore("ab-initio", true)).toBe(false);
  });

  it("boş/bilinmeyen entry: suspend_data varsa geri yükle (LMS uyumu)", () => {
    expect(shouldRestore("", true)).toBe(true);
    expect(shouldRestore("", false)).toBe(false);
    expect(shouldRestore(null, true)).toBe(true);
    expect(shouldRestore(undefined, false)).toBe(false);
  });

  it("büyük/küçük harf ve boşluk toleransı", () => {
    expect(shouldRestore(" Resume ", false)).toBe(true);
    expect(shouldRestore("AB-INITIO", true)).toBe(false);
  });
});

// --------------------------------------------------------------------------- //
// S1 — interactions
// --------------------------------------------------------------------------- //
describe("S1 etkileşim tipi eşlemesi", () => {
  it("puanlanan her ekran tipinin bir SCORM tipi vardır", () => {
    // core/project.py QUIZ_TYPES ile senkron kalmalı
    const quizTypes = [
      "mcq", "true_false", "fill_blank", "drag_drop", "hotspot", "matching", "sorting",
      "simulation", "decision_scenario", "term_match_race", "escape_room",
      "labeled_diagram", "game", "adaptive_practice",
    ];
    for (const t of quizTypes) {
      expect(INTERACTION_TYPES[t], `${t} eşlenmemiş`).toBeTruthy();
    }
  });

  it("bilinmeyen tip 'other'a düşer", () => {
    expect(interactionType("mcq")).toBe("choice");
    expect(interactionType("sorting")).toBe("sequencing");
    expect(interactionType("bilinmeyen")).toBe("other");
  });
});

describe("S1 sonuç sözlüğü 1.2 ve 2004'te FARKLI", () => {
  it("yanlış: 1.2 'wrong', 2004 'incorrect'", () => {
    expect(resultValue(false, false)).toBe("wrong");
    expect(resultValue(false, true)).toBe("incorrect");
  });
  it("doğru her iki sürümde 'correct'", () => {
    expect(resultValue(true, false)).toBe("correct");
    expect(resultValue(true, true)).toBe("correct");
  });
  it("neutral/unanticipated aynen geçer", () => {
    expect(resultValue("neutral", true)).toBe("neutral");
    expect(resultValue("unanticipated", false)).toBe("unanticipated");
  });
});

describe("S1 cevap deseni biçimleme", () => {
  it("choice: 1.2 virgül, 2004 [,]", () => {
    expect(formatResponse("choice", ["a", "b"], false)).toBe("a,b");
    expect(formatResponse("choice", ["a", "b"], true)).toBe("a[,]b");
    expect(formatResponse("choice", "a", false)).toBe("a");
  });

  it("true-false: 1.2 1/0, 2004 true/false", () => {
    expect(formatResponse("true-false", true, false)).toBe("1");
    expect(formatResponse("true-false", false, false)).toBe("0");
    expect(formatResponse("true-false", true, true)).toBe("true");
    expect(formatResponse("true-false", "false", true)).toBe("false");
  });

  it("matching: 1.2 a.b,c.d — 2004 a[.]b[,]c[.]d", () => {
    const m = { item1: "target2", item3: "target4" };
    expect(formatResponse("matching", m, false)).toBe("item1.target2,item3.target4");
    expect(formatResponse("matching", m, true)).toBe("item1[.]target2[,]item3[.]target4");
    expect(formatResponse("matching", [["a", "1"], ["b", "2"]], false)).toBe("a.1,b.2");
  });

  it("sequencing: sıra korunur", () => {
    expect(formatResponse("sequencing", ["c", "a", "b"], false)).toBe("c,a,b");
    expect(formatResponse("sequencing", ["c", "a", "b"], true)).toBe("c[,]a[,]b");
  });

  it("fill-in serbest metin, sürüm sınırında kırpılır", () => {
    expect(formatResponse("fill-in", "  cevap", false)).toBe("  cevap");
    const long = "x".repeat(400);
    expect(formatResponse("fill-in", long, true)).toHaveLength(250);
    expect(formatResponse("fill-in", long, false)).toHaveLength(255);
  });

  it("null/undefined boş dize", () => {
    expect(formatResponse("choice", null, false)).toBe("");
    expect(formatResponse("fill-in", undefined, true)).toBe("");
  });
});

describe("S1 id temizleme (CMIIdentifier)", () => {
  it("boşluk ve özel karakterler alt çizgiye döner", () => {
    expect(sanitizeId("soru 1")).toBe("soru_1");
    expect(sanitizeId("a/b?c")).toBe("a_b_c");
    expect(sanitizeId("ekran-1.2_x")).toBe("ekran-1.2_x");
  });
  it("boş id güvenli varsayılana düşer, 255'te kırpılır", () => {
    expect(sanitizeId("")).toBe("item");
    expect(sanitizeId(null)).toBe("item");
    expect(sanitizeId("y".repeat(400))).toHaveLength(255);
  });
});

describe("S1 interactionElements — yazılacak eleman listesi", () => {
  const rec = {
    id: "q1", screenType: "mcq", response: ["b"], correct: ["a"], ok: false,
    latencyMs: 12_500, time: Date.UTC(2026, 6, 24, 9, 5, 3, 250), description: "Başkent neresi?",
  };

  it("1.2: student_response + wrong + .time, description YAZILMAZ", () => {
    const kv = Object.fromEntries(interactionElements(rec, 0, false));
    expect(kv["cmi.interactions.0.id"]).toBe("q1");
    expect(kv["cmi.interactions.0.type"]).toBe("choice");
    expect(kv["cmi.interactions.0.student_response"]).toBe("b");
    expect(kv["cmi.interactions.0.correct_responses.0.pattern"]).toBe("a");
    expect(kv["cmi.interactions.0.result"]).toBe("wrong");
    expect(kv["cmi.interactions.0.latency"]).toBe("0000:00:12.50");
    expect(kv["cmi.interactions.0.time"]).toBe("09:05:03.25");
    expect(kv["cmi.interactions.0.description"]).toBeUndefined();
    expect(kv["cmi.interactions.0.learner_response"]).toBeUndefined();
  });

  it("2004: learner_response + incorrect + .timestamp + description", () => {
    const kv = Object.fromEntries(interactionElements(rec, 3, true));
    expect(kv["cmi.interactions.3.learner_response"]).toBe("b");
    expect(kv["cmi.interactions.3.result"]).toBe("incorrect");
    expect(kv["cmi.interactions.3.latency"]).toBe("PT12.5S");
    expect(kv["cmi.interactions.3.timestamp"]).toBe("2026-07-24T09:05:03Z");
    expect(kv["cmi.interactions.3.description"]).toBe("Başkent neresi?");
    expect(kv["cmi.interactions.3.student_response"]).toBeUndefined();
  });

  it("id her zaman İLK yazılır (bazı LMS alt elemanları önce reddeder)", () => {
    const keys = interactionElements(rec, 0, false).map(([k]) => k);
    expect(keys[0]).toBe("cmi.interactions.0.id");
    expect(keys[1]).toBe("cmi.interactions.0.type");
  });

  it("opsiyonel alanlar yoksa yazılmaz", () => {
    const kv = Object.fromEntries(
      interactionElements({ id: "q2", screenType: "fill_blank", response: "ankara" }, 1, true)
    );
    expect(kv["cmi.interactions.1.learner_response"]).toBe("ankara");
    expect(kv["cmi.interactions.1.result"]).toBeUndefined();
    expect(kv["cmi.interactions.1.latency"]).toBeUndefined();
    expect(kv["cmi.interactions.1.correct_responses.0.pattern"]).toBeUndefined();
  });

  it("weighting verilirse yazılır", () => {
    const kv = Object.fromEntries(
      interactionElements({ id: "q3", screenType: "mcq", response: ["a"], weighting: 10 }, 0, true)
    );
    expect(kv["cmi.interactions.0.weighting"]).toBe("10");
  });
});

// --------------------------------------------------------------------------- //
// S5 — suspend_data: kompakt v2 kodlaması + v1 migrasyonu + boyut regresyonu
// --------------------------------------------------------------------------- //
describe("S5 suspend_data kompakt kodlama", () => {
  // Sentetik büyük kurs: 64 ekran (uzun, gerçekçi id'ler), 30 puanlı soru — tam durum.
  const ORDER = Array.from({ length: 64 }, (_, i) =>
    `bolum_${Math.floor(i / 8)}_ekran_uzun_kimlik_${String(i).padStart(3, "0")}`);
  function bigState() {
    const st = { visited: {}, results: {}, history: [], vars: { puan: 300, can: 2 },
                 ix: {}, inext: 30, cursorId: ORDER[63], reachedEnd: true };
    ORDER.forEach((id, i) => {
      st.visited[id] = true;
      if (i < 63) st.history.push(id);
    });
    for (let q = 0; q < 30; q++) {
      const id = ORDER[q * 2 + 1];
      st.results[id] = { points: q % 3 ? 10 : 0, max: 10, ok: q % 3 !== 0, answered: true };
      st.ix[id] = q;
    }
    return st;
  }

  it("gidiş-dönüş kayıpsız (visited/results/history/vars/ix/inext/cursorId/reachedEnd)", () => {
    const st = bigState();
    const out = decodeSuspend(encodeSuspend(st, ORDER), ORDER);
    expect(out).toEqual(st);
  });

  it("kabul: 64 ekran / 30 puanlı kursta payload SCORM 1.2 sınırının altında", () => {
    const enc = encodeSuspend(bigState(), ORDER);
    expect(enc.length).toBeLessThan(SUSPEND_LIMIT_12);
    // regresyon çıpası: v1 JSON'dan belirgin küçük olmalı (kodlama gerçekten kompakt)
    const v1 = JSON.stringify(bigState());
    expect(v1.length).toBeGreaterThan(SUSPEND_LIMIT_12);   // v1 bu kursta TAŞIYORDU
    expect(enc.length).toBeLessThan(v1.length / 3);
  });

  it("eski (v1) format tanınır ve migrate edilir — yayındaki kurslarda resume bozulmaz", () => {
    const st = bigState();
    const out = decodeSuspend(JSON.stringify(st), ORDER);
    expect(out).toEqual(st);
    // çok eski v1 (history'siz fallback yazımı) → history boş diziye tamamlanır
    const old = decodeSuspend(JSON.stringify({ visited: { a: true }, results: {} }), ORDER);
    expect(old.visited).toEqual({ a: true });
    expect(old.history).toEqual([]);
  });

  it("v1 KİMLİK-anahtarlıdır → order NE OLURSA OLSUN (reorder/insert/farklı kurs) migrate eder", () => {
    const st = { visited: { a: true }, results: { a: { points: 5, max: 10, ok: false, answered: true } },
                 history: ["a"] };
    const shuffled = [...ORDER].reverse();
    const withInsert = [ORDER[0], "yeni_ekran", ...ORDER.slice(1)];
    expect(decodeSuspend(JSON.stringify(st), shuffled)).toEqual(st);
    expect(decodeSuspend(JSON.stringify(st), withInsert)).toEqual(st);
    expect(decodeSuspend(JSON.stringify(st), [])).toEqual(st);
  });

  it("boş/çöp girdi null döner (restore atlanır)", () => {
    expect(decodeSuspend("", ORDER)).toBeNull();
    expect(decodeSuspend(null, ORDER)).toBeNull();
    expect(decodeSuspend("çöp veri", ORDER)).toBeNull();
    expect(decodeSuspend("[1,2,3]", ORDER)).toBeNull();
    // fingerprint alanı yok/uyuşmuyor → temiz başlangıç (null), İSTİSNA fırlatmaz
    expect(decodeSuspend("2|bozuk", ORDER)).toBeNull();
  });

  // --------------------------------------------------------------------------- //
  // S5 (batch3 finding) — order parmak izi: reorder/insert paketi güncellendiğinde
  // pozisyonel v2 indeksleri YANLIŞ ekrana atfetmesin; eşleşmezse temiz başlangıç.
  // --------------------------------------------------------------------------- //
  it("AYNI order ile round-trip fingerprint eşleşir (regresyon çıpası)", () => {
    const st = bigState();
    const out = decodeSuspend(encodeSuspend(st, ORDER), ORDER);
    expect(out).toEqual(st);
  });

  it("YENİDEN SIRALANMIŞ order → decode temiz başlangıç (null) döner, yanlış atıf YOK", () => {
    const st = bigState();
    const encoded = encodeSuspend(st, ORDER);
    const reordered = [...ORDER].reverse();          // aynı elemanlar, farklı sıra
    expect(decodeSuspend(encoded, reordered)).toBeNull();
  });

  it("EKRAN EKLENMİŞ (araya insert) order → decode temiz başlangıç döner", () => {
    const st = bigState();
    const encoded = encodeSuspend(st, ORDER);
    const withInsert = [...ORDER.slice(0, 10), "yeni_ekran_araya", ...ORDER.slice(10)];
    expect(decodeSuspend(encoded, withInsert)).toBeNull();
  });

  it("EKRAN SİLİNMİŞ order → decode temiz başlangıç döner", () => {
    const st = bigState();
    const encoded = encodeSuspend(st, ORDER);
    const withDelete = ORDER.filter((_, i) => i !== 5);
    expect(decodeSuspend(encoded, withDelete)).toBeNull();
  });

  it("SONA EKLENMİŞ (append-only) order → decode YİNE temiz başlangıç döner (bilinçli basitlik: " +
      "append de fingerprint'i değiştirir, kayıp resume noktası yanlış atıftan güvenlidir)", () => {
    const st = bigState();
    const encoded = encodeSuspend(st, ORDER);
    const withAppend = [...ORDER, "yeni_ekran_sonda"];
    expect(decodeSuspend(encoded, withAppend)).toBeNull();
  });

  it("eski/sürüm-öncesi v2 zarfı (fingerprint alanı yok) çökmeden temiz başlangıç döner", () => {
    // fp-öncesi düzen taklidi: 9 alan (fp YOK) + boş tail — güncel decoder 9. alanı fp bekler.
    const preFingerprintRaw = "2|0||1|0|1:5:10:3||0|";
    expect(() => decodeSuspend(preFingerprintRaw, ORDER)).not.toThrow();
    expect(decodeSuspend(preFingerprintRaw, ORDER)).toBeNull();
  });

  it("order-dışı id'ler (yayın sonrası silinen ekran) tail'de KORUNUR — kayıpsızlık", () => {
    const st = { visited: { hayalet: true }, results: { hayalet: { points: 5, max: 10, ok: false, answered: true } },
                 history: [], vars: {}, ix: { hayalet: 7 }, inext: 8, cursorId: "hayalet" };
    const out = decodeSuspend(encodeSuspend(st, ORDER), ORDER);
    expect(out.visited.hayalet).toBe(true);
    expect(out.results.hayalet).toEqual({ points: 5, max: 10, ok: false, answered: true });
    expect(out.ix.hayalet).toBe(7);
    expect(out.cursorId).toBe("hayalet");
  });

  it("bilinmeyen üst-düzey durum alanları da gidiş-dönüşten sağ çıkar (gelecek alanlar)", () => {
    const st = { visited: {}, results: {}, history: [], yeniAlan: { x: 1 } };
    const out = decodeSuspend(encodeSuspend(st, ORDER), ORDER);
    expect(out.yeniAlan).toEqual({ x: 1 });
  });

  it("vars içindeki '|' karakteri formatı bozmaz (tail split-limit)", () => {
    const st = { visited: {}, results: {}, history: [], vars: { ad: "a|b|c" } };
    const out = decodeSuspend(encodeSuspend(st, ORDER), ORDER);
    expect(out.vars.ad).toBe("a|b|c");
  });

  it("vars boşsa decode vars ÜRETMEZ → runtime COURSE varsayılanlarını kurabilir", () => {
    const st = { visited: {}, results: {}, history: [], vars: {} };
    const out = decodeSuspend(encodeSuspend(st, ORDER), ORDER);
    expect(out.vars).toBeUndefined();
  });

  it("encodeSuspendFit: limit aşımında ÖNCE history düşer; vars ve ix korunur", () => {
    const st = bigState();
    // yapay dar limit → history düşmeli
    const full = encodeSuspend(st, ORDER);
    const fit = encodeSuspendFit(st, ORDER, full.length - 10);
    expect(fit.historyDropped).toBe(true);
    const out = decodeSuspend(fit.data, ORDER);
    expect(out.history).toEqual([]);
    expect(out.ix).toEqual(st.ix);          // v1 fallback ix'i atardı → kopya interaction bug'ı; v2 korur
    expect(out.vars).toEqual(st.vars);
    expect(fit.truncated).toBe(false);
  });

  it("encodeSuspendFit: history düştükten sonra bile sığmıyorsa truncated bayrağı kalkar", () => {
    const st = bigState();
    const fit = encodeSuspendFit(st, ORDER, 32);
    expect(fit.truncated).toBe(true);
    expect(decodeSuspend(fit.data, ORDER)).not.toBeNull();  // veri yine de çözülebilir
  });

  it("sınır sabitleri sürüme göre seçilir", () => {
    expect(suspendLimit(false)).toBe(SUSPEND_LIMIT_12);
    expect(suspendLimit(true)).toBe(SUSPEND_LIMIT_2004);
    expect(SUSPEND_LIMIT_12).toBe(4096);
  });
});

// --------------------------------------------------------------------------- //
// S5 (2.2c) — yazma hatası / kırpma görünürlüğü (saf karar katmanı)
// --------------------------------------------------------------------------- //
// --------------------------------------------------------------------------- //
// F2 (#113) — exploration girdi saklama: xp haritası (store_key → değer), v2 kuyruk JSON'unda
// --------------------------------------------------------------------------- //
describe("F2 exploration xp codec (setExploration/getExploration + v2 kuyruk)", () => {
  const ORDER = ["giris", "kesif", "acikla"];

  it("setExploration saklar, getExploration okur; eksik anahtar boş string döner", () => {
    const st = { visited: {}, results: {}, history: [] };
    const r = setExploration(st, "kesif_tahmin", "yüzer");
    expect(r.truncated).toBe(false);
    expect(r.value).toBe("yüzer");
    expect(getExploration(st, "kesif_tahmin")).toBe("yüzer");
    expect(getExploration(st, "yok")).toBe("");
    expect(getExploration(null, "yok")).toBe("");
  });

  it("değer 500 karakterde KIRPILIR (truncated bayrağıyla) — suspend bütçesi", () => {
    const st = { visited: {}, results: {}, history: [] };
    const long = "a".repeat(EXPLORATION_VALUE_MAX + 100);
    const r = setExploration(st, "k", long);
    expect(EXPLORATION_VALUE_MAX).toBe(500);
    expect(r.truncated).toBe(true);
    expect(r.value.length).toBe(EXPLORATION_VALUE_MAX);
    expect(getExploration(st, "k").length).toBe(EXPLORATION_VALUE_MAX);
  });

  it("string olmayan değerler string'e çevrilir; null/undefined boş sayılır", () => {
    const st = {};
    expect(setExploration(st, "n", 42).value).toBe("42");
    expect(setExploration(st, "b", null).value).toBe("");
    expect(getExploration(st, "n")).toBe("42");
  });

  it("xp haritası v2 zarfının kuyruk JSON'unda gidiş-dönüş KAYIPSIZ", () => {
    const st = { visited: { kesif: true }, results: {}, history: ["giris"], inext: 0,
                 cursorId: "acikla", xp: { kesif_tahmin: "yüzer", deneme_notu: "kütle 2× → battı | not" } };
    const enc = encodeSuspend(st, ORDER);
    expect(enc.slice(0, 2)).toBe("2|");
    const out = decodeSuspend(enc, ORDER);
    expect(out.xp).toEqual({ kesif_tahmin: "yüzer", deneme_notu: "kütle 2× → battı | not" });
    expect(out).toEqual(st);   // xp diğer alanları bozmadan taşınır
  });

  it("boş xp haritası kuyruğu ŞİŞİRMEZ (tail üretilmez)", () => {
    const bare = { visited: {}, results: {}, history: [] };
    expect(encodeSuspend({ ...bare, xp: {} }, ORDER)).toBe(encodeSuspend(bare, ORDER));
  });

  it("xp, history düşürmek (rung 1) YETERLİYSE korunur; ancak rung 2'de düşer (Faz 4-ek merdiveni)", () => {
    const order = Array.from({ length: 40 }, (_, i) => `ekran_uzun_kimlik_${i}`);
    const st = { visited: {}, results: {}, history: [], xp: {} };
    order.forEach((id) => { st.visited[id] = true; st.history.push(id); });
    for (let i = 0; i < 6; i++) setExploration(st, `kesif_${i}`, "x".repeat(500));
    const full = encodeSuspendFit(st, order, 100000).bytes;
    // rung 1 yeterli olacak bütçe: history (~40 indeks) düşünce sığar → xp KORUNUR
    const fit1 = encodeSuspendFit(st, order, full - 10);
    expect(fit1.rung).toBe(1);
    expect(fit1.historyDropped).toBe(true);
    const out1 = decodeSuspend(fit1.data, order);
    expect(Object.keys(out1.xp)).toHaveLength(6);
    expect(out1.xp.kesif_0).toBe("x".repeat(500));
    // daha dar bütçe: öğrenen serbest metni (xp) rung 2'de düşer — cevap/pozisyondan ÖNCE
    const fit2 = encodeSuspendFit(st, order, 3000);
    expect(fit2.rung).toBe(2);
    expect(decodeSuspend(fit2.data, order).xp).toBeUndefined();
  });

  it("v1 (eski JSON) migrasyonu xp'yi olduğu gibi taşır", () => {
    const st = { visited: { a: true }, results: {}, history: [], xp: { k: "v" } };
    expect(decodeSuspend(JSON.stringify(st), ORDER).xp).toEqual({ k: "v" });
  });
});

describe("S5 suspend_data yazma görünürlüğü", () => {
  it("başarısız sSet (mock API 'false' döner) uyarı yolunu tetikler", () => {
    // sahte 1.2 API: suspend_data yazımını reddeder (SPM aşımı senaryosu)
    const mockApi = { LMSSetValue: () => "false" };
    const ok = setResultOk(mockApi.LMSSetValue("cmi.suspend_data", "x".repeat(5000)));
    expect(ok).toBe(false);
    const issues = suspendWriteIssues({ ok, size: 5000, limit: SUSPEND_LIMIT_12, truncated: false });
    expect(issues).toEqual([{ kind: "write_failed", size: 5000, limit: 4096 }]);
  });

  it("başarılı yazım + kırpma yok → hiç uyarı üretilmez", () => {
    const mockApi = { LMSSetValue: () => "true" };
    const ok = setResultOk(mockApi.LMSSetValue("cmi.suspend_data", "kısa"));
    expect(ok).toBe(true);
    expect(suspendWriteIssues({ ok, size: 4, limit: SUSPEND_LIMIT_12, truncated: false })).toEqual([]);
  });

  it("kırpma (fit sığdıramadı) yazım başarılı olsa bile raporlanır", () => {
    const issues = suspendWriteIssues({ ok: true, size: 4400, limit: 4096, truncated: true });
    expect(issues).toEqual([{ kind: "truncated", size: 4400, limit: 4096 }]);
  });

  it("hem kırpma hem yazma hatası → iki ayrı uyarı", () => {
    const kinds = suspendWriteIssues({ ok: false, size: 4400, limit: 4096, truncated: true }).map(i => i.kind);
    expect(kinds).toEqual(["truncated", "write_failed"]);
  });

  it("belirsiz API dönüşleri (boş/undefined/true) başarısızlık SAYILMAZ — uyarı spam'i yok", () => {
    expect(setResultOk("true")).toBe(true);
    expect(setResultOk("")).toBe(true);
    expect(setResultOk(undefined)).toBe(true);
    expect(setResultOk(true)).toBe(true);
    expect(setResultOk(false)).toBe(false);
    expect(setResultOk("false")).toBe(false);
  });
});

// --------------------------------------------------------------------------- //
// S2 — cmi.objectives.* (hedef toplama + eleman üretimi)
// --------------------------------------------------------------------------- //
describe("S2 aggregateObjectives", () => {
  const OBJ = ["o1", "o2", "o3"];
  const MAP = { q1: ["o1"], q2: ["o1"], q3: ["o2"], q4: ["o2", "o3"] };

  it("hedef başına doğru/toplam → scaled; sıra HER ZAMAN kurs hedef sırası", () => {
    const res = {
      q1: { points: 10, max: 10, ok: true, answered: true },
      q2: { points: 0, max: 10, ok: false, answered: true },
      q4: { points: 10, max: 10, ok: true, answered: true },
    };
    const out = aggregateObjectives(OBJ, MAP, res);
    expect(out.map((a) => a.id)).toEqual(["o1", "o2", "o3"]);
    expect(out[0]).toEqual({ id: "o1", correct: 1, total: 2, answered: 2, scaled: 0.5 });
    expect(out[1]).toEqual({ id: "o2", correct: 1, total: 2, answered: 1, scaled: 0.5 });
    expect(out[2]).toEqual({ id: "o3", correct: 1, total: 1, answered: 1, scaled: 1 });
  });

  it("çok-hedefli ekran her bağlı hedefte sayılır (q4 → o2 VE o3)", () => {
    const out = aggregateObjectives(OBJ, MAP, {});
    expect(out.find((a) => a.id === "o2").total).toBe(2);
    expect(out.find((a) => a.id === "o3").total).toBe(1);
  });

  it("bağsız hedef kayıt ÜRETMEZ (politika: lint WARN'lık yazarlık hatası)", () => {
    const out = aggregateObjectives(["o1", "yalniz"], { q1: ["o1"] }, {});
    expect(out.map((a) => a.id)).toEqual(["o1"]);
  });

  it("hiç cevap yokken kayıtlar yine üretilir (answered=0, scaled=0)", () => {
    const out = aggregateObjectives(OBJ, MAP, {});
    expect(out).toHaveLength(3);
    out.forEach((a) => { expect(a.answered).toBe(0); expect(a.scaled).toBe(0); });
  });

  it("boş girdiler güvenli: hedef yok / harita yok → boş dizi", () => {
    expect(aggregateObjectives([], {}, {})).toEqual([]);
    expect(aggregateObjectives(undefined, undefined, undefined)).toEqual([]);
    expect(aggregateObjectives(["o1"], {}, {})).toEqual([]);
  });

  it("haritadaki bilinmeyen hedef id'si (kursta tanımsız) sessizce yok sayılır", () => {
    const out = aggregateObjectives(["o1"], { q1: ["o1", "hayalet"] }, {});
    expect(out.map((a) => a.id)).toEqual(["o1"]);
  });
});

describe("S2 objectiveIndices — LMS pre-populate ile çarpışmasız deterministik indeks", () => {
  it("boş LMS: kurs sırasına göre 0..n-1", () => {
    expect(objectiveIndices([], ["o1", "o2", "o3"])).toEqual({ o1: 0, o2: 1, o3: 2 });
  });

  it("manifest'ten FARKLI sırada pre-populate edilmiş id kendi indeksini korur", () => {
    expect(objectiveIndices(["o3", "o1"], ["o1", "o2", "o3"])).toEqual({ o1: 1, o2: 2, o3: 0 });
  });

  it("LMS'te alakasız kayıt varsa yeniler sona eklenir (üzerine yazılmaz)", () => {
    expect(objectiveIndices(["lms_obj"], ["o1", "o2"])).toEqual({ o1: 1, o2: 2 });
  });
});

describe("S2 objectiveElements — 1.2 ↔ 2004 sözlük/eleman farkları", () => {
  const done = { id: "o1", correct: 2, total: 3, answered: 3, scaled: 2 / 3 };
  const part = { id: "o1", correct: 1, total: 3, answered: 1, scaled: 1 / 3 };
  const none = { id: "o1", correct: 0, total: 3, answered: 0, scaled: 0 };

  it("1.2: id + score.raw/min/max (0-100) + status; id İLK", () => {
    const kv = objectiveElements(done, 0, false, 0.6);
    expect(kv[0]).toEqual(["cmi.objectives.0.id", "o1"]);
    const o = Object.fromEntries(kv);
    expect(o["cmi.objectives.0.score.raw"]).toBe("67");
    expect(o["cmi.objectives.0.score.min"]).toBe("0");
    expect(o["cmi.objectives.0.score.max"]).toBe("100");
    expect(o["cmi.objectives.0.status"]).toBe("passed");
    expect(o["cmi.objectives.0.score.scaled"]).toBeUndefined();
    expect(o["cmi.objectives.0.success_status"]).toBeUndefined();
  });

  it("2004: id + score.scaled (0-1) + success_status + completion_status", () => {
    const o = Object.fromEntries(objectiveElements(done, 2, true, 0.7));
    expect(o["cmi.objectives.2.id"]).toBe("o1");
    expect(o["cmi.objectives.2.score.scaled"]).toBe("0.6667");
    expect(o["cmi.objectives.2.success_status"]).toBe("failed");   // 0.667 < 0.7
    expect(o["cmi.objectives.2.completion_status"]).toBe("completed");
    expect(o["cmi.objectives.2.score.raw"]).toBeUndefined();
    expect(o["cmi.objectives.2.status"]).toBeUndefined();
  });

  it("kısmen cevaplanmış: 1.2 incomplete, 2004 unknown+incomplete; skor yazılır", () => {
    const o12 = Object.fromEntries(objectiveElements(part, 0, false, 0.6));
    expect(o12["cmi.objectives.0.status"]).toBe("incomplete");
    expect(o12["cmi.objectives.0.score.raw"]).toBe("33");
    const o04 = Object.fromEntries(objectiveElements(part, 0, true, 0.6));
    expect(o04["cmi.objectives.0.success_status"]).toBe("unknown");
    expect(o04["cmi.objectives.0.completion_status"]).toBe("incomplete");
  });

  it("hiç denenmemiş: skor YAZILMAZ; 1.2 'not attempted', 2004 unknown+'not attempted'", () => {
    const kv12 = objectiveElements(none, 0, false, 0.6);
    expect(Object.fromEntries(kv12)["cmi.objectives.0.status"]).toBe("not attempted");
    expect(kv12.some(([k]) => k.indexOf(".score.") >= 0)).toBe(false);
    const o04 = Object.fromEntries(objectiveElements(none, 0, true, 0.6));
    expect(o04["cmi.objectives.0.success_status"]).toBe("unknown");
    expect(o04["cmi.objectives.0.completion_status"]).toBe("not attempted");
    expect(o04["cmi.objectives.0.score.scaled"]).toBeUndefined();
  });

  it("includeId=false: id çifti atlanır (LMS'te aynı indekste id zaten kayıtlı)", () => {
    const kv = objectiveElements(done, 0, true, 0.6, false);
    expect(kv.some(([k]) => k === "cmi.objectives.0.id")).toBe(false);
    expect(kv.some(([k]) => k === "cmi.objectives.0.score.scaled")).toBe(true);
  });

  it("geçme eşiği tam sınırda geçer (scaled >= ratio)", () => {
    const agg = { id: "o", correct: 3, total: 5, answered: 5, scaled: 0.6 };
    expect(Object.fromEntries(objectiveElements(agg, 0, false, 0.6))["cmi.objectives.0.status"]).toBe("passed");
  });
});

// --------------------------------------------------------------------------- //
// Faz 4-ek — UTF-8 bayt ölçümü + çalışma bütçesi
// --------------------------------------------------------------------------- //
describe("Faz 4-ek: byteLen/byteSlice (UTF-8 bayt ölçümü)", () => {
  it("ASCII'de bayt = karakter; Türkçe harfler 2 bayt (ç ğ ı ö ş ü tuzağı)", () => {
    expect(byteLen("abc")).toBe(3);
    expect(byteLen("çğıöşü")).toBe(12);        // 6 karakter, 12 bayt
    expect(byteLen("öğrenci")).toBe(9);        // ö+ğ 2'şer bayt
    expect(byteLen("")).toBe(0);
    expect(byteLen(null)).toBe(0);
  });

  it("surrogate çifti (emoji) 4 bayt sayılır", () => {
    expect(byteLen("😀")).toBe(4);
    expect(byteLen("a😀b")).toBe(6);
  });

  it("byteSlice karakter ortasından KESMEZ (Türkçe harf/emoji bölünmez)", () => {
    expect(byteSlice("çç", 3)).toBe("ç");      // 2. ç 3. bayta sığmaz → düşer
    expect(byteSlice("çç", 4)).toBe("çç");
    expect(byteSlice("a😀b", 4)).toBe("a");    // emoji 4 bayt → 4 bütçesine a'dan sonra sığmaz
    expect(byteSlice("abc", 10)).toBe("abc");
    expect(byteLen(byteSlice("ığüşöç yüzer".repeat(50), 500))).toBeLessThanOrEqual(500);
  });

  it("çalışma bütçesi: 1.2'de 3500 bayt; 2004'te aynı rezerv oranı", () => {
    expect(SUSPEND_BUDGET_12).toBe(3500);
    expect(suspendBudget(false)).toBe(3500);
    expect(suspendBudget(true)).toBe(Math.floor(64000 * 3500 / 4096));
    expect(suspendBudget(true)).toBeLessThan(SUSPEND_LIMIT_2004);
  });

  it("setExploration 500 UTF-8 BAYTTA kırpar (karakterde değil)", () => {
    const st = {};
    const turkce = "ç".repeat(400);                        // 400 karakter = 800 bayt
    const r = setExploration(st, "k", turkce);
    expect(r.truncated).toBe(true);
    expect(byteLen(r.value)).toBeLessThanOrEqual(500);
    expect(r.value).toBe("ç".repeat(250));                 // 250 × 2 bayt = 500
    const ascii = "a".repeat(500);                         // 500 bayt → tam sığar
    expect(setExploration(st, "k2", ascii).truncated).toBe(false);
  });
});

// --------------------------------------------------------------------------- //
// Faz 4-ek — KIRPMA MERDİVENİ (taşma önceliği): pozisyon > hedef/skor > cevaplar > serbest metin
// --------------------------------------------------------------------------- //
describe("Faz 4-ek: encodeSuspendFit kırpma merdiveni", () => {
  const ORDER = Array.from({ length: 40 }, (_, i) => `unite_${Math.floor(i / 10)}_ekran_${String(i).padStart(2, "0")}`);
  const OBJ_IDS = ["o1", "o2"];
  const OBJ_MAP = {};
  function ladderState() {
    const st = { visited: {}, results: {}, history: [], ix: {}, inext: 0,
                 vars: { puan: 120, can: 2 }, xp: {}, cursorId: ORDER[25], reachedEnd: false };
    ORDER.forEach((id, i) => {
      st.visited[id] = true;
      if (i > 0) st.history.push(ORDER[i - 1]);
      if (i % 2 === 0) {
        st.results[id] = { points: 10, max: 10, ok: i % 4 === 0, answered: true };
        st.ix[id] = st.inext++;
        OBJ_MAP[id] = [i < 20 ? "o1" : "o2"];
      }
    });
    for (let k = 0; k < 4; k++) st.xp[`kesif_${k}`] = "gözlemim şu: yüzer çünkü yoğunluk ".repeat(8);
    return st;
  }
  const META = { node: "u2", cv: 7, objIds: OBJ_IDS, objMap: OBJ_MAP };

  it("bütçeye sığıyorsa merdiven HİÇ çalışmaz: t yazılmaz, rung=0", () => {
    const st = ladderState();
    const fit = encodeSuspendFit(st, ORDER, 100000, META);
    expect(fit.rung).toBe(0);
    expect(fit.truncated).toBe(false);
    const out = decodeSuspend(fit.data, ORDER);
    expect(out.t).toBeUndefined();
    expect(out.results).toEqual(st.results);
    expect(out.xp).toEqual(st.xp);
  });

  it("rung 1: önce history düşer; xp/cevaplar/pozisyon KORUNUR; t=1 yazılır+okunur", () => {
    const st = ladderState();
    const full = encodeSuspendFit(st, ORDER, 100000, META).bytes;
    const fit = encodeSuspendFit(st, ORDER, full - 1, META);
    expect(fit.rung).toBe(1);
    const out = decodeSuspend(fit.data, ORDER);
    expect(out.t).toBe(1);
    expect(out.history).toEqual([]);
    expect(out.xp).toEqual(st.xp);
    expect(out.results).toEqual(st.results);
    expect(out.vars).toEqual(st.vars);
    expect(out.cursorId).toBe(ORDER[25]);
  });

  it("rung 2: sonra öğrenen serbest metni (xp) düşer; cevaplar hâlâ KORUNUR", () => {
    const st = ladderState();
    const r1 = encodeSuspendFit(st, ORDER, encodeSuspendFit(st, ORDER, 100000, META).bytes - 1, META);
    const fit = encodeSuspendFit(st, ORDER, r1.bytes - 1, META);
    expect(fit.rung).toBe(2);
    const out = decodeSuspend(fit.data, ORDER);
    expect(out.t).toBe(2);
    expect(out.xp).toBeUndefined();
    expect(out.results).toEqual(st.results);
    expect(out.ix).toEqual(st.ix);
    expect(out.cursorId).toBe(ORDER[25]);
  });

  it("rung 3: sayfa cevapları düşer ama HEDEF/SKOR durumu g/e tabanı olarak YAŞAR", () => {
    const st = ladderState();
    const r2bytes = (() => {
      let b = encodeSuspendFit(st, ORDER, 100000, META).bytes;
      let f = encodeSuspendFit(st, ORDER, b - 1, META);          // rung 1
      f = encodeSuspendFit(st, ORDER, f.bytes - 1, META);        // rung 2
      return f.bytes;
    })();
    const fit = encodeSuspendFit(st, ORDER, r2bytes - 1, META);
    expect(fit.rung).toBe(3);
    const out = decodeSuspend(fit.data, ORDER);
    expect(out.t).toBe(3);
    expect(out.results).toEqual({});                     // cevaplar düştü
    expect(out.ix).toBeUndefined();
    expect(out.vars).toBeUndefined();
    // hedef tamamlanma/skor tabanı: o1 = 10 ekran (hepsi cevaplı), o2 = 10 ekran
    expect(out.g.o1).toEqual([5, 10, 10]);               // i%4 doğru → 20'ye kadar 5 doğru
    expect(out.g.o2).toEqual([5, 10, 10]);
    expect(out.e).toBe(200);                             // 20 cevaplı ekran × 10 puan
    expect(out.visited).toEqual(st.visited);             // visited rung 3'te KORUNUR
    expect(out.cursorId).toBe(ORDER[25]);                // pozisyon ASLA düşmez
  });

  it("rung 4 (son çare): yalnız pozisyon — cursor korunur, visited lineer yaklaşımla kurulur", () => {
    const st = ladderState();
    const fit = encodeSuspendFit(st, ORDER, 120, META);
    expect(fit.rung).toBe(4);
    const out = decodeSuspend(fit.data, ORDER);
    expect(out.t).toBe(4);
    expect(out.cursorId).toBe(ORDER[25]);                // POZİSYON SON BASAMAKTA BİLE SAĞ
    expect(out.g).toBeUndefined();
    // lineer yaklaşım: cursor'a kadarki ekranlar visited (kilit tuzağı yok); cursor değil
    for (let i = 0; i < 25; i++) expect(out.visited[ORDER[i]]).toBe(true);
    expect(out.visited[ORDER[25]]).toBeUndefined();
  });

  it("her basamakta YENİDEN ölçülür ve sığdığı yerde durur (alt basamağa inilmez)", () => {
    const st = ladderState();
    const r1 = encodeSuspendFit(st, ORDER, encodeSuspendFit(st, ORDER, 100000, META).bytes - 1, META);
    expect(r1.rung).toBe(1);
    expect(decodeSuspend(r1.data, ORDER).xp).toEqual(st.xp);   // rung 1 yeterliyken xp düşmedi
  });

  it("TÜRKÇE-YOĞUN tuzak: karakterce sığan ama BAYTÇA taşan payload kırpılır", () => {
    const st = { visited: {}, results: {}, history: [], cursorId: "e1",
                 xp: { not_1: "ğüşıöç".repeat(300) } };          // 1800 kchar = 3600 bayt
    const order = ["e1", "e2"];
    const enc = encodeSuspend(st, order, { cv: 1 });
    expect(enc.length).toBeLessThan(3500);               // karakter ölçümü YANILTICI: sığıyor görünür
    expect(byteLen(enc)).toBeGreaterThan(3500);          // gerçek UTF-8 boyutu taşıyor
    const fit = encodeSuspendFit(st, order, 3500, { cv: 1 });
    expect(fit.rung).toBeGreaterThan(0);                 // .length ile ölçülseydi rung=0 kalırdı
    expect(byteLen(fit.data)).toBeLessThanOrEqual(3500);
    expect(fit.truncated).toBe(false);
  });

  it("zarfın kendi alanları ASCII'dir (Türkçe yalnız tail serbest metninde olabilir)", () => {
    const st = ladderState();
    delete st.xp; delete st.vars;                        // serbest metin kanalları boş
    const enc = encodeSuspend(st, ORDER, META);
    // eslint-disable-next-line no-control-regex
    expect(/^[\x00-\x7F]*$/.test(enc)).toBe(true);       // saf ASCII → bayt = karakter
    expect(byteLen(enc)).toBe(enc.length);
  });

  it("suspendWriteIssues rung'u taşır (verilmişse) — konsol uyarısı basamağı raporlar", () => {
    const issues = suspendWriteIssues({ ok: true, size: 3600, limit: 3500, truncated: true, rung: 4 });
    expect(issues).toEqual([{ kind: "truncated", size: 3600, limit: 3500, rung: 4 }]);
    // rung verilmezse alan eklenmez (geriye uyum)
    expect(suspendWriteIssues({ ok: true, size: 10, limit: 3500, truncated: true }))
      .toEqual([{ kind: "truncated", size: 10, limit: 3500 }]);
  });

  it("KAYIP SESSİZ KALMAZ: merdiven veri düşürüp sığdırdıysa (rung>0) 'trimmed' uyarısı üretilir", () => {
    // xAPI/LRS'e BAĞIMLI DEĞİL: bu saf karar katmanıdır; runtime bunu HER ZAMAN console.warn'a,
    // xAPI'ye yalnız LRS konfigürasyonu varsa EK olarak çevirir (templates suspendTrouble).
    const issues = suspendWriteIssues({ ok: true, size: 3400, limit: 3500, truncated: false, rung: 2 });
    expect(issues).toEqual([{ kind: "trimmed", size: 3400, limit: 3500, rung: 2 }]);
    // sığdı + kayıp yok → uyarı yok
    expect(suspendWriteIssues({ ok: true, size: 900, limit: 3500, truncated: false, rung: 0 })).toEqual([]);
  });

  it("mergeObjectiveSnapshot: canlı cevap varsa canlı kazanır, yoksa g tabanı (skor geriye gitmez)", () => {
    const g = { o1: [5, 10, 10], o2: [3, 10, 10] };
    const live = [{ id: "o1", correct: 1, total: 10, answered: 1, scaled: 0.1 }];
    const out = mergeObjectiveSnapshot(live, ["o1", "o2"], g);
    expect(out[0]).toEqual({ id: "o1", correct: 1, total: 10, answered: 1, scaled: 0.1 });
    expect(out[1]).toEqual({ id: "o2", correct: 3, total: 10, answered: 10, scaled: 0.3 });
    expect(mergeObjectiveSnapshot(live, ["o1"], null)).toBe(live);
  });
});

// --------------------------------------------------------------------------- //
// Faz 4-ek — REPUBLISH-RESUME okuma merdiveni (resumeSuspend): orderFp × v etkileşimi
// --------------------------------------------------------------------------- //
describe("Faz 4-ek: resumeSuspend republish merdiveni", () => {
  const ORDER = ["t1", "c1", "c2", "c3", "s1"];
  const SN = { t1: "u1", c1: "u1", c2: "b2", c3: "b2" };       // s1 düğümsüz
  function state() {
    const st = { visited: { t1: true, c1: true }, results: { c1: { points: 10, max: 10, ok: true, answered: true } },
                 history: ["t1", "c1"], ix: { c1: 0 }, inext: 1, cursorId: "c2",
                 vars: { puan: 10 }, xp: { kesif: "tahminim bu" } };
    return st;
  }
  const META = { node: "b2", cv: 41 };

  it("v/order eşleşir → TAM resume, SESSİZ (bildirim yok)", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const r = resumeSuspend(raw, ORDER, { cv: 41, screenNode: SN });
    expect(r.mode).toBe("full");
    expect(r.notice).toBe(false);
    expect(r.state.cursorId).toBe("c2");
    expect(r.state.results.c1.points).toBe(10);
    expect(r.state.history).toEqual(["t1", "c1"]);
  });

  it("order değişti + düğüm yaşıyor + ekran yaşıyor → ekrana devam, SESSİZ", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const newOrder = ["t1", "yeni", "c1", "c2", "c3", "s1"];   // araya ekran girdi (fp uyuşmaz)
    const newSN = { ...SN, yeni: "u1" };
    const r = resumeSuspend(raw, newOrder, { cv: 42, screenNode: newSN });
    expect(r.mode).toBe("node");
    expect(r.notice).toBe(false);
    expect(r.target).toBe("c2");
    expect(r.state.cursorId).toBe("c2");
  });

  it("düğüm yaşıyor ama ekran silinmiş → düğümün YENİ ilk ekranına devam, SESSİZ", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const newOrder = ["t1", "c1", "c9", "c3", "s1"];           // c2 silindi; b2'de c9+c3 var
    const newSN = { t1: "u1", c1: "u1", c9: "b2", c3: "b2" };
    const r = resumeSuspend(raw, newOrder, { cv: 42, screenNode: newSN });
    expect(r.mode).toBe("node");
    expect(r.target).toBe("c9");
    expect(r.notice).toBe(false);
  });

  it("DÜĞÜM SİLİNMİŞ ama ekran yaşıyor → ekranın YENİ düğümünde devam + BİLDİRİM", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const newOrder = ["t1", "c1", "c2", "s1"];                 // c3 gitti, b2 düğümü kalktı
    const newSN = { t1: "u1", c1: "u1", c2: "u9" };            // c2 artık u9 düğümünde
    const r = resumeSuspend(raw, newOrder, { cv: 42, screenNode: newSN });
    expect(r.mode).toBe("screen");
    expect(r.target).toBe("c2");
    expect(r.notice).toBe(true);
  });

  it("İKİSİ DE gitmiş → kurs başı + BİLDİRİM (sessiz sıfırlama YOK); kimlik-tabanlı veri yaşar", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const newOrder = ["a1", "a2", "a3"];                       // tamamen yeni içerik
    const r = resumeSuspend(raw, newOrder, { cv: 99, screenNode: { a1: "x" } });
    expect(r.mode).toBe("start");
    expect(r.notice).toBe(true);
    expect(r.state.cursorId).toBeUndefined();                  // baştan başlar
    expect(r.state.vars).toEqual({ puan: 10 });                // id-tabanlı alanlar kurtuldu
    expect(r.state.xp).toEqual({ kesif: "tahminim bu" });
    expect(r.state.inext).toBe(1);                             // LMS interaction sayacı korunur
  });

  it("POZİSYONEL YANLIŞ ATIF YOK: order değişince indeks-tabanlı results/visited/history atılır", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const newOrder = ["c9", "c1", "c2", "t1"];                 // reorder + değişim
    const r = resumeSuspend(raw, newOrder, { cv: 42, screenNode: { c9: "b2", c2: "b2" } });
    // eski order'da c1 indeks-tabanlı cevaplıydı; yeni order'a karşı indeks çözülemez → results boş
    expect(r.state.results).toEqual({});
    expect(r.state.history).toEqual([]);
    // ama pozisyon kimlik-tabanlı z'den geldi: c2 (b2 yaşıyor) → sessiz düğüm devamı
    expect(r.mode).toBe("node");
    expect(r.target).toBe("c2");
  });

  it("fallback devamda hedefe kadarki ekranlar lineer yaklaşımla visited (kilit tuzağı yok)", () => {
    const raw = encodeSuspend(state(), ORDER, META);
    const newOrder = ["t1", "yeni", "c1", "c2", "c3", "s1"];
    const r = resumeSuspend(raw, newOrder, { cv: 42, screenNode: { ...SN, yeni: "u1" } });
    expect(r.state.visited).toEqual({ t1: true, yeni: true, c1: true });
  });

  it("POZİSYON KAYDI OLMAYAN eski v2 payload'u order değişiminde başa döner + BİLDİRİM", () => {
    // Faz 4-ek ÖNCESİ üretilmiş payload taklidi: meta'sız encode (z yok)
    const raw = encodeSuspend(state(), ORDER);
    expect(raw.indexOf('"z"')).toBeGreaterThan(-1);            // cursorId varsa z.s yazılır (yeni encoder)
    // gerçek eski payload'da z hiç yoktu → elle sök
    const legacy = raw.replace(/"z":\{[^}]*\},?/, "").replace(/,\}/, "}");
    const r = resumeSuspend(legacy, ["x1", "x2"], { cv: 5, screenNode: {} });
    expect(r.mode).toBe("start");
    expect(r.notice).toBe(true);
  });

  it("v1 (kimlik-anahtarlı) payload TAM resume sayılır — reorder'a zaten bağışık", () => {
    const st = { visited: { a: true }, results: {}, history: [], cursorId: "a" };
    const r = resumeSuspend(JSON.stringify(st), ["b", "a"], { cv: 1, screenNode: {} });
    expect(r.mode).toBe("full");
    expect(r.notice).toBe(false);
    expect(r.state.cursorId).toBe("a");
  });

  it("boş/çöp girdi mode=none (bildirimsiz temiz başlangıç)", () => {
    expect(resumeSuspend("", ORDER, {}).mode).toBe("none");
    expect(resumeSuspend(null, ORDER, {}).mode).toBe("none");
    expect(resumeSuspend("çöp", ORDER, {}).mode).toBe("none");
  });
});
