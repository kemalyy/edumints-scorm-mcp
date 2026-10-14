"""K1 — kompozisyon çözücü (saf mantık). Katalog (compositions/*.json) + ekran parametreleri →
ResolvedComposition. Izgara hücreleri `c{sütun}r{satır}` (1 tabanlı); alan "c1r1-c2r3"
(her iki uç DAHİL) → CSS grid-area (row_start, col_start, row_end, col_end; bitiş DIŞLAYICI)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.project import CompositionSpec

CATALOG_DIR = Path(__file__).resolve().parent.parent / "compositions"
SLOTS = ("support", "focal", "aux", "steps")
ROWS = 3
_RANGE = re.compile(r"^c([1-9])r([1-9])-c([1-9])r([1-9])$")
_CELL = re.compile(r"^r([1-9])c([1-9])$")
_RATIO = re.compile(r"^([1-9]):([1-9])$")


class CompositionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedComposition:
    preset: str | None
    cols: str
    rows: str
    areas: dict[str, tuple[int, int, int, int]]
    focal: str
    focal_cell: str | None
    flow: str
    whitespace: str
    intensity: str
    mirror: bool
    symmetry: str
    auto: bool
    dom_order: str = "focal-first"  # K2 — soru kipinde "support-first"
    # v1.8.1 — karar izi (#173) ve geçersiz ezmede yedek (#170)
    source: str = "auto"      # auto | rhythm | course:visual=… | course:question=… | screen
    reason: str = ""          # kısa gerekçe (ör. "stimulus_words=46>40")
    error: str | None = None  # ekranın açık kompozisyonu geçersizse hata kodu (desen = yedek)


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(CATALOG_DIR.glob("*.json")):
        if p.stem.startswith("_"):
            continue
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _grid(grid: str) -> tuple[int, str]:
    if grid == "thirds":
        return 3, "1fr 1fr 1fr"
    if grid == "halves":
        return 2, "1fr 1fr"
    m = _RATIO.match(grid or "")
    if m:
        return 2, f"{m.group(1)}fr {m.group(2)}fr"
    raise CompositionError("composition_unknown", f"Geçersiz ızgara: {grid!r}")


def _area(spec: str, ncols: int) -> tuple[int, int, int, int]:
    m = _RANGE.match(spec or "")
    if not m:
        raise CompositionError("composition_unknown", f"Geçersiz alan: {spec!r}")
    c1, r1, c2, r2 = (int(g) for g in m.groups())
    if not (1 <= c1 <= c2 <= ncols and 1 <= r1 <= r2 <= ROWS):
        raise CompositionError("composition_unknown",
                               f"Alan ızgara dışında ya da ters: {spec!r} ({ncols}×{ROWS})")
    return (r1, c1, r2 + 1, c2 + 1)


def _mirror(a: tuple[int, int, int, int], ncols: int) -> tuple[int, int, int, int]:
    rs, cs, re_, ce = a
    return (rs, ncols + 2 - ce, re_, ncols + 2 - cs)


def resolve_spec(spec: str | CompositionSpec, screen_type: str, *,
                 intensity: str = "normal", auto: bool = False,
                 dom_order: str = "focal-first") -> ResolvedComposition:
    if isinstance(spec, str):
        spec = CompositionSpec(preset=spec)
    catalog = load_catalog()
    base: dict = {}
    if spec.preset is not None:
        if spec.preset not in catalog:
            raise CompositionError("composition_unknown", f"Bilinmeyen desen: {spec.preset!r}")
        base = catalog[spec.preset]
        if screen_type not in base.get("applies_to", []):
            # v1.8.1 (#171) — desen VAR ama bu tipe uymuyor: ayrı kod + uyan desenler önerilir
            fits = sorted(n for n, d in catalog.items() if screen_type in d.get("applies_to", []))
            raise CompositionError(
                "composition_not_applicable",
                f"'{spec.preset}' deseni {screen_type} tipine uygulanamaz — bu tipe uyan desenler: "
                f"{', '.join(fits) or '(yok)'} (eski kod: composition_unknown)")
    elif not any(screen_type in d.get("applies_to", []) for d in catalog.values()):
        # serbest mod: kataloğun HERHANGİ bir desenine uygulanabilen her tip serbest ızgara alır
        raise CompositionError("composition_unknown",
                               f"{screen_type} tipi henüz kompozisyon desteklemiyor")
    ncols, cols = _grid(spec.grid or base.get("grid", "thirds"))
    raw_areas = spec.areas if spec.areas is not None else base.get(
        "areas", {"support": "c1r1-c3r3"})
    areas: dict[str, tuple[int, int, int, int]] = {}
    for slot, rng in raw_areas.items():
        if slot not in SLOTS:
            raise CompositionError("composition_unknown", f"Bilinmeyen yuva: {slot!r}")
        areas[slot] = _area(rng, ncols)
    mirror = bool(spec.mirror)
    if mirror:
        areas = {k: _mirror(v, ncols) for k, v in areas.items()}
    focal_raw = spec.focal or base.get("focal", "support")
    focal_cell = None
    if focal_raw in SLOTS:
        if focal_raw not in areas:
            raise CompositionError("focal_area_empty",
                                   f"Odak yuvası '{focal_raw}' kompozisyonda tanımlı değil")
        focal = focal_raw
    else:
        m = _CELL.match(focal_raw)
        if not m:
            raise CompositionError("composition_unknown", f"Geçersiz odak: {focal_raw!r}")
        r, c = int(m.group(1)), int(m.group(2))
        if c > ncols or r > ROWS:
            raise CompositionError("composition_unknown", f"Odak hücresi dışarıda: {focal_raw}")
        # Yazarın AÇIK odak hücresi ekranda GÖRÜNEN koordinattır (aynalanmaz); yalnız desenin
        # kendi varsayılan odağı yerleşimle birlikte aynalanır.
        if mirror and not spec.focal:
            c = ncols + 1 - c
        focal_cell = f"r{r}c{c}"
        focal = next((s for s, (rs, cs, re_, ce) in areas.items()
                      if rs <= r < re_ and cs <= c < ce), "__background__")
    return ResolvedComposition(
        preset=spec.preset, cols=cols, rows="1fr 1fr 1fr", areas=areas, focal=focal,
        focal_cell=focal_cell, flow=spec.flow or base.get("flow", "center"),
        whitespace=spec.whitespace or base.get("whitespace", "normal"),
        intensity=spec.intensity or intensity, mirror=mirror,
        symmetry=base.get("symmetry", "asymmetric" if spec.areas else "symmetric"), auto=auto,
        dom_order=dom_order,
    )
