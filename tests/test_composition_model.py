import pytest
from pydantic import TypeAdapter, ValidationError

from core.project import CompositionSpec, CourseSpec, Project, Screen

TA = TypeAdapter(Screen)


def test_project_defaults_to_classic():
    assert Project(id="p", title="t").composition == "classic"


def test_old_json_without_field_loads_as_classic():
    raw = Project(id="p", title="t").model_dump(mode="json")
    raw.pop("composition")
    assert Project.model_validate(raw).composition == "classic"


def test_coursespec_defaults_to_auto():
    assert CourseSpec(title="t", screens=[]).composition == "auto"


def test_screen_accepts_preset_name_and_object():
    s = TA.validate_python({"type": "content_slide", "title": "x", "composition": "split-thirds"})
    assert s.composition == "split-thirds"
    s2 = TA.validate_python({"type": "content_slide", "title": "x",
                             "composition": {"preset": "split-thirds", "mirror": True,
                                             "focal": "r3c1"}})
    assert isinstance(s2.composition, CompositionSpec) and s2.composition.mirror is True


def test_kicker_length_limited():
    with pytest.raises(ValidationError):
        TA.validate_python({"type": "title_slide", "title": "x", "kicker": "k" * 41})


def test_composition_spec_rejects_unknown_field():
    with pytest.raises(ValidationError):
        CompositionSpec.model_validate({"preset": "centered", "colour": "red"})


@pytest.mark.parametrize("bad", [{"flow": "x"}, {"whitespace": "huge"}, {"intensity": "loud"}])
def test_composition_spec_enums(bad):
    with pytest.raises(ValidationError):
        CompositionSpec.model_validate(bad)
