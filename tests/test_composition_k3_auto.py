from core.composition import resolve_spec
from core.composition_auto import Q_TYPES, auto_preset, resolve_project
from core.project import CompositionDefaults, Project
from tests.test_composition_k3_model import OPTS, TA


def MCQ(i=0, stim=None, **kw):
    d = {"type": "mcq", "id": f"m{i}", "title": "q", "prompt_html": "<p>p</p>", "options": OPTS}
    if stim:
        d["stimulus"] = stim
    return TA.validate_python(d | kw)


def P(*s, defaults=None):
    return Project(id="p", title="t", composition="auto", screens=list(s),
                   composition_defaults=defaults)


def test_question_column_catalog():
    r = resolve_spec("question-column", "mcq")
    assert r.areas["support"] == (1, 1, 2, 4) and r.areas["focal"] == (2, 1, 4, 4)
    for t in Q_TYPES:
        for p in ("question-column", "split-thirds", "visual-stack"):
            assert resolve_spec(p, t).preset == p


def test_defaults_without_and_with_stimulus():
    assert auto_preset(MCQ(), None, False)[0] == "question-column"
    assert auto_preset(MCQ(stim={"text_html": "<p>kısa vaka</p>"}), None, False)[0] == \
        "visual-stack"
    long = "<p>" + " ".join(["k"] * 41) + "</p>"
    assert auto_preset(MCQ(stim={"text_html": long}), None, False)[0] == "split-thirds"
    both = {"text_html": "<p>v</p>", "asset_id": "i", "alt": "a"}
    assert auto_preset(MCQ(stim=both), None, False)[0] == "split-thirds"


def test_dom_order():
    out = resolve_project(P(MCQ(0), MCQ(1, stim={"text_html": "v"})))
    assert [r.dom_order for r in out] == ["support-first", "focal-first"]


def test_question_preference_honoured_but_explicit_wins():
    st = {"text_html": "v"}
    out = resolve_project(P(MCQ(0, stim=st), MCQ(1, stim=st, composition="split-thirds"),
                            MCQ(2, stim=st), MCQ(3, stim=st), MCQ(4, stim=st),
                            defaults=CompositionDefaults(question="stack")))
    assert [r.preset for r in out] == ["visual-stack", "split-thirds", "visual-stack",
                                       "visual-stack", "visual-stack"]


def test_preference_does_not_touch_stimulus_free_questions():
    out = resolve_project(P(MCQ(0), defaults=CompositionDefaults(question="split")))
    assert out[0].preset == "question-column"


def test_steady_question_run_resolves_and_is_not_flagged():
    from core.antislop import lint_course
    p = P(*[MCQ(i) for i in range(6)])
    assert [r.preset for r in resolve_project(p)] == ["question-column"] * 6
    assert "composition_monotony" not in {i.code for i in lint_course(p)}


def test_stimulus_question_run_alternates_without_preference():
    st = {"text_html": "v"}
    presets = [r.preset for r in resolve_project(P(*[MCQ(i, stim=st) for i in range(5)]))]
    assert all(presets[i:i + 4] != [presets[i]] * 4 for i in range(len(presets) - 3))
