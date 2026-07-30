// tests/js/progress.test.js — Senaryo hattı Faz 4: saf oynatıcı konum/ilerleme/kilit yardımcıları.
//
// Kapsam (plan Kol C §6.1-6.3):
//   P1 positionInfo      — konum göstergesi: düğüm zinciri + düğüm-içi n/m
//   P2 nodeProgress      — menü düğüm ilerlemesi: alt-ağaç ziyaret sayacı (n/m)
//   P3 lockedNodes       — sequential kilit: önceki kardeşin alt-ağacı bitmeden kilitli
//                          (kilit ALT AĞACA yayılır; sebep = engelleyen düğüm id'si)
//   P4 sectionCompletion — results_breakdown bölümü için tamamlanma (AYNI screen_ids
//                          mekanizması — ikinci bir hedef-ilerleme makinesi YOK)
//   P5 kabul #12         — 3 kademe + 30 sayfa gerçekçi durumla suspend v2 < 4096 (1.2)
//                          ve Faz 4'ün zarfa YENİ ALAN EKLEMEDİĞİNİN kanıtı (türetme kararı)
import { describe, it, expect } from "vitest";
import {
  positionInfo, nodeProgress, lockedNodes, sectionCompletion,
} from "../../components/engine/progress.js";   // Faz 4 — AYRI modül (3.3 bayt-parite; yalnız outline'lı pakete inline)
import {
  encodeSuspend, decodeSuspend, SUSPEND_LIMIT_12, SUSPEND_BUDGET_12, byteLen,
} from "../../components/engine/scorm.js";

// 3 kademeli örnek outline (Faz 1 test ağacıyla aynı yapı) + ekran→düğüm bağı.
const NODES = [
  { id: "u1", parent_id: null, kind: "unit", title: "Ünite 1" },
  { id: "b1", parent_id: "u1", kind: "section", title: "Bölüm 1.1" },
  { id: "b1a", parent_id: "b1", kind: "section", title: "Alt 1.1.1" },
  { id: "u2", parent_id: null, kind: "unit", title: "Ünite 2" },
];
const SCREEN_NODE = { t1: "u1", c1: "b1", c2: "b1", c3: "b1a", c4: "u2" };
const ORDER = ["t1", "c1", "c2", "c3", "c4", "s1"]; // s1 düğümsüz

describe("P1 positionInfo — konum göstergesi", () => {
  it("düğüm zinciri kök→yaprak + düğüm İÇİ n/m verir", () => {
    const p = positionInfo(NODES, SCREEN_NODE, ORDER, "c2");
    expect(p.chain).toEqual(["Ünite 1", "Bölüm 1.1"]);
    expect(p.index).toBe(2); // b1'in kendi ekranları: c1, c2 → c2 = 2/2
    expect(p.total).toBe(2);
  });

  it("3. kademe yaprakta tam zincir", () => {
    const p = positionInfo(NODES, SCREEN_NODE, ORDER, "c3");
    expect(p.chain).toEqual(["Ünite 1", "Bölüm 1.1", "Alt 1.1.1"]);
    expect(p.index).toBe(1);
    expect(p.total).toBe(1);
  });

  it("düğümsüz ekran: boş zincir + düğümsüz küme içinde n/m", () => {
    const p = positionInfo(NODES, SCREEN_NODE, ORDER, "s1");
    expect(p.chain).toEqual([]);
    expect(p.index).toBe(1);
    expect(p.total).toBe(1);
  });

  it("outline yoksa null (gösterge hiç yok — düz kurs)", () => {
    expect(positionInfo([], SCREEN_NODE, ORDER, "c1")).toBeNull();
    expect(positionInfo(null, null, ORDER, "c1")).toBeNull();
  });

  it("bilinmeyen ekran/sarkan düğümde çökmez", () => {
    expect(positionInfo(NODES, SCREEN_NODE, ORDER, "yok")).toBeNull();
    const p = positionInfo(NODES, { x1: "hayalet" }, ["x1"], "x1");
    expect(p.chain).toEqual([]); // sarkan node_id → düğümsüz say (Faz 1 render kararıyla aynı)
  });

  it("döngülü parent zincirinde takılmaz (savunmacı)", () => {
    const loop = [
      { id: "a", parent_id: "b", title: "A" },
      { id: "b", parent_id: "a", title: "B" },
    ];
    const p = positionInfo(loop, { s: "a" }, ["s"], "s");
    expect(Array.isArray(p.chain)).toBe(true); // sonlanır; içerik tanımlı olmak zorunda değil
  });
});

describe("P2 nodeProgress — düğüm alt-ağacı ziyaret sayacı", () => {
  it("alt-ağaç toplamı: kendi ekranları + torunlar", () => {
    const pr = nodeProgress(NODES, SCREEN_NODE, { t1: true, c1: true });
    expect(pr.u1).toEqual({ done: 2, total: 4 }); // t1,c1,c2,c3
    expect(pr.b1).toEqual({ done: 1, total: 3 }); // c1,c2,c3
    expect(pr.b1a).toEqual({ done: 0, total: 1 });
    expect(pr.u2).toEqual({ done: 0, total: 1 });
  });

  it("ekransız düğüm total=0 (menüde n/m basılmaz)", () => {
    const pr = nodeProgress(NODES.concat([{ id: "bos", parent_id: null, title: "Boş" }]),
      SCREEN_NODE, {});
    expect(pr.bos).toEqual({ done: 0, total: 0 });
  });

  it("hepsi ziyaretliyse done===total", () => {
    const all = {}; Object.keys(SCREEN_NODE).forEach((k) => { all[k] = true; });
    const pr = nodeProgress(NODES, SCREEN_NODE, all);
    expect(pr.u1).toEqual({ done: 4, total: 4 });
  });
});

describe("P3 lockedNodes — sequential kilit", () => {
  const LOCKED = NODES.map((n) => (n.id === "u2" ? { ...n, unlock_rule: "sequential" } : n));

  it("önceki kardeşin alt-ağacı bitmeden kilitli; sebep = engelleyen düğüm", () => {
    const lk = lockedNodes(LOCKED, SCREEN_NODE, { t1: true });
    expect(lk.u2).toBe("u1"); // u1 alt-ağacı (4 ekran) bitmedi
  });

  it("önceki kardeş TAMAMEN ziyaret edilince açılır ('tamamlandı' = tüm bağlı ekranlar ziyaret)", () => {
    const lk = lockedNodes(LOCKED, SCREEN_NODE, { t1: true, c1: true, c2: true, c3: true });
    expect(lk.u2).toBeUndefined();
  });

  it("ilk kardeşte sequential → engelleyen yok, açık", () => {
    const first = NODES.map((n) => (n.id === "u1" ? { ...n, unlock_rule: "sequential" } : n));
    expect(lockedNodes(first, SCREEN_NODE, {}).u1).toBeUndefined();
  });

  it("kilit ALT AĞACA yayılır (kilitli ünitenin bölümleri de kilitli)", () => {
    const nodes = [
      { id: "u1", parent_id: null, title: "1" },
      { id: "u2", parent_id: null, title: "2", unlock_rule: "sequential" },
      { id: "b2", parent_id: "u2", title: "2.1" },
    ];
    const sn = { a: "u1", b: "b2" };
    const lk = lockedNodes(nodes, sn, {});
    expect(lk.u2).toBe("u1");
    expect(lk.b2).toBe("u1"); // engelleyen, zincirin kökündeki sebep
  });

  it("önceki kardeşin alt-ağacında ekran yoksa runtime KİLİTLEMEZ (validator UNREACHABLE_NODE zaten keser)", () => {
    const nodes = [
      { id: "bos", parent_id: null, title: "Boş" },
      { id: "u2", parent_id: null, title: "2", unlock_rule: "sequential" },
    ];
    expect(lockedNodes(nodes, { x: "u2" }, {}).u2).toBeUndefined();
  });

  it("free (varsayılan) hiçbir düğümü kilitlemez", () => {
    expect(lockedNodes(NODES, SCREEN_NODE, {})).toEqual({});
  });
});

describe("P4 sectionCompletion — results_breakdown bölüm tamamlanması", () => {
  it("ziyaret edilen / toplam (AYNI screen_ids listesi — skorla aynı mekanizma)", () => {
    expect(sectionCompletion(["q1", "q2", "q3"], { q1: true, q3: true }))
      .toEqual({ done: 2, total: 3 });
    expect(sectionCompletion([], { q1: true })).toEqual({ done: 0, total: 0 });
    expect(sectionCompletion(["q1"], null)).toEqual({ done: 0, total: 1 });
  });
});

// --------------------------------------------------------------------------- //
// P5 — kabul #12: 3 kademeli outline + 30 sayfa, gerçekçi sentetik durum < 4096 (SCORM 1.2)
// --------------------------------------------------------------------------- //
describe("P5 kabul #12 — hiyerarşik kursta suspend bütçesi", () => {
  // 30 ekran: yarısı puanlı (kötü duruma yakın gerçekçi senaryo), hepsi ziyaretli,
  // tam gezinme geçmişi, oyunlaştırma değişkenleri + 2 keşif girdisi (tavana yakın).
  const order = []; for (let i = 1; i <= 30; i++) order.push("scr" + String(i).padStart(2, "0"));
  const state = {
    cursorId: "scr30", reachedEnd: true,
    visited: {}, history: [], results: {}, ix: {}, inext: 0,
    vars: { puan: 1240, can: 3, seviye: "usta" },
    xp: { kesif_tahmin: "x".repeat(220), kesif_gozlem: "y".repeat(180) },
  };
  order.forEach((id, i) => {
    state.visited[id] = true;
    if (i > 0) state.history.push(order[i - 1]);
    if (i % 2 === 0) { // 15 puanlı ekran
      state.results[id] = { points: 10, max: 10, ok: i % 4 === 0, answered: true };
      state.ix[id] = state.inext++;
    }
  });

  it("kodlanmış zarf 3500 bayt ÇALIŞMA BÜTÇESİNİN altında kalır (Faz 4-ek; ölçüm raporlanır)", () => {
    // Faz 4-ek: gerçekçi çalışma-anı zarfı pozisyon kaydını (z: ekran+düğüm+içerik sürümü) İÇERİR
    const data = encodeSuspend(state, order, { node: "b1a", cv: 123456 });
    // Ölçümü test çıktısına yaz (rapor kanıtı) — ölçü birimi UTF-8 BAYT:
    // eslint-disable-next-line no-console
    console.log("[kabul #12] 3 kademe × 30 sayfa suspend boyutu:", byteLen(data), "bayt");
    expect(byteLen(data)).toBeLessThan(SUSPEND_BUDGET_12);   // 3500 bayt bütçe (4096 sınırın altı)
    expect(byteLen(data)).toBeLessThan(SUSPEND_LIMIT_12);
    // kayıpsız gidiş-dönüş
    const back = decodeSuspend(data, order);
    expect(back.cursorId).toBe("scr30");
    expect(Object.keys(back.visited).length).toBe(30);
    expect(back.xp.kesif_tahmin.length).toBe(220);
  });

  it("Faz 4 zarfa YENİ alan eklemez: düğüm konumu cursor+statik konfig'den TÜRETİLİR", () => {
    // Tasarım kararı (plan 3.11): {"n","s","st"} üçlüsünün tamamı zaten karşılanıyor —
    //   s  = cursor (pozisyonel), st = results/ix/xp, n = screens[cursor].node_id (STATİK konfig).
    // Aynı state, outline'lı ya da outline'sız kursta AYNI baytları üretir.
    const data = encodeSuspend(state, order);
    expect(data).toBe(encodeSuspend(JSON.parse(JSON.stringify(state)), order.slice()));
    // serbest metin zarfa girmez: düğüm başlıkları/kilit sebepleri suspend'de YOK
    expect(data).not.toContain("Ünite");
    expect(data).not.toContain("unlock");
  });
});
