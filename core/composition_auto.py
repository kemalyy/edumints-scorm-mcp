"""K1 — yazar kompozisyon vermediğinde deterministik desen seçimi + kurs ritmi (yoğunluk).
Saf mantık; yalnız spec'e bakar (LLM yok, ölçüm yok)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.composition import CompositionError, ResolvedComposition, resolve_spec
from core.project import CompositionSpec

K1_TYPES = frozenset({"title_slide", "content_slide"})
K2_TYPES = frozenset({"hotspot", "labeled_diagram", "image_compare", "data_chart", "video",
                      "lottie", "simulation"})
Q_TYPES = frozenset({"mcq", "true_false", "fill_blank", "drag_drop", "matching", "sorting",
                     "adaptive_practice"})
K4_TYPES = frozenset({"accordion", "tabs", "flashcards", "timeline", "summary",
                      "results_breakdown", "poll", "worked_example", "exploration"})
K5_TYPES = frozenset({"game", "decision_scenario", "escape_room", "term_match_race", "branching",
                      "embed_html"})
STIM_TYPES = Q_TYPES | {"poll", "exploration", "branching"}  # K3 `stimulus` alanını taşıyan tipler
COMPOSED_TYPES = K1_TYPES | K2_TYPES | Q_TYPES | K4_TYPES | K5_TYPES  # K5: 31 tipin tamamı
_K5_WIDE = frozenset({"game", "decision_scenario"})  # sahne geniş ister → başlık bandı üstte
_K4_WIDE = frozenset({"tabs", "flashcards"})  # koleksiyon geniş ister → başlık bandı üstte
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


def is_quiz_mode(s) -> bool:
    """Soru kipi: öğrenen görsele bakmadan ÖNCE ne arayacağını okumalı → mobilde support-önce."""
    t = s.type.value
    if t == "hotspot":
        return getattr(s, "mode", "quiz") != "explore"
    if t == "labeled_diagram":
        return getattr(s, "mode", "quiz") != "display"
    return t == "simulation"


def text_weight(s) -> int:
    """Metin ağırlığı = lead + istem/açıklama (+ video anlatımı). Etiket/şık metinleri hariç."""
    parts = [getattr(s, "lead", None) or "", getattr(s, "prompt_html", None) or ""]
    if s.type.value == "video":
        parts.append(getattr(s, "narration_text", None) or "")
    return sum(_words(p) for p in parts)


def _stimuli(s) -> list:
    if s.type.value == "adaptive_practice":
        return [it.stimulus for it in s.items if getattr(it, "stimulus", None)]
    st = getattr(s, "stimulus", None)
    return [st] if st else []


def has_stimulus(s) -> bool:
    return bool(_stimuli(s))


def stimulus_words(s) -> int:
    return max((_words(st.text_html) for st in _stimuli(s)), default=0)


def pref_for(project, s) -> str | None:
    """Kullanıcının üretim sırasında verdiği kurs düzeyi tercih (stack/split) bu ekrana uygulanıyorsa
    döndürür; yoksa None. K2 görsel tipleri `visual`, uyaranlı soru tipleri `question` alanını okur.
    Tercihle oluşan seriler monotonluk kırıcıdan ve lint uyarısından muaftır."""
    prefs = getattr(project, "composition_defaults", None)
    if prefs is None:
        return None
    t = s.type.value
    if t in K2_TYPES and prefs.visual not in (None, "auto"):
        return prefs.visual
    if t in STIM_TYPES and has_stimulus(s) and prefs.question not in (None, "auto"):
        return prefs.question
    return None


def k4_words(s) -> int:
    """K4 — tipin kendi giriş metni (istem / giriş / gövde) kelime sayısı."""
    return _words(" ".join(getattr(s, f, None) or "" for f in ("prompt_html", "intro_html",
                                                                 "body_html")))


def auto_preset(s, prev_preset: str | None, prev_mirror: bool) -> tuple[str, bool]:
    t = s.type.value
    if t in Q_TYPES or (t in STIM_TYPES and has_stimulus(s)):
        # K3 — uyaransız soru → soru sütunu; uyaranlı (K4: poll/exploration da) → vaka odakta
        if not has_stimulus(s):
            return "question-column", False
        sts = _stimuli(s)
        if stimulus_words(s) > 40 or any(st.asset_id and st.text_html for st in sts):
            mirror = (not prev_mirror) if prev_preset == "split-thirds" else False
            return "split-thirds", mirror
        return "visual-stack", False
    if t in K4_TYPES:  # K4 — içerik etkileşimleri
        if t == "summary":
            return "centered", False
        if t == "results_breakdown":
            return "split-thirds", False
        if getattr(s, "lead", None) or k4_words(s) > 30:
            mirror = (not prev_mirror) if prev_preset == "split-thirds" else False
            return "split-thirds", mirror
        return ("visual-stack" if t in _K4_WIDE else "question-column"), False
    if t in K5_TYPES:  # K5 — oyun/senaryo/gömülü
        if t == "embed_html":  # iframe her zaman geniş
            return "visual-stack", False
        if getattr(s, "lead", None) or k4_words(s) > 30:
            mirror = (not prev_mirror) if prev_preset == "split-thirds" else False
            return "split-thirds", mirror
        return ("visual-stack" if t in _K5_WIDE else "question-column"), False
    if s.type.value in K2_TYPES:  # K2 — varsayılan C: lead/uzun metin → split, aksi → stack
        if getattr(s, "lead", None) or text_weight(s) > 30:
            mirror = (not prev_mirror) if prev_preset == "split-thirds" else False
            return "split-thirds", mirror
        return "visual-stack", False
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
            if t in Q_TYPES or t in K4_TYPES or t in K5_TYPES:  # uyaranlı: vaka önce; aksi başlık
                # adaptive: vaka zaten her öğenin İÇİNDE istemden önce; odak tüm alıştırma olduğundan
                # focal-first başlık/yönergeyi Kontrol butonunun arkasına iterdi (WCAG 1.3.2)
                order = ("focal-first" if has_stimulus(s) and t != "adaptive_practice"
                         else "support-first")
            else:
                order = "support-first" if is_quiz_mode(s) else "focal-first"
            if explicit is not None:
                r = resolve_spec(explicit, t, intensity=_explicit_intensity(s) or inten[i],
                                 dom_order=order)
            elif t in COMPOSED_TYPES:
                preset, mirror = auto_preset(s, prev_preset, prev_mirror)
                pref = pref_for(project, s)
                pref_driven = pref is not None
                if pref_driven:
                    # kullanıcının cevabı (üretim sırasında soruldu) otomatik kuralı ezer ve
                    # monotonluk kırıcıdan MUAFTIR: "üstte" diyen kullanıcı her ekranda üstte görür.
                    if pref == "stack":
                        preset, mirror = "visual-stack", False
                    else:
                        preset = "split-thirds"
                        mirror = (not prev_mirror) if prev_preset == "split-thirds" else False
                # tek sütun dizisi tutarlı kalmalı (question-column'un alternatifi yok); summary
                # yalnız centered'a uyar
                steady = preset == "question-column" or t == "summary"
                if not pref_driven and not steady and preset == prev_preset and run >= 3:
                    alt = {"title_slide": "statement"}.get(t, "centered")
                    if t in K2_TYPES or t in STIM_TYPES or t in K4_TYPES or t in K5_TYPES:
                        alt = "split-thirds" if preset == "visual-stack" else "visual-stack"
                    preset, mirror = (alt if preset != alt else "f-flow"), False
                r = resolve_spec(CompositionSpec(preset=preset, mirror=mirror or None), t,
                                 intensity=inten[i], auto=True, dom_order=order)
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
