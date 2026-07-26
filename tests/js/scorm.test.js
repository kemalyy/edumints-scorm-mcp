import { describe, it, expect } from "vitest";
import {
  duration12, duration2004, sessionTime, timestamp12, timestamp2004,
  exitValue, shouldRestore,
  INTERACTION_TYPES, interactionType, sanitizeId, resultValue, formatResponse,
  interactionElements,
  SUSPEND_LIMIT_12, SUSPEND_LIMIT_2004, suspendLimit,
  encodeSuspend, decodeSuspend, encodeSuspendFit,
  setResultOk, suspendWriteIssues,
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
