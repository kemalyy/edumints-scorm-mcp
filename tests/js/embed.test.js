import { describe, it, expect, vi } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import * as EMB from "../../components/engine/embed.js";
import { bridgeToScorm, embedStateFromMsg, embedWrites, gatesPending, holdBackWrites, wrapEvaluate,
         isCompletionAssertion, wrapSet, isTransientExit, isGatedCompletionWrite }
  from "../../components/engine/embed.js";
import { encodeSuspend, decodeSuspend } from "../../components/engine/scorm.js";

describe("bridgeToScorm", () => {
  it("maps complete (1.2 + 2004)", () => {
    expect(bridgeToScorm({ scorm: "complete" }, false)).toEqual([
      { key: "cmi.core.lesson_status", value: "completed" },
    ]);
    expect(bridgeToScorm({ scorm: "complete" }, true)).toEqual([
      { key: "cmi.completion_status", value: "completed" },
    ]);
  });
  it("maps setScore with clamp + scaled(2004)", () => {
    expect(bridgeToScorm({ scorm: "setScore", value: 85 }, false)).toEqual([
      { key: "cmi.core.score.raw", value: "85" },
    ]);
    const s = bridgeToScorm({ scorm: "setScore", value: 150 }, true);
    expect(s).toContainEqual({ key: "cmi.score.raw", value: "100" });
    expect(s).toContainEqual({ key: "cmi.score.scaled", value: "1.0000" });
  });
  it("maps passed/failed", () => {
    expect(bridgeToScorm({ scorm: "passed" }, true)).toContainEqual({ key: "cmi.success_status", value: "passed" });
    expect(bridgeToScorm({ scorm: "failed" }, false)).toContainEqual({ key: "cmi.core.lesson_status", value: "failed" });
  });
  it("ignores invalid/unknown", () => {
    expect(bridgeToScorm(null, false)).toEqual([]);
    expect(bridgeToScorm({ scorm: "nope" }, false)).toEqual([]);
    expect(bridgeToScorm({ scorm: "setScore", value: "abc" }, false)).toEqual([]);
  });
  // fix round 1 / MINOR 4 — yalnız gerçek `number` kabul edilir (zımni tür dönüşümü reddedilir).
  it("rejects non-number setScore values (null, Infinity, array, bool)", () => {
    expect(bridgeToScorm({ scorm: "setScore", value: null }, false)).toEqual([]);
    expect(bridgeToScorm({ scorm: "setScore", value: Infinity }, true)).toEqual([]);
    expect(bridgeToScorm({ scorm: "setScore", value: [] }, false)).toEqual([]);
    expect(bridgeToScorm({ scorm: "setScore", value: true }, false)).toEqual([]);
  });
  // fix round 1 / MINOR 6 — setStatus daha önce hiç test edilmiyordu (tek serbest string girdi).
  describe("setStatus", () => {
    it("accepts a whitelisted value (1.2 → lesson_status verbatim)", () => {
      expect(bridgeToScorm({ scorm: "setStatus", value: "browsed" }, false)).toEqual([
        { key: "cmi.core.lesson_status", value: "browsed" },
      ]);
    });
    it("rejects a non-whitelisted value", () => {
      expect(bridgeToScorm({ scorm: "setStatus", value: "bogus" }, false)).toEqual([]);
      expect(bridgeToScorm({ scorm: "setStatus", value: "bogus" }, true)).toEqual([]);
    });
    // fix round 1 / IMPORTANT 1 — 2004: completion_status yalnız completed|incomplete|
    // not attempted kabul eder; passed/failed → success_status; browsed 2004'te GEÇERSİZ.
    it("2004: completed/incomplete/not attempted route to completion_status", () => {
      expect(bridgeToScorm({ scorm: "setStatus", value: "completed" }, true)).toEqual([
        { key: "cmi.completion_status", value: "completed" },
      ]);
      expect(bridgeToScorm({ scorm: "setStatus", value: "not attempted" }, true)).toEqual([
        { key: "cmi.completion_status", value: "not attempted" },
      ]);
    });
    it("2004: passed/failed route to success_status, NOT completion_status", () => {
      expect(bridgeToScorm({ scorm: "setStatus", value: "passed" }, true)).toEqual([
        { key: "cmi.success_status", value: "passed" },
      ]);
      expect(bridgeToScorm({ scorm: "setStatus", value: "failed" }, true)).toEqual([
        { key: "cmi.success_status", value: "failed" },
      ]);
    });
    it("2004: browsed is rejected (invalid completion_status vocabulary)", () => {
      expect(bridgeToScorm({ scorm: "setStatus", value: "browsed" }, true)).toEqual([]);
    });
  });
});

// fix round 2 / FINDING 2 — kalıcı kayıt artık KOMPAKT ve anlamsal (state.eb); cmi anahtarları
// ondan TÜRETİLİR. bridgeToScorm bu ikilinin kompozisyonudur (yukarıdaki 13 test onu kilitler).
describe("embedStateFromMsg / embedWrites (compact record)", () => {
  it("produces a compact patch that carries no cmi keys", () => {
    expect(embedStateFromMsg({ scorm: "setScore", value: 85 }, false)).toEqual({ s: 85 });
    expect(embedStateFromMsg({ scorm: "complete" }, true)).toEqual({ c: "completed" });
    expect(embedStateFromMsg({ scorm: "passed" }, true)).toEqual({ k: "passed" });
    // 1.2'de tek kanal vardır (lesson_status) → passed/failed de `c`'ye yazılır: son yazan kazanır.
    expect(embedStateFromMsg({ scorm: "passed" }, false)).toEqual({ c: "passed" });
    expect(embedStateFromMsg({ scorm: "nope" }, false)).toBeNull();
  });
  it("clamps score into the record itself (not at write time)", () => {
    expect(embedStateFromMsg({ scorm: "setScore", value: 150 }, true)).toEqual({ s: 100 });
    expect(embedStateFromMsg({ scorm: "setScore", value: -20 }, true)).toEqual({ s: 0 });
  });
  it("re-validates a record read back from suspend_data (only whitelisted cmi keys can result)", () => {
    // suspend_data'dan bozuk/eski bir kayıt gelirse ham cmi yazımına DÖNÜŞEMEZ.
    expect(embedWrites({ c: "bogus" }, false)).toEqual([]);
    expect(embedWrites({ c: "browsed" }, true)).toEqual([]);        // 2004 sözlüğünde yok
    expect(embedWrites({ s: "85" }, false)).toEqual([]);            // dize skor reddedilir
    expect(embedWrites({ k: "passed" }, false)).toEqual([]);        // 1.2'de success_status yok
    expect(embedWrites(null, false)).toEqual([]);
    expect(embedWrites({ "cmi.core.score.raw": "99" }, false)).toEqual([]);  // ham cmi anahtarı ETKİSİZ
  });
  it("emits score + status writes together for a full record", () => {
    expect(embedWrites({ s: 85, c: "completed", k: "passed" }, true)).toEqual([
      { key: "cmi.score.raw", value: "85" },
      { key: "cmi.score.scaled", value: "0.8500" },
      { key: "cmi.completion_status", value: "completed" },
      { key: "cmi.success_status", value: "passed" },
    ]);
  });
  // FINDING 2 — kayıt suspend_data'da gerçekten hayatta kalıyor mu? (şema değişikliği YOK:
  // encodeSuspend bilinmeyen state alanlarını tail'deki `o` sözlüğüne taşır, decode geri kurar)
  it("survives a real encodeSuspend → decodeSuspend round-trip (scorm.js, no schema change)", () => {
    const order = ["s1", "s2"];
    const raw = encodeSuspend({ visited: { s1: true }, results: {}, history: [],
                                cursorId: "s1", eb: { s: 85, c: "completed", d: { s2: 1 } } }, order, {});
    const back = decodeSuspend(raw, order);
    expect(back.eb).toEqual({ s: 85, c: "completed", d: { s2: 1 } });
    expect(embedWrites(back.eb, false)).toContainEqual({ key: "cmi.core.score.raw", value: "85" });
    // 1.2 bütçesi dar (3500 bayt çalışma bütçesi) → kayıt küçük kalmalı.
    expect(raw.length).toBeLessThan(200);
  });
});

// fix round 3 / FINDING A+B — kapı durumu artık motorun girdisini (state.visited) DEĞİŞTİRMEZ;
// yalnız "tamamlanma geri çekilsin mi?" sorusunu yanıtlar.
describe("gatesPending", () => {
  it("a time_threshold gate is pending until eb.d records it", () => {
    const g = [{ id: "e1", mode: "time_threshold" }];
    expect(gatesPending(g, {})).toBe(true);
    expect(gatesPending(g, { d: {} })).toBe(true);
    expect(gatesPending(g, { d: { e1: 1 } })).toBe(false);
  });
  it("an on_message gate is pending until eb.m records THAT screen (per-screen ledger)", () => {
    const g = [{ id: "e1", mode: "on_message" }, { id: "e2", mode: "on_message" }];
    expect(gatesPending(g, { m: { e1: 1 } })).toBe(true);      // e2 hâlâ bildirmedi
    expect(gatesPending(g, { m: { e1: 1, e2: 1 } })).toBe(false);
    // eb.c GLOBAL'dir, ekran atfı yoktur → tek başına hiçbir kapıyı açamaz
    expect(gatesPending(g, { c: "completed" })).toBe(true);
  });
  it("the two ledgers do not cross-satisfy each other", () => {
    expect(gatesPending([{ id: "e1", mode: "on_message" }], { d: { e1: 1 } })).toBe(true);
    expect(gatesPending([{ id: "e1", mode: "time_threshold" }], { m: { e1: 1 } })).toBe(true);
  });
  it("no gates → never pending (on_view kursu etkilenmez)", () => {
    expect(gatesPending([], { })).toBe(false);
    expect(gatesPending(null, null)).toBe(false);
  });
});

// fix round 3 — TAMAMLANMA KİLİDİ: yalnız GERİ ÇEKME. Hiçbir girdi için "completed"/"passed"
// üretemez ve skora/success_status'a dokunmaz (F1 değişmezinin yapısal kanıtı).
describe("holdBackWrites", () => {
  it("emits nothing when no gate is pending", () => {
    expect(holdBackWrites(false, false)).toEqual([]);
    expect(holdBackWrites(false, true)).toEqual([]);
  });
  it("downgrades completion + exit while pending (1.2 / 2004)", () => {
    expect(holdBackWrites(true, false)).toEqual([
      { key: "cmi.core.lesson_status", value: "incomplete" },
      { key: "cmi.core.exit", value: "suspend" },
    ]);
    expect(holdBackWrites(true, true)).toEqual([
      { key: "cmi.completion_status", value: "incomplete" },
      { key: "cmi.exit", value: "suspend" },
    ]);
  });
  it("can NEVER upgrade and never touches score/success_status (invariant sweep)", () => {
    [true, false, 1, 0, null, undefined, "x", {}].forEach((p) => {
      [true, false].forEach((is2004) => {
        holdBackWrites(p, is2004).forEach((w) => {
          expect(["incomplete", "suspend"]).toContain(w.value);
          expect(w.key).not.toMatch(/score|success/);
        });
      });
    });
  });
});

// fix round 4 / FIX 1+2 — bastırma YÜKLEMİ tek yerde: hem sSet sarmalayıcısı hem pin süzgeci
// bunu kullanır. Kapsamı DAR olmalı; genişlerse motorun/hedeflerin meşru yazımları kaybolur.
describe("isCompletionAssertion", () => {
  it("1.2: only lesson_status completed/passed are assertions", () => {
    expect(isCompletionAssertion("cmi.core.lesson_status", "completed", false)).toBe(true);
    expect(isCompletionAssertion("cmi.core.lesson_status", "passed", false)).toBe(true);
    ["failed", "incomplete", "browsed", "not attempted", ""].forEach((v) => {
      expect(isCompletionAssertion("cmi.core.lesson_status", v, false)).toBe(false);
    });
  });
  it("2004: only completion_status=completed (passed lives on success_status)", () => {
    expect(isCompletionAssertion("cmi.completion_status", "completed", true)).toBe(true);
    expect(isCompletionAssertion("cmi.completion_status", "incomplete", true)).toBe(false);
    // 2004'te başarı AYRI kanaldır ve kilit ona ASLA dokunmaz
    expect(isCompletionAssertion("cmi.success_status", "passed", true)).toBe(false);
    expect(isCompletionAssertion("cmi.success_status", "failed", true)).toBe(false);
  });
  it("never matches score / session / exit / suspend keys", () => {
    [["cmi.core.score.raw", "100"], ["cmi.score.raw", "100"], ["cmi.score.scaled", "1.0000"],
     ["cmi.core.exit", "normal"], ["cmi.exit", "normal"], ["cmi.suspend_data", "completed"],
     ["cmi.core.session_time", "00:10:00"]].forEach(([k, v]) => {
      expect(isCompletionAssertion(k, v, false)).toBe(false);
      expect(isCompletionAssertion(k, v, true)).toBe(false);
    });
  });
  // REGRESYON KORUMASI: alt-dize/regex eşleşmeye geçilirse hedef yazımları sessizce yutulurdu.
  // scorm.js:objectiveElements bu anahtarları AYNI sSet üzerinden yazar ve kapı beklerken de
  // yazılmalıdır (hedef ilerlemesi ≠ kursun tamamlanma iddiası).
  it("does NOT match objective/interaction keys that merely CONTAIN the status name", () => {
    expect(isCompletionAssertion("cmi.objectives.0.completion_status", "completed", true)).toBe(false);
    expect(isCompletionAssertion("cmi.objectives.0.success_status", "passed", true)).toBe(false);
    expect(isCompletionAssertion("cmi.objectives.0.status", "completed", false)).toBe(false);
    expect(isCompletionAssertion("cmi.interactions.0.result", "correct", false)).toBe(false);
  });
  it("coerces the value (sSet stringifies; a non-string must not slip through)", () => {
    expect(isCompletionAssertion("cmi.core.lesson_status", new String("completed"), false)).toBe(true);
    expect(isCompletionAssertion("cmi.core.lesson_status", 0, false)).toBe(false);
  });
});

// fix round 5 — geçici `exit=normal` (kapı beklerken motor "complete" hesapladığı için yazılır ve
// kilidin `exit=suspend`'inden ÖNCE COMMIT edilir): FIX 1'in kapattığı kusurun `exit` biçimi.
describe("isTransientExit / isGatedCompletionWrite", () => {
  it("matches ONLY exit=normal, in the right key for each flavor", () => {
    expect(isTransientExit("cmi.core.exit", "normal", false)).toBe(true);
    expect(isTransientExit("cmi.exit", "normal", true)).toBe(true);
    expect(isTransientExit("cmi.exit", "normal", false)).toBe(false);       // yanlış sürüm anahtarı
    expect(isTransientExit("cmi.core.exit", "normal", true)).toBe(false);
    ["suspend", "logout", "time-out", ""].forEach((v) => {
      expect(isTransientExit("cmi.core.exit", v, false)).toBe(false);
    });
    // alt-dize DEĞİL tam eşitlik
    expect(isTransientExit("cmi.core.exit_reason", "normal", false)).toBe(false);
  });
  it("isCompletionAssertion stays exit-free (the §9 scope table depends on it)", () => {
    expect(isCompletionAssertion("cmi.core.exit", "normal", false)).toBe(false);
    expect(isGatedCompletionWrite("cmi.core.exit", "normal", false)).toBe(true);
    expect(isGatedCompletionWrite("cmi.core.lesson_status", "completed", false)).toBe(true);
    expect(isGatedCompletionWrite("cmi.core.lesson_status", "failed", false)).toBe(false);
    expect(isGatedCompletionWrite("cmi.success_status", "passed", true)).toBe(false);
    expect(isGatedCompletionWrite("cmi.suspend_data", "completed", false)).toBe(false);
  });
});

// fix round 4 / FIX 1 — motorun KENDİ tamamlanma yazımı kapı beklerken cmi'ye HİÇ gitmez
// (round 3'te yazılıp COMMIT edilip sonra geri çekiliyordu: mandallayan LMS'te kapı çalışmıyordu).
describe("wrapSet", () => {
  it("suppresses only the completion assertion while pending, passes everything else", () => {
    const log = [];
    const set = wrapSet((k, v) => log.push(k + "=" + v), () => true, false);
    set("cmi.core.score.raw", "85");
    set("cmi.core.lesson_status", "completed");     // bastırılır
    set("cmi.core.lesson_status", "passed");        // bastırılır (1.2 tek kanal)
    set("cmi.core.lesson_status", "failed");
    set("cmi.core.lesson_status", "incomplete");
    set("cmi.core.exit", "suspend");
    set("cmi.core.exit", "normal");                 // fix round 5: bu da bastırılır
    set("cmi.objectives.0.completion_status", "completed");
    expect(log).toEqual(["cmi.core.score.raw=85", "cmi.core.lesson_status=failed",
                         "cmi.core.lesson_status=incomplete", "cmi.core.exit=suspend",
                         "cmi.objectives.0.completion_status=completed"]);
  });
  it("is fully transparent when no gate is pending", () => {
    const log = [];
    const set = wrapSet((k, v) => log.push(k + "=" + v), () => false, true);
    set("cmi.completion_status", "completed");
    set("cmi.success_status", "passed");
    expect(log).toEqual(["cmi.completion_status=completed", "cmi.success_status=passed"]);
  });
  it("asks pending() on EVERY write (a gate opening mid-session lifts it immediately)", () => {
    const log = [];
    let pend = true;
    const set = wrapSet((k, v) => log.push(k + "=" + v), () => pend, true);
    set("cmi.completion_status", "completed");
    pend = false;
    set("cmi.completion_status", "completed");
    expect(log).toEqual(["cmi.completion_status=completed"]);
  });
  it("2004: success_status is NEVER suppressed, even while pending", () => {
    const log = [];
    const set = wrapSet((k, v) => log.push(k + "=" + v), () => true, true);
    set("cmi.success_status", "passed");
    set("cmi.score.raw", "90");
    set("cmi.score.scaled", "0.9000");
    expect(log).toEqual(["cmi.success_status=passed", "cmi.score.raw=90", "cmi.score.scaled=0.9000"]);
  });
});

// task-5 / FIX 3 — round 4'ün AYRI artifact-pin süzgeci (`suppressCompletionWrites`) SİLİNDİ:
// `wrapSet` onu tamamen kapsıyordu (aynı `pending()`, katı üst-küme yüklem, her iki yazım yolu da
// sSet'ten geçiyor). Onun ölçtüğü DAVRANIŞ burada, sarmalayıcı üzerinden ölçülür — "A ekranının
// artifact'i B ekranının kapısını atlatamaz" değişmezi (fix round 4 / FIX 2) yerinde durmalı.
describe("artifact pin under a pending gate (wrapSet covers it — FIX 3)", () => {
  it("drops the completion pin while pending but keeps score / success_status (2004)", () => {
    const log = [];
    const set = wrapSet((k, v) => log.push(k + "=" + v), () => true, true);
    embedWrites({ s: 85, c: "completed", k: "passed" }, true).forEach((w) => set(w.key, w.value));
    expect(log).toEqual(["cmi.score.raw=85", "cmi.score.scaled=0.8500", "cmi.success_status=passed"]);
  });
  it("1.2: drops completed AND passed (single channel), keeps failed / browsed", () => {
    const run = (eb) => {
      const log = [];
      const set = wrapSet((k, v) => log.push(k + "=" + v), () => true, false);
      embedWrites(eb, false).forEach((w) => set(w.key, w.value));
      return log;
    };
    expect(run({ c: "completed" })).toEqual([]);
    expect(run({ c: "passed" })).toEqual([]);
    expect(run({ c: "failed" })).toEqual(["cmi.core.lesson_status=failed"]);
    expect(run({ c: "browsed" })).toEqual(["cmi.core.lesson_status=browsed"]);
  });
  it("is a no-op when nothing is pending (pin priority unchanged)", () => {
    const log = [];
    const set = wrapSet((k, v) => log.push(k + "=" + v), () => false, false);
    embedWrites({ s: 85, c: "completed" }, false).forEach((w) => set(w.key, w.value));
    expect(log).toEqual(["cmi.core.score.raw=85", "cmi.core.lesson_status=completed"]);
  });
});

// fix round 1 / CRITICAL — köprü yazımları motorun kendi evaluate() döngüsünden SAĞ ÇIKMALI.
describe("wrapEvaluate", () => {
  it("re-applies embed writes AFTER the original evaluate(), so a setScore write survives", () => {
    const calls = [];
    const sSet = (k, v) => calls.push([k, v]);
    // motorun kendi evaluate()'ini taklit eder: her çağrıda skoru/durumu YENİDEN yazar.
    const origEvaluate = () => {
      sSet("cmi.core.score.raw", "0");
      sSet("cmi.core.lesson_status", "incomplete");
    };
    const wrapped = wrapEvaluate(origEvaluate, sSet,
      () => [{ key: "cmi.core.score.raw", value: "85" }]);

    wrapped();

    const scoreWrites = calls.filter(([k]) => k === "cmi.core.score.raw").map(([, v]) => v);
    expect(scoreWrites[scoreWrites.length - 1]).toBe("85");
    expect(calls).toContainEqual(["cmi.core.lesson_status", "incomplete"]);
  });

  it("calling wrapped evaluate() repeatedly keeps the embed write pinned (simulates repeated navigation)", () => {
    const calls = [];
    const sSet = (k, v) => calls.push([k, v]);
    const origEvaluate = () => sSet("cmi.core.score.raw", "0");
    const wrapped = wrapEvaluate(origEvaluate, sSet,
      () => [{ key: "cmi.core.score.raw", value: "85" }]);

    wrapped(); wrapped(); wrapped(); // ör. üç showAt() gezinmesi + exit

    const scoreWrites = calls.filter(([k]) => k === "cmi.core.score.raw").map(([, v]) => v);
    expect(scoreWrites).toEqual(["0", "85", "0", "85", "0", "85"]);
  });

  it("no embed writes → behaves exactly like the original evaluate() (and does not commit)", () => {
    const calls = [];
    const sSet = (k, v) => calls.push([k, v]);
    const commit = vi.fn();
    const origEvaluate = () => sSet("cmi.core.lesson_status", "completed");
    const wrapped = wrapEvaluate(origEvaluate, sSet, () => [], commit);
    wrapped();
    expect(calls).toEqual([["cmi.core.lesson_status", "completed"]]);
    expect(commit).not.toHaveBeenCalled();
  });

  // fix round 2 / FINDING 3 — yeniden yazımlar persist() içindeki commit'ten SONRA olduğundan,
  // yazım varsa AYRICA commit edilir (Terminate'in örtük kalıcılığına güvenilmez).
  it("commits AFTER re-asserting embed writes (FINDING 3)", () => {
    const log = [];
    const sSet = (k, v) => log.push("set:" + k + "=" + v);
    const commit = () => log.push("commit");
    const origEvaluate = () => { sSet("cmi.core.score.raw", "0"); commit(); };  // persist() → sCommit()
    wrapEvaluate(origEvaluate, sSet, () => [{ key: "cmi.core.score.raw", value: "85" }], commit)();
    expect(log).toEqual(["set:cmi.core.score.raw=0", "commit", "set:cmi.core.score.raw=85", "commit"]);
  });

  // fix round 3 — kilit + artifact pini AYNI dizidedir ve SIRA önemlidir: kilit önce, artifact
  // sonra. fix round 4 NOTU: bu sıra KORUNUR ama artık "artifact her şeyi ezer" demek değildir —
  // tamamlanma İMA EDEN pinler (1.2 completed/passed, 2004 completed) kapı beklerken
  // `wrapSet` ile sarmalanmış sSet'ten GEÇMEZ (task-5 / FIX 3). Sıranın hâlâ
  // koruduğu şey: `failed`/`browsed`, skor ve 2004 `success_status` pinleri kilidin üstünde kalır.
  // Bu test wrapEvaluate'in SAF sıra sözleşmesini ölçer (süzgeçsiz getWrites verilir).
  it("applies the hold-back lock BEFORE the artifact's own writes (last-writer-wins order)", () => {
    const log = [];
    const sSet = (k, v) => log.push("set:" + k + "=" + v);
    const origEvaluate = () => sSet("cmi.core.lesson_status", "completed");
    wrapEvaluate(origEvaluate, sSet,
      () => holdBackWrites(true, false).concat([{ key: "cmi.core.lesson_status", value: "passed" }]),
      null)();
    expect(log).toEqual([
      "set:cmi.core.lesson_status=completed",   // motor
      "set:cmi.core.lesson_status=incomplete",  // kilit (geri çekme)
      "set:cmi.core.exit=suspend",
      "set:cmi.core.lesson_status=passed",      // artifact'in KENDİ komutu — F1: yalnız o ezebilir
    ]);
  });
});

// --------------------------------------------------------------------------- //
// DAVRANIŞ TESTLERİ — templates.py'deki GERÇEK EMBED_JS metnini çalıştırır.
// --------------------------------------------------------------------------- //
// EMBED_JS bir Python string sabiti olduğu için buradan metin olarak okunur ve motorun ilgili
// parçalarını YANSILAYAN (mirror) küçük bir kapsamda çalıştırılır. DOM stub'ı asgaridir
// (querySelectorAll/closest/dataset/contentWindow/addEventListener) — jsdom bağımlılığı YOK.
// SINIR (dürüstlük notu): motor gövdesi ENGINE_JS'ten KOPYALANMAZ, elle yansılanır; gerçek
// tarayıcı + gerçek LMS API'siyle uçtan uca doğrulama DEĞİLDİR. Yansılanan kurallar
// templates.py'deki evaluate()/writeScore()/isComplete()/viewedAll()/showAt()/updateChrome()/
// prev()/isVisible() ile birebir tutulmalıdır (değişirlerse bu yansı da güncellenmelidir).
// fix round 3: yansıya updateChrome() + prev() + isVisible() + state.history EKLENDİ — round 2'nin
// kusurları (FINDING C history-pop, FINDING D ilerleme göstergesi) tam olarak yansının MODELLEMEDİĞİ
// yerlerdeydi. updateChrome'un DOM yazımları yerine bir "chrome" toplayıcısına yazılır: ölçülen şey
// gösterilecek DEĞER (pct/dots), DOM çağrısı değil.
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const TEMPLATES_PY = fs.readFileSync(path.join(REPO, "components/templates.py"), "utf8");
const EMBED_JS = TEMPLATES_PY.split('EMBED_JS = r"""')[1].split('"""')[0];
// fix round 5 — LMS-adaptör vekili: extras'ta (engine_js'ten ÖNCE) basılan koşullu inline script.
// Yansıda da AYNI sırada koşar: önce vekil, sonra motorun getAPI()'si.
const SHIM_JS = TEMPLATES_PY.includes('EMBED_SHIM_JS = r"""')
  ? TEMPLATES_PY.split('EMBED_SHIM_JS = r"""')[1].split('"""')[0]
  : "/* EMBED_SHIM_JS yok */";

// --------------------------------------------------------------------------- //
// task-5 / FIX 6 — YANSI DRİFT KORUMASI.
// Aşağıdaki harness, ENGINE_JS'in bir avuç fonksiyonunu ELLE yansılar. Bu yansı önceden
// SATIR NUMARASI veren yorumlarla korunuyordu — ve o numaralar çoktan kaymıştı (ör. SCORM
// katmanı için "936-951" yazıyordu, gerçek 942-959'du). Satır numarası bir koruma DEĞİL,
// bakımı unutulan bir dipnottur. Gerçek tripwire bu testtir: yansılanan fonksiyonların
// GÖVDELERİ ENGINE_JS'ten ADLARIYLA çıkarılır ve SHA-256'ları sabitlenir. ENGINE_JS'te bu
// fonksiyonlardan biri değişirse test kırılır ve yansının güncellenmesi gerektiğini söyler.
// (EMBED_JS/EMBED_SHIM_JS kopyalanmaz, test anında templates.py'den okunur → drift riski yok.)
// --------------------------------------------------------------------------- //
const MIRRORED_ENGINE_FNS = [
  "findAPI", "getAPI", "sSet", "sCommit", "persist", "scoreValue", "quizPassed", "viewedAll",
  "isComplete", "writeScore", "evaluate", "isVisible", "indexOfId", "showAt", "prev",
  "updateChrome", "buildDots",
];
// ENGINE_JS'ten `function <ad>(` gövdesini süslü parantez eşleyerek çıkarır (dize ve yorum
// içindeki parantezler atlanır). ENGINE_JS'te backtick/şablon dizgesi YOKTUR (doğrulandı).
function engineFn(src, name) {
  const marker = "\nfunction " + name + "(";
  const start = src.indexOf(marker);
  if (start < 0) throw new Error("ENGINE_JS'te bulunamadı: function " + name);
  let i = src.indexOf("{", start);
  let depth = 0, q = null, esc = false;
  for (; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (q) {
      if (esc) { esc = false; continue; }
      if (c === "\\") { esc = true; continue; }
      if (q === "line" && c === "\n") q = null;
      else if (q === "block" && c === "*" && n === "/") { q = null; i++; }
      else if ((q === "'" || q === '"') && c === q) q = null;
      continue;
    }
    if (c === "/" && n === "/") { q = "line"; i++; continue; }
    if (c === "/" && n === "*") { q = "block"; i++; continue; }
    if (c === "'" || c === '"') { q = c; continue; }
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) return src.slice(start + 1, i + 1); }
  }
  throw new Error("ENGINE_JS'te süslü parantez dengesiz: function " + name);
}

describe("ENGINE_JS mirror drift guard (task-5 / FIX 6)", () => {
  const ENGINE_JS = TEMPLATES_PY.split('ENGINE_JS = r"""')[1].split('"""')[0];

  it("every mirrored function still exists in ENGINE_JS", () => {
    MIRRORED_ENGINE_FNS.forEach((n) => {
      expect(() => engineFn(ENGINE_JS, n), `ENGINE_JS'te ${n} yok`).not.toThrow();
    });
  });

  it("the mirrored ENGINE_JS bodies match their pinned SHA-256", () => {
    const bodies = MIRRORED_ENGINE_FNS.map((n) => engineFn(ENGINE_JS, n));
    const sha = createHash("sha256").update(bodies.join("\n")).digest("hex");
    expect(
      sha,
      "ENGINE_JS'te yansılanan fonksiyonlardan biri DEĞİŞTİ.\n" +
      "tests/js/embed.test.js içindeki elle yansılanmış motoru (harness()'in `body` şablonu:\n" +
      MIRRORED_ENGINE_FNS.join(", ") + ") yeni davranışa göre GÜNCELLE, sonra buradaki pinlenmiş\n" +
      "SHA-256'yı yenisiyle değiştir. Pin'i yansıya bakmadan güncellemek koruma yok demektir.",
    ).toBe("964658850ba02eb77cde440efbed7dbb32cded02c621f2a9d27fcfff71560a62");
  });
});

function harness(opts) {
  const o = Object.assign({
    screens: [],          // [{id, embed?: {completion, minSeconds}}]
    is2004: false,
    totalPoints: 0,
    earned: 0,
    rule: "viewed_all",
    passingScore: 80,
    startIdx: 0,
    state: null,          // önceki oturumdan gelen (resume) state
    hidden: {},           // {screenId: true} — visible_if false (Faz 5 koşullu ekran)
    lms: "parent",        // "parent" | "opener" | "none" — gerçek LMS adaptörünün NEREDE olduğu
    skipShim: false,      // EMBED_SHIM_JS'i hiç çalıştırma (kusur üretimi / karşılaştırma)
    skipEmbedJs: false,   // EMBED_JS'i hiç çalıştırma (vekilin failsafe'i: kilit HİÇ gelmezse)
    // fix round 6 — GEÇ KURULAN ADAPTÖR: eski LMS başlatıcıları window.API'yi bir yer tutucu
    // nesne (ya da <object>/applet öğesi) olarak yayınlar ve METOTLAR ancak eklenti hazır
    // olunca belirir. h.populateApi() o anı temsil eder.
    lmsLate: false,
  }, opts);

  const frames = [];
  o.screens.forEach((s) => {
    if (!s.embed) return;
    frames.push({
      contentWindow: { __screen: s.id },
      dataset: { completion: s.embed.completion, minSeconds: String(s.embed.minSeconds || 0) },
      closest: (sel) => (sel === "[data-screen-id]" ? { dataset: { screenId: s.id } } : null),
    });
  });
  const listeners = [];
  // fix round 6 — vekilin bırakma tetiği artık DOMContentLoaded (setTimeout(0) DEĞİL): sahte
  // document bu yüzden readyState + addEventListener taşımak ZORUNDA, yoksa shim kayıt satırında
  // patlar ve dıştaki try/catch bunu yutar (yarım kurulmuş vekil).
  const domListeners = [];
  const fakeDocument = {
    readyState: "loading",
    querySelectorAll: (sel) => (sel === "iframe.embed-frame" ? frames.slice() : []),
    addEventListener: (type, fn) => { if (type === "DOMContentLoaded") domListeners.push(fn); },
  };
  // fix round 5 — LMS KATMANI: sSet artık doğrudan bir nesneye değil, GERÇEK bir SCORM adaptörüne
  // yazar (ENGINE_JS getAPI/findAPI/sSet yansısı). Bunun tek sebebi vekilin (EMBED_SHIM_JS) test
  // edilebilir olması: vekil sSet'in ALTINA, API katmanına kurulur — log'a düşen şey artık
  // "motor ne yazmak istedi" değil, "LMS'e NE ULAŞTI"dır (bootstrap penceresi ancak böyle ölçülür).
  const cmi = {};
  const log = [];
  function makeApi(is2004) {
    const set = (k, v) => { cmi[k] = String(v); log.push("set:" + k + "=" + String(v)); return "true"; };
    const get = (k) => (cmi[k] === undefined ? "" : cmi[k]);
    const commit = () => { log.push("commit"); return "true"; };
    const a = { __real: true, calls: [] };
    const names = is2004
      ? ["Initialize", "Terminate", "GetValue", "SetValue", "Commit", "GetLastError",
         "GetErrorString", "GetDiagnostic"]
      : ["LMSInitialize", "LMSFinish", "LMSGetValue", "LMSSetValue", "LMSCommit", "LMSGetLastError",
         "LMSGetErrorString", "LMSGetDiagnostic"];
    const impl = {
      init: () => "true", fin: () => "true", get, set, commit,
      lastErr: () => a.lastError, errStr: (c) => "err:" + c, diag: (c) => "diag:" + c,
    };
    const map = [impl.init, impl.fin, impl.get, impl.set, impl.commit, impl.lastErr, impl.errStr,
                 impl.diag];
    names.forEach((n, i) => {
      a[n] = function (x, y) { a.calls.push([n, x, y, this === a]); return map[i](x, y); };
    });
    a.lastError = "0";
    a.__names = names;
    return a;
  }
  const realApi = o.lms === "none" ? null : makeApi(o.is2004);
  const apiName = o.is2004 ? "API_1484_11" : "API";
  // fix round 6 — lmsLate: adaptör NESNESİ var ama metotları HENÜZ yok (applet/eklenti geç
  // kuruluyor). Metotlar kenara alınır; populateApi() onları geri takar.
  const lateStash = {};
  if (realApi && o.lmsLate) {
    realApi.__names.forEach((n) => { lateStash[n] = realApi[n]; delete realApi[n]; });
  }
  const topWin = {};
  topWin.parent = topWin;
  if (realApi && o.lms !== "opener") topWin[apiName] = realApi;
  const openerWin = {};
  openerWin.parent = openerWin;
  if (realApi && o.lms === "opener") openerWin[apiName] = realApi;
  const fakeWindow = {
    SCORMEMBED: EMB,
    addEventListener: (type, fn) => { if (type === "message") listeners.push(fn); },
    parent: o.lms === "opener" || o.lms === "none" ? null : topWin,
    opener: o.lms === "opener" ? openerWin : null,
    // ENGINE_JS getAPI() yerel fallback'i (LMS yoksa): kayıt tutan sahte adaptör.
    Scorm12API: function () { return makeApi(false); },
    Scorm2004API: function () { return makeApi(true); },
  };
  if (fakeWindow.parent === null) fakeWindow.parent = fakeWindow;

  const body = `
    ${o.skipShim ? "" : SHIM_JS}
    // ---- ENGINE_JS SCORM katmanı yansısı (templates.py: findAPI/getAPI/sSet/sCommit) ----
    var SCORM_NAME = S2004 ? "API_1484_11" : "API";
    function findAPI(win){ var n=0;
      while(win && !win[SCORM_NAME] && win.parent && win.parent!==win && n<12){ win=win.parent; n++; }
      return win ? win[SCORM_NAME] : null; }
    function getAPI(){
      var api=findAPI(window);
      if(!api && window.opener) api=findAPI(window.opener);
      if(!api){ try { var Ctor = S2004 ? window.Scorm2004API : window.Scorm12API;
        if(Ctor){ api=new Ctor({autocommit:false,logLevel:5}); window[SCORM_NAME]=api; } } catch(e){} }
      return api; }
    var api=getAPI();
    function sSet(k, v){ if(!api)return;
      try{ S2004?api.SetValue(k,String(v)):api.LMSSetValue(k,String(v)); }catch(e){} }
    function sCommit(){ if(!api)return; try{ S2004?api.Commit(""):api.LMSCommit(""); }catch(e){} }
    function persist(){ LOG.push("persist"); sCommit(); }   // ENGINE_JS: persist() içinde sCommit()
    function scoreValue(){ return TP > 0 ? Math.round(EARNED / TP * 100) : 0; }
    function quizPassed(){ return scoreValue() >= PASS; }
    function viewedAll(){ var seen = 0;
      order.forEach(function(id){ if(state.visited[id]) seen++; });
      return seen >= order.length || !!state.reachedEnd; }
    function isComplete(){
      if(RULE === "passed_quiz") return quizPassed();
      if(RULE === "viewed_all_and_passed") return viewedAll() && quizPassed();
      return viewedAll(); }
    function evaluate(){
      var sc = scoreValue();
      if(S2004){ sSet("cmi.score.raw", sc); sSet("cmi.score.scaled", (sc/100).toFixed(4)); }
      else { sSet("cmi.core.score.raw", sc); }
      var complete = isComplete();
      if(S2004){
        sSet("cmi.completion_status", complete ? "completed" : "incomplete");
        if(TP > 0) sSet("cmi.success_status", quizPassed() ? "passed" : "failed");
      } else {
        var status;
        if(TP > 0 && RULE !== "viewed_all"){ status = complete ? (quizPassed() ? "passed" : "failed") : "incomplete"; }
        else { status = complete ? "completed" : "incomplete"; }
        sSet("cmi.core.lesson_status", status);
      }
      // S4 — exit HER değerlendirmede yazılır (scorm.js:exitValue → complete ? normal : suspend)
      sSet(S2004 ? "cmi.exit" : "cmi.core.exit", complete ? "normal" : "suspend");
      persist();
    }
    function isVisible(id){ return !HIDDEN[id]; }
    function indexOfId(id){ return order.indexOf(id); }
    // updateChrome/buildDots — ENGINE_JS updateChrome()/buildDots() yansısı. DOM yerine CH toplayıcısı: ölçülen
    // şey GÖSTERİLECEK değer. (curScreen().type==="branching" dalı yansılanmaz: bu harness'ta
    // branching ekran yok.)
    function buildDots(){ CH.dots = order.map(function(id, i){
      return (state.visited[id] ? "v" : "") + (i === cursor ? "c" : ""); }); }
    function updateChrome(){
      CH.calls++;
      CH.pct = Math.round((Object.keys(state.visited).length / order.length) * 100);
      CH.pill = (cursor + 1) + " / " + order.length;
      CH.prevDisabled = (cursor === 0 && state.history.length === 0);
      CH.nextDisabled = (cursor >= order.length - 1);
      buildDots();
    }
    function showAt(idx, push){
      if(idx < 0 || idx >= order.length) return;
      if(push && order[cursor]) state.history.push(order[cursor]);
      cursor = idx;
      var id = order[cursor];
      state.visited[id] = true;
      state.cursorId = id;
      if(cursor === order.length - 1) state.reachedEnd = true;
      updateChrome();               // ENGINE_JS sırası: updateChrome ÖNCE, evaluate SONRA
      evaluate();
    }
    // prev() — ENGINE_JS prev() yansısı. KRİTİK: history hızlı yolu showAt'i ÇAĞIRMAZ
    // (dolayısıyla evaluate() de koşmaz); yalnız cursor/cursorId + updateChrome + persist.
    // DOM-only adımlar (updateVideos/aria/resolveExplorationRefs/applyAnsweredState/focusActive)
    // yansılanmaz.
    function prev(){
      if(state.history.length){ var id = state.history.pop(); var i = indexOfId(id);
        if(i >= 0){ cursor = i; state.cursorId = id; updateChrome(); persist(); return; } }
      showAt(cursor - 1, false);
    }
    showAt(START, false);            // bootstrap — sentinel'den ÖNCE (ENGINE_JS init sırası)
    // fix round 4: sentinel SINIRI. Bootstrap showAt()'in evaluate()'i EMBED_JS'ten ÖNCE koşar
    // (kilit/sSet sarmalaması henüz yok) — o pencerede yazılan "completed" bu turun KAPSAMI
    // DIŞINDA (ENGINE_JS sırası değişmeden düzeltilemez, bayt-parite). BOOT bu sınırı işaretler:
    // testler "sentinel'den SONRA hiç completed yok" diye ölçebilsin.
    var BOOT = LOG.length;
    ${o.skipEmbedJs ? "" : EMBED_JS}
    return { state: state, chrome: CH, boot: BOOT, engineApi: api,
             go: function(i){ showAt(i, true); },
             prev: function(){ prev(); },
             finish: function(){ evaluate(); } };
  `;
  const fn = new Function(
    "document", "window", "state", "order", "cursor", "S2004", "TP", "EARNED", "RULE", "PASS",
    "START", "setTimeout", "HIDDEN", "CH", "LOG", body);
  const state = o.state || { visited: {}, results: {}, history: [] };
  if (!state.history) state.history = [];
  const order = o.screens.map((s) => s.id);
  const chrome = { calls: 0, pct: null, pill: null, dots: [], prevDisabled: null, nextDisabled: null };
  const api = fn(fakeDocument, fakeWindow, state, order, 0, o.is2004, o.totalPoints, o.earned,
                 o.rule, o.passingScore, o.startIdx, setTimeout, o.hidden, chrome, log);
  api.cmi = cmi;
  api.log = log;
  api.win = fakeWindow;
  api.realApi = realApi;
  api.apiName = apiName;
  // fix round 6 — DOMContentLoaded'ı ateşle (vekilin bırakma tetiği). Tarayıcıda TÜM senkron
  // script'ler (ENGINE_JS dahil) koştuktan SONRA olur; harness'ta da öyle: harness() döndükten
  // sonra çağrılır.
  api.domReady = () => {
    fakeDocument.readyState = "interactive";
    domListeners.slice().forEach((f) => f());
  };
  // fix round 6 — geç kurulan adaptörün metotları ŞİMDİ belirdi.
  api.populateApi = () => {
    Object.keys(lateStash).forEach((n) => { realApi[n] = lateStash[n]; });
  };
  api.post = (data, screenId) => {
    const src = frames.find((f) => f.contentWindow.__screen === screenId) || frames[0];
    listeners.forEach((fn2) => fn2({ source: src.contentWindow, data }));
  };
  return api;
}

describe("EMBED_JS (real template text, mirrored engine)", () => {
  // ---- FINDING 1 regresyon testleri: launcher'ın kendi otomatik tamamlanması motoru EZMEZ ----
  it("1.2 + quiz: an on_view embed screen does NOT pin 'completed' over the engine's status", () => {
    // 2 ekran: quiz + embed(on_view). Öğrenci ikisini de görüyor ama quizden 0 alıyor.
    // Motor (viewed_all_and_passed): complete=false → "incomplete". Round-1'de embed ekranı
    // state.embedWrites'a "completed" pinliyordu ve bu her evaluate sonrası geri yazılıyordu.
    const h = harness({
      screens: [{ id: "q1" }, { id: "e1", embed: { completion: "on_view" } }],
      totalPoints: 10, earned: 0, rule: "viewed_all_and_passed", passingScore: 80,
    });
    h.go(1);            // embed ekranına gir
    h.finish();         // finishNow() → evaluate()
    expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
    expect(h.log.filter((l) => l === "set:cmi.core.lesson_status=completed")).toEqual([]);
  });

  it("2004 + 20 screens: an on_view embed on screen 3 does not pin completion_status", () => {
    const screens = [];
    for (let i = 0; i < 20; i++) {
      screens.push(i === 2 ? { id: "s3", embed: { completion: "on_view" } } : { id: "s" + (i + 1) });
    }
    const h = harness({ screens, is2004: true });
    h.go(1); h.go(2);   // ekran 3'e (embed) gir
    expect(h.cmi["cmi.completion_status"]).toBe("incomplete");
    h.go(3);            // ekran 4'e geç, sonra öğrenci terk ediyor
    h.finish();
    expect(h.cmi["cmi.completion_status"]).toBe("incomplete");
    expect(h.log.filter((l) => l === "set:cmi.completion_status=completed")).toEqual([]);
  });

  it("embed-only course: on_view still completes (engine derives it from state.visited)", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_view" } }] });
    expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
  });

  // ---- artifact'in KENDİ komutu pinleyebilir (sözleşmenin izin verdiği tek ezme) ----
  it("an artifact postMessage pins its value over the engine's recomputation", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_message" } }, { id: "s2" }] });
    h.post({ scorm: "setScore", value: 85 }, "e1");
    expect(h.cmi["cmi.core.score.raw"]).toBe("85");
    // FINDING 3 + 2 — artifact yazımı hemen persist() edilir (suspend_data'ya girer) ve commit olur
    expect(h.log.slice(-3)).toEqual(["set:cmi.core.score.raw=85", "persist", "commit"]);
    h.go(1);            // motor yeniden hesaplar (skorsuz kurs → 0)
    h.finish();
    expect(h.cmi["cmi.core.score.raw"]).toBe("85");
    expect(h.state.eb).toEqual({ s: 85 });
    // FINDING 3 — yeniden yazımdan SONRA commit
    // evaluate() yolunda: origEvaluate → persist → commit, SONRA yeniden yazım + commit
    expect(h.log.slice(-2)).toEqual(["set:cmi.core.score.raw=85", "commit"]);
  });

  it("ignores messages from a foreign window (source check)", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_message" } }] });
    h.post({ scorm: "setScore", value: 85 }, "e1");
    expect(h.cmi["cmi.core.score.raw"]).toBe("85");
    // yabancı pencere: post() yalnız kendi frame'lerimizin contentWindow'unu kullanır; burada
    // elle bir yabancı kaynak taklidi yapılamadığı için doğrudan kayıt kontrolü yapılır.
    expect(h.state.eb).toEqual({ s: 85 });
  });

  // ---- FINDING 2: önceki oturumun kaydı resume'da geri konur ----
  it("session 2: a resumed eb record is re-applied at init (init's score 0 is corrected)", () => {
    const prev = { visited: { e1: true }, results: {}, history: [], eb: { s: 85 } };
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_view" } }], state: prev });
    // bootstrap showAt() → evaluate() önce 0 yazdı; EMBED_JS init'te 85 geri kondu.
    expect(h.log[0]).toBe("set:cmi.core.score.raw=0");
    expect(h.cmi["cmi.core.score.raw"]).toBe("85");
    expect(h.log[h.log.length - 1]).toBe("commit");
  });

  it("drops a legacy round-1 state.embedWrites blob so it stops riding suspend_data", () => {
    const prev = { visited: {}, results: {}, history: [],
                   embedWrites: { "cmi.core.score.raw": "85" } };
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_view" } }], state: prev });
    expect(h.state.embedWrites).toBeUndefined();
  });

  // ---- ekrana GİRİŞ davranışı (test gereksinimi 1): sayaç sayfa yüklenince kurulmaz ----
  // fix round 3 NOTU: round 2'de bu test "state.visited.e1 undefined" (kapı motorun girdisini geri
  // çekiyor) diye ölçüyordu. O MEKANİZMA kaldırıldı (FINDING A/C/D'nin kaynağıydı); kalan
  // DEĞİŞMEZLER burada korunuyor: sayaç yalnız ekrana GİRİLİNCE kurulur, eşik aşılınca eb.d yazılır
  // ve tamamlanma o ana dek GERİ ÇEKİLİR.
  it("time_threshold timer is armed on screen ENTER, not at page load", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "s1" }, { id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } },
                  { id: "s3" }],
      });
      vi.advanceTimersByTime(60000);          // sayfa yüklendi, embed ekranına HİÇ girilmedi
      expect(h.state.eb.d).toBeUndefined();   // sayaç kurulmadı → eşik aşılmadı
      expect(h.state.visited.e1).toBeFalsy();

      h.go(1);                                // şimdi embed ekranına giriliyor
      expect(h.state.visited.e1).toBe(true);  // motorun girdisine ARTIK dokunulmuyor (round 3)
      vi.advanceTimersByTime(4999);
      expect(h.state.eb.d).toBeUndefined();
      vi.advanceTimersByTime(1);              // eşik aşıldı → evaluate() yeniden koştu
      expect(h.state.eb.d).toEqual({ e1: 1 });
    } finally { vi.useRealTimers(); }
  });

  // ---- fix round 3 / FINDING A: TEK EKRANLI time_threshold kursu (bu özelliğin amiral gemisi) ----
  it("FINDING A: a SINGLE-screen time_threshold course is held back until the threshold", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } }],
      });
      // Round 2'de burada "completed" raporlanıyordu: showAt son ekranda reachedEnd=true yapar,
      // viewedAll() reachedEnd'i kabul eder → visited'ı geri çekmek HİÇBİR ŞEY değiştirmiyordu.
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      expect(h.cmi["cmi.core.exit"]).toBe("suspend");   // exit de geri çekilir (veri kaybı riski)
      expect(h.state.visited.e1).toBe(true);            // ilerleme motorun gördüğü gibi (%100)
      vi.advanceTimersByTime(4999);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      vi.advanceTimersByTime(1);                        // eşik aşıldı → kilit devre dışı
      expect(h.state.eb.d).toEqual({ e1: 1 });
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
      expect(h.cmi["cmi.core.exit"]).toBe("normal");
    } finally { vi.useRealTimers(); }
  });

  it("FINDING A (2004): the same single-screen course, completion_status held back", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        is2004: true,
        screens: [{ id: "e1", embed: { completion: "time_threshold", minSeconds: 3 } }],
      });
      expect(h.cmi["cmi.completion_status"]).toBe("incomplete");
      vi.advanceTimersByTime(3000);
      expect(h.cmi["cmi.completion_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });

  // ---- fix round 3 / FINDING B: on_message sözleşmesi (core/project.py) artık UYGULANIYOR ----
  it("FINDING B: a single on_message embed course does NOT complete without a message", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_message" } }] });
    expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");   // sıfır mesaj
    h.post({ scorm: "setScore", value: 40 }, "e1");               // skor bildirmek tamamlanma DEĞİL
    expect(h.cmi["cmi.core.score.raw"]).toBe("40");
    expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
    expect(h.state.eb.m).toBeUndefined();
    h.finish();                                                   // exit → yine tamamlanmadı
    expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
  });

  it("FINDING B: the on_message gate opens when THAT screen's artifact reports complete", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_message" } }] });
    h.post({ scorm: "complete" }, "e1");
    expect(h.state.eb.m).toEqual({ e1: 1 });
    expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    expect(h.log[h.log.length - 1]).toBe("commit");   // kapı açılışı commit edilir
  });

  // fix round 4 / FIX 2 NOTU: round 3'te bu test e1 bildirdikten SONRA
  // `completion_status === "completed"` bekliyordu (eb.c pini kilidin üstündeydi) — yani FINDING
  // B'nin ta kendisini, iki ekranlı biçiminde, DOĞRU davranış diye kilitliyordu. Artifact pini
  // artık bekleyen kapının ALTINDADIR.
  it("FINDING B: with two on_message screens, one report is not enough (per-screen ledger)", () => {
    const h = harness({
      is2004: true,
      screens: [{ id: "e1", embed: { completion: "on_message" } },
                { id: "e2", embed: { completion: "on_message" } }],
    });
    h.go(1);
    h.post({ scorm: "complete" }, "e1");
    expect(h.state.eb.m).toEqual({ e1: 1 });
    expect(h.state.eb.c).toBe("completed");                      // kayıt tutulur (pin geri gelecek)
    expect(h.cmi["cmi.completion_status"]).toBe("incomplete");   // e2'nin kapısı BEKLİYOR
    h.post({ scorm: "complete" }, "e2");
    expect(h.state.eb.m).toEqual({ e1: 1, e2: 1 });
    expect(h.cmi["cmi.completion_status"]).toBe("completed");
  });

  // --------------------------------------------------------------------------- //
  // fix round 4 — FIX 1: kilit, bekleyen kapıda "completed"i COMMIT ETTİRMEZ
  // --------------------------------------------------------------------------- //
  // Round 3'te sıra "origEvaluate() → kilit" idi ve origEvaluate persist()→sCommit() yapıyordu:
  // yani HER evaluate()'te önce `completed` YAZILIP COMMIT EDİLİYOR, sonra `incomplete`e
  // düşürülüyordu. Tamamlanmayı ilk commit'te MANDALLAYAN bir LMS'te (1.2 raporlamasında ve 2004
  // rollup'ında yaygın) kapı özelliği sessizce hiç çalışmazdı. Bunu YALNIZ log düzeyinde bir
  // assertion yakalar — son durum her iki hâlde de "incomplete"tir.
  const DONE_12 = (l) => /^set:cmi\.core\.lesson_status=(completed|passed)$/.test(l);
  const DONE_2004 = (l) => /^set:cmi\.completion_status=completed$/.test(l);

  it("FIX 1: while a gate pends, NO evaluate() writes completed/passed (1.2, write LOG)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } }],
      });
      // fix round 5 — Sentinel ÖNCESİ (bootstrap showAt) yazım da artık LMS'e ULAŞMAZ: vekil
      // (EMBED_SHIM_JS) motorun API'sinin ALTINDA durur. Round 4'te burada TAM OLARAK BİR
      // "completed" vardı; bu satır o "bir"i "sıfır"a çeker.
      expect(h.log.slice(0, h.boot).filter(DONE_12)).toEqual([]);
      // Sentinel SONRASI: EMBED_JS'in init evaluate()'i + her gezinme/exit → HİÇBİRİ yazmamalı.
      expect(h.log.slice(h.boot).filter(DONE_12)).toEqual([]);
      h.finish(); h.finish();
      expect(h.log.slice(h.boot).filter(DONE_12)).toEqual([]);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      vi.advanceTimersByTime(5000);                     // kapı açıldı → kilit kalkar
      expect(h.log.slice(h.boot).filter(DONE_12)).toEqual(["set:cmi.core.lesson_status=completed"]);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });

  it("FIX 1 (2004): the same at completion_status level", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        is2004: true,
        screens: [{ id: "s1" }, { id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } }],
      });
      h.go(1);
      expect(h.log.slice(h.boot).filter(DONE_2004)).toEqual([]);
      h.finish();
      expect(h.log.slice(h.boot).filter(DONE_2004)).toEqual([]);
      vi.advanceTimersByTime(5000);
      expect(h.log.slice(h.boot).filter(DONE_2004)).toEqual(["set:cmi.completion_status=completed"]);
    } finally { vi.useRealTimers(); }
  });

  // fix round 5 / "ALSO FIX" — kapı beklerken motor "complete" hesaplar ve `exit=normal` yazar;
  // bu, `persist()` içindeki sCommit'te COMMIT edilir, kilidin `exit=suspend`'i ANCAK ondan sonra
  // gelir. FIX 1'in kapattığı kusurun `exit` anahtarındaki aynı biçimi — aynı sSet sarmalayıcısıyla
  // kapatılır. YALNIZ log seviyesinde görünür: son durum her iki hâlde de "suspend"tir.
  it("ALSO FIX: while a gate pends, no evaluate() commits a transient exit=normal (write LOG)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } }],
      });
      const EXIT_N = (l) => l === "set:cmi.core.exit=normal";
      expect(h.log.filter(EXIT_N)).toEqual([]);
      h.finish(); h.finish();
      expect(h.log.filter(EXIT_N)).toEqual([]);
      expect(h.cmi["cmi.core.exit"]).toBe("suspend");
      vi.advanceTimersByTime(5000);                     // kapı açıldı → normal exit serbest
      expect(h.log.filter(EXIT_N)).toEqual(["set:cmi.core.exit=normal"]);
      expect(h.cmi["cmi.core.exit"]).toBe("normal");
    } finally { vi.useRealTimers(); }
  });

  it("FIX 1: a pending on_message gate holds the engine's completed the same way", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_message" } }] });
    expect(h.log.slice(h.boot).filter(DONE_12)).toEqual([]);
    h.post({ scorm: "setScore", value: 40 }, "e1");
    h.finish();
    expect(h.log.slice(h.boot).filter(DONE_12)).toEqual([]);
    h.post({ scorm: "complete" }, "e1");                // kapı açıldı
    // kapı açılınca iki yazım: (1) motorun evaluate()'i, (2) artifact pini (eb.c) — ikisi de meşru
    expect(h.log.slice(h.boot).filter(DONE_12)).toEqual([
      "set:cmi.core.lesson_status=completed", "set:cmi.core.lesson_status=completed",
    ]);
  });

  // --------------------------------------------------------------------------- //
  // fix round 4 — FIX 2: bekleyen kapı, artifact pininden ÜSTÜNDÜR
  // --------------------------------------------------------------------------- //
  it("FIX 2: screen A's artifact 'complete' cannot outrank screen B's pending gate", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "a1", embed: { completion: "on_view" } },
                  { id: "b1", embed: { completion: "time_threshold", minSeconds: 600 } }],
      });
      h.post({ scorm: "complete" }, "a1");
      expect(h.state.eb.c).toBe("completed");                    // kayıt TUTULUR (pin geri gelecek)
      expect(h.log[h.log.length - 1]).toBe("commit");            // ...ve suspend_data'ya persist edilir
      expect(h.log.slice(h.boot).filter(DONE_12)).toEqual([]);   // ama cmi'ye YAZILMAZ
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      expect(h.cmi["cmi.core.exit"]).toBe("suspend");
      h.go(1);                                                   // b1'e gir → sayaç kurulur
      h.finish();
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      vi.advanceTimersByTime(600000);                            // b1'in kapısı açıldı
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });

  it("FIX 2: the artifact pin survives the hold-back and is re-applied when the gate opens", () => {
    const h = harness({
      is2004: true,
      screens: [{ id: "a1", embed: { completion: "on_view" } },
                { id: "b1", embed: { completion: "on_message" } }],
    });
    h.go(1);
    h.post({ scorm: "setStatus", value: "completed" }, "a1");
    expect(h.cmi["cmi.completion_status"]).toBe("incomplete");
    h.post({ scorm: "complete" }, "b1");                         // b1'in kapısı açıldı
    expect(h.cmi["cmi.completion_status"]).toBe("completed");
  });

  // ---- geçiş serbestliği: tamamlanma İMA ETMEYEN değerler ve skor/success_status dokunulmaz ----
  it("FIX 1/2 (1.2): failed / browsed / incomplete still reach lesson_status while a gate pends", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "a1", embed: { completion: "on_view" } },
                  { id: "b1", embed: { completion: "time_threshold", minSeconds: 600 } }],
      });
      h.post({ scorm: "failed" }, "a1");
      expect(h.cmi["cmi.core.lesson_status"]).toBe("failed");
      h.post({ scorm: "setStatus", value: "browsed" }, "a1");
      expect(h.cmi["cmi.core.lesson_status"]).toBe("browsed");
      h.post({ scorm: "setStatus", value: "incomplete" }, "a1");
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      // ...ama 1.2'de `passed` tek başarı kanalı olan lesson_status'tadır ve tamamlanma İMA EDER →
      // kapı beklerken TUTULUR (FIX 2'nin kabul edilen bedeli, CONTRACTS.md §9'da belgeli).
      h.post({ scorm: "passed" }, "a1");
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      expect(h.state.eb.c).toBe("passed");                       // kayıt DURUYOR
      h.go(1);                                                   // b1'e gir → sayaç kurulur
      vi.advanceTimersByTime(600000);                            // kapı açıldı → pin geri konur
      expect(h.cmi["cmi.core.lesson_status"]).toBe("passed");
    } finally { vi.useRealTimers(); }
  });

  it("FIX 1/2 (2004): score + success_status keep pin priority while a gate pends", () => {
    const h = harness({
      is2004: true,
      screens: [{ id: "a1", embed: { completion: "on_view" } },
                { id: "b1", embed: { completion: "on_message" } }],
    });
    h.post({ scorm: "setScore", value: 85 }, "a1");
    h.post({ scorm: "passed" }, "a1");         // 2004: AYRI kanal (success_status) → kilitten muaf
    expect(h.cmi["cmi.score.raw"]).toBe("85");
    expect(h.cmi["cmi.score.scaled"]).toBe("0.8500");
    expect(h.cmi["cmi.success_status"]).toBe("passed");
    expect(h.cmi["cmi.completion_status"]).toBe("incomplete");
    h.finish();                                // evaluate() sonrası da korunur
    expect(h.cmi["cmi.score.raw"]).toBe("85");
    expect(h.cmi["cmi.success_status"]).toBe("passed");
    expect(h.cmi["cmi.completion_status"]).toBe("incomplete");
  });

  // ---- fix round 3 / FINDING C: history-pop yolu (prev) kapıyı sonsuza dek kilitlemez ----
  it("FINDING C: the history-pop path arms the gate timer (no permanent stall)", () => {
    vi.useFakeTimers();
    try {
      // Oturum 1: s1 → e1 → s3 yürüdü, eşik dolmadan bitti. Oturum 2: s3'te devam ediyor.
      const resumed = { visited: { s1: true, e1: true, s3: true }, results: {},
                        history: ["s1", "e1"], cursorId: "s3", reachedEnd: true };
      const h = harness({
        screens: [{ id: "s1" },
                  { id: "e1", embed: { completion: "time_threshold", minSeconds: 10 } },
                  { id: "s3" }],
        state: resumed, startIdx: 2,
      });
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");   // kapı bekliyor
      vi.advanceTimersByTime(60000);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");   // s3'te sayaç yok

      h.prev();                                  // history'den e1'e dönüş — showAt ÇAĞRILMAZ
      expect(h.state.cursorId).toBe("e1");
      vi.advanceTimersByTime(9999);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      vi.advanceTimersByTime(1);                 // sayaç bu yolda da kuruldu → kapı açıldı
      expect(h.state.eb.d).toEqual({ e1: 1 });
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });

  it("FINDING C: prev()'s history fast-path really does bypass showAt/evaluate (mirror sanity)", () => {
    // Yansının FINDING C'yi gerçekten modellediğinin kanıtı: prev() evaluate() ÇAĞIRMAZ
    // (log'a hiçbir set/persist eklenmez), yalnız updateChrome + persist yapar.
    const h = harness({ screens: [{ id: "s1" }, { id: "s2" }] });
    h.go(1);
    const before = h.log.length;
    h.prev();
    expect(h.log.slice(before)).toEqual(["persist", "commit"]);   // evaluate() yok
    expect(h.state.cursorId).toBe("s1");
  });

  // ---- fix round 3 / FINDING D: ilerleme göstergesi kapı çevresinde tutarlı ----
  it("FINDING D: the displayed progress always matches state.visited (no phantom %)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "s1" }, { id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } },
                  { id: "s3" }],
      });
      const shown = () => Math.round((Object.keys(h.state.visited).length / 3) * 100);
      expect(h.chrome.pct).toBe(33);
      expect(h.chrome.pct).toBe(shown());
      h.go(1);                                   // kapılı ekrana gir
      // round 2'de burada gösterge %67, state.visited ise %33 idi (updateChrome evaluate'ten ÖNCE
      // koşuyor, kapı ise anahtarı SONRA siliyordu).
      expect(h.chrome.pct).toBe(67);
      expect(h.chrome.pct).toBe(shown());
      expect(h.chrome.dots[1]).toContain("v");
      const callsBefore = h.chrome.calls;
      vi.advanceTimersByTime(5000);              // kapı açıldı → chrome TAZELENİR
      expect(h.chrome.calls).toBeGreaterThan(callsBefore);
      expect(h.chrome.pct).toBe(shown());
    } finally { vi.useRealTimers(); }
  });

  // ---- erişilemeyen (visible_if=false) ekranın kapısı kursu kilitlemez ----
  it("a gate on a hidden (visible_if false) screen does not lock the course forever", () => {
    vi.useFakeTimers();
    try {
      const h = harness({
        screens: [{ id: "s1" }, { id: "e1", embed: { completion: "time_threshold", minSeconds: 10 } }],
        hidden: { e1: true },
      });
      h.go(1);                                   // (motor next()'te atlardı; burada doğrudan)
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
      expect(h.state.eb.d).toBeUndefined();      // kapı hiç açılmadı, yine de kilit yok
    } finally { vi.useRealTimers(); }
  });

  it("a satisfied gate stays satisfied after resume (eb.d persists, no re-gating)", () => {
    vi.useFakeTimers();
    try {
      const prev = { visited: { e1: true, s2: true }, results: {}, history: [], eb: { d: { e1: 1 } } };
      const h = harness({
        screens: [{ id: "e1", embed: { completion: "time_threshold", minSeconds: 10 } },
                  { id: "s2" }],
        state: prev,
      });
      // önceki oturumda eşik aşılmıştı → kilit hiç devreye girmez
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
      vi.advanceTimersByTime(20000);
      expect(h.state.eb.d).toEqual({ e1: 1 });
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });
});

// --------------------------------------------------------------------------- //
// fix round 5 — EMBED_SHIM_JS: LMS-ADAPTÖR VEKİLİ (bootstrap penceresi)
//
// ENGINE_JS'in bootstrap showAt(startIdx,false)'u (ENGINE_JS'in sonundaki init bloğu) sentinel'den — yani
// EMBED_JS'ten — ÖNCE koşar; kapılı TEK ekranlı (ya da embed'i son ekranda olan) kursta o anda
// tam olarak bir "completed" + Commit LMS'e gidiyordu. Tamamlanmayı İLK commit'te MANDALLAYAN
// LMS'te kapı daha doğmadan yeniliyordu. ENGINE_JS'in sırası bayt-parite yüzünden
// değiştirilemez → kapı motorun ALTINA, API katmanına kurulur (extras engine_js'ten ÖNCE basılır).
//
// Bu blok vekili GERÇEK şablon metniyle (templates.py'den kesilen EMBED_SHIM_JS) ve gerçek bir
// adaptör nesnesiyle çalıştırır. SINIR: yansı hâlâ elle yazılmış bir motor kopyasıdır; gerçek
// tarayıcı/gerçek LMS uçtan uca doğrulaması DEĞİLDİR.
// --------------------------------------------------------------------------- //

// fix round 6 — VEKİLİ TEK BAŞINA koşturan mini runner. harness() her şeyi TEK bir senkron
// fonksiyon gövdesinde çalıştırdığı için "vekil ile ENGINE_JS arasına bir görev sınırı düşerse"
// senaryosu orada ÜRETİLEMEZ. Burada vekil yalnız başına koşturulur ve araya gerçek bir görev
// sınırı (advanceTimersByTime) konur: round 5'in setTimeout(release,0) failsafe'i bu noktada
// bastırmayı EMEKLİ EDİYORDU — yani motor bootstrap'i kapı KAPALI değilken koşabiliyordu.
function shimOnly(opts) {
  const o = Object.assign({ is2004: false, completion: "time_threshold",
                            readyState: "loading" }, opts);
  const frames = [{ dataset: { completion: o.completion } }];
  const domListeners = [];
  const doc = {
    readyState: o.readyState,
    querySelectorAll: (sel) => (sel === "iframe.embed-frame" ? frames.slice() : []),
    addEventListener: (type, fn) => { if (type === "DOMContentLoaded") domListeners.push(fn); },
  };
  const log = [];
  const setName = o.is2004 ? "SetValue" : "LMSSetValue";
  const real = { __real: true };
  real[setName] = function (k, v) { log.push("set:" + k + "=" + v); return "true"; };
  const win = { SCORMEMBED: EMB };
  win.parent = win;
  win[o.is2004 ? "API_1484_11" : "API"] = real;
  new Function("window", "document", "setTimeout", SHIM_JS)(win, doc, setTimeout);
  return {
    win, doc, log, real,
    name: o.is2004 ? "API_1484_11" : "API",
    domReady: () => { doc.readyState = "interactive"; domListeners.slice().forEach((f) => f()); },
  };
}

describe("EMBED_SHIM_JS (LMS adapter proxy, real template text)", () => {
  const DONE_12 = (l) => /^set:cmi\.core\.lesson_status=(completed|passed)$/.test(l);
  const DONE_2004 = (l) => /^set:cmi\.completion_status=completed$/.test(l);
  const gated12 = { screens: [{ id: "e1", embed: { completion: "time_threshold", minSeconds: 5 } }] };

  // ---- fix round 6 / FIX 1: bırakma tetiği bir GÖREV SINIRINDA ateşlenmemeli ---------------- //
  it("FIX 1: a task boundary between the shim and ENGINE_JS must NOT retire suppression", () => {
    vi.useFakeTimers();
    try {
      const s = shimOnly({});
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(true);
      // Satır içi script'ler TEK bir parser görevinde koşmak ZORUNDA DEĞİLDİR: shim ile
      // {engine_js} arasında ~4.5KB + kurs JSON'u var, chunk sınırı oraya düşebilir.
      vi.advanceTimersByTime(0);
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(true);    // round 5'te FALSE'tu (KUSUR)
      expect(s.win[s.name].__scormEmbedShim).toBe(true);          // vekil hâlâ zincirde
      expect(s.win[s.name].LMSSetValue("cmi.core.lesson_status", "completed")).toBe("true");
      expect(s.log).toEqual([]);                                  // ...ve LMS'e gitmedi
      // ...bırakma DOMContentLoaded'da (TÜM senkron script'lerden SONRA) olur.
      s.domReady();
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(false);
      // adaptör BU window'un KENDİ özelliğiydi → undo onu aynen geri yazar (silmez)
      expect(s.win[s.name]).toBe(s.real);
      s.win[s.name].LMSSetValue("cmi.core.lesson_status", "completed");
      expect(s.log).toEqual(["set:cmi.core.lesson_status=completed"]);
    } finally { vi.useRealTimers(); }
  });

  it("FIX 1: 2004 flavor behaves identically at the task boundary", () => {
    vi.useFakeTimers();
    try {
      const s = shimOnly({ is2004: true, completion: "on_message" });
      vi.advanceTimersByTime(1000);
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(true);
      s.domReady();
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(false);
    } finally { vi.useRealTimers(); }
  });

  it("FIX 1: if parsing already finished, the shim falls back to a timer (never locked forever)", () => {
    vi.useFakeTimers();
    try {
      // Bu dal gerçek belgede ERİŞİLEMEZ (vekil satır içi, ayrıştırma sürerken koşar) ama
      // kısıt 6'nın amacı — kurs SONSUZA KADAR kilitli kalamaz — burada da korunur.
      const s = shimOnly({ readyState: "complete" });
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(true);
      vi.advanceTimersByTime(0);
      expect(s.win.__SCORM_EMBED_SHIM__.pending()).toBe(false);
    } finally { vi.useRealTimers(); }
  });

  // ---- fix round 6 / FIX 2: metot varlığı KURULUM'da değil ÇAĞRI'da sınanır ----------------- //
  it("FIX 2: the proxy defines the full surface even when the adapter's methods appear LATER", () => {
    const h = harness({ ...gated12, skipEmbedJs: true, lmsLate: true });
    const p = h.win.API;
    expect(p.__scormEmbedShim).toBe(true);
    // round 5: kurulum anında typeof kontrolü yapıldığı için burası HEPSİ undefined'dı → motor
    // vekili `api` değişkenine kilitliyor ve TÜM SCORM raporlaması sessizce kayboluyordu.
    ["LMSInitialize", "LMSFinish", "LMSGetValue", "LMSSetValue", "LMSCommit", "LMSGetLastError",
     "LMSGetErrorString", "LMSGetDiagnostic"].forEach((n) => expect(typeof p[n]).toBe("function"));
    h.populateApi();                       // applet/eklenti ŞİMDİ hazır
    expect(p.LMSInitialize("")).toBe("true");
    expect(p.LMSSetValue("cmi.core.score.raw", "42")).toBe("true");
    expect(p.LMSGetValue("cmi.core.score.raw")).toBe("42");
    expect(h.log).toContain("set:cmi.core.score.raw=42");
    expect(h.realApi.calls.every((c) => c[3] === true)).toBe(true);   // `this` yine gerçek adaptör
  });

  it("FIX 2: while the method is still missing the proxy THROWS — exactly like the bare placeholder", () => {
    const h = harness({ ...gated12, skipEmbedJs: true, lmsLate: true });
    const p = h.win.API;
    const before = h.log.length;
    // KARAR: uydurma bir dönüş değeri YOK. Vekilsiz hâlde motor `api.LMSGetValue(...)` çağırır ve
    // TypeError alır; sSet/sGet/sInit hepsi bunu zaten yutar. "true" döndürmek başarısızlığı
    // MASKELERDİ; metot başına sahte değer üretmek vekilsiz hâlde olmayan bir hata yüzeyi icat eder.
    expect(() => p.LMSGetValue("cmi.core.entry")).toThrow(TypeError);
    expect(() => p.LMSCommit("")).toThrow(TypeError);
    // ...ama BASTIRMA dalı metottan ÖNCE gelir: kapı beklerken tamamlanma yazımı yine tutulur.
    expect(p.LMSSetValue("cmi.core.lesson_status", "completed")).toBe("true");
    expect(h.log.slice(before)).toEqual([]);
  });

  it("FIX 2 (defect shape): a late-populating adapter no longer loses ALL SCORM reporting", () => {
    vi.useFakeTimers();
    try {
      const h = harness({ ...gated12, lmsLate: true });
      h.populateApi();                          // eklenti kuruldu (bootstrap'ten hemen sonra)
      vi.advanceTimersByTime(5000);             // kapı açıldı
      // round 5: [] — motor sıfır-metotlu vekili tuttuğu için oturum boyunca HİÇBİR yazım gitmedi.
      expect(h.log.filter(DONE_12)).toEqual(["set:cmi.core.lesson_status=completed"]);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });

  it("bootstrap: ZERO completed/passed reaches the LMS before the gate opens (1.2)", () => {
    vi.useFakeTimers();
    try {
      const h = harness(gated12);
      expect(h.log.slice(0, h.boot).filter(DONE_12)).toEqual([]);   // vekil bootstrap'i yuttu
      expect(h.log.filter(DONE_12)).toEqual([]);                    // ...ve sonrası da temiz
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
      vi.advanceTimersByTime(5000);                                 // kapı açıldı
      expect(h.log.filter(DONE_12)).toEqual(["set:cmi.core.lesson_status=completed"]);
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
    } finally { vi.useRealTimers(); }
  });

  it("bootstrap: the same at completion_status level (2004)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({ is2004: true, ...gated12 });
      expect(h.log.slice(0, h.boot).filter(DONE_2004)).toEqual([]);
      expect(h.log.filter(DONE_2004)).toEqual([]);
      vi.advanceTimersByTime(5000);
      expect(h.log.filter(DONE_2004)).toEqual(["set:cmi.completion_status=completed"]);
    } finally { vi.useRealTimers(); }
  });

  it("KUSUR ÜRETİMİ: without the shim the bootstrap write DOES reach the LMS (round-4 state)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({ ...gated12, skipShim: true });
      // round 4'ün kilidi (EMBED_JS/wrapSet) bunu yakalayamaz: bootstrap ondan ÖNCE koşar.
      expect(h.log.slice(0, h.boot).filter(DONE_12)).toEqual(["set:cmi.core.lesson_status=completed"]);
      expect(h.log.slice(0, h.boot)).toContain("commit");           // ...ve COMMIT edildi
    } finally { vi.useRealTimers(); }
  });

  it("bootstrap: exit=normal is held back too (same defect shape, 'ALSO FIX')", () => {
    vi.useFakeTimers();
    try {
      const h = harness(gated12);
      expect(h.log.slice(0, h.boot)).not.toContain("set:cmi.core.exit=normal");
      expect(h.cmi["cmi.core.exit"]).toBe("suspend");               // kilit tutarlı çifti yazdı
      const noShim = harness({ ...gated12, skipShim: true });
      expect(noShim.log.slice(0, noShim.boot)).toContain("set:cmi.core.exit=normal");
    } finally { vi.useRealTimers(); }
  });

  it("is NOT installed when no screen is gated (on_view only)", () => {
    const h = harness({ screens: [{ id: "e1", embed: { completion: "on_view" } }] });
    expect(h.win.API).toBeUndefined();          // window'a hiçbir vekil konmadı
    expect(h.engineApi).toBe(h.realApi);        // motor doğrudan gerçek adaptöre bağlandı
    expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
  });

  it("MIXED: one on_view screen + one gated screen still installs the proxy", () => {
    vi.useFakeTimers();
    try {
      // fix round 6 — renderer artık vekili YALNIZ kapılı kursta basıyor; "kapılı kurs"un tanımı
      // ekran-BAŞINA değil KURS-başınadır: tek bir kapılı ekran yeter.
      const h = harness({ screens: [
        { id: "a1", embed: { completion: "on_view" } },
        { id: "b1", embed: { completion: "time_threshold", minSeconds: 5 } },
      ] });
      expect(h.engineApi.__scormEmbedShim).toBe(true);
      expect(h.log.slice(0, h.boot).filter(DONE_12)).toEqual([]);
    } finally { vi.useRealTimers(); }
  });

  it("is NOT installed when there is no upstream LMS API (engine's local fallback survives)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({ ...gated12, lms: "none" });
      expect(h.realApi).toBe(null);
      // getAPI() yerel Scorm12API fallback'ini kurdu ve window.API ONA eşit — vekile DEĞİL.
      expect(h.win.API).toBe(h.engineApi);
      expect(h.engineApi.__real).toBe(true);
      expect(h.engineApi.__scormEmbedShim).toBeUndefined();
      // Not: fallback yolunda bootstrap yazımı bastırılmaz (bastırılacak bir LMS yok) — ama
      // EMBED_JS'in kilidi yine çalışır, bu yüzden son durum "incomplete"tir.
      expect(h.cmi["cmi.core.lesson_status"]).toBe("incomplete");
    } finally { vi.useRealTimers(); }
  });

  it("finds the API through window.opener too (getAPI's second leg)", () => {
    vi.useFakeTimers();
    try {
      const h = harness({ ...gated12, lms: "opener" });
      // vekil KURULDU: motorun getAPI()'si onu değişkene aldı (window'daki ad devirde geri
      // verildiği için oraya bakılamaz — bkz. HANDOFF testi).
      expect(h.engineApi.__scormEmbedShim).toBe(true);
      expect(h.log.slice(0, h.boot).filter(DONE_12)).toEqual([]);
    } finally { vi.useRealTimers(); }
  });

  it("proxies the FULL 8-method 1.2 surface: return value, args and `this` all delegate", () => {
    const h = harness({ ...gated12, skipEmbedJs: true });
    const p = h.win.API;
    expect(p.__scormEmbedShim).toBe(true);
    expect(p.LMSInitialize("")).toBe("true");
    expect(p.LMSSetValue("cmi.core.score.raw", "42")).toBe("true");
    expect(p.LMSGetValue("cmi.core.score.raw")).toBe("42");
    expect(p.LMSCommit("")).toBe("true");
    expect(p.LMSGetLastError()).toBe("0");
    expect(p.LMSGetErrorString("201")).toBe("err:201");
    expect(p.LMSGetDiagnostic("201")).toBe("diag:201");
    expect(p.LMSFinish("")).toBe("true");
    const names = h.realApi.calls.map((c) => c[0]);
    ["LMSInitialize", "LMSSetValue", "LMSGetValue", "LMSCommit", "LMSGetLastError",
     "LMSGetErrorString", "LMSGetDiagnostic", "LMSFinish"].forEach((n) => {
      expect(names).toContain(n);
    });
    // `this` gerçek adaptöre bağlanır (scorm-again gibi adaptörler buna GÜVENİR)
    expect(h.realApi.calls.every((c) => c[3] === true)).toBe(true);
  });

  it("proxies the FULL 8-method 2004 surface", () => {
    const h = harness({ is2004: true, ...gated12, skipEmbedJs: true });
    const p = h.win.API_1484_11;
    expect(p.__scormEmbedShim).toBe(true);
    ["Initialize", "Terminate", "GetValue", "SetValue", "Commit", "GetLastError",
     "GetErrorString", "GetDiagnostic"].forEach((n) => expect(typeof p[n]).toBe("function"));
    expect(p.SetValue("cmi.score.raw", "42")).toBe("true");
    expect(p.GetValue("cmi.score.raw")).toBe("42");
    expect(p.GetDiagnostic("101")).toBe("diag:101");
  });

  it("error codes propagate through the proxy", () => {
    const h = harness({ ...gated12, skipEmbedJs: true });
    h.realApi.lastError = "403";
    expect(h.win.API.LMSGetLastError()).toBe("403");
    h.realApi.lastError = "0";
    expect(h.win.API.LMSGetLastError()).toBe("0");
  });

  it("passes everything that is not a completion assertion straight through (boot window)", () => {
    const h = harness({ is2004: true, ...gated12, skipEmbedJs: true });
    const p = h.win.API_1484_11;
    const before = h.log.length;
    p.SetValue("cmi.score.raw", "85");
    p.SetValue("cmi.score.scaled", "0.8500");
    p.SetValue("cmi.success_status", "passed");          // 2004'te başarı AYRI kanal
    p.SetValue("cmi.suspend_data", "completed");         // içinde "completed" geçse bile
    p.SetValue("cmi.completion_status", "incomplete");
    p.SetValue("cmi.objectives.0.completion_status", "completed");
    p.SetValue("cmi.completion_status", "completed");    // ← YALNIZ bu bastırılır
    p.SetValue("cmi.exit", "suspend");                   // geçerli vokabüler, geçer
    expect(h.log.slice(before)).toEqual([
      "set:cmi.score.raw=85", "set:cmi.score.scaled=0.8500", "set:cmi.success_status=passed",
      "set:cmi.suspend_data=completed", "set:cmi.completion_status=incomplete",
      "set:cmi.objectives.0.completion_status=completed", "set:cmi.exit=suspend",
    ]);
  });

  it("1.2: passes failed/incomplete/browsed through, suppresses completed/passed", () => {
    const h = harness({ ...gated12, skipEmbedJs: true });
    const p = h.win.API;
    const before = h.log.length;
    ["failed", "incomplete", "browsed", "not attempted", "completed", "passed"].forEach((v) => {
      p.LMSSetValue("cmi.core.lesson_status", v);
    });
    expect(h.log.slice(before)).toEqual([
      "set:cmi.core.lesson_status=failed", "set:cmi.core.lesson_status=incomplete",
      "set:cmi.core.lesson_status=browsed", "set:cmi.core.lesson_status=not attempted",
    ]);
  });

  it("FAILSAFE: if the real lock never installs, suppression dies at DOMContentLoaded", () => {
    vi.useFakeTimers();
    try {
      const h = harness({ ...gated12, skipEmbedJs: true });   // EMBED_JS HİÇ koşmadı
      expect(h.win.API.__scormEmbedShim).toBe(true);
      const before = h.log.length;
      h.win.API.LMSSetValue("cmi.core.lesson_status", "completed");
      expect(h.log.slice(before)).toEqual([]);                // hâlâ bastırılıyor
      // fix round 6: ZAMANLAYICI TEK BAŞINA artık bırakmaz — motorun bootstrap'i, vekil hâlâ
      // ayaktayken koşmuş olmalı; bırakma tüm senkron script'lerden SONRAYA sabitlendi.
      vi.advanceTimersByTime(60000);
      expect(h.win.API.__scormEmbedShim).toBe(true);
      h.win.API.LMSSetValue("cmi.core.lesson_status", "completed");
      expect(h.log.slice(before)).toEqual([]);
      h.domReady();                                           // DOMContentLoaded
      // vekil window'dan ÇEKİLDİ: kendi koyduğumuz özellik silindi → zincir şekli AYNEN geri
      // (gerçek adaptör üst çerçevede; findAPI oraya yürüyerek yine ulaşır).
      expect(Object.prototype.hasOwnProperty.call(h.win, "API")).toBe(false);
      h.engineApi.LMSSetValue("cmi.core.lesson_status", "completed");   // motorun tuttuğu referans
      expect(h.log.slice(before)).toEqual(["set:cmi.core.lesson_status=completed"]);
    } finally { vi.useRealTimers(); }
  });

  it("HANDOFF: EMBED_JS releases the shim, so the two locks never double-suppress", () => {
    vi.useFakeTimers();
    try {
      // Devam eden oturum: kapı ÖNCEKİ oturumda aşılmış (eb.d). Vekil bunu BİLEMEZ (suspend_data'yı
      // okumaz) ve bootstrap yazımını yine de tutar; EMBED_JS'in son evaluate()'i — devirden SONRA
      // koştuğu için — doğru durumu geri yazar. Devir olmasaydı kurs yanlışlıkla kilitli kalırdı.
      const prev = { visited: {}, results: {}, history: [], eb: { d: { e1: 1 } } };
      const h = harness({ ...gated12, state: prev });
      expect(Object.prototype.hasOwnProperty.call(h.win, "API")).toBe(false);   // devir yapıldı
      expect(h.engineApi.__scormEmbedShim).toBe(true);         // ...ama motor referansı şeffaflaştı
      expect(h.cmi["cmi.core.lesson_status"]).toBe("completed");
      expect(h.log.filter(DONE_12).length).toBe(1);           // TAM OLARAK bir kez, EMBED_JS'ten
    } finally { vi.useRealTimers(); }
  });

  it("release() is idempotent and the shim handle is exposed on window", () => {
    const h = harness({ ...gated12, skipEmbedJs: true });
    expect(typeof h.win.__SCORM_EMBED_SHIM__.release).toBe("function");
    expect(h.win.__SCORM_EMBED_SHIM__.pending()).toBe(true);
    h.win.__SCORM_EMBED_SHIM__.release();
    expect(h.win.__SCORM_EMBED_SHIM__.pending()).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(h.win, "API")).toBe(false);
    h.win.__SCORM_EMBED_SHIM__.release();                     // ikinci çağrı zararsız
    expect(Object.prototype.hasOwnProperty.call(h.win, "API")).toBe(false);
  });
});
