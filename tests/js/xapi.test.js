import { describe, it, expect } from "vitest";
import { XAPI_VERBS, XAPI_EXT, verb, activity, result, statement, fromEngineEvent, parseLaunch, normalizeActor }
  from "../../components/engine/xapi.js";

const ACTOR = { objectType: "Agent", account: { homePage: "https://edumints.com", name: "u1" } };
const CTX = { actor: ACTOR, activityBase: "https://edumints.com/xapi/activity/course1", timestamp: "2026-06-13T00:00:00Z" };

describe("xAPI yapı taşları", () => {
  it("verb: bilinen anahtar → ADL IRI + display", () => {
    expect(verb("answered")).toEqual({ id: XAPI_VERBS.answered, display: { "en-US": "answered" } });
    expect(verb("passed").id).toContain("adlnet.gov/expapi/verbs/passed");
  });

  it("activity: objectType + id + opsiyonel definition", () => {
    expect(activity("a/b")).toEqual({ objectType: "Activity", id: "a/b" });
    const a = activity("x", { name: "Soru", type: "http://adlnet.gov/expapi/activities/cmi.interaction" });
    expect(a.definition.name["en-US"]).toBe("Soru");
    expect(a.definition.type).toContain("cmi.interaction");
  });

  it("result: yalnız verilen alanlar; score nesnesi toplanır; duration ISO8601", () => {
    const r = result({ success: true, scoreRaw: 8, scoreMax: 10, response: "a", durationMs: 1500 });
    expect(r).toEqual({ success: true, score: { raw: 8, max: 10 }, response: "a", duration: "PT1.5S" });
    expect(result({})).toEqual({}); // boş → boş
  });

  it("statement: zorunlu alanlar + boş result/undefined düşer", () => {
    const s = statement({ actor: ACTOR, verb: verb("experienced"), object: activity("o"), result: {}, timestamp: "T" });
    expect(s.actor).toBe(ACTOR);
    expect(s.result).toBeUndefined(); // boş result eklenmez
    expect(s.timestamp).toBe("T");
    expect("context" in s).toBe(false);
  });
});

describe("fromEngineEvent (olay → ifade eşleme)", () => {
  it("choice.taken → answered + response, nesne düğüm IRI'si", () => {
    const s = fromEngineEvent("choice.taken", { node: "n1", choice: "a" }, CTX);
    expect(s.verb.id).toBe(XAPI_VERBS.answered);
    expect(s.object.id).toBe(CTX.activityBase + "/n1");
    expect(s.result.response).toBe("a");
    expect(s.timestamp).toBe(CTX.timestamp);
  });

  it("answer → success + difficulty uzantısı", () => {
    const s = fromEngineEvent("answer", { itemId: "q3", correct: true, response: "b", difficulty: 1.5 }, CTX);
    expect(s.result.success).toBe(true);
    expect(s.result.extensions[XAPI_EXT.difficulty]).toBe(1.5);
    expect(s.object.id).toBe(CTX.activityBase + "/q3");
  });

  it("adaptive.observe → ability VEYA mastery uzantısı", () => {
    const e = fromEngineEvent("adaptive.observe", { itemId: "q1", correct: true, ability: 0.7 }, CTX);
    expect(e.result.extensions[XAPI_EXT.ability]).toBe(0.7);
    const b = fromEngineEvent("adaptive.observe", { itemId: "q1", correct: false, mastery: 0.4 }, CTX);
    expect(b.result.extensions[XAPI_EXT.mastery]).toBe(0.4);
    expect(b.result.success).toBe(false);
  });

  it("hint.revealed → experienced + maliyet/indeks uzantısı", () => {
    const s = fromEngineEvent("hint.revealed", { index: 0, cost: 4 }, CTX);
    expect(s.verb.id).toBe(XAPI_VERBS.experienced);
    expect(s.result.extensions[XAPI_EXT.hintCost]).toBe(4);
  });

  it("lives.depleted → failed + completion", () => {
    const s = fromEngineEvent("lives.depleted", {}, CTX);
    expect(s.verb.id).toBe(XAPI_VERBS.failed);
    expect(s.result.completion).toBe(true);
  });

  it("finalize → passed/failed + skor", () => {
    const p = fromEngineEvent("finalize", { ok: true, score: 30, max: 40 }, CTX);
    expect(p.verb.id).toBe(XAPI_VERBS.passed);
    expect(p.result.score).toEqual({ raw: 30, max: 40 });
    expect(p.result.completion).toBe(true);
    const f = fromEngineEvent("finalize", { ok: false, score: 5, max: 40 }, CTX);
    expect(f.verb.id).toBe(XAPI_VERBS.failed);
  });

  it("bilinmeyen olay → experienced fiili, nesne olay adıyla", () => {
    const s = fromEngineEvent("custom.thing", {}, CTX);
    expect(s.verb.id).toBe(XAPI_VERBS.experienced); // varsayılan: experienced (bilinen fiil → IRI)
    expect(s.object.id).toBe(CTX.activityBase + "/custom.thing");
  });

  it("deterministik: aynı girdi → bit-denk ifade (actor+ts enjekte)", () => {
    const a = JSON.stringify(fromEngineEvent("answer", { itemId: "q", correct: true, difficulty: 1 }, CTX));
    const b = JSON.stringify(fromEngineEvent("answer", { itemId: "q", correct: true, difficulty: 1 }, CTX));
    expect(a).toBe(b);
  });
});

describe("parseLaunch (cmi5/xAPI başlatma ayrıştırma)", () => {
  it("cmi5 sorgu parametrelerini ayrıştırır + actor normalize", () => {
    const actor = encodeURIComponent(JSON.stringify({ objectType: "Agent", account: { homePage: "https://lms", name: "42" } }));
    const q = parseLaunch("?endpoint=https%3A%2F%2Flrs%2Fxapi%2F&fetch=https%3A%2F%2Flms%2Ffetch&registration=reg-1&activityId=act-9&actor=" + actor);
    expect(q.endpoint).toBe("https://lrs/xapi/");
    expect(q.fetch).toBe("https://lms/fetch");
    expect(q.registration).toBe("reg-1");
    expect(q.activityId).toBe("act-9");
    expect(q.actor.account.name).toBe("42");
  });

  it("boş/eksik sorgu → boş nesne; bilinmeyen anahtarlar atlanır", () => {
    expect(parseLaunch("")).toEqual({});
    expect(parseLaunch("?foo=bar")).toEqual({});
  });
});

describe("normalizeActor", () => {
  it("hesap/mbox'lu actor → objectType eklenir, korunur", () => {
    expect(normalizeActor({ account: { homePage: "h", name: "n" } }))
      .toEqual({ objectType: "Agent", account: { homePage: "h", name: "n" } });
    expect(normalizeActor({ mbox: "mailto:a@b.c" }).mbox).toBe("mailto:a@b.c");
  });

  it("düz isim/JSON-string → anonim hesaba sarılır", () => {
    expect(normalizeActor("Ada").account.name).toBe("Ada");
    expect(normalizeActor(undefined).account.name).toBe("anonymous");
    expect(normalizeActor('{"name":"Bob"}').account.name).toBe("Bob");
  });
});
