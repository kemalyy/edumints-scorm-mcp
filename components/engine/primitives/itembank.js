// components/engine/primitives/itembank.js — W2 mekanik primitifi: parametrik soru bankası.
// Aralıklı tekrar + üretim etkisi: değişkenli madde + çeldirici havuzu + SEED → her oynayışta farklı,
// ama denk zorlukta madde. Determinizm W1 rng'den (Math.random YASAK). eval YOK — deklaratif op seti.
//
// Madde tipleri:
//  - statik:    { id, prompt, answer, distractors:[...] }
//  - parametrik:{ id, template:"{{a}} + {{b}}", vars:{a:{min,max},b:{min,max}},
//                 answer:{op:"add|sub|mul|min|max", operands:["a","b"]},
//                 distractors:{offsets:[-1,1,2]} }   // doğru cevaba göre çeldirici üret

const OPS = {
  add: (a, b) => a + b,
  sub: (a, b) => a - b,
  mul: (a, b) => a * b,
  min: (a, b) => Math.min(a, b),
  max: (a, b) => Math.max(a, b),
};

function _materialize(item, rng) {
  if (!item.vars) {
    // statik
    return {
      id: item.id,
      prompt: item.prompt,
      correct: String(item.answer),
      options: rng.shuffle([String(item.answer), ...(item.distractors || []).map(String)]),
    };
  }
  // parametrik: değişkenleri seed'e göre üret
  const v = {};
  for (const name of Object.keys(item.vars)) {
    const { min, max } = item.vars[name];
    v[name] = rng.int(Number(min), Number(max) + 1); // [min,max] dahil
  }
  const prompt = String(item.template).replace(/\{\{(\w+)\}\}/g, (_, k) => (k in v ? v[k] : `{{${k}}}`));
  const { op, operands } = item.answer;
  const fn = OPS[op] || OPS.add;
  // operands = değişken İSİMLERİ → önce DEĞERLERE çevir, sonra soldan-katla
  const vals = operands.map((name) => v[name]);
  const ans = vals.reduce((acc, x, i) => (i === 0 ? x : fn(acc, x)));
  const offsets = (item.distractors && item.distractors.offsets) || [-2, -1, 1, 2];
  const distractors = rng
    .shuffle(offsets)
    .slice(0, 3)
    .map((o) => ans + o)
    .filter((d) => d !== ans);
  return {
    id: item.id,
    prompt,
    correct: String(ans),
    options: rng.shuffle([String(ans), ...distractors.map(String)]),
  };
}

export function createItemBank({ items = [] } = {}, rng) {
  if (!rng) throw new Error("itembank: deterministik W1 rng gerekli (Math.random YASAK)");
  return {
    /** n madde çek (seed'e göre seçim + materyalize) */
    draw(n = 1) {
      const picked = rng.shuffle(items).slice(0, Math.min(n, items.length));
      return picked.map((it) => _materialize(it, rng));
    },
    /** tek madde (id'ye göre, materyalize) */
    get(id) {
      const it = items.find((x) => x.id === id);
      return it ? _materialize(it, rng) : null;
    },
    size: items.length,
  };
}
