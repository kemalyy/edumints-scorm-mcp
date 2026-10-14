"""v1.8.1 — karar izi (#173), vaka eşiği (#172), tercihli dizide ayna (#180)."""
from pydantic import TypeAdapter

from core.composition_auto import _words, resolve_project, summary
from core.project import CompositionDefaults, Project, Screen

TA = TypeAdapter(Screen)
OPTS = [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]


def mcq(i, words=5, **kw):
    return TA.validate_python({"type": "mcq", "id": f"m{i}", "title": f"M{i}", "prompt_html": "<p>?</p>",
                               "options": OPTS, "stimulus": {"text_html": " ".join(["vaka"] * words)},
                               **kw})


def hs(i):
    return TA.validate_python({"type": "hotspot", "id": f"h{i}", "title": "H", "prompt_html": "<p>bul</p>",
                               "image_asset_id": "i", "image_alt": "a",
                               "regions": [{"id": "r", "shape": "rect", "coords": [1, 1, 5, 5]}]})


def P(*s, defaults=None):
    return Project(id="p", title="t", composition="auto", screens=list(s),
                   composition_defaults=defaults)


def test_summary_has_trace_fields():
    rec = summary(P(mcq(0, 46)))[0]
    assert rec["source"] == "auto" and rec["preset"] == "split-thirds"
    assert rec["reason"] == "stimulus_words=46>40"
    assert rec["dom_order"] == ["title", "focal", "support"]  # #175 başlık önce
    assert "params" in rec


def test_rhythm_source_explains_report_case():
    # G5: art arda kısa vakalı sorular — 4.'sü eşik yüzünden değil ritim yüzünden split
    out = summary(P(*[mcq(i, 30) for i in range(4)]))
    assert [r["preset"] for r in out] == ["visual-stack"] * 3 + ["split-thirds"]
    assert out[3]["source"] == "rhythm" and out[3]["reason"].startswith("rhythm:visual-stack")
    assert out[0]["reason"] == "stimulus_words=30<=40"


def test_course_and_screen_sources():
    out = summary(P(mcq(0, 5), mcq(1, 5, composition="split-thirds"),
                    defaults=CompositionDefaults(question="split")))
    assert out[0]["source"] == "course:question=split"
    assert out[1]["source"] == "screen" and out[1]["auto"] is False


def test_mirror_visible_in_params():
    rec = summary(P(mcq(0, 5, composition={"preset": "split-thirds", "mirror": True})))[0]
    assert rec["params"].get("mirror") is True


def test_word_counter_ignores_blanks_and_punctuation():
    assert _words("<p>Murat'a gelen ___ e-posta: “acil”!</p>") == 4
    assert _words("<p>— · ___ ...</p>") == 0


def test_course_split_run_alternates_mirror():
    out = resolve_project(P(*[hs(i) for i in range(4)], defaults=CompositionDefaults(visual="split")))
    assert [r.preset for r in out] == ["split-thirds"] * 4
    assert [r.mirror for r in out] == [False, True, False, True]


def test_dom_order_lists_only_slots_that_exist():
    # final inceleme M1: hero-focal'da odak alanı yok → izde 'focal' olmamalı; başlıksız ekranda 'title' yok
    from pydantic import TypeAdapter
    from core.project import Screen
    ta = TypeAdapter(Screen)
    hero = ta.validate_python({"type": "title_slide", "id": "t", "title": "T", "background_asset_id": "i",
                               "composition": "hero-focal"})
    rec = summary(P(hero))[0]
    assert rec["dom_order"] == ["title", "support"]
    untitled = ta.validate_python({"type": "content_slide", "id": "c", "title": "", "media_asset_id": "i"})
    assert summary(P(untitled))[0]["dom_order"][0] != "title"
