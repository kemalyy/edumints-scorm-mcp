import json
from pathlib import Path

from core.project import ThemeTokens
from core.theme_emphasis import resolve_emphasis

THEMES = Path(__file__).resolve().parent.parent / "themes"


def test_derived_from_palette_when_block_missing():
    t = ThemeTokens()
    em = resolve_emphasis(t)
    assert em.e1.color == t.color.primary
    assert em.e2.color == t.color.text
    assert em.e5.color == t.color.text_muted
    # e3: AA'yı geçen ilk aday (accent → primary → metin); zemin 15% renklendirilmiş hex
    assert em.e3.color in (t.color.accent, t.color.primary, t.color.text)
    assert em.e3_bg.startswith("#")


def test_explicit_block_wins():
    raw = json.loads((THEMES / "mint.json").read_text())
    t = ThemeTokens.model_validate({k: v for k, v in raw.items() if k != "extends"})
    em = resolve_emphasis(t)
    assert em.e1.color.lower() == raw["emphasis"]["e1"]["color"].lower()


def test_new_presets_exist_and_define_emphasis():
    for name in ("mint", "ink", "slate"):
        raw = json.loads((THEMES / f"{name}.json").read_text())
        assert raw["name"] == name and "emphasis" in raw
        for lvl in ("e1", "e2", "e3", "e4", "e5"):
            assert raw["emphasis"][lvl]["color"].startswith("#")


def test_default_json_untouched():
    raw = json.loads((THEMES / "default.json").read_text())
    assert "emphasis" not in raw  # classic + default bayt-aynı kalmalı
