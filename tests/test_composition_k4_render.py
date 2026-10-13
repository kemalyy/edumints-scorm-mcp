"""K4 — dokuz içerik etkileşimi kompozisyon yuvalarında: içerik korunur, JS kapları bozulmaz,
tabs ana–detay yalnız auto'da."""
import re

import pytest

from components.renderer import render_html
from core.project import Project
from tests.test_composition_k4_classic import SPECS, TA

TEXT_KEYS = {"title", "body_html", "label", "front_html", "back_html", "date", "text_html",
             "prompt_html", "reflection_html", "intro_html", "action_html", "rationale_html",
             "self_explanation_prompt_html", "advice_html"}
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
    return re.search(r'<section class="screen".*?</section>', html, re.S).group(0), d, html


COMPS = [None, "question-column", "split-thirds", "visual-stack",
         {"preset": "split-thirds", "mirror": True},
         {"grid": "1:2", "areas": {"support": "c1r1-c1r3", "focal": "c2r1-c2r3"}}]
NON_SUMMARY = [x for x in SPECS if x["type"] != "summary"]


@pytest.mark.parametrize("spec", NON_SUMMARY, ids=lambda x: x["id"])
@pytest.mark.parametrize("comp", COMPS, ids=lambda c: str(c)[:20])
def test_every_text_survives(spec, comp):
    sec, d, _ = R(spec, comp)
    missing = [t for t in set(texts(d)) | {"KCK"} if t not in sec]
    assert not missing, missing
    assert "data-comp=" in sec and "c-body" in sec


@pytest.mark.parametrize("spec", [SPECS[6], SPECS[8]], ids=["poll", "xp"])
@pytest.mark.parametrize("comp", COMPS, ids=lambda c: str(c)[:20])
def test_stimulus_screens(spec, comp):
    sec, d, _ = R(spec, comp, stim=True)
    assert "VAKA_T" in sec and 'alt="ALT_S"' in sec
    assert not [t for t in set(texts(d)) if t not in sec]


def test_summary_in_centered_support_slot():
    sec, _, _ = R(SPECS[4])
    assert 'data-comp="centered"' in sec and "slot-support" in sec
    assert "summary-score" in sec and "KCK" in sec and "Bitti" in sec


def test_poll_submit_after_options():
    sec, _, _ = R(SPECS[6], "split-thirds", stim=True)
    assert sec.index("poll-submit") > sec.rindex('class="poll-opt"')


def test_results_total_inside_container():
    sec, _, _ = R(dict(SPECS[5], show_total=True))
    box = sec[sec.index("data-results"):]
    assert "rb-total" in box and "rb-section" in box


def test_exploration_prompt_keeps_label_id():
    sec, _, _ = R(dict(SPECS[8], input_kind="choice",
                       choices=[{"id": "a", "text_html": "A"}, {"id": "b", "text_html": "B"}]))
    assert 'id="xp-xp-prompt"' in sec and 'aria-labelledby="xp-xp-prompt"' in sec


def test_tabs_vertical_only_in_auto_and_js_conditional():
    sec, _, html = R(SPECS[1])
    assert 'aria-orientation="vertical"' in sec and "__tabsV" in html
    classic = render_html(Project(id="p", title="t", screens=[TA.validate_python(SPECS[1])]),
                          mode="package", runtime_js="")
    assert "aria-orientation" not in classic and "__tabsV" not in classic


def test_no_tabs_no_tabs_js():
    _, _, html = R(SPECS[0])
    assert "__tabsV" not in html
