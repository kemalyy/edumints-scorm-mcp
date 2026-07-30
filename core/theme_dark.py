"""core/theme_dark.py — Faz 6b: karanlık mod türetimi (Faz 5 token katmanının kozmetik ekseni).

TASARIM KARARI (plan 7.3 — mod, preset'lere ORTOGONAL bir eksendir):
karanlık mod ayrı bir preset DEĞİLDİR; ÇÖZÜLMÜŞ temanın (preset + audience + kurs custom,
bkz. server._load_theme katman sırası) üstüne render anında compose edilen overlay'dir:

    themes/_dark-overlay.json  →  nötr zeminler + durum renkleri + koyu grafik serisi
    en-yakın-uyumlu oturtma    →  preset KİMLİK renkleri (primary/hover/focus) korunur,
                                  yalnız AA'yı tutturacak ASGARİ beyaz karışımına çekilir.

Neden overlay + oturtma (18 ayrı koyu preset dosyası değil):
- kitle (audience) katmanı ve kurs custom'ı karanlıkta da otomatik görünür (katman sırası
  bozulmaz — overlay çözülmüş temanın üstüne gelir);
- preset kimliği (tipografi, radius, motion, marka primary tonu) korunur;
- yeni preset eklendiğinde koyu varyantı otomatik doğar ve AA matrisine otomatik girer.

Nötr/durum değerleri themes/dark.json preset'iyle aynı ailedendir (o palet AA matrisinde
kanıtlı); grafik serisi rapor §4.1 uyarınca koyu zeminde ≥3:1 kontrastlı setle değişir.
Oturtma matematiği tests/test_theme_contrast.py ile AYNI WCAG formülleridir (gamma-uzayı
color-mix dahil) — kapı ile üretici aynı cetveli kullanır.

Bilinçli kapsam: secondary/accent oturtulmaz — renderer bunları metin×zemin çifti olarak
kullanmaz (matris başlığındaki kapsam-dışı notuyla senkron); kullanım eklendiği gün buraya
ve matrise birlikte eklenmek zorunda. Demo SVG varlıkları tek-şemadır ve tema tersine
dönünce uyum sağlamaz (ölçüm raporu §4.1'de bilinçli sınırlama olarak kayıtlı).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .project import ThemeTokens

_OVERLAY_PATH = Path(__file__).resolve().parent.parent / "themes" / "_dark-overlay.json"

# en-yakın-uyum adımı: %2 beyaz karışımı × ≤50 adım (0 → değişmedi, 50 → saf beyaz)
_FIT_STEP = 0.02


@lru_cache(maxsize=1)
def _overlay_tokens() -> ThemeTokens:
    raw = json.loads(_OVERLAY_PATH.read_text(encoding="utf-8"))
    raw.pop("extends", None)  # overlay bir tema değildir: miras zinciri kuramaz
    raw.pop("name", None)     # mod ≠ kimlik (3.4) — ad çözülmüş temadan gelir
    return ThemeTokens.model_validate(raw)


def deep_merge_theme(base: ThemeTokens, override: ThemeTokens) -> ThemeTokens:
    """Yalnız override'da AÇIKÇA verilmiş alanları base üstüne uygula (derin merge).
    server._deep_merge_theme buraya taşındı (Faz 6b) — tema katmanlama TEK yerde yaşasın;
    server tarafı geriye-uyum için bu fonksiyonu delege eder."""
    def merge(b: dict, o_model) -> dict:
        out = dict(b)
        for name in o_model.model_fields_set:
            val = getattr(o_model, name)
            if hasattr(val, "model_fields_set"):
                out[name] = merge(out.get(name, {}), val)
            else:
                out[name] = val if not hasattr(val, "model_dump") else val.model_dump()
        return out
    merged = merge(base.model_dump(), override)
    return ThemeTokens.model_validate(merged)


# --------------------------------------------------------------------------- #
# WCAG renk matematiği — tests/test_theme_contrast.py ile birebir aynı formüller
# --------------------------------------------------------------------------- #
def _hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _mix(a: str | tuple, b: str | tuple, pa: float) -> tuple[float, float, float]:
    """color-mix(in srgb, A pa%, B) — gamma-uzayı sabit katsayılı karışım (CSS Color 5)."""
    ra = a if isinstance(a, tuple) else _hex_rgb(a)
    rb = b if isinstance(b, tuple) else _hex_rgb(b)
    return tuple(ra[i] * pa + rb[i] * (1 - pa) for i in range(3))  # type: ignore[return-value]


def _to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(c: str | tuple) -> float:
    r, g, b = c if isinstance(c, tuple) else _hex_rgb(c)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(a: str | tuple, b: str | tuple) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _fit_ink(ink: str, ok) -> str:
    """EN YAKIN uyumlu mürekkep: %2'lik adımlarla beyaza karıştır, İLK geçen adayı döndür
    (adım 0 = orijinal → zaten geçiyorsa DEĞİŞMEZ). Saf beyaz da geçmezse beyaz döner —
    kalan ihlali AA matris kapısı raporlar (sessiz yutma yok)."""
    for k in range(0, 51):
        cand = _to_hex(_mix("#ffffff", ink, k * _FIT_STEP))
        if ok(cand):
            return cand
    return "#ffffff"


# --------------------------------------------------------------------------- #
# Türetim
# --------------------------------------------------------------------------- #
def derive_dark_theme(theme: ThemeTokens) -> ThemeTokens:
    """Çözülmüş temanın koyu varyantı. Deterministik ve saf (dosya okuma lru_cache'li).

    1) _dark-overlay compose edilir (nötr zeminler/durumlar/koyu grafik serisi/elevation);
    2) preset kimlik mürekkepleri (primary, primary_hover, focus_ring) koyu zeminlere
       en-yakın-uyumla oturtulur. Denetlenen çiftler AA matrisinin primary'yi mürekkep YA DA
       zemin-bileşeni olarak kullandığı satırlarının birebir aynasıdır."""
    dark = deep_merge_theme(theme, _overlay_tokens())
    c = dark.color
    surface, bg, surface_alt = c.surface, c.bg, c.surface_alt

    def primary_ok(p: str) -> bool:
        # primary MÜREKKEP: 4.5 (TEXT) — düz zeminler + tint zeminleri (tint p'ye bağlı)
        text_grounds = [
            surface, bg,
            _mix(p, surface, .04), _mix(p, surface, .06), _mix(p, surface, .08),
            _mix(p, surface_alt, .10),
        ]
        if any(_contrast(p, g) < 4.5 for g in text_grounds):
            return False
        # primary METİN-DIŞI gösterge: 3.0 (1.4.11) — ilerleme dolgusu vs raylı zemin
        if _contrast(p, _mix(c.border, surface, .40)) < 3.0:
            return False
        # primary ZEMİN-BİLEŞENİ: seçili/hover tintleri üstünde gövde/muted metin (4.5)
        if _contrast(c.text, _mix(p, bg, .07)) < 4.5:
            return False
        if _contrast(c.text, _mix(p, bg, .08)) < 4.5:
            return False
        if _contrast(c.text_muted, _mix(p, bg, .06)) < 4.5:
            return False
        # primary üstü buton metni (koyu mürekkep) + disabled birleşimi (INACTIVE 2.0)
        if _contrast(c.primary_contrast, p) < 4.5:
            return False
        if _contrast(_mix(c.primary_contrast, surface, .55), _mix(p, surface, .55)) < 2.0:
            return False
        return True

    c.primary = _fit_ink(c.primary, primary_ok)

    # hover: koyu UI'da bir tık AÇIK ton; buton metni (primary_contrast) 4.5'i tutana dek açılır
    hover = _to_hex(_mix("#ffffff", c.primary, .12))
    while _contrast(c.primary_contrast, hover) < 4.5 and hover != "#ffffff":
        hover = _to_hex(_mix("#ffffff", hover, .10))
    c.primary_hover = hover

    # odak halkası: 1.4.11 metin-dışı ≥3:1 — bitişik zeminler surface + bg
    c.focus_ring = _fit_ink(
        c.focus_ring,
        lambda f: _contrast(f, surface) >= 3.0 and _contrast(f, bg) >= 3.0,
    )
    return dark
