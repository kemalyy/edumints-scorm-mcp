from core.antislop import lint_course
from core.project import Project
from tests.test_composition_k5_classic import SPECS, TA


def test_branching_accepts_stimulus():
    s = TA.validate_python(dict(SPECS[4], stimulus={"text_html": "<p>Vaka</p>"}))
    assert s.stimulus.text_html == "<p>Vaka</p>"


def test_branching_stimulus_without_alt_is_error():
    s = TA.validate_python(dict(SPECS[4], stimulus={"asset_id": "i"}))
    codes = {i.code: i.severity for i in lint_course(Project(id="p", title="t", screens=[s]))}
    assert codes["stimulus_without_alt"] == "error"
