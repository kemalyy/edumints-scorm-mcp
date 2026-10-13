import pytest

from core.composition import CompositionError, load_catalog, resolve_spec

K2 = ["hotspot", "labeled_diagram", "image_compare", "data_chart", "video", "lottie", "simulation"]


def test_visual_stack_exists_and_is_band_over_focal():
    r = resolve_spec("visual-stack", "data_chart")
    assert r.areas["support"] == (1, 1, 2, 4) and r.areas["focal"] == (2, 1, 4, 4)
    assert r.focal == "focal" and r.symmetry == "symmetric"


@pytest.mark.parametrize("t", K2)
@pytest.mark.parametrize("preset", ["visual-stack", "split-thirds"])  # centered K2'de yok (review)
def test_presets_apply_to_k2_types(t, preset):
    assert resolve_spec(preset, t).preset == preset


def test_visual_stack_also_applies_to_content_slide():
    assert "content_slide" in load_catalog()["visual-stack"]["applies_to"]


def test_dom_order_default_and_override():
    assert resolve_spec("split-thirds", "hotspot").dom_order == "focal-first"
    assert resolve_spec("split-thirds", "hotspot", dom_order="support-first").dom_order == \
        "support-first"


def test_preset_rejects_type_outside_applies_to():
    with pytest.raises(CompositionError):
        resolve_spec("hero-focal", "embed_html")  # hero-focal yalnız giriş slaytına uyar
