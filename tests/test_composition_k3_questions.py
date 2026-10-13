from core.composition_questions import build_questions
from core.project import CompositionDefaults, HotspotRegion, HotspotScreen, Project
from tests.test_composition_k3_model import OPTS, TA


def MCQ(i, words=5):
    return TA.validate_python({"type": "mcq", "id": f"m{i}", "title": f"M{i}", "prompt_html": "p",
                               "options": OPTS,
                               "stimulus": {"text_html": " ".join(["k"] * words)}})


def HS(i, words=30):
    return HotspotScreen(id=f"h{i}", title=f"H{i}", image_asset_id="i",
                         prompt_html=" ".join(["k"] * words),
                         regions=[HotspotRegion(id="r", shape="rect", coords=[1, 1, 5, 5])])


def P(*s, defaults=None, lang="tr"):
    return Project(id="p", title="t", composition="auto", language=lang, screens=list(s),
                   composition_defaults=defaults)


def ids(qs):
    return [q["id"] for q in qs]


def test_question_layout_course_question():
    qs = build_questions(P(MCQ(1), MCQ(2), MCQ(3)))
    q = next(q for q in qs if q["id"] == "question_layout")
    assert q["apply"] == {"tool": "set_composition", "args": {"mode": "auto", "question": "$value"}}
    assert [o["value"] for o in q["options"]] == ["stack", "split", "auto"]
    assert "question_layout" not in ids(build_questions(
        P(MCQ(1), MCQ(2), MCQ(3), defaults=CompositionDefaults(question="auto"))))


def test_question_layout_needs_three_stimulus_screens():
    assert "question_layout" not in ids(build_questions(P(MCQ(1), MCQ(2))))


def test_question_layout_independent_of_visual_answer():
    qs = build_questions(P(MCQ(1), MCQ(2), MCQ(3), defaults=CompositionDefaults(visual="stack")))
    assert "question_layout" in ids(qs)


def test_answering_question_layout_keeps_visual_question():
    qs = build_questions(P(HS(1), HS(2), HS(3), defaults=CompositionDefaults(question="split")))
    assert "visual_layout" in ids(qs)


def test_stimulus_screen_band_and_global_cap():
    qs = build_questions(P(HS(1), HS(2), MCQ(3, 30), MCQ(4, 50), MCQ(5, 29),
                           defaults=CompositionDefaults(visual="auto", question="auto")))
    assert ids(qs) == ["screen:h1", "screen:h2", "screen:m3"]


def test_stimulus_screen_question_band_edges():
    qs = build_questions(P(MCQ(3, 30), MCQ(4, 50), MCQ(5, 29), MCQ(6, 51),
                           defaults=CompositionDefaults(question="auto")))
    assert ids(qs) == ["screen:m3", "screen:m4"]
    q = qs[0]
    assert [o["value"] for o in q["options"]] == ["visual-stack", "split-thirds"]
    assert q["apply"]["tool"] == "set_screen_composition"


def test_question_preference_silences_stimulus_screen_questions():
    qs = build_questions(P(MCQ(3, 30), defaults=CompositionDefaults(question="split")))
    assert qs == []


def test_questions_translated():
    en = build_questions(P(MCQ(1), MCQ(2), MCQ(3), lang="en"))
    tr = build_questions(P(MCQ(1), MCQ(2), MCQ(3), lang="tr"))
    assert en[0]["question"] != tr[0]["question"]
    assert all(o["label"] for o in en[0]["options"])
    assert en[0]["options"][0]["label"] != tr[0]["options"][0]["label"]


def test_k2_questions_translated_too():
    en = build_questions(P(HS(1), HS(2), HS(3), lang="en"))
    assert en[0]["id"] == "visual_layout" and "Görsel" not in en[0]["question"]
