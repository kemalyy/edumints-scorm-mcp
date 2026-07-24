"""tests/test_theme_style_variants.py — W10: stil-varyantı preset'lerinin ÇÖZÜMLENMİŞ (extends dahil)
custom_css'i marka renginden bağımsız çalışmalı (yalnız var(--c-*) token referansı, nötr #000/#fff
istisnası dışında sabit hex renk kodu YOK) — böylece herhangi bir marka rengiyle set_theme ile
birleştirilebilir."""
import re

import pytest

import server

STYLE_VARIANTS = ["style-minimal", "style-playful", "style-premium"]

# #fff / #ffffff / #000 / #000000 (case-insensitive) nötr color-mix ortağı olarak izinli;
# başka HERHANGİ bir hex kod (3/6/8 haneli) yasak.
_NEUTRAL_HEX = re.compile(r"#(fff|000)(fff|000)?\b", re.IGNORECASE)
_ANY_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


@pytest.mark.parametrize("name", STYLE_VARIANTS)
def test_style_variant_resolved_custom_css_has_no_brand_hex(name):
    resolved = server._load_theme(name)
    css = resolved.custom_css or ""
    non_neutral = [m.group(0) for m in _ANY_HEX.finditer(css) if not _NEUTRAL_HEX.fullmatch(m.group(0))]
    assert non_neutral == [], f"{name} çözümlenmiş custom_css'te sabit marka rengi bulundu: {non_neutral}"


@pytest.mark.parametrize("name", STYLE_VARIANTS)
def test_style_variant_resolved_custom_css_uses_color_tokens(name):
    resolved = server._load_theme(name)
    css = resolved.custom_css or ""
    assert "var(--c-" in css, f"{name} çözümlenmiş custom_css hiç renk token'ı kullanmıyor"


def test_style_variants_load_as_valid_theme_tokens():
    for name in STYLE_VARIANTS:
        resolved = server._load_theme(name)
        assert resolved.name == name


def test_style_playful_inherits_structure_from_playground_not_copies():
    """style-playful.json'ın KENDİ dosyasında custom_css yok — extends ile playground'dan miras
    alınıyor. Bu test hem mirasın çalıştığını hem duplikasyon olmadığını kanıtlıyor."""
    import json
    from pathlib import Path

    raw = json.loads((Path("themes") / "style-playful.json").read_text(encoding="utf-8"))
    assert "custom_css" not in raw
    assert raw.get("extends") == "playground"

    resolved = server._load_theme("style-playful")
    playground = server._load_theme("playground")
    assert resolved.custom_css == playground.custom_css      # yapı miras alındı
    assert resolved.color.primary != playground.color.primary  # renk override edildi
