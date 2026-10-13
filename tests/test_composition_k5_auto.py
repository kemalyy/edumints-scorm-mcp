from core.composition import resolve_spec
from core.composition_auto import COMPOSED_TYPES, K5_TYPES, auto_preset, resolve_project
from core.composition_questions import build_questions
from core.project import Project, ScreenType
from tests.test_composition_k5_classic import SPECS, TA

BY = {x["type"]: x for x in SPECS}


def S(t, **kw):
    return TA.validate_python(dict(BY[t], **kw))


def P(*s):
    return Project(id="p", title="t", composition="auto", screens=list(s))


def test_all_31_types_composed():
    assert {t.value for t in ScreenType} <= COMPOSED_TYPES


def test_catalog():
    for t in K5_TYPES:
        for p in ("question-column", "split-thirds", "visual-stack"):
            assert resolve_spec(p, t).preset == p


def test_defaults_and_long_intro():
    want = {"game": "visual-stack", "decision_scenario": "visual-stack",
            "escape_room": "question-column", "term_match_race": "question-column",
            "branching": "question-column", "embed_html": "visual-stack"}
    for t, p in want.items():
        assert auto_preset(S(t), None, False)[0] == p, t
    long = "<p>" + " ".join(["k"] * 31) + "</p>"
    assert auto_preset(S("game", intro_html=long), None, False)[0] == "split-thirds"
    assert auto_preset(S("escape_room", lead="Ana mesaj"), None, False)[0] == "split-thirds"
    assert auto_preset(S("embed_html", lead="Ana mesaj"), None, False)[0] == "visual-stack"


def test_branching_stimulus_rule_and_order():
    out = resolve_project(P(S("branching", stimulus={"text_html": "<p>kısa</p>"})))
    assert out[0].preset == "visual-stack" and out[0].dom_order == "focal-first"
    out = resolve_project(P(*[S(t) for t in sorted(K5_TYPES)]))
    assert {r.dom_order for r in out} == {"support-first"}


def test_stimulus_branching_counts_for_questions():
    st = {"text_html": " ".join(["k"] * 35)}
    qs = build_questions(P(*[S("branching", id=f"b{i}", stimulus=st) for i in range(3)]))
    assert {"question_layout", "screen:b0"} <= {q["id"] for q in qs}
