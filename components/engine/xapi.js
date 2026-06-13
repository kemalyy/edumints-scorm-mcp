// components/engine/xapi.js — W5 telemetri: motor olaylarını xAPI (Experience API) ifadelerine çevirir.
// Saf-mantık, DOM'suz, AĞSIZ, deterministik (actor + timestamp DIŞARIDAN enjekte → vitest'te sabit).
// W5b runtime bunu olay veriyolundan besler + (cmi5/explicit) bir LRS'e iletir; bu modül YALNIZ ifade KURAR.
// ECD bağlantısı: her gözlemlenebilir (kanıt) bir statement → stealth assessment telemetrisi (Shute).
//
// xAPI ifadesi: { actor, verb, object, result?, context?, timestamp?, id? }. Standart ADL fiil IRI'leri.

export const XAPI_VERBS = {
  answered: "http://adlnet.gov/expapi/verbs/answered",
  experienced: "http://adlnet.gov/expapi/verbs/experienced",
  completed: "http://adlnet.gov/expapi/verbs/completed",
  passed: "http://adlnet.gov/expapi/verbs/passed",
  failed: "http://adlnet.gov/expapi/verbs/failed",
  progressed: "http://adlnet.gov/expapi/verbs/progressed",
  mastered: "http://adlnet.gov/expapi/verbs/mastered",
};

// edumints uzantı IRI'leri (sonuç ekleri — adaptif yeterlilik/ipucu sinyalleri)
export const XAPI_EXT = {
  difficulty: "https://edumints.com/xapi/ext/difficulty",
  ability: "https://edumints.com/xapi/ext/ability",
  mastery: "https://edumints.com/xapi/ext/mastery",
  hintCost: "https://edumints.com/xapi/ext/hint-cost",
  hintIndex: "https://edumints.com/xapi/ext/hint-index",
};

export function verb(key) {
  return { id: XAPI_VERBS[key] || key, display: { "en-US": key } };
}

export function activity(id, { name, description, type } = {}) {
  const def = {};
  if (name) def.name = { "en-US": name };
  if (description) def.description = { "en-US": description };
  if (type) def.type = type;
  const obj = { objectType: "Activity", id: String(id) };
  if (Object.keys(def).length) obj.definition = def;
  return obj;
}

function isoDuration(ms) {
  return "PT" + (Math.max(0, Math.round((Number(ms) || 0) / 100)) / 10) + "S";
}

// Bir result nesnesi kur (yalnız verilen alanlar; xAPI şemasına uygun).
export function result(opts = {}) {
  const r = {};
  if (opts.success != null) r.success = !!opts.success;
  if (opts.completion != null) r.completion = !!opts.completion;
  const score = {};
  if (opts.scoreRaw != null) score.raw = Number(opts.scoreRaw);
  if (opts.scoreMin != null) score.min = Number(opts.scoreMin);
  if (opts.scoreMax != null) score.max = Number(opts.scoreMax);
  if (opts.scoreScaled != null) score.scaled = Number(opts.scoreScaled);
  if (Object.keys(score).length) r.score = score;
  if (opts.response != null) r.response = String(opts.response);
  if (opts.durationMs != null) r.duration = isoDuration(opts.durationMs);
  if (opts.extensions && Object.keys(opts.extensions).length) r.extensions = opts.extensions;
  return r;
}

// Tam bir ifade kur (tanımsız alanları düşürür). actor/verb/object zorunlu.
export function statement({ actor, verb: v, object, result: res, context, timestamp, id }) {
  const s = { actor, verb: v, object };
  if (res && Object.keys(res).length) s.result = res;
  if (context) s.context = context;
  if (timestamp) s.timestamp = timestamp;
  if (id) s.id = id;
  return s;
}

// --- W5b: başlatma bağlamı (cmi5/xAPI launch) — saf ayrıştırma (DOM/ağ runtime'da) -----------
// cmi5/xAPI AU başlatma sorgusu: ?endpoint=&fetch=&auth=&actor=&registration=&activityId=
// fetch → auth-token almak için POST edilecek URL (runtime); auth → doğrudan token (bazı LMS).
export function parseLaunch(search = "") {
  const s = String(search).replace(/^\?/, "");
  const q = {};
  if (s) {
    for (const pair of s.split("&")) {
      if (!pair) continue;
      const i = pair.indexOf("=");
      const k = decodeURIComponent(i < 0 ? pair : pair.slice(0, i));
      q[k] = i < 0 ? "" : decodeURIComponent(pair.slice(i + 1).replace(/\+/g, " "));
    }
  }
  const out = {};
  for (const key of ["endpoint", "fetch", "auth", "registration", "activityId"]) {
    if (q[key]) out[key] = q[key];
  }
  if (q.actor) out.actor = normalizeActor(q.actor);
  return out;
}

// Ham actor (cmi5 JSON / isim / nesne) → geçerli xAPI Agent. Tanımsız → anonim hesap.
export function normalizeActor(raw) {
  let a = raw;
  if (typeof raw === "string") {
    try { a = JSON.parse(raw); } catch (e) { a = { name: raw }; }
  }
  if (a && (a.mbox || a.account || a.mbox_sha1sum || a.openid)) {
    return Object.assign({ objectType: "Agent" }, a);
  }
  const name = (a && (a.name || (a.account && a.account.name))) || "anonymous";
  return { objectType: "Agent", account: { homePage: "https://edumints.com", name: String(name) } };
}

// Motor olayı → ifade. ctx: { actor, activityBase, timestamp?, context? }. W5b olay veriyolundan çağırır.
export function fromEngineEvent(event, payload = {}, ctx = {}) {
  const actor = ctx.actor;
  const base = ctx.activityBase || "https://edumints.com/xapi/activity";
  const ts = ctx.timestamp;
  const ext = (m) => (m && Object.keys(m).length ? m : undefined);
  const mk = (vkey, suffix, res, name) =>
    statement({
      actor, verb: verb(vkey),
      object: activity(suffix ? base + "/" + suffix : base, name ? { name } : {}),
      result: res, context: ctx.context, timestamp: ts,
    });

  switch (event) {
    case "choice.taken":
      return mk("answered", payload.node, result({ response: payload.choice }), "decision");
    case "answer":
      return mk("answered", payload.itemId, result({
        success: payload.correct, response: payload.response,
        extensions: ext(payload.difficulty != null ? { [XAPI_EXT.difficulty]: payload.difficulty } : null),
      }), "item");
    case "adaptive.observe":
      return mk("answered", payload.itemId, result({
        success: payload.correct,
        extensions: ext(payload.ability != null ? { [XAPI_EXT.ability]: payload.ability }
                      : payload.mastery != null ? { [XAPI_EXT.mastery]: payload.mastery } : null),
      }), "item");
    case "hint.revealed":
      return mk("experienced", "hint", result({
        extensions: { [XAPI_EXT.hintCost]: payload.cost || 0, [XAPI_EXT.hintIndex]: payload.index },
      }), "hint");
    case "lives.depleted":
      return mk("failed", null, result({ success: false, completion: true }), "game");
    case "finalize":
      return mk(payload.ok ? "passed" : "failed", null, result({
        success: !!payload.ok, completion: true, scoreRaw: payload.score, scoreMax: payload.max,
      }), "activity");
    default:
      return mk("experienced", event, undefined, event);
  }
}
