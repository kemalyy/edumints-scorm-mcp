// components/engine/primitives/branchgraph.js — W2 mekanik primitifi: koşullu düğüm grafiği.
// Dallanan vaka simülasyonu, kaçış-odası istasyonları, quest hatları, anlatı macerası — hepsinin
// kompozisyon substratı. Koşullar deklaratif ({var,cmp,value}); SAHTE-SEÇİM YASAK (W6): her dalın
// sonuç farkı olmalı (effects ya da farklı goto). a11y: navigasyon seçimle (klavye-operable render).
//
// nodes: [{ id, choices:[{ id, to, condition?:{var,cmp,value}, effects?:[{var,op,value}] }] }]
// Olaylar (bus): node.entered {node,via}, choice.taken {choice,from,to}.

const CMP = {
  "==": (a, b) => a === b,
  "!=": (a, b) => a !== b,
  ">": (a, b) => Number(a) > Number(b),
  "<": (a, b) => Number(a) < Number(b),
  ">=": (a, b) => Number(a) >= Number(b),
  "<=": (a, b) => Number(a) <= Number(b),
};

export function evalCondition(cond, vars = {}) {
  if (!cond) return true;
  const fn = CMP[cond.cmp] || CMP["=="];
  return fn(vars[cond.var], cond.value);
}

export function createBranchGraph({ nodes = [], start = null } = {}, bus = null) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  let current = start || (nodes[0] && nodes[0].id) || null;
  const history = current ? [current] : [];

  const emit = (type, payload) => { if (bus) bus.emit(type, payload); };
  const node = () => byId.get(current) || null;

  return {
    current() { return current; },
    node,
    /** koşulu geçen seçenekler (render için) */
    available(vars = {}) {
      const n = node();
      if (!n) return [];
      return (n.choices || []).filter((c) => evalCondition(c.condition, vars));
    },
    /** bir seçim yap → koşul geçerse hedefe git, effects'i applyFn ile uygula */
    choose(choiceId, vars = {}, applyFn = null) {
      const n = node();
      if (!n) return null;
      const c = (n.choices || []).find((x) => x.id === choiceId);
      if (!c || !evalCondition(c.condition, vars)) return null; // geçersiz/kilitli seçim
      if (c.effects && applyFn) for (const e of c.effects) applyFn(e); // {var,op,value}
      const from = current;
      if (c.to && byId.has(c.to)) {
        current = c.to;
        history.push(current);
      }
      emit("choice.taken", { choice: choiceId, from, to: current });
      emit("node.entered", { node: current, via: choiceId });
      return node();
    },
    isTerminal() { const n = node(); return !n || !(n.choices && n.choices.length); },
    history() { return history.slice(); },
    state() { return { current, history: history.slice() }; },
    restore(s) { if (s && s.current && byId.has(s.current)) { current = s.current; history.length = 0; history.push(...(s.history || [current])); } return this; },
  };
}
