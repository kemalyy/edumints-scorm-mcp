from core.antislop import STRICT_PROMOTED_CODES, lint_course
from core.project import Project
from tests.test_composition_k3_model import TA


def codes(*specs, comp="classic"):
    p = Project(id="p", title="t", composition=comp, screens=[TA.validate_python(x) for x in specs])
    return {i.code: i.severity for i in lint_course(p)}


MCQ = {"type": "mcq", "title": "q", "prompt_html": "<p>Başkent?</p>",
       "options": [{"id": "a", "text_html": "Ankara", "correct": True},
                   {"id": "b", "text_html": "İzmir"}]}


def test_stimulus_without_alt_is_error_in_any_mode():
    assert codes(dict(MCQ, stimulus={"asset_id": "i"}))["stimulus_without_alt"] == "error"
    assert codes(dict(MCQ, stimulus={"asset_id": "i"}), comp="auto")["stimulus_without_alt"] \
        == "error"


def test_adaptive_item_stimulus_without_alt():
    opts = [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]
    ap = {"type": "adaptive_practice", "title": "a", "adaptive": {"strategy": "elo"},
          "items": [{"id": f"i{k}", "prompt_html": "p", "options": opts,
                     "stimulus": {"asset_id": "x"} if k == 2 else None} for k in range(4)]}
    assert codes(ap)["stimulus_without_alt"] == "error"


def test_answer_leak_normalised_and_word_bounded():
    leak = dict(MCQ, stimulus={"text_html": "<p>Toplantı <b>ankara</b>  ofisinde.</p>"})
    assert codes(leak)["stimulus_answer_leak"] == "warn"
    ok = dict(MCQ, stimulus={"text_html": "<p>Ankaralı müşteri aradı.</p>"})
    assert "stimulus_answer_leak" not in codes(ok)


def test_answer_leak_punctuation_boundary():
    leak = dict(MCQ, stimulus={"text_html": "<p>Merkez: Ankara.</p>"})
    assert codes(leak)["stimulus_answer_leak"] == "warn"


def test_fill_blank_leak():
    fb = {"type": "fill_blank", "title": "f", "prompt_html": "<p>___</p>",
          "blanks": [{"id": "b", "accepted": ["MFA"]}], "stimulus": {"text_html": "<p>MFA açık</p>"}}
    assert codes(fb)["stimulus_answer_leak"] == "warn"


def test_true_false_leak_when_prompt_restated():
    tf = {"type": "true_false", "title": "t", "prompt_html": "<p>Parolalar paylaşılmaz.</p>",
          "correct": True, "stimulus": {"text_html": "<p>Kural: parolalar paylaşılmaz.</p>"}}
    assert codes(tf)["stimulus_answer_leak"] == "warn"
    tf_false = dict(tf, correct=False)
    assert "stimulus_answer_leak" not in codes(tf_false)


def test_strict_promotes_leak():
    assert "stimulus_answer_leak" in STRICT_PROMOTED_CODES
