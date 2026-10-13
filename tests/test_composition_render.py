"""K1 — renderer: yuvalar, vurgu kademeleri, koşullu CSS, auto'da <mark>; classic bayt-aynı."""
import re

from components.renderer import render_html
from core.project import ContentBlock, ContentSlide, Project, TitleSlide


def R(p):
    return render_html(p, mode="preview", runtime_js="/*RT*/")


def P(*screens, comp="auto"):
    return Project(id="p", title="t", composition=comp, screens=list(screens))


def test_classic_has_no_composition_artifacts_and_strips_mark():
    html = R(P(ContentSlide(title="a", body_html="<p>x <mark>y</mark></p>", lead="L",
                            kicker="K"), comp="classic"))
    assert "data-comp" not in html and "slot-" not in html and "--em1" not in html
    assert "<mark>" not in html and 'class="lead"' not in html


def test_auto_split_thirds_slots_and_attrs():
    html = R(P(ContentSlide(title="a", body_html="<p>x</p>", media_asset_id="img",
                            kicker="Adım 1", lead="Alan adı tek harf farklı.")))
    sec = re.search(r'<section class="screen"[^>]*>', html).group(0)
    assert 'data-comp="split-thirds"' in sec and 'data-focal="focal"' in sec
    assert 'data-intensity="high"' in sec  # tek ekran = ilk = high
    assert re.search(r'class="slot slot-focal"[^>]*grid-area:1 / 2 / 4 / 4', html)
    assert '<p class="kicker">Adım 1</p>' in html
    assert '<p class="lead">Alan adı tek harf farklı.</p>' in html


def test_mark_allowed_in_auto():
    html = R(P(ContentSlide(title="a", body_html="<p>x <mark>y</mark></p>")))
    assert "<mark>y</mark>" in html


def test_focal_first_in_dom_order_for_mobile():
    html = R(P(ContentSlide(title="a", body_html="<p>x</p>", media_asset_id="img",
                            composition={"preset": "split-thirds", "mirror": True})))
    assert html.index("slot-focal") < html.index("slot-support")


def test_statement_lead_is_focal_slot():
    html = R(P(ContentSlide(title="a", lead="%91 e-postayla başlar", body_html="<p>kısa</p>")))
    focal = re.search(r'<div class="slot slot-focal"[^>]*>(.*?)</div>', html, re.S).group(1)
    assert 'class="lead"' in focal


def test_title_only_falls_back_to_title_as_focal():
    html = R(P(ContentSlide(title="Yalnız başlık")))
    assert 'data-comp="centered"' in html and 'data-focal="support"' in html


def test_emphasis_and_composition_css_only_in_auto():
    auto = R(P(TitleSlide(title="t")))
    classic = R(P(TitleSlide(title="t"), comp="classic"))
    assert "--em1:" in auto and ".slot-focal" in auto
    assert "--em1:" not in classic and ".slot-focal" not in classic


def test_z_flow_steps_slot_marks_last_step():
    html = R(P(ContentSlide(title="a", blocks=[
        ContentBlock(html="<p>1</p>", asset_id="a"), ContentBlock(html="<p>2</p>", asset_id="b"),
        ContentBlock(html="<p>3</p>"), ContentBlock(html="<p>4</p>")])))
    assert 'data-comp="z-flow"' in html and 'class="slot slot-steps"' in html
    assert html.count('class="step"') == 3 and html.count('class="step step-focal"') == 1


def test_dark_mode_emphasis_vars_differ_from_light():
    p = P(TitleSlide(title="t"))
    p.theme_mode = "dark"
    dark = R(p)
    light = R(P(TitleSlide(title="t")))
    assert re.search(r"--em2:([^;]+);", dark).group(1) != re.search(r"--em2:([^;]+);",
                                                                     light).group(1)


def test_hero_background_covers_instead_of_repeating():
    html = R(P(TitleSlide(title="t", background_asset_id="bg")))
    assert 'data-comp="hero-focal"' in html
    assert re.search(r"\.title-slide\.comp\[data-bg-asset\]\{[^}]*background-size:cover", html)
