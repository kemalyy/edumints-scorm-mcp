import { describe, it, expect } from "vitest";
import {
  encodeState, decodeState, byteLength, fitsScorm12, SCORM12_SUSPEND_MAX,
  packKeys, unpackKeys, serializeForTarget, deserialize,
} from "../../components/engine/state.js";

describe("state serileştirici (versiyonlu + bütçe-bilinçli)", () => {
  it("encode → decode round-trip", () => {
    const s = { score: 30, lives: 2, node: "n3", visited: ["n1", "n2"] };
    const { version, state } = decodeState(encodeState(s, 1));
    expect(version).toBe(1);
    expect(state).toEqual(s);
  });

  it("ileri-göç (migration) eski sürümü güncele taşır", () => {
    const oldStr = encodeState({ pts: 10 }, 1);
    const migrations = { 1: (d) => ({ score: d.pts }) }; // v1 pts → v2 score
    const { version, state } = decodeState(oldStr, migrations);
    expect(version).toBe(2);
    expect(state).toEqual({ score: 10 });
  });

  it("şema-bilinçli anahtar kısaltma (pack/unpack) round-trip + küçülme", () => {
    const alias = { score: "s", lives: "l", visited: "v", inventory: "i" };
    const s = { score: 100, lives: 3, visited: ["a", "b", "c"], inventory: ["key", "map"] };
    const packed = packKeys(s, alias);
    expect(packed).toEqual({ s: 100, l: 3, v: ["a", "b", "c"], i: ["key", "map"] });
    expect(unpackKeys(packed, alias)).toEqual(s);
    // kısaltma gerçekten küçültür
    expect(byteLength(JSON.stringify(packed))).toBeLessThan(byteLength(JSON.stringify(s)));
  });

  it("SCORM 1.2 4096B kırmızı çizgisi — temsili oyun durumu sığar", () => {
    // gerçekçi kaçış-odası durumu: 6 istasyon, envanter, ipucu sayaçları, skor
    const alias = { score: "s", lives: "l", station: "st", solved: "sv", hints: "h", inv: "iv", seed: "sd" };
    const state = {
      seed: "cyber-escape-2026", score: 240, lives: 2, station: 4,
      solved: [true, true, true, true, false, false],
      hints: [0, 1, 0, 2, 0, 0],
      inv: ["badge", "usb", "note", "code-fragment"],
    };
    const r = serializeForTarget(state, { version: 1, alias, target: "scorm12" });
    expect(r.fits).toBe(true);
    expect(r.bytes).toBeLessThanOrEqual(SCORM12_SUSPEND_MAX);
    expect(deserialize(r.str, { alias }).state).toEqual(state);
  });

  it("aşırı büyük durum scorm12'ye SIĞMAZ → degrade sinyali", () => {
    const big = { blob: "x".repeat(5000) };
    const r = serializeForTarget(big, { target: "scorm12" });
    expect(r.fits).toBe(false); // runtime 2004/cmi5'e degrade etmeli
    const r2 = serializeForTarget(big, { target: "cmi5" });
    expect(r2.fits).toBe(true); // cmi5 sınırsız
  });

  it("scorm2004 hedefi 64K sınır + alias'sız yol", () => {
    const state = { a: 1, b: [1, 2, 3] };
    const r = serializeForTarget(state, { target: "scorm2004" }); // alias yok
    expect(r.limit).toBe(64000);
    expect(r.fits).toBe(true);
    expect(deserialize(r.str).state).toEqual(state); // alias'sız deserialize
  });

  it("packKeys iç içe dizi/obje + alias dışı anahtar korunur", () => {
    const alias = { score: "s" };
    const s = { score: 5, meta: { keep: [{ score: 1 }] } };
    const p = packKeys(s, alias);
    expect(p).toEqual({ s: 5, meta: { keep: [{ s: 1 }] } }); // iç içe de kısalır
    expect(unpackKeys(p, alias)).toEqual(s);
  });

  it("fitsScorm12 + byteLength UTF-8", () => {
    expect(fitsScorm12("a".repeat(4096))).toBe(true);
    expect(fitsScorm12("a".repeat(4097))).toBe(false);
    expect(byteLength("é")).toBe(2); // UTF-8 çok-byte
  });
});
