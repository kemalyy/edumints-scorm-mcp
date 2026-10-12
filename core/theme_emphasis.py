"""K1 — tema vurgu kademelerinin çözümü. Açık `emphasis` bloğu varsa o; yoksa paletten türetilir
(eski 18 tema kırılmaz). Koyu modda açık blok YOK SAYILIR ve kademeler koyu paletten türetilir:
açık-zemin için seçilmiş renkler koyu zeminde AA'yı geçemez. Saf fonksiyon."""
from __future__ import annotations

from core.project import Emphasis, EmphasisLevel, ThemeTokens
from core.theme_dark import _contrast, _mix, _to_hex

_AA = 4.5


def _tint(ink: str, surface: str) -> str:
    return _to_hex(_mix(ink, surface, 0.15))


def _e3_pair(c, dark: bool) -> tuple[str, str]:
    """Türetilmiş E3 (kicker, <mark>): accent dekoratif olabilir — AA'yı (yüzeyde VE kendi
    vurgu zemininde) geçen ilk aday kullanılır; hiçbiri geçmezse metin rengi + primary zemini."""
    for ink in ([c.primary] if dark else [c.accent, c.primary]):
        bg = _tint(ink, c.surface)
        if _contrast(ink, c.surface) >= _AA and _contrast(ink, bg) >= _AA:
            return ink, bg
    return c.text, _tint(c.primary, c.surface)


def resolve_emphasis(theme: ThemeTokens, *, dark: bool = False) -> Emphasis:
    if theme.emphasis is not None and not dark:
        return theme.emphasis
    c, ty = theme.color, theme.typography
    e3_ink, e3_bg = _e3_pair(c, dark)
    return Emphasis(
        e1=EmphasisLevel(color=c.primary, size="h3", weight=ty.weight_heading),
        e2=EmphasisLevel(color=c.text, size="h2", weight=ty.weight_heading),
        # koyu modda accent dönüştürülmez (theme_dark yalnız primary'yi AA'ya taşır) → aday primary
        e3=EmphasisLevel(color=e3_ink, size="sm", weight=ty.weight_strong),
        e3_bg=e3_bg,
        e4=EmphasisLevel(color=c.text, size="base", weight=ty.weight_body),
        e5=EmphasisLevel(color=c.text_muted, size="sm", weight=ty.weight_body),
    )
