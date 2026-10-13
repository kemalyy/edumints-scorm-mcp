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

# Repo kökü sys.path'in BAŞINDA olmalı: `pip install -e .` server.py'yi site-packages'a KOPYALAR
# (pyproject force-include) ve o kopyanın yanında themes/ yok → tema sessizce varsayılana düşer.
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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


# K1 — kompozisyon fixture'ları: deterministik sentetik görsel (harici dosya yok) + sabit içerik.
_COMP_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">'
    '<rect width="640" height="420" fill="#e7ece9"/><rect x="40" y="40" width="560" height="56" '
    'rx="8" fill="#cfd8d3"/><rect x="40" y="120" width="360" height="18" rx="4" fill="#b9c5bf"/>'
    '<rect x="40" y="150" width="300" height="18" rx="4" fill="#b9c5bf"/>'
    '<rect x="420" y="230" width="180" height="150" rx="10" fill="#9fb3a9"/></svg>')
COMP_ASSET = {"id": "compimg", "filename": "comp.svg",
              "source": "data:image/svg+xml;base64," + base64.b64encode(
                  _COMP_SVG.encode()).decode()}
COMP_SCREENS = {
    "centered": {"type": "title_slide", "title": "Üç e-postadan biri tuzak", "kicker": "Bölüm 2",
                 "lead": "Hangisi olduğunu 90 saniyede bulacaksın.", "composition": "centered"},
    "split-thirds": {"type": "content_slide", "title": "Gönderen adresine bak",
                     "kicker": "Adım 1", "lead": "Alan adı tek harf farklı.",
                     "media_asset_id": "compimg", "media_alt": "E-posta başlığı",
                     "body_html": "<p>Saldırganlar gerçek adrese çok benzeyen bir alan adı "
                                  "kaydeder; <mark>harf harf</mark> oku.</p>",
                     "composition": "split-thirds"},
    "split-halves": {"type": "content_slide", "title": "Gerçek ve klon",
                     "composition": "split-halves",
                     "blocks": [{"asset_id": "compimg", "caption": "Gerçek"},
                                {"asset_id": "compimg", "caption": "Klon"}]},
    "hero-focal": {"type": "title_slide", "title": "Gelen kutunda bir tuzak var",
                   "kicker": "Pazartesi 08:47", "lead": "Bul, tıklama.",
                   "background_asset_id": "compimg", "composition": "hero-focal"},
    "statement": {"type": "content_slide", "title": "Akılda kalan", "lead": "%91",
                  "body_html": "<p>saldırının ilk adımı bir <mark>e-posta</mark>.</p>",
                  "composition": "statement"},
    "z-flow": {"type": "content_slide", "title": "Tıkla → hasat → saldırı", "composition": "z-flow",
               "blocks": [{"html": "<p>08:49 tıklama</p>", "asset_id": "compimg"},
                          {"html": "<p>08:50 parola hasadı</p>", "asset_id": "compimg"},
                          {"html": "<p>11:20 hesap ele geçti</p>"},
                          {"html": "<p>3. gün fidye</p>"}]},
    "f-flow": {"type": "content_slide", "title": "Tıklamadan önce 4 işaret",
               "lead": "Biri bile varsa dur.", "composition": "f-flow",
               "body_html": "<ol><li>Gönderen</li><li>Aciliyet</li><li>Bağlantı</li>"
                            "<li>Ek</li></ol>"},
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
                   theme_mode: str = "light", composition: str | None = None) -> str:
    """Tek ekranlık projeyi server'ın kendi spec ayrıştırıcısı + tema çözücüsüyle kurar ve
    `_render_preview_html`in çağırdığı render yolunun aynısını çalıştırır."""
    spec_dict = {"title": title, "scorm_version": "1.2", "language": "tr",
                 "theme_mode": theme_mode, "screens": [screen]}
    if preset:
        # Tema ADI string olarak verilir. Eski {"preset": ...} sözlüğü ThemeTokens'a ayrışıp
        # sessizce varsayılan temaya düşüyordu — tema varyantları marka temasını hiç test etmiyordu.
        spec_dict["theme"] = preset
    spec = server._parse_spec(spec_dict)
    # K1 — composition verilmezse Project varsayılanı (classic) → mevcut fixture'lar bayt-aynı.
    # Verilirse sunucunun yeni-proje yolu: "default" tema auto'da mint'e yönlenir.
    theme_name = server._theme_for(spec.theme, composition) if composition else spec.theme
    extra = {"composition": composition} if composition else {}

    p = Project(
        id=new_project_id(),
        title=spec.title,
        scorm_version=spec.scorm_version,
        language=spec.language,
        theme=server._load_theme(theme_name, audience=spec.audience_pack),
        **extra,
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

    # C) K1 kompozisyon katmanı — 7 desen × açık/koyu (mint) + iki mobil + iki palet (ink/slate)
    for name, screen in COMP_SCREENS.items():
        for mode in ("light", "dark"):
            html = render_fixture(f"Gorsel: comp {name}", screen, [COMP_ASSET], None, mode,
                                  composition="auto")
            (OUT_DIR / f"comp-{name}-{mode}.html").write_text(html, encoding="utf-8", newline="")
    for name in ("split-thirds", "z-flow"):
        html = render_fixture(f"Gorsel: comp {name} mobil", COMP_SCREENS[name], [COMP_ASSET],
                              composition="auto")
        (OUT_DIR / f"comp-{name}@mobile.html").write_text(html, encoding="utf-8", newline="")
    for pal in ("ink", "slate"):
        html = render_fixture(f"Gorsel: palet {pal}", COMP_SCREENS["split-thirds"], [COMP_ASSET],
                              pal, composition="auto")
        (OUT_DIR / f"comp-palette-{pal}.html").write_text(html, encoding="utf-8", newline="")

    # D) K2 — yedi görsel etkileşimli tip × {visual-stack, split-thirds} (auto, mint) + hotspot ve
    #    data_chart için split-thirds koyu ve mobil. İçerik examples/'tan (A katmanıyla aynı kaynak).
    k2 = ["hotspot", "labeled_diagram", "image_compare", "data_chart", "video", "lottie",
          "simulation"]
    def _real(assets):
        # examples/'taki görseller çoğunlukla 1×1 yer tutucu → yerleşim görünmez; D katmanında
        # aynı asset kimlikleri gerçek boyutlu sentetik SVG'ye bağlanır (A katmanı değişmez).
        return [dict(a, source=COMP_ASSET["source"], filename=a.get("filename", "x") + ".svg")
                if str(a.get("source", "")).startswith("data:image/png") else a for a in assets]

    for t in k2:
        screen, assets, _ = screens[t]
        assets = _real(assets)
        for preset in ("visual-stack", "split-thirds"):
            html = render_fixture(f"Gorsel: k2 {t} {preset}", dict(screen, composition=preset),
                                  assets, composition="auto")
            (OUT_DIR / f"k2-{t}-{preset}.html").write_text(html, encoding="utf-8", newline="")
    for t in ("hotspot", "data_chart"):
        screen, assets, _ = screens[t]
        assets = _real(assets)
        sc = dict(screen, composition="split-thirds")
        html = render_fixture(f"Gorsel: k2 {t} koyu", sc, assets, None, "dark", composition="auto")
        (OUT_DIR / f"k2-{t}-split-thirds-dark.html").write_text(html, encoding="utf-8", newline="")
        html = render_fixture(f"Gorsel: k2 {t} mobil", sc, assets, composition="auto")
        (OUT_DIR / f"k2-{t}@mobile.html").write_text(html, encoding="utf-8", newline="")

    # E) K3 — yedi soru tipi × {question-column (uyaransız), split-thirds + uyaran (görsel + vaka)}
    #    + uyaranlı mcq koyu ve mobil. Uyaran sentetik (examples/'ta soru uyaranı yok).
    stim = {"asset_id": "compimg", "alt": "Şüpheli e-posta ekran görüntüsü",
            "caption": "Pazartesi 08:47 gelen e-posta",
            "text_html": "<p>Muhasebeden Elif, “fatura onayı” konulu bir e-posta aldı. Gönderen "
                         "adresi tanıdık görünüyor ama bağlantı farklı bir alan adına gidiyor.</p>"}
    q_types = ["mcq", "true_false", "fill_blank", "drag_drop", "matching", "sorting",
               "adaptive_practice"]

    def _with_stim(screen):
        if screen["type"] == "adaptive_practice":
            return dict(screen, items=[dict(it, stimulus=stim) for it in screen["items"]])
        return dict(screen, stimulus=stim)

    for t in q_types:
        screen, assets, _ = screens[t]
        assets = _real(assets)
        html = render_fixture(f"Gorsel: k3 {t} soru sutunu", dict(screen, composition="question-column"),
                              assets, composition="auto")
        (OUT_DIR / f"k3-{t}-question-column.html").write_text(html, encoding="utf-8", newline="")
        html = render_fixture(f"Gorsel: k3 {t} uyaranli", _with_stim(dict(screen, composition="split-thirds")),
                              assets + [COMP_ASSET], composition="auto")
        (OUT_DIR / f"k3-{t}-split-thirds-stim.html").write_text(html, encoding="utf-8", newline="")
    screen, assets, _ = screens["mcq"]
    sc = _with_stim(dict(screen, composition="split-thirds"))
    html = render_fixture("Gorsel: k3 mcq koyu", sc, _real(assets) + [COMP_ASSET], None, "dark",
                          composition="auto")
    (OUT_DIR / "k3-mcq-split-thirds-stim-dark.html").write_text(html, encoding="utf-8", newline="")
    html = render_fixture("Gorsel: k3 mcq mobil", sc, _real(assets) + [COMP_ASSET], composition="auto")
    (OUT_DIR / "k3-mcq-stim@mobile.html").write_text(html, encoding="utf-8", newline="")

    # F) K4 — sekiz içerik etkileşimi × {varsayılan (otomatik), split-thirds} + summary centered
    #    + uyaranlı poll koyu ve mobil + tabs mobil (ana–detay dar ekranda yatay).
    k4 = ["accordion", "tabs", "flashcards", "timeline", "results_breakdown", "poll",
          "worked_example", "exploration"]
    for t in k4:
        screen, assets, _ = screens[t]
        assets = _real(assets)
        html = render_fixture(f"Gorsel: k4 {t}", dict(screen), assets, composition="auto")
        (OUT_DIR / f"k4-{t}-auto.html").write_text(html, encoding="utf-8", newline="")
        html = render_fixture(f"Gorsel: k4 {t} split", dict(screen, composition="split-thirds"),
                              assets, composition="auto")
        (OUT_DIR / f"k4-{t}-split-thirds.html").write_text(html, encoding="utf-8", newline="")
    screen, assets, _ = screens["summary"]
    html = render_fixture("Gorsel: k4 summary", dict(screen), _real(assets), composition="auto")
    (OUT_DIR / "k4-summary-centered.html").write_text(html, encoding="utf-8", newline="")
    screen, assets, _ = screens["poll"]
    sc = dict(screen, stimulus=stim, composition="split-thirds")
    html = render_fixture("Gorsel: k4 poll koyu", sc, _real(assets) + [COMP_ASSET], None, "dark",
                          composition="auto")
    (OUT_DIR / "k4-poll-stim-dark.html").write_text(html, encoding="utf-8", newline="")
    html = render_fixture("Gorsel: k4 poll mobil", sc, _real(assets) + [COMP_ASSET],
                          composition="auto")
    (OUT_DIR / "k4-poll-stim@mobile.html").write_text(html, encoding="utf-8", newline="")
    sc_stack = dict(screen, stimulus={k: v for k, v in stim.items() if k != "asset_id" and k != "alt"
                                      and k != "caption"})  # kısa metin → varsayılan visual-stack
    html = render_fixture("Gorsel: k4 poll vaka ustte", sc_stack, _real(assets), composition="auto")
    (OUT_DIR / "k4-poll-stim-stack.html").write_text(html, encoding="utf-8", newline="")
    screen, assets, _ = screens["tabs"]
    html = render_fixture("Gorsel: k4 tabs mobil", dict(screen), _real(assets), composition="auto")
    (OUT_DIR / "k4-tabs@mobile.html").write_text(html, encoding="utf-8", newline="")

    # G) K5 — altı tip × {varsayılan, split-thirds} + game ve decision_scenario mobil + vakalı
    #    branching koyu. Oyun/senaryo düğümlerine görsel eklenir (yan yana sahne görünsün).
    def _with_scene(screen):
        key = {"game": "nodes", "decision_scenario": "nodes"}.get(screen["type"])
        if not key:
            return dict(screen), []
        nodes = [dict(n, image_asset_id="compimg", image_alt="Sahne") for n in screen[key]]
        return dict(screen, **{key: nodes}), [COMP_ASSET]
    k5 = ["game", "decision_scenario", "escape_room", "term_match_race", "branching", "embed_html"]
    for t in k5:
        screen, assets, _ = screens[t]
        sc, extra = _with_scene(screen)
        assets = _real(assets) + extra
        html = render_fixture(f"Gorsel: k5 {t}", sc, assets, composition="auto")
        (OUT_DIR / f"k5-{t}-auto.html").write_text(html, encoding="utf-8", newline="")
        html = render_fixture(f"Gorsel: k5 {t} split", dict(sc, composition="split-thirds"), assets,
                              composition="auto")
        (OUT_DIR / f"k5-{t}-split-thirds.html").write_text(html, encoding="utf-8", newline="")
        if t in ("game", "decision_scenario"):
            html = render_fixture(f"Gorsel: k5 {t} mobil", sc, assets, composition="auto")
            (OUT_DIR / f"k5-{t}@mobile.html").write_text(html, encoding="utf-8", newline="")
    screen, assets, _ = screens["branching"]
    html = render_fixture("Gorsel: k5 branching vakali koyu", dict(screen, stimulus=stim),
                          _real(assets) + [COMP_ASSET], None, "dark", composition="auto")
    (OUT_DIR / "k5-branching-stim-dark.html").write_text(html, encoding="utf-8", newline="")

    print(f"\ntoplam {len(list(OUT_DIR.glob('*.html')))} fixture -> {OUT_DIR}")


if __name__ == "__main__":
    main()
