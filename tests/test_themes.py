import json
import pytest
from pathlib import Path

THEMES_DIR = Path("themes")

# Mevcut 6 temadan (academic, agency, dark, default, high-contrast, modern-light) 
# çıkarılan ortak zorunlu token'lar.
MANDATORY_KEYS = {
    "name",
    "background_pattern",
    "typography",
    "color",
}

MANDATORY_TYPOGRAPHY = {
    "font_heading", "font_body", "font_mono", "base_size_px", "scale_ratio",
    "weight_heading", "weight_body", "weight_strong", "line_height_tight",
    "line_height_normal", "letter_spacing_heading"
}

MANDATORY_COLOR = {
    "primary", "primary_hover", "primary_contrast", "secondary", "accent",
    "bg", "surface", "surface_alt", "border", "text", "text_muted",
    "text_on_dark", "success", "success_bg", "error", "error_bg",
    "warning", "info", "focus_ring"
}

# Tüm temaların birleşimi (union) - izin verilen tüm token'lar.
ALLOWED_TOP_LEVEL = MANDATORY_KEYS | {
    "spacing", "radii", "elevation", "motion", "logo_asset_id", "custom_css"
}

ALLOWED_SPACING = {"base_px", "scale", "content_max_width", "gutter"}
ALLOWED_RADII = {"none", "sm", "md", "lg", "pill"}
ALLOWED_ELEVATION = {"e0", "e1", "e2", "e3", "e4"}
ALLOWED_MOTION = {
    "duration_fast", "duration_base", "duration_slow",
    "easing_standard", "easing_emphasized", "slide_transition",
    "reduce_motion_respect"
}

def get_theme_files():
    return list(THEMES_DIR.glob("*.json"))

@pytest.mark.parametrize("theme_path", get_theme_files())
def test_theme_schema_integrity(theme_path):
    with open(theme_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 1. Üst düzey zorunlu anahtarlar
    missing_top = MANDATORY_KEYS - set(data.keys())
    assert not missing_top, f"{theme_path.name} eksik üst düzey anahtarlar: {missing_top}"
    
    # 2. Üst düzey fazla anahtarlar
    extra_top = set(data.keys()) - ALLOWED_TOP_LEVEL
    assert not extra_top, f"{theme_path.name} bilinmeyen üst düzey anahtarlar: {extra_top}"
    
    # 3. Typography detayları (Zorunlu)
    typo = data.get("typography", {})
    missing_typo = MANDATORY_TYPOGRAPHY - set(typo.keys())
    assert not missing_typo, f"{theme_path.name} eksik typography anahtarları: {missing_typo}"
    extra_typo = set(typo.keys()) - MANDATORY_TYPOGRAPHY
    assert not extra_typo, f"{theme_path.name} bilinmeyen typography anahtarları: {extra_typo}"
    
    # 4. Color detayları (Zorunlu)
    color = data.get("color", {})
    missing_color = MANDATORY_COLOR - set(color.keys())
    assert not missing_color, f"{theme_path.name} eksik color anahtarları: {missing_color}"
    extra_color = set(color.keys()) - MANDATORY_COLOR
    assert not extra_color, f"{theme_path.name} bilinmeyen color anahtarları: {extra_color}"
    
    # 5. Opsiyonel grupların iç bütünlüğü (varsa tam olmalı)
    if "spacing" in data:
        missing_sp = ALLOWED_SPACING - set(data["spacing"].keys())
        assert not missing_sp, f"{theme_path.name} spacing grubu eksik: {missing_sp}"
        extra_sp = set(data["spacing"].keys()) - ALLOWED_SPACING
        assert not extra_sp, f"{theme_path.name} spacing grubu bilinmeyen anahtar: {extra_sp}"

    if "radii" in data:
        missing_rd = ALLOWED_RADII - set(data["radii"].keys())
        assert not missing_rd, f"{theme_path.name} radii grubu eksik: {missing_rd}"
        extra_rd = set(data["radii"].keys()) - ALLOWED_RADII
        assert not extra_rd, f"{theme_path.name} radii grubu bilinmeyen anahtar: {extra_rd}"

    if "elevation" in data:
        missing_el = ALLOWED_ELEVATION - set(data["elevation"].keys())
        assert not missing_el, f"{theme_path.name} elevation grubu eksik: {missing_el}"
        extra_el = set(data["elevation"].keys()) - ALLOWED_ELEVATION
        assert not extra_el, f"{theme_path.name} elevation grubu bilinmeyen anahtar: {extra_el}"

    if "motion" in data:
        missing_mt = ALLOWED_MOTION - set(data["motion"].keys())
        assert not missing_mt, f"{theme_path.name} motion grubu eksik: {missing_mt}"
        extra_mt = set(data["motion"].keys()) - ALLOWED_MOTION
        assert not extra_mt, f"{theme_path.name} motion grubu bilinmeyen anahtar: {extra_mt}"
