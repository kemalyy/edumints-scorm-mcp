"""tests/visual/generate_fixtures.py — #150 görsel regresyon harness'ının fixture üreteci.

Her ekran tipi için TEK ekranlık bir kursun `preview` HTML'ini `tests/visual/fixtures/`
altına yazar. Snapshot adımı (`tests/visual/snapshot.mjs`) bu dosyaları SABİTLENMİŞ bir
Playwright konteynerinde açıp PNG'ye çeker.

İki katman (kapsam kararı — 31 tip × 18 tema × 2 kip = 1116 snapshot kombinatorik
patlaması BİLİNÇLİ olarak alınmadı):
  A) Ekran tipi kapsamı — 31 tipin her biri BİR kez, tek tema, açık kip.
  B) Tema katmanlaması — TEK sabit ekran (`mcq`) × {marka teması açık, marka teması koyu,
     ikinci bir stil preseti}. Aynı ekranı üç tema altında karşılaştırmak tema
     regresyonunu ekran regresyonundan AYIRIR; farklı ekranlar kullanmak ikisini karıştırırdı.

İçerik UYDURULMUYOR: `examples/**` 31 tipin 30'unu zaten kapsıyor ve o içerik küratörlü,
repoyla birlikte bakımı yapılıyor. Üreteç örnekten ilgili ekranı + REFERANS VERDİĞİ
asset'leri çekip tek ekranlık bir projeye sarar. Yalnız `embed_html`in örneği yok (tip
sonradan geldi) — o sentezlenir.

Yeni bir ekran tipi eklenip örneği yazılmazsa üreteç SESSİZ GEÇMEZ, hata verir: kapsam
boşluğu görünür olsun (tests/test_docs_a11y_matrix.py bekçisiyle aynı felsefe).

NOT — neden `build_from_spec` DEĞİL: o yol her fixture için tam SCORM zip build'i +
doğrulama + SQLite yazımı yapıyor (ölçüldü: fixture başına ~2 dk, 34 fixture = kabul
edilemez). Burada ihtiyaç duyulan tek şey preview HTML'i, yani `renderer.render_html`in
kendisi — `server._render_preview_html`in tam olarak çağırdığı şey. Tema çözümü ve spec
ayrıştırması yine SUNUCUNUN kendi fonksiyonlarıyla yapılır ki fixture, gerçek kursun
render yolundan sapmasın.
"""
import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="visual-fixtures-")
os.environ.setdefault("SCORM_AUTH_ENABLED", "0")
os.environ.setdefault("DATA_DIR", _TMP)
os.environ.setdefault("DB_PATH", os.path.join(_TMP, "scorm.db"))
os.environ.setdefault("PUBLIC_BASE_URL", "https://mcp.test/scorm")
os.environ.setdefault("SCORM_NO_TTL_CLEANER", "1")
os.environ.setdefault("SCORM_SCHEMA_DIR", os.path.join(_TMP, "no_schemas"))

import server  # noqa: E402

from auth.ssrf import decode_data_uri  # noqa: E402
from components import renderer  # noqa: E402
from core.project import (  # noqa: E402
    AssetRef,
    Project,
    ScreenType,
    new_asset_id,
    new_project_id,
    new_screen_id,
)

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES = ROOT / "examples"
OUT_DIR = Path(__file__).resolve().parent / "fixtures"

MAX_ASSET_BYTES = 25 * 1024 * 1024

# Katman B — tema katmanlaması. Aynı ekran, üç tema yapılandırması.
THEME_VARIANTS = [
    ("theme-brand-light", "corporate/brand-academy", "light"),
    ("theme-brand-dark", "corporate/brand-academy", "dark"),
    ("theme-playful-light", "style-playful", "light"),
]
THEME_VARIANT_TYPE = "mcq"   # şık butonları + zengin metin + rozet: çok token'a dokunur

# embed_html'in örneği yok (tip sonradan geldi) — deterministik minimum sentez.
_EMBED_HTML = (
    "<!doctype html><meta charset=utf-8><title>demo</title>"
    "<body style='margin:0;font:16px sans-serif;display:grid;place-items:center;height:100vh'>"
    "<p>gomulu artifact</p></body>"
)
SYNTHETIC = {
    "embed_html": {
        "assets": [{
            "id": "embed1", "filename": "demo.html",
            "source": "data:text/html;base64," + base64.b64encode(_EMBED_HTML.encode()).decode(),
        }],
        "screen": {"type": "embed_html", "id": "eh1", "title": "Gomulu artifact",
                   "html_asset_id": "embed1", "aspect": "16:9"},
    },
}


def _asset_ids(node) -> set[str]:
    """Ekran sözlüğünde geçen tüm *_asset_id değerlerini toplar (iç içe yapılar dahil)."""
    out: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith("_asset_id") and isinstance(v, str):
                out.add(v)
            else:
                out |= _asset_ids(v)
    elif isinstance(node, list):
        for v in node:
            out |= _asset_ids(v)
    return out


def collect_screens() -> dict[str, tuple[dict, list, str]]:
    """type -> (screen, assets, kaynak). Deterministik: dosya yolu + ekran sırasına göre İLK
    bulunan kazanır, böylece yeni örnek eklemek mevcut fixture'ları kaydırmaz."""
    found: dict[str, tuple[dict, list, str]] = {}
    for path in sorted(EXAMPLES.rglob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        assets = spec.get("assets") or []
        for screen in spec.get("screens") or []:
            t = screen.get("type")
            if not t or t in found:
                continue
            need = _asset_ids(screen)
            found[t] = (screen, [a for a in assets if a.get("id") in need],
                        str(path.relative_to(ROOT)).replace(os.sep, "/"))
    for t, syn in SYNTHETIC.items():
        found.setdefault(t, (syn["screen"], syn["assets"], "sentetik"))
    return found


def render_fixture(title: str, screen: dict, assets: list, preset: str | None = None,
                   theme_mode: str = "light") -> str:
    """Tek ekranlık projeyi server'ın kendi spec ayrıştırıcısı + tema çözücüsüyle kurar ve
    `_render_preview_html`in çağırdığı render yolunun aynısını çalıştırır."""
    spec_dict = {"title": title, "scorm_version": "1.2", "language": "tr",
                 "theme_mode": theme_mode, "screens": [screen]}
    if preset:
        spec_dict["theme"] = {"preset": preset}
    spec = server._parse_spec(spec_dict)

    p = Project(
        id=new_project_id(),
        title=spec.title,
        scorm_version=spec.scorm_version,
        language=spec.language,
        theme=server._load_theme(spec.theme, audience=spec.audience_pack),
        theme_mode=spec.theme_mode,
        tracking=spec.tracking,
        layout_mode=spec.layout_mode,
        screens=list(spec.screens),
    )
    for s in p.screens:
        if not s.id:
            s.id = new_screen_id()

    asset_data: dict[str, tuple[str, bytes]] = {}
    existing: set[str] = set()
    for a in assets:
        data, mime = decode_data_uri(a["source"], max_bytes=MAX_ASSET_BYTES)
        rel = server._safe_filename(a.get("filename") or "asset.bin", existing)
        existing.add(rel)
        aid = a.get("id") or new_asset_id()
        p.assets.append(AssetRef(id=aid, filename=os.path.basename(rel), mime=mime,
                                 size_bytes=len(data),
                                 sha256=hashlib.sha256(data).hexdigest(), rel_path=rel))
        asset_data[aid] = (mime, data)

    return renderer.render_html(p, mode="preview", runtime_js=renderer.load_runtime_js(),
                                asset_data=asset_data)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.html"):
        stale.unlink()

    screens = collect_screens()
    missing = sorted({t.value for t in ScreenType} - set(screens))
    if missing:
        raise SystemExit(
            f"HATA: bu ekran tiplerinin ne ornegi ne de sentezi var: {missing}\n"
            "examples/ altina bu tipi kullanan bir ornek ekleyin ya da SYNTHETIC'e girin — "
            "aksi halde tip gorsel regresyondan KORUNMASIZ kalir."
        )
    extra = sorted(set(screens) - {t.value for t in ScreenType})
    if extra:
        raise SystemExit(f"HATA: modelde olmayan ekran tipi orneklerde geciyor: {extra}")

    for t in sorted(screens):                     # deterministik sıra
        screen, assets, src = screens[t]
        html = render_fixture(f"Gorsel: {t}", screen, assets)
        (OUT_DIR / f"screen-{t}.html").write_text(html, encoding="utf-8", newline="")
        print(f"screen-{t}.html  ({len(html)} bayt)  <- {src}")

    screen, assets, _ = screens[THEME_VARIANT_TYPE]
    for name, preset, mode in THEME_VARIANTS:
        html = render_fixture(f"Gorsel: {name}", screen, assets, preset, mode)
        (OUT_DIR / f"{name}.html").write_text(html, encoding="utf-8", newline="")
        print(f"{name}.html  ({len(html)} bayt)")

    print(f"\ntoplam {len(list(OUT_DIR.glob('*.html')))} fixture -> {OUT_DIR}")


if __name__ == "__main__":
    main()
