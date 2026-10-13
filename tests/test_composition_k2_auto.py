from core.composition_auto import (K2_TYPES, auto_preset, is_quiz_mode, resolve_project,
                                   text_weight)
from core.project import (CompositionDefaults, DataChartScreen, HotspotRegion, HotspotScreen,
                          Project, VideoScreen)


def HS(**kw):
    return HotspotScreen(title="h", prompt_html=kw.pop("prompt_html", "<p>Bul.</p>"),
                         image_asset_id="img",
                         regions=[HotspotRegion(id="r", shape="rect", coords=[1, 1, 5, 5])], **kw)


def CH(**kw):
    return DataChartScreen.model_validate({
        "title": "c", "chart_type": "bar",
        "data": [{"label": "a", "value": 1}, {"label": "b", "value": 2}], **kw})


def P(*s, defaults=None):
    return Project(id="p", title="t", composition="auto", screens=list(s),
                   composition_defaults=defaults)


def test_k2_types():
    assert K2_TYPES == {"hotspot", "labeled_diagram", "image_compare", "data_chart", "video",
                        "lottie", "simulation"}


def test_text_weight_counts_lead_and_prompt_not_labels():
    assert text_weight(HS(lead="iki kelime", prompt_html="<p>üç kelime burada</p>")) == 5


def test_short_text_is_visual_stack_long_or_lead_is_split():
    assert auto_preset(HS(), None, False)[0] == "visual-stack"
    assert auto_preset(HS(lead="Sahte gönderen"), None, False)[0] == "split-thirds"
    long = "<p>" + " ".join(["k"] * 31) + "</p>"
    assert auto_preset(HS(prompt_html=long), None, False)[0] == "split-thirds"


def test_project_defaults_override_auto_rule_but_not_explicit():
    out = resolve_project(P(HS(lead="uzun"), CH(composition="split-thirds"),
                            defaults=CompositionDefaults(visual="stack")))
    assert out[0].preset == "visual-stack" and out[1].preset == "split-thirds"
    out = resolve_project(P(HS(), defaults=CompositionDefaults(visual="split")))
    assert out[0].preset == "split-thirds"


def test_quiz_mode_is_support_first_display_is_focal_first():
    assert is_quiz_mode(HS()) and not is_quiz_mode(HS(mode="explore"))
    out = resolve_project(P(HS(), HS(mode="explore"), CH()))
    assert [r.dom_order for r in out] == ["support-first", "focal-first", "focal-first"]


def test_k2_screens_are_normal_intensity_in_middle():
    v = VideoScreen(title="v", video_asset_id="x")
    out = resolve_project(P(CH(), v, CH()))
    assert out[1].intensity == "normal"
