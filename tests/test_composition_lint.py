"""K1 — kompozisyon lint'i (9 kod) + çözülmüş kompozisyon özeti."""
from core.antislop import STRICT_PROMOTED_CODES, lint_course
from core.composition_auto import summary
from core.project import ContentSlide, Project, TitleSlide
from core.validator import validate_project


def P(*screens, comp="auto"):
    return Project(id="p", title="t", composition=comp, screens=list(screens))


def codes(p):
    return {i.code: i.severity for i in lint_course(p)}


def test_unknown_preset_is_error():
    assert codes(P(ContentSlide(title="a", composition="nope")))["composition_unknown"] == "error"


def test_unknown_preset_reported_once_by_validator():
    errs = validate_project(P(ContentSlide(title="a", composition="nope")))
    assert sum("nope" in e.message for e in errs) == 1


def test_focal_area_empty_error():
    s = ContentSlide(title="a", composition={"preset": "split-thirds", "focal": "aux"})
    assert codes(P(s))["focal_area_empty"] == "error"


def test_hero_without_background_is_focal_area_empty():
    assert codes(P(TitleSlide(title="t", composition="hero-focal")))["focal_area_empty"] == "error"


def test_title_only_screen_no_false_positive():
    assert "focal_area_empty" not in codes(P(ContentSlide(title="Yalnız başlık")))


def test_mark_overuse_and_inflation():
    body = "<p>" + " ".join(f"<mark>t{i}</mark>" for i in range(4)) + " düz</p>"
    c = codes(P(ContentSlide(title="a", body_html=body)))
    assert c["mark_overuse"] == "warn" and c["emphasis_inflation"] == "warn"


def test_lead_too_long():
    assert codes(P(ContentSlide(title="a", lead=" ".join(["k"] * 21))))["lead_too_long"] == "warn"


def test_multiple_focal_points_when_lead_and_media_both_compete():
    s = ContentSlide(title="a", lead="L", media_asset_id="img",
                     composition={"preset": "statement"})
    assert codes(P(s))["multiple_focal_points"] == "warn"


def test_monotony_and_intensity_run_on_explicit_choices():
    same = [ContentSlide(title=f"s{i}", composition={"preset": "centered", "intensity": "high"})
            for i in range(5)]
    c = codes(P(*same))
    assert c["composition_monotony"] == "warn" and c["intensity_run"] == "warn"


def test_ignored_on_classic_is_info_and_does_not_block():
    p = P(ContentSlide(title="a", lead="L"), comp="classic")
    assert codes(p)["composition_ignored_classic"] == "info"
    assert not [e for e in validate_project(p) if "classic" in e.message]


def test_strict_promotes_composition_warnings():
    assert {"emphasis_inflation", "mark_overuse", "lead_too_long",
            "multiple_focal_points", "composition_monotony", "intensity_run"} \
        <= STRICT_PROMOTED_CODES


def test_summary_lists_resolved():
    out = summary(P(ContentSlide(id="c1", title="a", media_asset_id="img")))
    base = {k: out[0][k] for k in ("screen_id", "preset", "focal", "intensity", "auto")}
    assert base == {"screen_id": "c1", "preset": "split-thirds", "focal": "focal",
                    "intensity": "high", "auto": True}
    # v1.8.1 (#173) — karar izi alanları da var
    assert out[0]["source"] == "auto" and out[0]["dom_order"] == ["title", "focal", "support"]
