"""get_guide schema:<tip> — alanlar Pydantic modelinden (spec §3)."""
import pytest

from core import guides as g
from core.project import ScreenType


@pytest.mark.parametrize("t", [s.value for s in ScreenType])
def test_every_type_has_schema_within_limit(t):
    out = g.screen_schema(t)
    assert out.startswith(f"# {t}") and len(out.encode()) <= g.MAX_SCHEMA_BYTES
    assert "\n- type:" not in out  # 'type' ayrımcı alanı listelenmez


def test_required_and_nested_fields_marked():
    out = g.screen_schema("mcq")
    assert "\n- title: " in out and "— zorunlu" in out
    assert "stimulus.alt" in out  # iç içe model bir kez açılır


def test_normalizes_and_rejects_unknown():
    assert g.screen_schema(" MCQ ").startswith("# mcq")
    with pytest.raises(KeyError):
        g.screen_schema("nope")


def test_type_specific_fields_come_before_common_ones():
    # tipe özgü alanlar (şıklar, vaka) önce; tüm ekranlarda ortak olanlar (visible_if…) ayrı bölümde, sonra
    out = g.screen_schema("mcq")
    assert out.index("- options:") < out.index("## Ortak alanlar") < out.index("- visible_if:")
    assert "- title: " in out


def test_union_of_models_lists_every_variant():
    # final inceleme I1: adaptive = Union[EloSpec, BktSpec] — iki varyant da görünmeli (BKT gizlenmesin)
    out = g.screen_schema("adaptive_practice")
    assert "adaptive[elo].k" in out and "adaptive[bkt].p_slip" in out
    assert len(out.encode()) <= g.MAX_SCHEMA_BYTES


def test_type_names_have_no_module_paths():
    assert "core." not in g.screen_schema("adaptive_practice")
