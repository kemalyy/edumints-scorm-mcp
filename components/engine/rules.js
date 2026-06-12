// components/engine/rules.js — W3 kural motoru: "when <olay> if <koşul> then <aksiyon>".
// Deklaratif, eval YOK. Olay veriyoluna bağlanır; mekanik primitiflere + değişkenlere etki eder.
// Storyline trigger modelinin tam karşılığı. Saf-mantık, vitest'le test edilir.
//
// rule: { when:"choice.taken", if?:{var,cmp,value}, then:[ {do:"score.correct", points:10}, ... ] }
// ctx:  { vars:{}, mechanics:{score,lives,timer,hints,...}, bus }
// Aksiyonlar deklaratif (do + parametreler); bilinmeyen do güvenle yutulur.

const CMP = {
  "==": (a, b) => a === b, "!=": (a, b) => a !== b,
  ">": (a, b) => Number(a) > Number(b), "<": (a, b) => Number(a) < Number(b),
  ">=": (a, b) => Number(a) >= Number(b), "<=": (a, b) => Number(a) <= Number(b),
};

export function evalCond(cond, vars = {}) {
  if (!cond) return true;
  const fn = CMP[cond.cmp] || CMP["=="];
  return fn(vars[cond.var], cond.value);
}

// Aksiyon kayıt defteri — her do bir ctx-operatörü. Genişletilebilir.
export const ACTIONS = {
  "score.correct": (a, ctx) => ctx.mechanics.score && ctx.mechanics.score.correct(a.points),
  "score.wrong": (a, ctx) => ctx.mechanics.score && ctx.mechanics.score.wrong(),
  "score.add": (a, ctx) => ctx.mechanics.score && ctx.mechanics.score.add(a.value),
  "lives.lose": (a, ctx) => ctx.mechanics.lives && ctx.mechanics.lives.lose(a.n != null ? a.n : 1),
  "lives.gain": (a, ctx) => ctx.mechanics.lives && ctx.mechanics.lives.gain(a.n != null ? a.n : 1),
  "timer.extend": (a, ctx) => ctx.mechanics.timer && ctx.mechanics.timer.extend(a.sec),
  "timer.disable": (a, ctx) => ctx.mechanics.timer && ctx.mechanics.timer.disable(),
  "hint.reveal": (a, ctx) => ctx.mechanics.hints && ctx.mechanics.hints.reveal(),
  "var.set": (a, ctx) => { ctx.vars[a.var] = a.value; },
  "var.add": (a, ctx) => { ctx.vars[a.var] = (Number(ctx.vars[a.var]) || 0) + (Number(a.value) || 0); },
  "emit": (a, ctx) => ctx.bus && ctx.bus.emit(a.event, a.payload || null),
};

// Tek bir kuralı bir olaya karşı değerlendir + çalıştır (test için saf).
export function runRule(rule, payload, ctx) {
  if (!evalCond(rule.if, ctx.vars)) return false;
  for (const act of rule.then || []) {
    const fn = ACTIONS[act.do];
    if (fn) fn(act, ctx);
  }
  return true;
}

// Kuralları olay veriyoluna bağla — her kural kendi `when` olayını dinler.
// Döner: detach() — tüm abonelikleri kaldırır.
export function attachRules(rules, ctx) {
  if (!ctx.bus) throw new Error("attachRules: ctx.bus (eventbus) gerekli");
  const offs = [];
  for (const rule of rules || []) {
    offs.push(ctx.bus.on(rule.when, (payload) => runRule(rule, payload, ctx)));
  }
  return () => offs.forEach((off) => off());
}
