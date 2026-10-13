"""K5 — oyun/senaryo/gömülü kompozisyon yuvalarında: içerik korunur, JS kapları bozulmaz."""
import re

import pytest

from components.renderer import render_html
from core.project import Project
from tests.test_composition_k5_classic import SPECS, TA

TEXT_KEYS = {"title", "intro_html", "prompt_html", "content_html", "text_html", "feedback_html",
             "term_html", "definition_html", "hint_html"}
STIM = {"text_html": "<p>VAKA_T</p>", "asset_id": "IMG_S", "alt": "ALT_S"}


def texts(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in TEXT_KEYS and isinstance(v, str):
                t = re.sub(r"<[^>]+>", "", v).strip()
                if t:
                    yield t
            else:
                yield from texts(v)
    elif isinstance(o, list):
        for v in o:
            yield from texts(v)


def R(spec, comp=None, stim=False):
    d = dict(spec, kicker="KCK", composition=comp)
    if stim:
        d["stimulus"] = STIM
    html = render_html(Project(id="p", title="t", composition="auto",
                               screens=[TA.validate_python(d)]), mode="package", runtime_js="")
    return re.search(r'<section class="screen".*?</section>', html, re.S).group(0), d


COMPS = [None, "question-column", "split-thirds", "visual-stack",
         {"preset": "split-thirds", "mirror": True},
         {"grid": "1:2", "areas": {"support": "c1r1-c1r3", "focal": "c2r1-c2r3"}}]
BODY = [x for x in SPECS if x["type"] != "embed_html"]


@pytest.mark.parametrize("spec", BODY, ids=lambda x: x["id"])
@pytest.mark.parametrize("comp", COMPS, ids=lambda c: str(c)[:20])
def test_every_text_survives(spec, comp):
    sec, d = R(spec, comp)
    missing = [t for t in set(texts(d)) | {"KCK"} if t not in sec]
    assert not missing, missing
    assert "data-comp=" in sec and "c-body" in sec


@pytest.mark.parametrize("comp", [None, "visual-stack", "split-thirds",
                                  {"grid": "1:2", "areas": {"support": "c1r1-c1r3",
                                                            "focal": "c2r1-c2r3"}}],
                         ids=lambda c: str(c)[:20])
def test_embed_fills_focal_without_body_wrapper(comp):
    sec, _ = R(SPECS[5], comp)
    assert "c-body" not in sec and "KCK" in sec
    focal = sec[sec.index("slot-focal"):]
    assert "embed-frame" in focal


@pytest.mark.parametrize("comp", COMPS, ids=lambda c: str(c)[:20])
def test_branching_stimulus(comp):
    sec, d = R(SPECS[4], comp, stim=True)
    assert "VAKA_T" in sec and 'alt="ALT_S"' in sec and "branch-choice" in sec


def test_tmr_finish_after_selects_and_feedback_after_container():
    sec, _ = R(SPECS[3])
    assert sec.index("tmr-finish") > sec.rindex("tmr-select")
    assert sec.index('class="feedback"') > sec.index("data-tmr")


def test_game_hud_and_nodes_in_one_container():
    sec, _ = R(SPECS[0])
    box = sec[sec.index("data-game"):]
    assert "game-hud" in box and "game-node" in box
