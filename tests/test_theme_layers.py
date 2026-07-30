"""tests/test_theme_layers.py — Senaryo hattı Faz 5 (Kol D §7.1): tema konsolidasyonu.

Garantiler:
  1) themes/_tokens.json = TEK taban semantik token seti; içeriği ThemeTokens model
     varsayılanlarıyla BİREBİR aynı (çift-yönlü drift bekçisi: kod ↔ dosya).
  2) Her sevk edilen tema dosyası bir extends zinciriyle _tokens'a ulaşır (kendisi taban
     DEĞİL, override katmanı). Zincir sonlu ve döngüsüz.
  3) Çözülmüş (extends dahil) token seti tema başına fixture'a kilitli
     (tests/fixtures/themes_resolved.json) — konsolidasyon regresyonu: katmanlamaya
     geçiş hiçbir temanın SONUÇ token'larını değiştirmez. Bilinçli AA düzeltmeleri bu
     fixture'ı yeniden üreterek yapılır (delta PR gövdesinde raporlanır).
  4) Döngüsel extends hâlâ tespit edilir (ToolError).
  5) Katman sırası (CONTRACTS §1.1): _tokens → stil preseti → kitle (audience) override →
     kurs custom. Kitle katmanı Faz 5'te YALNIZ mekanizmadır (paket sevk edilmez):
     - themes/audience/<pack>.json varsa preset'in ÜZERİNE, kurs custom'ın ALTINA merge edilir;
     - yoksa no-op (audience_pack tema-dışı davranışlar da taşıyabilir — sessiz düşüş DEĞİL,
       sözleşmeli yokluk; bkz. themes/audience/_README.md);
     - kitle dosyası sıfırdan tema OLAMAZ: "extends" içermesi hata (AUDIENCE_NO_EXTENDS).
"""
import json
from pathlib import Path

import pytest
from auth.errors import ToolError

import server
from core.project import ThemeTokens

THEMES_DIR = Path("themes")
TOKENS_PATH = THEMES_DIR / "_tokens.json"
RESOLVED_FIXTURE = Path("tests/fixtures/themes_resolved.json")


def _shipped_theme_files() -> list[Path]:
    """Sevk edilen tema preset dosyaları: themes/**/*.json, _-öneklihariç, audience/ hariç."""
    return sorted(
        p for p in THEMES_DIR.rglob("*.json")
        if not p.name.startswith("_") and "audience" not in p.parts
    )


def _theme_name(p: Path) -> str:
    return str(p.relative_to(THEMES_DIR))[: -len(".json")]


# --------------------------------------------------------------------------- #
# 1) _tokens.json ↔ ThemeTokens model varsayılanları senkron
# --------------------------------------------------------------------------- #
def test_tokens_base_exists_and_matches_model_defaults():
    assert TOKENS_PATH.exists(), "themes/_tokens.json (taban token seti) yok"
    raw = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    assert "extends" not in raw, "_tokens taban katmandır; extends kullanamaz"
    loaded = ThemeTokens.model_validate(raw)
    expected = ThemeTokens(name="_tokens")
    assert loaded.model_dump() == expected.model_dump(), (
        "themes/_tokens.json ile ThemeTokens model varsayılanları birbirinden saptı — "
        "ikisi tek kaynak olarak senkron tutulmalı"
    )


# --------------------------------------------------------------------------- #
# 2) Her tema override katmanıdır: extends zinciri _tokens'a ulaşır
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", _shipped_theme_files(), ids=_theme_name)
def test_theme_extends_chain_reaches_tokens(path):
    seen: set[str] = set()
    cur = path
    for _ in range(6):  # sonlu zincir; makul derinlik tavanı
        raw = json.loads(cur.read_text(encoding="utf-8"))
        parent = raw.get("extends")
        assert parent is not None, (
            f"{path} extends zinciri _tokens'a ulaşmadan bitti ({cur}) — her tema "
            "_tokens üzerinde bir override katmanı olmalı"
        )
        if parent == "_tokens":
            return
        assert parent not in seen, f"{path}: extends döngüsü ({parent})"
        seen.add(parent)
        cur = THEMES_DIR / f"{parent}.json"
        assert cur.exists(), f"{path}: extends hedefi yok: {parent}"
    pytest.fail(f"{path}: extends zinciri çok derin (>6)")


# --------------------------------------------------------------------------- #
# 3) Çözülmüş token regresyonu (fixture kilidi)
# --------------------------------------------------------------------------- #
def test_resolved_tokens_match_fixture():
    fixture = json.loads(RESOLVED_FIXTURE.read_text(encoding="utf-8"))
    names = [_theme_name(p) for p in _shipped_theme_files()]
    assert sorted(fixture) == sorted(names), (
        "fixture tema listesi diskle uyuşmuyor — tema eklendi/silindiyse fixture'ı "
        "bilinçli olarak yeniden üret (PR'da raporla)"
    )
    for name in names:
        resolved = server._load_theme(name).model_dump(mode="json")
        assert resolved == fixture[name], (
            f"tema '{name}' çözülmüş token seti fixture'dan saptı — istenmeyen regresyon "
            "veya raporlanmamış bilinçli değişiklik"
        )


# --------------------------------------------------------------------------- #
# 4) Döngü tespiti korunur
# --------------------------------------------------------------------------- #
def test_extends_cycle_still_detected(tmp_path, monkeypatch):
    (tmp_path / "a.json").write_text(json.dumps({"name": "a", "extends": "b"}))
    (tmp_path / "b.json").write_text(json.dumps({"name": "b", "extends": "a"}))
    monkeypatch.setattr(server, "THEMES_DIR", tmp_path)
    with pytest.raises(ToolError):
        server._load_theme("a")


# --------------------------------------------------------------------------- #
# 6) _tokens seçilebilir preset olarak SIZMAZ
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_themes_hides_infrastructure_layers():
    from fastmcp import Client

    async with Client(server.mcp) as c:
        res = await c.call_tool("list_themes", {})
    names = [t["name"] for t in res.data["themes"]]
    assert "_tokens" not in names
    assert "default" in names
