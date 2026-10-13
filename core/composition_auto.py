"""K1 — yazar kompozisyon vermediğinde deterministik desen seçimi + kurs ritmi (yoğunluk).
Saf mantık; yalnız spec'e bakar (LLM yok, ölçüm yok)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.composition import CompositionError, ResolvedComposition, resolve_spec
from core.project import CompositionSpec

K1_TYPES = frozenset({"title_slide", "content_slide"})
_TAG = re.compile(r"<[^>]+>")
_LI = re.compile(r"<li[\s>]", re.I)


@dataclass(frozen=True)
class Signals:
    media: int
    words: int
    lis: int
    blocks: int
    has_lead: bool
    has_bg: bool


def _words(html: str | None) -> int:
    return len(_TAG.sub(" ", html or "").split())


def signals(s) -> Signals:
    blocks = getattr(s, "blocks", None) or []
    if blocks:
        media = sum(1 for b in blocks if b.asset_id)
        html = " ".join(b.html or "" for b in blocks)
    else:
        media = 1 if getattr(s, "media_asset_id", None) else 0
        html = getattr(s, "body_html", None) or ""
    return Signals(media=media, words=_words(html), lis=len(_LI.findall(html)),
                   blocks=len(blocks), has_lead=bool(getattr(s, "lead", None)),
                   has_bg=bool(getattr(s, "background_asset_id", None)))


def auto_preset(s, prev_preset: str | None, prev_mirror: bool) -> tuple[str, bool]:
    if s.type.value == "title_slide":
        return ("hero-focal" if signals(s).has_bg else "centered"), False
    sg = signals(s)
    if sg.media == 0 and sg.has_lead and sg.words <= 25:
        return "statement", False
    if sg.media == 2 and sg.blocks <= 3:  # 4 bloklu iki görselli dizi z-flow'a düşer
        return "split-halves", False
    if 3 <= sg.blocks <= 4 and sg.media >= 2:
        return "z-flow", False
    if sg.media >= 2:  # bölünmüş düzene sığmayan çok görselli dizi: sıra korunarak tek sütun
        return "f-flow", False
    if sg.media >= 1:
        mirror = (not prev_mirror) if prev_preset == "split-thirds" else False
        return "split-thirds", mirror
    if sg.lis >= 4 or sg.words > 120:
        return "f-flow", False
    return "centered", False


def intensities(project) -> list[str]:
    n = len(project.screens)
    unit_ids = {o.id for o in project.outline if getattr(o, "kind", None) == "unit"}
    seen_units: set[str] = set()
    out: list[str] = []
    for i, s in enumerate(project.screens):
        nid = getattr(s, "node_id", None)
        opener = nid in unit_ids and nid not in seen_units
        if nid in unit_ids:
            seen_units.add(nid)
        if i == 0 or i == n - 1 or opener:
            out.append("high")
        elif s.type.value in K1_TYPES:
            out.append("calm")
        else:
            out.append("normal")
    for i in range(1, n - 1):  # ≥3 high zinciri: ortadakini indir
        if out[i - 1] == out[i] == out[i + 1] == "high":
            out[i] = "normal"
    return out


def _explicit_intensity(s) -> str | None:
    c = getattr(s, "composition", None)
    return getattr(c, "intensity", None) if c is not None and not isinstance(c, str) else None


def _resolve(project, collect: list | None) -> list[ResolvedComposition | None]:
    if project.composition != "auto":
        return [None] * len(project.screens)
    inten = intensities(project)
    out: list[ResolvedComposition | None] = []
    prev_preset, prev_mirror, run = None, False, 0
    for i, s in enumerate(project.screens):
        t = s.type.value
        explicit = getattr(s, "composition", None)
        try:
            if explicit is not None:
                r = resolve_spec(explicit, t, intensity=_explicit_intensity(s) or inten[i])
            elif t in K1_TYPES:
                preset, mirror = auto_preset(s, prev_preset, prev_mirror)
                if preset == prev_preset and run >= 3:  # monotonluk kırıcı (> 3 tekrar yok)
                    alt = {"title_slide": "statement"}.get(t, "centered")
                    preset, mirror = (alt if preset != alt else "f-flow"), False
                r = resolve_spec(CompositionSpec(preset=preset, mirror=mirror or None), t,
                                 intensity=inten[i], auto=True)
            else:
                r = None
        except CompositionError as e:
            if collect is None:
                raise
            collect.append((i, e))
            r = None
        out.append(r)
        if r is not None:
            run = run + 1 if r.preset == prev_preset else 1
            prev_preset, prev_mirror = r.preset, r.mirror
    return out


def resolve_project(project) -> list[ResolvedComposition | None]:
    return _resolve(project, None)


def resolve_project_safe(project):
    errs: list[tuple[int, CompositionError]] = []
    return _resolve(project, errs), errs


def summary(project) -> list[dict]:
    """Şeffaflık — çözülmüş kompozisyonların özeti (lint_course / preview yanıtında döner)."""
    comps, _ = resolve_project_safe(project)
    return [{"screen_id": s.id, "preset": c.preset, "focal": c.focal,
             "intensity": c.intensity, "auto": c.auto}
            for s, c in zip(project.screens, comps) if c is not None]
