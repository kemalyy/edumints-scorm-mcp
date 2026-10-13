"""K3 — yedi soru tipi kompozisyon yuvalarında: içerik korunur, kontrol girdilerden sonra,
JS'in beklediği kaplar bozulmaz, uyaran odakta."""
import re

import pytest

from components.renderer import render_html
from core.project import Project
from tests.test_composition_k3_classic import SPECS
from tests.test_composition_k3_model import TA

STIM = {"text_html": "<p>VAKA_T</p>", "asset_id": "IMG_S", "alt": "ALT_S"}
TEXT_KEYS = {"text_html", "left_html", "right_html", "label_html", "prompt_html", "feedback_html",
             "title"}


def texts(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in TEXT_KEYS and isinstance(v, str):
                t = re.sub(r"<[^>]+>", "", v).strip()
                if t:
                    yield t
            else:
                yield from texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from texts(v)


def R(spec, comp=None, stim=False):
    d = dict(spec, kicker="KCK", composition=comp)
    if stim and d["type"] != "adaptive_practice":
        d["stimulus"] = STIM
    if stim and d["type"] == "adaptive_practice":
        d["items"] = [dict(it, stimulus=STIM) for it in d["items"]]
    s = TA.validate_python(d)
    html = render_html(Project(id="p", title="t", composition="auto", screens=[s]),
                       mode="package", runtime_js="")
    return re.search(r'<section class="screen".*?</section>', html, re.S).group(0), d


COMPS = [None, "question-column", "split-thirds", "visual-stack",
         {"preset": "split-thirds", "mirror": True},
         {"grid": "1:2", "areas": {"support": "c1r1-c1r3", "focal": "c2r1-c2r3"}}]
INPUTS = ('class="opt"', "data-blank=", 'class="drop-zone"', 'class="match-select"',
          'class="sort-item')


@pytest.mark.parametrize("spec", SPECS, ids=lambda x: x["id"])
@pytest.mark.parametrize("comp", COMPS, ids=lambda c: str(c)[:20])
@pytest.mark.parametrize("stim", [False, True])
def test_every_input_survives_and_controls_after_inputs(spec, comp, stim):
    sec, d = R(spec, comp, stim)
    missing = [t for t in set(texts(d)) | {"KCK"} if t not in sec]
    assert not missing, missing
    assert "data-comp=" in sec
    if stim:
        assert "VAKA_T" in sec and 'alt="ALT_S"' in sec
    if spec["type"] != "adaptive_practice":
        last_input = max(sec.rfind(x) for x in INPUTS)
        assert last_input >= 0 and sec.index("btn-check") > last_input


def test_drag_pool_and_targets_share_container():
    sec, _ = R(SPECS[4], "split-thirds")
    dd = sec[sec.index('class="dragdrop"'):]
    assert "drag-pool" in dd and "drop-list" in dd


def test_adaptive_stimulus_inside_item():
    sec, _ = R(SPECS[7], None, True)
    item = re.search(r'<div class="ap-item"[^>]*>(.*?)<div class="quiz-actions">', sec, re.S)
    assert item and "VAKA_T" in item.group(1)


def test_stimulus_is_focal_and_first():
    sec, _ = R(SPECS[0], "split-thirds", True)
    assert sec.index("slot-focal") < sec.index("slot-support")
    focal = sec[sec.index("slot-focal"):sec.index("slot-support")]
    assert "VAKA_T" in focal


def test_no_stimulus_question_prompt_first():
    sec, _ = R(SPECS[0])
    assert sec.index("slot-support") < sec.index("slot-focal")


def test_many_options_flag():
    spec = dict(SPECS[0], options=[{"id": f"o{k}", "text_html": f"S{k}", "correct": k == 0}
                                   for k in range(7)])
    sec, _ = R(spec)
    assert 'data-many="1"' in sec
