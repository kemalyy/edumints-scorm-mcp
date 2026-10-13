"""K2 — yedi görsel etkileşimli tip kompozisyon yuvalarında: içerik korunur, JS'in beklediği
kaplar bozulmaz, soru kipinde support-önce."""
import re

import pytest

from components.renderer import render_html
from core.project import (DataChartScreen, HotspotRegion, HotspotScreen, ImageCompareScreen,
                          LabeledDiagramScreen, LottieScreen, Project, SimulationScreen,
                          VideoScreen)

REG = [HotspotRegion(id="r1", shape="rect", coords=[1, 1, 5, 5], label_html="BÖLGE_A")]


def screens():
    return {
        "hotspot": HotspotScreen(title="T_HS", prompt_html="<p>P_HS</p>", image_asset_id="IMG_HS",
                                 regions=REG),
        "hotspot_explore": HotspotScreen(title="T_HX", prompt_html="<p>P_HX</p>",
                                         image_asset_id="IMG_HX", regions=REG, mode="explore",
                                         require_all=True),
        "labeled_diagram": LabeledDiagramScreen.model_validate({
            "title": "T_LD", "prompt_html": "<p>P_LD</p>", "image_asset_id": "IMG_LD",
            "labels": [{"id": "l1", "x": 100, "y": 100, "text": "ETK_1"},
                       {"id": "l2", "x": 500, "y": 500, "text": "ETK_2"}]}),
        "labeled_display": LabeledDiagramScreen.model_validate({
            "title": "T_LX", "prompt_html": "<p>P_LX</p>", "image_asset_id": "IMG_LX",
            "mode": "display",
            "labels": [{"id": "l1", "x": 100, "y": 100, "text": "ETK_X1"},
                       {"id": "l2", "x": 500, "y": 500, "text": "ETK_X2"}]}),
        "image_compare": ImageCompareScreen(title="T_IC", before_asset_id="IMG_B",
                                            after_asset_id="IMG_A", caption="CAP_IC"),
        "data_chart": DataChartScreen.model_validate({
            "title": "T_DC", "chart_type": "bar", "caption": "CAP_DC",
            "data": [{"label": "a", "value": 1}, {"label": "b", "value": 2}]}),
        "video": VideoScreen(title="T_V", video_asset_id="VID", narration_text="NARR_V",
                             caption="CAP_V"),
        "lottie": LottieScreen(title="T_L", lottie_asset_id="LOT", prompt_html="<p>P_L</p>"),
        "simulation": SimulationScreen.model_validate({
            "title": "T_S", "prompt_html": "<p>P_S</p>",
            "steps": [{"instruction_html": "<p>ADIM_1</p>", "image_asset_id": "IMG_S1",
                       "regions": [{"id": "x", "shape": "rect", "coords": [1, 1, 3, 3],
                                    "correct": True}]},
                      {"instruction_html": "<p>ADIM_2</p>", "image_asset_id": "IMG_S2",
                       "input_accepted": ["ok"]}]}),
    }


def R(s, comp=None):
    """Yalnız ekranın <section> gövdesini döndürür (CSS/JS'teki sınıf adları karışmasın).
    Model doğrulanarak kurulur — model_copy(update=) sözlük kompozisyonu doğrulamaz."""
    data = s.model_dump(mode="json") | {"composition": comp, "kicker": "KCK"}
    s = type(s).model_validate(data)
    html = render_html(Project(id="p", title="t", composition="auto", screens=[s]),
                       mode="package", runtime_js="")
    return re.search(r'<section class="screen".*?</section>', html, re.S).group(0)


def needles(s):
    return set(re.findall(r"(?:T|P|IMG|CAP|NARR|ETK|ADIM|BÖLGE)_\w+|VID|LOT",
                          s.model_dump_json()))


COMPS = [None, "visual-stack", "split-thirds",
         {"preset": "split-thirds", "mirror": True},
         {"grid": "1:2", "areas": {"support": "c1r1-c1r3", "focal": "c2r1-c2r3"}}]


@pytest.mark.parametrize("name", list(screens()))
@pytest.mark.parametrize("comp", COMPS, ids=lambda c: str(c)[:24])
def test_every_input_survives(name, comp):
    s = screens()[name]
    html = R(s, comp)
    missing = [n for n in needles(s) | {"KCK"} if n not in html]
    assert not missing, f"{name}/{comp}: {missing}"
    assert "data-comp=" in html


def test_question_first_and_controls_after_inputs():
    html = R(screens()["hotspot"], "split-thirds")
    assert html.index("slot-support") < html.index("slot-focal")  # mobilde soru önce
    assert html.index("hotspot-stage") < html.index("btn-check")  # kontrol girdilerden sonra
    assert 'class="feedback"' in html


def test_labeled_diagram_selects_stay_inside_labeled_diagram_in_focal():
    html = R(screens()["labeled_diagram"], "split-thirds")
    focal = html[html.index("slot-focal"):]
    ld = focal[focal.index('class="labeled-diagram"'):]
    assert "ld-select" in ld and ld.index("ld-select") < ld.index("btn-check")


def test_simulation_steps_keep_instruction_inside_step():
    html = R(screens()["simulation"])
    step = re.search(r'<div class="sim-step" data-step="0">(.*?)</div><div class="sim-step"',
                     html, re.S)
    assert step and "ADIM_1" in step.group(1)


def test_hotspot_explore_progress_and_hint_inside_explore_container():
    html = R(screens()["hotspot_explore"])
    hx = html[html.index('class="hotspot hs-explore"'):]
    assert "hs-progress" in hx and "hs-hint" in hx


def test_video_narration_in_support_and_no_inner_split():
    html = R(screens()["video"], "split-thirds")
    sup = re.search(r'<div class="slot slot-support"[^>]*>(.*?)</div>', html, re.S).group(1)
    assert "NARR_V" in sup and 'class="split text-first"' not in html


def test_display_types_are_focal_first():
    html = R(screens()["data_chart"], "split-thirds")
    assert html.index("slot-focal") < html.index("slot-support")
