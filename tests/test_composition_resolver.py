import pytest

from core.composition import CompositionError, load_catalog, resolve_spec
from core.project import CompositionSpec


def test_catalog_has_seven_presets():
    assert set(load_catalog()) == {"centered", "split-thirds", "split-halves", "hero-focal",
                                   "statement", "z-flow", "f-flow"}


def test_preset_by_name():
    r = resolve_spec("split-thirds", "content_slide")
    assert r.preset == "split-thirds" and r.cols == "1fr 1fr 1fr"
    assert r.areas["support"] == (1, 1, 4, 2)
    assert r.areas["focal"] == (1, 2, 4, 4)
    assert r.focal == "focal" and r.symmetry == "asymmetric" and r.mirror is False


def test_mirror_flips_columns():
    r = resolve_spec(CompositionSpec(preset="split-thirds", mirror=True), "content_slide")
    assert r.areas["support"] == (1, 3, 4, 4)
    assert r.areas["focal"] == (1, 1, 4, 3)


def test_override_merges_over_preset():
    r = resolve_spec(CompositionSpec(preset="split-thirds", whitespace="high",
                                     intensity="high"), "content_slide")
    assert r.whitespace == "high" and r.intensity == "high" and r.flow == "z"


def test_free_mode_without_preset():
    r = resolve_spec(CompositionSpec(grid="1:2", areas={"support": "c1r1-c1r3",
                                                        "focal": "c2r1-c2r3"},
                                     focal="focal"), "content_slide")
    assert r.preset is None and r.cols == "1fr 2fr"
    assert r.areas["focal"] == (1, 2, 4, 3)


def test_focal_cell_maps_to_covering_slot():
    r = resolve_spec(CompositionSpec(preset="split-thirds", focal="r2c3"), "content_slide")
    assert r.focal == "focal" and r.focal_cell == "r2c3"


def test_hero_focal_cell_is_background():
    assert resolve_spec("hero-focal", "title_slide").focal == "__background__"


@pytest.mark.parametrize("spec,stype,code", [
    ("nope", "content_slide", "composition_unknown"),
    ("split-thirds", "title_slide", "composition_unknown"),
    ("centered", "mcq", "composition_unknown"),
    (CompositionSpec(grid="thirds", areas={"support": "c4r1-c4r1"}), "content_slide",
     "composition_unknown"),
    (CompositionSpec(grid="thirds", areas={"support": "c2r1-c1r1"}), "content_slide",
     "composition_unknown"),
    (CompositionSpec(grid="thirds", areas={"banner": "c1r1-c1r1"}), "content_slide",
     "composition_unknown"),
    (CompositionSpec(grid="7:x"), "content_slide", "composition_unknown"),
    (CompositionSpec(preset="split-thirds", focal="aux"), "content_slide", "focal_area_empty"),
])
def test_errors(spec, stype, code):
    with pytest.raises(CompositionError) as e:
        resolve_spec(spec, stype)
    assert e.value.code == code


def test_explicit_focal_cell_is_in_displayed_coordinates_even_when_mirrored():
    # "görsel solda (mirror), odak sol-alt kesişimde" → odak görselin yuvası olmalı
    r = resolve_spec(CompositionSpec(preset="split-thirds", mirror=True, focal="r3c1"),
                     "content_slide")
    assert r.focal == "focal" and r.focal_cell == "r3c1"


def test_preset_focal_cell_mirrors_with_layout():
    r = resolve_spec(CompositionSpec(preset="hero-focal", mirror=True), "title_slide")
    assert r.focal_cell == "r1c1"
