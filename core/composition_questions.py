"""K2/K3 — üretim sırasında kullanıcıya sorulacak kompozisyon soruları (deterministik).

Araç yanıtında (`lint_course` / `preview`) döner; Claude kullanıcıya sorar ve `apply` ile
uygular. Şema MRTR `inputRequests`'e eşlenebilecek biçimdedir (public #97): `id` ↔ istek
anahtarı, `options` ↔ enum, `default` ↔ varsayılan, `apply` ↔ sunucunun cevabı uygulama yolu.
Klasik elicitation kullanılmaz: sunucu json_response=True (sunucudan istemciye istek yok).
Metinler kursun diline (project.language) çevrilir."""
from __future__ import annotations

from components import i18n
from core.composition_auto import (
    K2_TYPES,
    STIM_TYPES,
    has_stimulus,
    resolve_project_safe,
    stimulus_words,
    text_weight,
)

BAND = (23, 37)    # K2: varsayılan C eşiğinin (30 kelime) ±%25'i — kuralın sınırda kaldığı aralık
Q_BAND = (30, 50)  # K3: uyaran eşiğinin (40 kelime) ±%25'i
MAX_SCREEN_QUESTIONS = 3  # K2 + K3 ekran soruları TOPLAMI


def _t(lang, key: str, **kw) -> str:
    return i18n.fmt(i18n.t(lang, key), **kw)


def _course_question(lang, qid: str, field: str, prefix: str) -> dict:
    return {
        "id": qid, "scope": "course",
        "question": _t(lang, "cq_visual_q" if field == "visual" else "cq_question_q"),
        "options": [{"value": v, "label": _t(lang, f"{prefix}{v}"),
                     "description": _t(lang, f"{prefix}{v}_d")}
                    for v in ("stack", "split")]
        + [{"value": "auto", "label": _t(lang, "cq_opt_auto"),
            "description": _t(lang, "cq_opt_auto_d")}],
        "default": "auto",
        "apply": {"tool": "set_composition", "args": {"mode": "auto", field: "$value"}},
    }


def _open(pref) -> bool:
    """Ekran düzeyinde sorulabilir mi: kurs tercihi verilmemiş ya da 'auto'."""
    return pref in (None, "auto")


def build_questions(project) -> list[dict]:
    if project.composition != "auto":
        return []
    lang = project.language
    prefs = project.composition_defaults
    visual = prefs.visual if prefs is not None else None
    question = prefs.question if prefs is not None else None
    k2 = [s for s in project.screens if s.type.value in K2_TYPES]
    qs = [s for s in project.screens if s.type.value in STIM_TYPES and has_stimulus(s)]
    out: list[dict] = []
    if visual is None and len(k2) >= 3:
        out.append(_course_question(lang, "visual_layout", "visual", "cq_opt_"))
    if question is None and len(qs) >= 3:
        out.append(_course_question(lang, "question_layout", "question", "cq_q_opt_"))
    comps, _ = resolve_project_safe(project)
    asked = 0
    for s, c in zip(project.screens, comps):
        if asked >= MAX_SCREEN_QUESTIONS:
            break
        if getattr(s, "composition", None) is not None or c is None:
            continue
        t = s.type.value
        if t in K2_TYPES and _open(visual) and BAND[0] <= text_weight(s) <= BAND[1]:
            key = "cq_screen_visual_q"
        elif (t in STIM_TYPES and t != "adaptive_practice" and has_stimulus(s) and _open(question)
              and Q_BAND[0] <= stimulus_words(s) <= Q_BAND[1]):
            key = "cq_screen_question_q"
        else:
            continue
        out.append({
            "id": f"screen:{s.id}", "scope": "screen", "screen_id": s.id,
            "question": _t(lang, key, title=s.title),
            "options": [{"value": "visual-stack", "label": _t(lang, "cq_opt_above")},
                        {"value": "split-thirds", "label": _t(lang, "cq_opt_beside")}],
            "default": c.preset,
            "apply": {"tool": "set_screen_composition",
                      "args": {"screen_id": s.id, "composition": "$value"}},
        })
        asked += 1
    return out
