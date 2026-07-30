"""tests/test_theme_audience.py — Senaryo hattı Faz 5: kitle (audience) katmanı MEKANİZMASI.

Katman sırası (CONTRACTS §1.1): _tokens → stil preseti → audience override → kurs custom.
Faz 5 paket sevk etmez (6'lı set tanımlı değil) — yalnız yükleyici desteği + sözleşme
(themes/audience/_README.md). Kitle paketi sıfırdan tema OLAMAZ ve ekran tipi kısıtlayamaz (3.7).
"""
import json
from pathlib import Path

import pytest
from auth.errors import ToolError

import server
from core.project import ThemeTokens

THEMES_DIR = Path("themes")
TOKENS_PATH = THEMES_DIR / "_tokens.json"


# --------------------------------------------------------------------------- #
# 5) Kitle (audience) katmanı — mekanizma
# --------------------------------------------------------------------------- #
def _mini_themes(tmp_path: Path) -> Path:
    """Gerçek _tokens + yapay preset içeren geçici tema dizini."""
    (tmp_path / "_tokens.json").write_text(TOKENS_PATH.read_text(encoding="utf-8"))
    (tmp_path / "preset.json").write_text(json.dumps({
        "name": "preset", "extends": "_tokens",
        "color": {"primary": "#111111", "text": "#222222"},
    }))
    aud = tmp_path / "audience"
    aud.mkdir()
    return aud


def test_audience_layer_sits_between_preset_and_course_custom(tmp_path, monkeypatch):
    aud = _mini_themes(tmp_path)
    (aud / "k12-lise.json").write_text(json.dumps({
        "color": {"primary": "#333333", "accent": "#444444"},
    }))
    monkeypatch.setattr(server, "THEMES_DIR", tmp_path)

    # preset + audience: audience preset'i ezer, dokunmadıkları mirastan gelir
    t = server._load_theme("preset", audience="k12-lise")
    assert t.color.primary == "#333333"   # audience > preset
    assert t.color.text == "#222222"      # preset korunur
    assert t.color.accent == "#444444"    # audience yeni override
    assert t.name == "preset"             # kitle paketi tema kimliği DEĞİLDİR

    # kurs custom (tam ThemeTokens) audience'ı ezer: katman sırasının tepesi
    course = ThemeTokens.model_validate({"name": "kurs", "color": {"primary": "#555555"}})
    t2 = server._load_theme(course, audience="k12-lise")
    assert t2.color.primary == "#555555"  # kurs custom > audience
    assert t2.color.accent == "#444444"   # kursun AÇIKÇA vermediği alanda audience görünür


def test_audience_missing_file_is_contracted_noop(tmp_path, monkeypatch):
    _mini_themes(tmp_path)
    monkeypatch.setattr(server, "THEMES_DIR", tmp_path)
    t = server._load_theme("preset", audience="mevcut-degil")
    assert t.model_dump() == server._load_theme("preset").model_dump()


def test_audience_file_may_not_extend(tmp_path, monkeypatch):
    aud = _mini_themes(tmp_path)
    (aud / "kotu.json").write_text(json.dumps({"extends": "preset", "color": {"bg": "#000000"}}))
    monkeypatch.setattr(server, "THEMES_DIR", tmp_path)
    with pytest.raises(ToolError, match="AUDIENCE_NO_EXTENDS"):
        server._load_theme("preset", audience="kotu")


def test_audience_name_is_guarded(tmp_path, monkeypatch):
    """Yol enjeksiyonu: kitle adı makine-dostu desenle sınırlı (CourseSpec ile aynı)."""
    _mini_themes(tmp_path)
    monkeypatch.setattr(server, "THEMES_DIR", tmp_path)
    with pytest.raises(ToolError):
        server._load_theme("preset", audience="../preset")


def test_audience_none_behavior_unchanged():
    """audience verilmediğinde bugünkü davranış bayt-bayt korunur (3.3)."""
    for name in ("default", "dark", "style-premium"):
        a = server._load_theme(name).model_dump()
        b = server._load_theme(name, audience=None).model_dump()
        assert a == b
