"""K1 final review düzeltmeleri — içerik koruma, eski temalarda E3 AA, önizleme dayanıklılığı, OFL."""
import re

import pytest

import server
from components.renderer import extra_runtime_files, render_html
from core.project import ContentBlock, ContentSlide, MCQScreen, Choice, Project, TitleSlide
from core.theme_dark import _contrast, derive_dark_theme
from core.theme_emphasis import resolve_emphasis

PRESETS = ["centered", "split-thirds", "split-halves", "hero-focal", "statement", "z-flow",
           "f-flow", None]
SHAPES = {
    "body+media": dict(body_html="<p>TXT_A</p>", media_asset_id="IMG_A"),
    "blocks1": dict(blocks=[ContentBlock(html="<p>TXT_A</p>"), ContentBlock(asset_id="IMG_A")]),
    "blocks2": dict(blocks=[ContentBlock(html="<p>TXT_A</p>", asset_id="IMG_A"),
                            ContentBlock(asset_id="IMG_B")]),
    "blocks5": dict(blocks=[ContentBlock(html="<p>TXT_A</p>"), ContentBlock(asset_id="IMG_A"),
                            ContentBlock(html="<p>TXT_B</p>"), ContentBlock(asset_id="IMG_B"),
                            ContentBlock(html="<p>TXT_C</p>")]),
    "title-only": dict(),
}


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("shape", list(SHAPES))
def test_every_text_and_asset_survives(preset, shape):
    kw = dict(SHAPES[shape])
    if preset:
        kw["composition"] = preset
    s = ContentSlide(id="c", title="TITLE_X", **kw)
    html = render_html(Project(id="p", title="t", composition="auto", screens=[s]),
                       mode="package", runtime_js="")
    needles = ["TITLE_X"] + re.findall(r"TXT_\w|IMG_\w", repr(kw))
    missing = [n for n in set(needles) if n not in html]
    assert not missing, f"{preset}/{shape} içerik kaybı: {missing}"


def test_block_order_kept_in_single_column_layouts():
    s = ContentSlide(id="c", title="t", composition="f-flow", blocks=[
        ContentBlock(html="<p>FIRST</p>"), ContentBlock(asset_id="IMG_MID"),
        ContentBlock(html="<p>LAST</p>")])
    html = render_html(Project(id="p", title="t", composition="auto", screens=[s]),
                       mode="package", runtime_js="")
    assert html.index("FIRST") < html.index("IMG_MID") < html.index("LAST")


def _shipped():
    from tests.test_theme_contrast import shipped_presets
    return shipped_presets()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_derived_e3_is_aa_on_every_shipped_theme(mode):
    fails = []
    for name in _shipped():
        t = server._load_theme(name)
        if mode == "dark":
            t = derive_dark_theme(t)
        em = resolve_emphasis(t, dark=mode == "dark")
        bg = t.color.surface
        for label, fg, back in (("e3/surface", em.e3.color, bg), ("e3/e3bg", em.e3.color, em.e3_bg)):
            if _contrast(fg, back) < 4.5:
                fails.append((name, label, round(_contrast(fg, back), 2)))
    assert not fails, fails


def test_bad_composition_does_not_break_preview_render():
    p = Project(id="p", title="t", composition="auto", screens=[
        ContentSlide(id="c", title="ok", body_html="<p>x</p>"),
        MCQScreen(id="q", title="q", prompt_html="p", composition="centered",
                  options=[Choice(id="a", text_html="a", correct=True),
                           Choice(id="b", text_html="b")]),
        ContentSlide(id="d", title="bad", composition="nope")])
    html = render_html(p, mode="preview", runtime_js="")
    assert 'data-screen-id="d"' in html and 'data-screen-id="q"' in html


def test_ofl_license_texts_shipped_with_fonts():
    p = Project(id="p", title="t", composition="auto", theme=server._load_theme("mint"),
                screens=[TitleSlide(title="t")])
    rels = [r for r, _ in extra_runtime_files(p)]
    assert "runtime/fonts/OFL-Inter.txt" in rels and "runtime/fonts/OFL-Outfit.txt" in rels
