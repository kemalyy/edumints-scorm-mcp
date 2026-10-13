from core.composition_auto import auto_preset, intensities, resolve_project, signals
from core.project import (Choice, ContentBlock, ContentSlide, MCQScreen, OutlineNode, Project,
                          SummaryScreen, TitleSlide)


def P(*screens, comp="auto", outline=()):
    return Project(id="p", title="t", composition=comp, screens=list(screens),
                   outline=list(outline))


def C(**kw):
    return ContentSlide(title=kw.pop("title", "Başlık"), **kw)


def Q():
    return MCQScreen(title="q", prompt_html="p", options=[
        Choice(id="a", text_html="a", correct=True), Choice(id="b", text_html="b")])


def test_classic_resolves_nothing():
    assert resolve_project(P(C(body_html="<p>x</p>"), comp="classic")) == [None]


def test_title_with_bg_is_hero_else_centered():
    assert auto_preset(TitleSlide(title="t", background_asset_id="a"), None, False)[0] == \
        "hero-focal"
    assert auto_preset(TitleSlide(title="t"), None, False)[0] == "centered"


def test_statement_for_short_lead_only():
    s = C(lead="%91 saldırı e-postayla başlar", body_html="<p>Kısa bir not.</p>")
    assert auto_preset(s, None, False)[0] == "statement"


def test_single_media_is_split_thirds_and_alternates_mirror():
    s = C(body_html="<p>x</p>", media_asset_id="img")
    assert auto_preset(s, None, False) == ("split-thirds", False)
    assert auto_preset(s, "split-thirds", False) == ("split-thirds", True)


def test_legacy_layout_ignored_media_still_found():
    s = C(body_html="<p>x</p>", media_asset_id="img", layout="full_media")
    assert auto_preset(s, None, False)[0] == "split-thirds"


def test_two_images_halves_and_steps_z():
    two = C(blocks=[ContentBlock(asset_id="a"), ContentBlock(asset_id="b"),
                    ContentBlock(html="<p>x</p>")])
    assert auto_preset(two, None, False)[0] == "split-halves"
    steps = C(blocks=[ContentBlock(html="<p>1</p>", asset_id="a"),
                      ContentBlock(html="<p>2</p>", asset_id="b"),
                      ContentBlock(html="<p>3</p>"), ContentBlock(html="<p>4</p>")])
    assert auto_preset(steps, None, False)[0] == "z-flow"


def test_list_heavy_is_f_flow_and_title_only_is_centered():
    lst = C(body_html="<ul>" + "<li>a</li>" * 4 + "</ul>")
    assert auto_preset(lst, None, False)[0] == "f-flow"
    assert auto_preset(C(), None, False)[0] == "centered"


def test_signals_count_words_without_tags():
    sg = signals(C(body_html="<p>bir <b>iki</b> üç</p>"))
    assert sg.words == 3 and sg.media == 0


def test_rhythm_first_last_and_unit_openers_high():
    p = P(TitleSlide(title="t"), C(body_html="<p>x</p>"), Q(), SummaryScreen(title="s"))
    assert intensities(p) == ["high", "calm", "normal", "high"]


def test_rhythm_never_three_highs_in_a_row():
    p = P(TitleSlide(title="a", node_id="u1"), C(title="b", node_id="u2"),
          C(title="c", node_id="u3"), C(title="d"),
          outline=[OutlineNode(id="u1", title="1", kind="unit"),
                   OutlineNode(id="u2", title="2", kind="unit"),
                   OutlineNode(id="u3", title="3", kind="unit")])
    seq = intensities(p)
    assert all(seq[i:i + 3] != ["high"] * 3 for i in range(len(seq) - 2))


def test_monotony_breaker_after_three_repeats():
    imgs = [C(title=f"s{i}", body_html="<p>x</p>", media_asset_id="img") for i in range(5)]
    presets = [r.preset for r in resolve_project(P(*imgs))]
    assert all(presets[i:i + 4] != [presets[i]] * 4 for i in range(len(presets) - 3))


def test_explicit_composition_wins_and_every_type_resolves():
    from core.project import EmbedHtmlScreen
    emb = EmbedHtmlScreen(title="a", html_asset_id="h")  # K5 — 31 tipin tamamı kompozisyonlu
    out = resolve_project(P(C(body_html="<p>x</p>", composition="centered"), emb))
    assert out[0].preset == "centered" and out[0].auto is False
    assert out[1] is not None and out[1].auto is True
