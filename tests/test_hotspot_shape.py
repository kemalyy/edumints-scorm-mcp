"""tests/test_hotspot_shape.py — #153: hotspot bölge geometrisi (şekil + koordinat aritesi).

Hata: `HotspotRegion.shape` `"poly"`yi kabul ediyordu ama oynatıcı onu HİÇ konumlandırmıyor
(`components/templates.py` `place()` yalnız `rect`/`circle` dallarını yazar). Sonuç sessiz:
`position:absolute`lu buton offset'siz kalır → sıfır boyutlu, görünmez, tıklanamaz; ama tab
sırasında durur ve `correct` listesinde olabilir → doğru cevap poly ise ekran HİÇ geçilemez.
Aynı sessiz arıza yanlış koordinat sayısında da oluşur (NaN offset) ve `coords: list[float]`
bugüne dek hiç doğrulanmıyordu.

Çözümün şekli — neden `Literal`'dan çıkarılmadı: `core/store.py` her projeyi
`Project.model_validate_json` ile okur (`get_project`, `list_projects`, `list_projects_page`).
Enum'u daraltmak kayıtlı poly'li bir projeyi YÜKLENEMEZ yapar ve `list_projects` sayfanın
TAMAMINI patlatır — bugünkü hatadan daha kötü bir arıza. Bu yüzden model kabul etmeye devam
eder, build `core/validator.py`de SERT hatayla kesilir: `require_all` (#138) ile aynı desen.
`test_legacy_poly_project_still_loads` bu kararın bekçisidir.
"""
from core.antislop import lint_course
from core.project import (
    HotspotRegion,
    HotspotScreen,
    Project,
    ThemeTokens,
    new_project_id,
)
from core.validator import validate_project


def _hs(regions):
    return HotspotScreen(id="hs1", title="Motor", prompt_html="<p>Bul.</p>",
                         image_asset_id="img1", image_alt="şema", regions=regions)


def _proj(regions):
    return Project(id=new_project_id(), title="T", theme=ThemeTokens(),
                   screens=[_hs(regions)])


def _rect(id="r1"):
    return HotspotRegion(id=id, shape="rect", coords=[10, 10, 40, 40], label_html="Karbüratör")


def _circle(id="c1"):
    return HotspotRegion(id=id, shape="circle", coords=[100, 100, 20], label_html="Piston")


def _poly(id="p1"):
    return HotspotRegion(id=id, shape="poly", coords=[0, 0, 10, 0, 10, 10], label_html="Blok")


# --------------------------------------------------------------------------- #
# Validator — şekil
# --------------------------------------------------------------------------- #
def test_poly_region_is_rejected():
    errs = validate_project(_proj([_rect(), _poly()]))
    hits = [e for e in errs if e.path.endswith("regions[1].shape")]
    assert hits, f"poly reddedilmedi: {[e.path for e in errs]}"
    assert "poly" in hits[0].message and "rect" in hits[0].message


def test_supported_shapes_are_accepted():
    errs = validate_project(_proj([_rect(), _circle()]))
    assert not [e for e in errs if ".regions[" in e.path]


def test_poly_error_does_not_mask_the_other_regions():
    """poly satırında `continue` var — sonraki bölgelerin denetimi düşmemeli."""
    bad_rect = HotspotRegion(id="r2", shape="rect", coords=[1, 2, 3])  # 3 sayı, 4 gerek
    errs = validate_project(_proj([_poly(), bad_rect]))
    paths = [e.path for e in errs]
    assert any(p.endswith("regions[0].shape") for p in paths)
    assert any(p.endswith("regions[1].coords") for p in paths)


# --------------------------------------------------------------------------- #
# Validator — koordinat aritesi
# --------------------------------------------------------------------------- #
def test_rect_needs_four_coords():
    short = HotspotRegion(id="r1", shape="rect", coords=[10, 10, 40])
    errs = validate_project(_proj([short]))
    hits = [e for e in errs if e.path.endswith("regions[0].coords")]
    assert hits and "4 koordinat" in hits[0].message


def test_circle_needs_three_coords():
    long = HotspotRegion(id="c1", shape="circle", coords=[10, 10, 40, 40])
    errs = validate_project(_proj([long]))
    hits = [e for e in errs if e.path.endswith("regions[0].coords")]
    assert hits and "3 koordinat" in hits[0].message


# --------------------------------------------------------------------------- #
# Geriye uyum — bu PR'ın tasarım kararının bekçisi
# --------------------------------------------------------------------------- #
def test_legacy_poly_project_still_loads():
    """Şema `poly`yi KABUL etmeye devam etmeli: store kayıtlı projeyi
    `Project.model_validate_json` ile okur; enum daraltılsaydı eski kayıt yüklenemez olurdu
    ve tek bozuk proje `list_projects` sayfasının tamamını patlatırdı."""
    raw = _proj([_poly()]).model_dump_json()
    loaded = Project.model_validate_json(raw)
    assert loaded.screens[0].regions[0].shape == "poly"


# --------------------------------------------------------------------------- #
# Anti-slop — yazar build denemeden lint_course'ta görsün
# --------------------------------------------------------------------------- #
def test_lint_reports_unsupported_shape_as_error():
    issues = [i for i in lint_course(_proj([_poly()]))
              if i.code == "hotspot_unsupported_shape"]
    assert issues and issues[0].severity == "error"


def test_lint_reports_bad_coords_as_error():
    short = HotspotRegion(id="r1", shape="rect", coords=[1, 2], label_html="X")
    issues = [i for i in lint_course(_proj([short])) if i.code == "hotspot_bad_coords"]
    assert issues and issues[0].severity == "error"


def test_lint_quiet_for_valid_geometry():
    codes = [i.code for i in lint_course(_proj([_rect(), _circle()]))]
    assert "hotspot_unsupported_shape" not in codes
    assert "hotspot_bad_coords" not in codes
