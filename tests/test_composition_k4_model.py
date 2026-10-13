from core.antislop import lint_course
from core.project import Project
from tests.test_composition_k4_classic import SPECS, TA

STIM = {"text_html": "<p>Vaka</p>"}


def test_poll_and_exploration_accept_stimulus():
    for spec in (SPECS[6], SPECS[8]):
        assert TA.validate_python(dict(spec, stimulus=STIM)).stimulus.text_html == "<p>Vaka</p>"


def test_other_content_types_have_no_stimulus():
    # ekran modelleri bilinmeyen alanı yok sayar (forbid değil): accordion'da uyaran alanı oluşmaz
    assert getattr(TA.validate_python(dict(SPECS[0], stimulus=STIM)), "stimulus", None) is None


def test_poll_stimulus_without_alt_is_error():
    s = TA.validate_python(dict(SPECS[6], stimulus={"asset_id": "i"}))
    codes = {i.code: i.severity for i in lint_course(Project(id="p", title="t", screens=[s]))}
    assert codes["stimulus_without_alt"] == "error"
