"""tests/test_strict_and_zipcheck.py — SP-5: B4-strict (opt-in strict anti-slop) + B1 delta
(build sonrası zip doğrulama kapısı).

Part A — strict mod:
- Küratörlü WARN kümesi (STRICT_PROMOTED_CODES) yalnız strict=True'da bloklamaya terfi eder.
- Varsayılan davranış DEĞİŞMEZ: warn'lı kurs non-strict build'de yine geçer (regresyon).
- ANTISLOP_STRICT=1 sunucu varsayılanını strict yapar; açık strict=False bunu geçersiz kılar.

Part B — artifact kapısı:
- Paketçi zip'i üretince, başarı işaretlemeden ÖNCE validate_zip koşar; yapısal hata → job error
  (+ fast-path'te ToolError), bozuk zip diskten silinir.
- schema_unavailable BLOKLAMAZ; yanıtta uyarı olarak taşınır (testte şemalar kasıtlı erişilemez).
"""

from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError as MCPToolError

import server
from core.antislop import STRICT_PROMOTED_CODES, lint_errors
from core.project import ContentSlide, GameScreen, Project, new_project_id
from core.validator import validate_project


def _text_wall_screens(n: int = 4) -> list[dict]:
    # n ardışık görselsiz ekran → text_only_run (strict-promoted WARN); yapısal hata YOK.
    return [{"type": "content_slide", "id": f"c{i}", "title": f"Ekran {i} — neden {i}?",
             "body_html": f"<p>metin {i}</p>"} for i in range(n)]


def _warny_spec(title: str) -> dict:
    return {"title": title, "scorm_version": "1.2", "screens": _text_wall_screens()}


def _decorative_score_game() -> GameScreen:
    # skor mekaniği tanımlı ama hiçbir kural/seçim değiştirmiyor → decorative_score (WARN)
    return GameScreen(
        id="g", title="Skorlu ama süs",
        feedback={"correct_html": "İyi.", "incorrect_html": "Tekrar."},
        mechanics={"score": {"id": "sc"}},
        nodes=[
            {"id": "n1", "content_html": "<p>x</p>", "choices": [
                {"id": "a", "text_html": "A", "to": "n2"},
                {"id": "b", "text_html": "B", "to": None}]},
            {"id": "n2", "content_html": "<p>y</p>",
             "choices": [{"id": "c", "text_html": "Bitir", "to": None}]},
        ], rules=[])


# --------------------------------------------------------------------------- #
# Part A — birim: lint_errors(strict=) + validate_project(strict=)
# --------------------------------------------------------------------------- #
def test_strict_promoted_codes_is_curated_set():
    assert STRICT_PROMOTED_CODES == frozenset({
        "penalty_without_rationale", "text_only_run", "visual_poverty",
        "missing_alt_text", "decorative_score",
        # E1 (#110) — kanıt-bağlama tabanları (K1/K2/T1): varsayılanda WARN, strict'te blok
        "unbound_scored_question", "evidence_target_not_evidentiary",
    })


def test_lint_errors_default_excludes_promoted_warns():
    p = Project(id=new_project_id(), title="K", screens=[_decorative_score_game()])
    assert [i for i in lint_errors(p)] == []  # varsayılan: WARN bloklamaz (davranış değişmedi)


def test_lint_errors_strict_promotes_curated_warns():
    p = Project(id=new_project_id(), title="K", screens=[_decorative_score_game()])
    codes = {i.code for i in lint_errors(p, strict=True)}
    assert "decorative_score" in codes
    # strict, küratörlü küme DIŞINDAKİ warn'ları terfi ETTİRMEZ
    assert codes <= STRICT_PROMOTED_CODES | {"unreachable_node", "fake_choice"}


def test_validate_project_strict_blocks_text_wall():
    screens = [ContentSlide(id=f"c{i}", title=f"Ekran {i} — neden {i}?",
                            body_html=f"<p>m{i}</p>") for i in range(4)]
    p = Project(id=new_project_id(), title="K", screens=screens)
    assert validate_project(p) == []  # non-strict: temiz geçer
    msgs = [e.message for e in validate_project(p, strict=True)]
    assert any("strict:text_only_run" in m for m in msgs)


# --------------------------------------------------------------------------- #
# Part A — tool yüzeyi
# --------------------------------------------------------------------------- #
async def test_warn_laden_course_builds_non_strict():
    """REGRESYON: warn'lı kurs varsayılan (non-strict) build'de değişmeden geçer."""
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": _warny_spec("SP5 non-strict")})
        assert res.data.status == "done"
        assert res.data.download_url


async def test_build_from_spec_strict_blocks_warny_course():
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError, match="validation_error") as ei:
            await c.call_tool("build_from_spec",
                              {"spec": _warny_spec("SP5 strict blok"), "strict": True})
        assert "strict:text_only_run" in str(ei.value)


async def test_build_package_strict_blocks_then_default_passes():
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": _warny_spec("SP5 bp strict")})
        pid = res.data.project_id
        with pytest.raises(MCPToolError, match="validation_error"):
            await c.call_tool("build_package", {"project_id": pid, "strict": True})
        out = await c.call_tool("build_package", {"project_id": pid})  # varsayılan: geçer
        assert out.data.status == "done"


async def test_lint_course_strict_reports_promoted_as_errors():
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": _warny_spec("SP5 lint strict")})
        pid = res.data.project_id
        loose = (await c.call_tool("lint_course", {"project_id": pid})).data
        assert loose["error_count"] == 0
        assert any(i["code"] == "text_only_run" and i["severity"] == "warn"
                   for i in loose["issues"])
        strict = (await c.call_tool("lint_course", {"project_id": pid, "strict": True})).data
        assert strict["strict"] is True
        assert strict["error_count"] >= 1
        assert any(i["code"] == "text_only_run" and i["severity"] == "error"
                   for i in strict["issues"])
        # terfi etmeyen warn'lar warn kalır (consecutive_content_slides küratörlü kümede değil)
        assert any(i["code"] == "consecutive_content_slides" and i["severity"] == "warn"
                   for i in strict["issues"])


async def test_env_antislop_strict_flips_default(monkeypatch):
    """ANTISLOP_STRICT=1 → parametresiz çağrı strict davranır; açık strict=False geri açar."""
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": _warny_spec("SP5 env default")})
        pid = res.data.project_id
        monkeypatch.setattr(server.SETTINGS, "antislop_strict", True)
        with pytest.raises(MCPToolError, match="validation_error"):
            await c.call_tool("build_package", {"project_id": pid})
        out = await c.call_tool("build_package", {"project_id": pid, "strict": False})
        assert out.data.status == "done"


def test_settings_reads_antislop_strict_env(monkeypatch):
    monkeypatch.setenv("ANTISLOP_STRICT", "1")
    assert server.Settings().antislop_strict is True
    monkeypatch.setenv("ANTISLOP_STRICT", "0")
    assert server.Settings().antislop_strict is False


# --------------------------------------------------------------------------- #
# Part B — build sonrası zip doğrulama kapısı
# --------------------------------------------------------------------------- #
async def test_corrupt_zip_fails_build_visibly(monkeypatch):
    """Paketçi bozuk zip üretirse: fast-path ToolError, job 'error', dosya diskten silinir."""
    await server.SVC.ensure()
    orig = server.SVC.packager.build_sync
    written: list[Path] = []

    def corrupting_build(project, assets):
        meta = orig(project, assets)
        path = Path(server.SETTINGS.data_dir) / meta.rel_path
        path.write_bytes(b"BU BIR ZIP DEGIL")  # truncate/corrupt
        written.append(path)
        return meta

    monkeypatch.setattr(server.SVC.packager, "build_sync", corrupting_build)
    async with Client(server.mcp) as c:
        res = await c.call_tool("create_project", {"title": "SP5 bozuk zip"})
        pid = res.data.project_id
        await c.call_tool("add_screen", {"project_id": pid, "screen": {
            "type": "title_slide", "id": "t1", "title": "T"}})
        with pytest.raises(MCPToolError, match="build_error"):
            await c.call_tool("build_package", {"project_id": pid})
        # job görünür şekilde error; download_url asla dolmaz
        st = (await c.call_tool("build_status", {"project_id": pid})).data
        assert st.status == "error"
        assert st.download_url is None
        assert "ArtifactValidationError" in (st.error or "")
    assert written and not written[0].exists()  # bozuk artifact servis edilemez (silindi)


async def test_normal_build_unaffected_and_schema_unavailable_tolerated():
    """Normal build geçer; şemalar erişilemezken schema_unavailable yanıtta UYARI olarak taşınır
    (conftest SCORM_SCHEMA_DIR'i şemasız dizine işaret ettirir → uyarı deterministik)."""
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "SP5 normal", "scorm_version": "1.2",
            "screens": [{"type": "title_slide", "id": "t1", "title": "T"}]}})
        assert res.data.status == "done"
        assert res.data.download_url
        assert any("XSD" in w or "şema" in w.lower() for w in res.data.warnings)
        st = (await c.call_tool("build_status", {"project_id": res.data.project_id})).data
        assert st.status == "done"
        assert any("XSD" in w or "şema" in w.lower() for w in st.warnings)
