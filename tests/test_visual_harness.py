"""tests/test_visual_harness.py — #150 görsel regresyon harness'ının sözleşme bekçileri.

Snapshot karşılaştırmasının KENDİSİ burada koşmaz (tarayıcı + sabitlenmiş konteyner gerekir;
o iş `visual` CI job'ında). Buradaki testler harness'ın SESSİZCE İŞLEVSİZLEŞMESİNİ engeller —
üçü de bu harness'ı kurarken gerçekten karşılaşılan tuzaklar:

1. Playwright sürümü kayarsa (`^1.48.0` gibi bir aralık) `npm ci` yeni bir Chromium çeker,
   rasterizasyon değişir ve 34 snapshot'ın tamamı sebepsiz kırılır. TAM sürüm zorunlu.
2. Sürüm yükseltilip CI'daki konteyner tag'i unutulursa iş daha kötü olur: kap "browser not
   found" ile değil, BAŞKA bir tarayıcıyla koşar ve baseline'lar sessizce anlamsızlaşır.
3. Yeni bir ekran tipi eklenip `examples/` altına örneği yazılmazsa o tip görsel regresyondan
   korunmasız kalır. Üreteç bunu hata olarak keser ama üreteç yalnız `visual` job'ında koşar;
   bu test aynı boşluğu SANİYELER içinde, normal pytest turunda yakalar.
"""
import json
import re
from pathlib import Path

from core.project import ScreenType

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON = ROOT / "package.json"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"

_EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_IMAGE_TAG = re.compile(r"mcr\.microsoft\.com/playwright:v(\d+\.\d+\.\d+)-\w+")


def _pinned_playwright() -> str:
    dev = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["devDependencies"]
    return dev["playwright"]


def test_playwright_version_is_exactly_pinned():
    v = _pinned_playwright()
    assert _EXACT_VERSION.match(v), (
        f"package.json devDependencies.playwright = '{v}' — görsel regresyon kapısı için TAM "
        "sürüm gerekir. Aralık (^/~) yeni bir Chromium çeker, rasterizasyon değişir ve tüm "
        "baseline'lar sebepsiz kırılır."
    )


def test_ci_container_tag_matches_the_pinned_version():
    tags = set(_IMAGE_TAG.findall(CI_YML.read_text(encoding="utf-8")))
    assert tags, "ci.yml'de Playwright konteyner imajı bulunamadı — visual job'ı kayboldu mu?"
    pinned = _pinned_playwright()
    assert tags == {pinned}, (
        f"ci.yml imaj tag'i {sorted(tags)}, package.json ise '{pinned}' diyor. Sürüm "
        "yükseltirken İKİSİ birlikte değişmeli; yoksa kap başka bir tarayıcıyla koşar ve "
        "baseline'lar sessizce anlamsızlaşır."
    )


def test_every_screen_type_has_a_visual_fixture_source():
    """Üreteci ÇALIŞTIRMADAN kapsamı denetler: fixture kaynağı toplama saf fonksiyondur."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_visual_gen", ROOT / "tests" / "visual" / "generate_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    covered = set(mod.collect_screens())
    missing = sorted({t.value for t in ScreenType} - covered)
    assert not missing, (
        f"görsel regresyondan korunmasız ekran tipi: {missing} — `examples/` altına bu tipi "
        "kullanan bir örnek ekleyin ya da generate_fixtures.SYNTHETIC'e girin"
    )


def test_theme_variant_screen_exists():
    """Katman B sabit ekranı gerçekten toplanabiliyor olmalı (yoksa tema kapsamı sessizce düşer)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_visual_gen", ROOT / "tests" / "visual" / "generate_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.THEME_VARIANT_TYPE in mod.collect_screens()
