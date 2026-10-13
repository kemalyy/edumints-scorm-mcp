from core.antislop import lint_course
from core.composition import resolve_spec
from core.composition_auto import K4_TYPES, auto_preset, resolve_project
from core.composition_questions import build_questions
from core.project import CompositionDefaults, Project
from tests.test_composition_k4_classic import SPECS, TA

BY = {x["type"]: x for x in SPECS}


def S(t, **kw):
    return TA.validate_python(dict(BY[t], **kw))


def P(*s, defaults=None):
    return Project(id="p", title="t", composition="auto", screens=list(s),
                   composition_defaults=defaults)


def test_catalog_applies_to():
    for t in K4_TYPES - {"summary"}:
        for p in ("question-column", "split-thirds", "visual-stack"):
            assert resolve_spec(p, t).preset == p
    assert resolve_spec("centered", "summary").preset == "centered"


def test_defaults():
    want = {"accordion": "question-column", "timeline": "question-column",
            "worked_example": "question-column", "tabs": "visual-stack",
            "flashcards": "visual-stack", "summary": "centered",
            "results_breakdown": "split-thirds", "poll": "question-column",
            "exploration": "question-column"}
    for t, p in want.items():
        assert auto_preset(S(t), None, False)[0] == p, t


def test_lead_or_long_text_goes_split():
    long = "<p>" + " ".join(["k"] * 31) + "</p>"
    assert auto_preset(S("accordion", lead="Ana mesaj"), None, False)[0] == "split-thirds"
    assert auto_preset(S("tabs", prompt_html=long), None, False)[0] == "split-thirds"
    assert auto_preset(S("worked_example", intro_html=long), None, False)[0] == "split-thirds"


def test_stimulus_poll_follows_k3_rule_and_preference():
    st = {"text_html": "<p>kısa vaka</p>"}
    assert auto_preset(S("poll", stimulus=st), None, False)[0] == "visual-stack"
    out = resolve_project(P(S("exploration", stimulus=st),
                            defaults=CompositionDefaults(question="split")))
    assert out[0].preset == "split-thirds" and out[0].dom_order == "focal-first"


def test_dom_order_support_first_without_stimulus():
    out = resolve_project(P(*[S(t) for t in sorted(K4_TYPES)]))
    assert {r.dom_order for r in out} == {"support-first"}


def test_steady_column_run_not_broken_or_flagged():
    p = P(*[S("accordion", id=f"a{i}") for i in range(5)])
    assert [r.preset for r in resolve_project(p)] == ["question-column"] * 5
    assert "composition_monotony" not in {i.code for i in lint_course(p)}


def test_stimulus_poll_counts_for_questions():
    st = {"text_html": " ".join(["k"] * 35)}
    qs = build_questions(P(*[S("poll", id=f"p{i}", stimulus=st) for i in range(3)]))
    ids = [q["id"] for q in qs]
    assert "question_layout" in ids and "screen:p0" in ids


def test_summary_after_centered_run_not_flagged_as_monotony():
    from core.antislop import lint_errors
    from core.project import ContentSlide
    cs = [ContentSlide(id=f"c{i}", title=f"C{i}", body_html="<p>kısa metin</p>") for i in range(3)]
    p = P(*cs, S("summary"))
    assert "composition_monotony" not in {i.code for i in lint_course(p)}
    assert "composition_monotony" not in {i.code for i in lint_errors(p, strict=True)}
