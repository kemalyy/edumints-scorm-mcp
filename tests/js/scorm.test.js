import { describe, it, expect } from "vitest";
import {
  duration12, duration2004, sessionTime, timestamp12, timestamp2004,
  exitValue, shouldRestore,
  INTERACTION_TYPES, interactionType, sanitizeId, resultValue, formatResponse,
  interactionElements,
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
