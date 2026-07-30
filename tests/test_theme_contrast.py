"""tests/test_theme_contrast.py — Faz 5 (Kol D): OTOMATİK AA KONTRAST KAPISI (3.5 — zemin).

Her sevk edilen tema (themes/**/*.json, _-önekli hariç) ve her sevk edilen
preset × audience-override kombinasyonu için, renderer'ın GERÇEKTE eşleştirdiği
mürekkep×zemin çiftlerinin WCAG 2.x kontrast oranını hesaplar ve eşiğe bağlar.

ÇİFT MATRİSİ NASIL TÜRETİLDİ — components/templates.py BASE_CSS + OUTLINE_CSS satır satır
okunarak (uydurma çift yok). Kaynak seçici her satırın yanında. Durum varyantları dahil:
  - disabled (opacity-tabanlı → EFEKTİF birleşik renk hesaplanır: fg' = a·fg+(1-a)·zemin),
  - placeholder (::placeholder{color:var(--c-muted)} — bu fazda CSS'e sabitlendi),
  - ikincil/yardımcı metin (muted × her zemin),
  - odak halkası (1.4.11 metin-dışı ≥3:1; bu fazda %50-mix yerine SOLID var(--c-focus)
    yapıldı — %50 alfa halka açık temalarda matematiksel olarak 3:1'i GEÇEMİYORDU),
  - hover (btn-primary:hover, drop-target.over),
  - selected/active (.opt.selected, .chosen, .fc-back, sekme/menü current).
color-mix(in srgb, X p%, Y) CSS spec gereği gamma-uzayında sabit-katsayılı karışımdır;
aynı formül burada uygulanır. Saf Python, bağımlılık yok.

EŞİKLER:
  TEXT     4.5:1 — normal metin (temkinli varsayılan: renderer'ın "her zaman büyük" garanti
                   ettiği çift yok; başlıklar zaten text×surface çiftine düşer → 4.5 kapsar)
  NONTEXT  3.0:1 — 1.4.11 (odak halkası, seçim işareti, ilerleme dolgusu)
  INACTIVE 2.0:1 — devre dışı/dim bileşen METNİ. WCAG 1.4.3 inaktif bileşeni AÇIKÇA muaf
                   tutar (endüstri pratiği de kasıtlı soluklaştırır, ör. Material disabled
                   ≈2:1); yine de "hiç algılanamaz" durumunu yakalamak için ev-içi taban.
                   Oranlar rapor çıktısında görünür.

BİLİNÇLİ KAPSAM DIŞI (rapor edilir, iddia edilmez):
  - --c-border çerçeveleri: 1.4.11 "sınır çizgisi, bileşen başka yolla tanımlanabiliyorsa
    gerekli değildir" (etiketli inputlar, dolgulu kartlar) — tüm temaların kenarlıklarını
    koyulaştırmak ayrı bir tasarım kararı olur; Faz 6 düzen ölçümüyle birlikte ele alınmalı.
  - accent/secondary/info/text_on_dark: renderer bunları metin×zemin çifti olarak
    KULLANMIYOR (accent yalnız degrade/dekor ucu; info hiç; on-dark yalnız sabit #fff'li
    cc-bar'a benzer statik bağlamlar). Kullanım eklendiği gün çift buraya eklenmek zorunda.
"""
from pathlib import Path

import pytest

import server

THEMES_DIR = Path("themes")

# --------------------------------------------------------------------------- #
# Saf-Python WCAG renk matematiği
# --------------------------------------------------------------------------- #
def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise ValueError(f"desteklenmeyen renk biçimi: #{h} (tema token'ları 6 haneli hex olmalı)")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a: str | tuple, b: str | tuple, pa: float) -> tuple[float, float, float]:
    """color-mix(in srgb, A pa%, B) — gamma-uzayı sabit katsayılı karışım (CSS Color 5)."""
    ra = a if isinstance(a, tuple) else hex_rgb(a)
    rb = b if isinstance(b, tuple) else hex_rgb(b)
    return tuple(ra[i] * pa + rb[i] * (1 - pa) for i in range(3))  # type: ignore[return-value]


def over(fg: str | tuple, alpha: float, backdrop: str | tuple) -> tuple[float, float, float]:
    """opacity:a uygulanmış katmanın efektif rengi (basit alfa birleşimi, gamma uzayı)."""
    return mix(fg, backdrop, alpha)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(c: str | tuple) -> float:
    r, g, b = c if isinstance(c, tuple) else hex_rgb(c)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str | tuple, b: str | tuple) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------- #
# ÇİFT MATRİSİ — (id, kategori, fg(c), bg(c), CSS kaynağı)
# c: ColorPalette; fg/bg lambda'ları hex ya da (r,g,b) tuple döndürür.
# --------------------------------------------------------------------------- #
TEXT, NONTEXT, INACTIVE = "TEXT", "NONTEXT", "INACTIVE"
THRESHOLD = {TEXT: 4.5, NONTEXT: 3.0, INACTIVE: 2.0}

PAIRS = [
    # --- gövde / temel metin ---
    ("text_on_bg", TEXT, lambda c: c.text, lambda c: c.bg,
     "body{color:text;background:bg}; .opt/.blank input/.drag-item (background:bg)"),
    ("text_on_surface", TEXT, lambda c: c.text, lambda c: c.surface,
     ".screen-inner/.app-header/.app-footer/.slide-menu (background:surface)"),
    ("text_on_surface_alt", TEXT, lambda c: c.text, lambda c: c.surface_alt,
     ".rich code/.rich thead th/.we-rationale/.btn-ghost:hover (background:surface-alt)"),
    # --- ikincil/yardımcı + placeholder (durum 2-3) ---
    ("muted_on_bg", TEXT, lambda c: c.text_muted, lambda c: c.bg,
     "::placeholder + .blank>label/.drop-label/.xp-hint (muted, input bg=bg)"),
    ("muted_on_surface", TEXT, lambda c: c.text_muted, lambda c: c.surface,
     ".status-pill/.pl-time/.scen-conseq/.pos-strip/.mtree-num/.pl-btn (muted on surface)"),
    ("muted_on_surface_alt", TEXT, lambda c: c.text_muted, lambda c: c.surface_alt,
     ".rich blockquote (bg:surface-alt,color:muted); .sort-ctrl button"),
    # --- primary mürekkep olarak ---
    ("primary_on_surface", TEXT, lambda c: c.primary, lambda c: c.surface,
     ".rich a/.tab[aria-selected]/.mtree-btn[aria-current]/.xp-saved"),
    ("primary_on_bg", TEXT, lambda c: c.primary, lambda c: c.bg,
     ".branch-choice::before/.scen-choice::before/.accordion summary::before (bg zeminli kart)"),
    ("primary_on_tint6_surface", TEXT, lambda c: c.primary,
     lambda c: mix(c.primary, c.surface, .06), ".timer-hud (bg:mix(primary 6%,surface))"),
    ("primary_on_tint8_surface", TEXT, lambda c: c.primary,
     lambda c: mix(c.primary, c.surface, .08),
     ".level-hud; .pl-btn:hover; .slide-menu li[aria-current] (mix(primary 8%,·) surface üstünde)"),
    ("primary_on_tint10_surface_alt", TEXT, lambda c: c.primary,
     lambda c: mix(c.primary, c.surface_alt, .10), ".ui-chip (bg:mix(primary 10%,surface-alt))"),
    ("kicker_primary_on_title_bg", TEXT, lambda c: c.primary,
     lambda c: mix(c.primary, c.surface, .04),
     ".title-kicker (title_slide inner: mix(primary 4%,surface); opacity kaldırıldı — Faz 5)"),
    # --- primary üzerinde metin (+ hover durumu 5) ---
    ("contrast_on_primary", TEXT, lambda c: c.primary_contrast, lambda c: c.primary,
     ".btn-primary/.btn-check/.skip-link/.ld-pin/.we-num/.pl-btn[aria-pressed]/.review-btn"),
    ("contrast_on_primary_hover", TEXT, lambda c: c.primary_contrast, lambda c: c.primary_hover,
     ".btn-primary:hover{background:primary-hover} — HOVER durumu"),
    # --- durum renkleri metin olarak ---
    ("success_on_success_bg", TEXT, lambda c: c.success, lambda c: c.success_bg,
     ".feedback.ok{background:success-bg;color:success}"),
    ("error_on_error_bg", TEXT, lambda c: c.error, lambda c: c.error_bg,
     ".feedback.no{...}; .timer-hud.urgent"),
    ("success_on_surface", TEXT, lambda c: c.success, lambda c: c.surface,
     ".review-status/.summary-completion.passed/.mtree .mi-done"),
    ("error_on_surface", TEXT, lambda c: c.error, lambda c: c.surface,
     ".summary-completion.failed/.game-hud-lives"),
    ("warning_on_surface", TEXT, lambda c: c.warning, lambda c: c.surface,
     ".scen-hud (color:warning, screen-inner surface üstünde)"),
    ("warning_on_warn14_bg", TEXT, lambda c: c.warning,
     lambda c: mix(c.warning, c.bg, .14), ".sim-hint{background:mix(warning 14%,bg);color:warning}"),
    ("warning_on_warn8_surface", TEXT, lambda c: c.warning,
     lambda c: mix(c.warning, c.surface, .08), ".points-hud{background:mix(warning 8%,surface)}"),
    # --- selected / hover zeminleri (durum 5-6) ---
    ("text_on_selected7_bg", TEXT, lambda c: c.text,
     lambda c: mix(c.primary, c.bg, .07), ".opt.selected/.fc-back{background:mix(primary 7%,bg)}"),
    ("text_on_chosen8_bg", TEXT, lambda c: c.text,
     lambda c: mix(c.primary, c.bg, .08),
     ".scen-choice.chosen/.game-choice.chosen/.sim-instruction{background:mix(primary 8%,bg)}"),
    ("muted_on_dropover6_bg", TEXT, lambda c: c.text_muted,
     lambda c: mix(c.primary, c.bg, .06), ".drop-target.over{background:mix(primary 6%,bg)} .drop-label"),
    # --- metin-dışı göstergeler (1.4.11 ≥3:1; durum 4: odak halkası) ---
    ("focus_ring_on_surface", NONTEXT, lambda c: c.focus_ring, lambda c: c.surface,
     ":focus-visible{outline:3px solid focus} — bitişik zemin: screen-inner/menü (surface)"),
    ("focus_ring_on_bg", NONTEXT, lambda c: c.focus_ring, lambda c: c.bg,
     ":focus-visible — bitişik zemin: bg zeminli kart içi (ui-card/opsiyon içeriği)"),
    ("selected_mark_on_bg", NONTEXT, lambda c: c.primary, lambda c: c.bg,
     ".opt.selected .opt-mark{background:primary} / .blank input:focus{border-color:primary} — bg üstünde"),
    ("progress_fill_vs_track", NONTEXT, lambda c: c.primary,
     lambda c: mix(c.border, c.surface, .40),
     ".progress-bar (primary) vs .progress track (mix(border 40%,transparent) surface üstünde)"),
    ("dot_current_on_surface", NONTEXT, lambda c: c.primary, lambda c: c.surface,
     ".dot.current{background:primary} — footer surface üstünde"),
    # --- inaktif/disabled birleşik renkler (durum 1; WCAG-muaf, ev-içi taban 2:1) ---
    ("disabled_btn_primary", INACTIVE,
     lambda c: over(c.primary_contrast, .55, c.surface),
     lambda c: over(c.primary, .55, c.surface),
     ".btn-primary:disabled{opacity:.55} — surface zemininde efektif birleşim "
     "(Faz 5: .45→.55; .45 hiçbir açık temada 2:1 tabanını tutturamıyordu)"),
    ("disabled_btn_ghost", INACTIVE,
     lambda c: over(c.text_muted, .55, c.surface), lambda c: c.surface,
     ".btn-ghost:disabled{opacity:.55} (bg şeffaf → yalnız mürekkep soluk; Faz 5: .4→.55)"),
    ("dim_choice", INACTIVE,
     lambda c: over(c.text, .50, c.surface), lambda c: over(c.bg, .50, c.surface),
     ".scen-choice.dim/.game-choice.dim{opacity:.5} — cevap sonrası pasif seçenek"),
    ("locked_choice", INACTIVE,
     lambda c: over(c.text, .45, c.surface), lambda c: over(c.bg, .45, c.surface),
     ".game-choice.locked{opacity:.45}"),
    ("locked_tree_item", INACTIVE,
     lambda c: over(c.text, .55, c.surface), lambda c: c.surface,
     'OUTLINE_CSS .mtree-btn[aria-disabled="true"]{opacity:.55}'),
]

# Faz 6b — grafik seri renkleri token'a taşındı (ColorPalette.chart_series → --chart-N);
# her seri rengi 1.4.11 metin-dışı tabanına bağlanır (grafik .screen-inner surface üstünde
# render edilir). Ölçüm raporu §4.1: eski sabit #2563eb premium koyu zeminde 3.19:1'di —
# artık her preset × mod için kapıda.
PAIRS += [
    (f"chart_series_{_ci}_on_surface", NONTEXT,
     (lambda c, i=_ci: c.chart_series[i]), lambda c: c.surface,
     f".chart-svg seri {_ci} dolgu/vuruş (var(--chart-{_ci})) — figure surface zemininde")
    for _ci in range(8)
]


# --------------------------------------------------------------------------- #
# Sevk edilen varyantlar: her preset + her preset×audience kombinasyonu
# --------------------------------------------------------------------------- #
def shipped_presets() -> list[str]:
    return sorted(
        str(p.relative_to(THEMES_DIR))[:-5]
        for p in THEMES_DIR.rglob("*.json")
        if not p.name.startswith("_") and "audience" not in p.parts
    )


def shipped_audiences() -> list[str]:
    aud = THEMES_DIR / "audience"
    if not aud.exists():
        return []
    return sorted(p.stem for p in aud.glob("*.json") if not p.name.startswith("_"))


def shipped_variants() -> list[tuple[str, str | None, str]]:
    """Faz 6b — matris MOD ekseniyle büyür: her preset(×audience) hem aydınlık hem koyu
    varyantıyla kapıya girer (koyu varyant = core.theme_dark.derive_dark_theme çıktısı;
    ayrı preset dosyası DEĞİL — yeni preset eklendiğinde koyu türevi otomatik matrise düşer)."""
    presets = shipped_presets()
    combos: list[tuple[str, str | None]] = [(p, None) for p in presets]
    for a in shipped_audiences():  # Faz 5'te boş; ilk paket sevkiyle otomatik matrise girer
        combos.extend((p, a) for p in presets)
    return [(p, a, m) for p, a in combos for m in ("light", "dark")]


def check_palette(c) -> list[tuple[str, float, float, str]]:
    """(çift, oran, eşik, css_kaynağı) — eşiğin ALTINDA kalanlar."""
    fails = []
    for pid, cat, fg, bg, ref in PAIRS:
        ratio = contrast(fg(c), bg(c))
        if ratio < THRESHOLD[cat] - 1e-9:
            fails.append((pid, round(ratio, 2), THRESHOLD[cat], ref))
    return fails


@pytest.mark.parametrize(
    "preset,audience,mode", shipped_variants(),
    ids=[f"{p}+{a}@{m}" if a else f"{p}@{m}" for p, a, m in shipped_variants()])
def test_aa_contrast_gate(preset, audience, mode):
    theme = server._load_theme(preset, audience=audience)
    if mode == "dark":
        from core.theme_dark import derive_dark_theme

        theme = derive_dark_theme(theme)
    fails = check_palette(theme.color)
    assert not fails, (
        f"tema '{preset}'"
        + (f" × audience '{audience}'" if audience else "")
        + f" × mod '{mode}'"
        + " AA kontrast kapısını GEÇEMEDİ (3.5 — erişilebilirlik zemindir):\n"
        + "\n".join(f"  {pid}: {r}:1 < {t}:1  [{ref}]" for pid, r, t, ref in fails)
    )


# --------------------------------------------------------------------------- #
# Negatif kontrol: kapı bilerek-bozuk temayı GERÇEKTEN yakalıyor (kapının kapı testi)
# --------------------------------------------------------------------------- #
def test_gate_catches_deliberately_broken_theme():
    from core.project import ColorPalette

    broken = ColorPalette(
        text="#9a9a9a", bg="#ffffff",          # ~2.6:1 — metin çifti düşmeli
        text_muted="#cccccc",                  # placeholder/yardımcı çifti düşmeli
        focus_ring="#eeeeee",                  # odak halkası 3:1 düşmeli
        primary="#ffe66d", primary_contrast="#ffffff",  # buton metni düşmeli
    )
    fails = {pid for pid, *_ in check_palette(broken)}
    for expected in ("text_on_bg", "muted_on_bg", "focus_ring_on_surface", "contrast_on_primary"):
        assert expected in fails, f"kapı '{expected}' ihlalini yakalayamadı — kapı bozuk"


def test_matrix_keeps_state_variant_coverage():
    """Durum varyantı kapsamı erimesin: matris disabled/placeholder/hover/selected/focus
    satırlarını içermek ZORUNDA (koordinatör direktifi — ölçek 3 tema × 6 paket iken
    elle yakalama imkânsız; kapsam Faz 5'te kurulmazsa hiç kurulmaz)."""
    ids = {pid for pid, *_ in PAIRS}
    assert {"disabled_btn_primary", "disabled_btn_ghost", "dim_choice"} <= ids       # disabled
    assert "muted_on_bg" in ids                                                      # placeholder
    assert {"contrast_on_primary_hover", "muted_on_dropover6_bg"} <= ids             # hover
    assert {"text_on_selected7_bg", "text_on_chosen8_bg"} <= ids                     # selected
    assert {"focus_ring_on_surface", "focus_ring_on_bg"} <= ids                      # focus 1.4.11
    # Faz 6b — grafik serisi kapsamı (8 seri × surface) matristen erimesin
    assert {f"chart_series_{i}_on_surface" for i in range(8)} <= ids
    cats = {cat for _, cat, *_ in PAIRS}
    assert cats == {TEXT, NONTEXT, INACTIVE}
    # Faz 6b — mod ekseni kapsamı: her varyant çifti aydınlık VE koyu modla kapıda
    modes = {m for *_, m in shipped_variants()}
    assert modes == {"light", "dark"}


# --------------------------------------------------------------------------- #
# Fontlar: CDN/harici referans YASAK — tema dosyaları + render çıktısı
# --------------------------------------------------------------------------- #
_CDN_MARKERS = ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit", "cdn.jsdelivr",
                "unpkg.com", "@import url(http")


def test_no_cdn_font_or_external_ref_in_theme_files():
    for p in THEMES_DIR.rglob("*.json"):
        raw = p.read_text(encoding="utf-8")
        assert "http://" not in raw and "https://" not in raw, (
            f"{p}: tema dosyasında harici URL — fontlar gömülü woff2 (custom_fonts asset) "
            "ya da sistem yığını olmalı, CDN yasak")


def test_no_cdn_font_in_rendered_output():
    from components.renderer import render_html
    from core.project import ContentSlide, Project, TitleSlide

    for name in shipped_presets():
        p = Project(
            id="proj_CDNGATE0000000000000000000", title="t",
            theme=server._load_theme(name),
            screens=[TitleSlide(id="t1", title="a"), ContentSlide(id="c1", title="b", body_html="<p>x</p>")],
        )
        html = render_html(p, mode="preview", runtime_js="/*STUB*/")
        low = html.lower()
        for marker in _CDN_MARKERS:
            assert marker not in low, f"tema '{name}' render çıktısında CDN izi: {marker}"
