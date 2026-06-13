"""core/antislop.py — W6 oyun anti-slop kalite kapısı.

Kompozisyonel oyun (`game`) + adaptif pratik (`adaptive_practice`) spec'lerini ARAŞTIRMA-TEMELLİ
deterministik kurallarla denetler. SUNUCUDA LLM YOK — heuristikler şeffaf, test edilir, üretilebilir.

Araştırma temeli (her kural bir ilkeye dayanır):
- İçsel-bütünleşme (Habgood): mekanik öğrenme hedefini taşımalı, süs olmamalı ("çikolata kaplı brokoli").
- Anlamlı seçim (öz-belirleme): dallar sonuç bakımından farklı olmalı — sahte/illüzyon seçim yasak.
- Scaffolding dengesi (Shute): bedava ipucu öğrenmeyi baltalar (maliyet ilkesi).
- Adaptif anlam (akış/ZPD): zorluk yelpazesi olmalı; tek zorluk → adaptiflik anlamsız.
- a11y sözleşmesi (docs/GAME-A11Y.md): süre uzat/kapat (zaten validator'da).

İki şiddet:
- ERROR: yapısal bug (ulaşılamaz düğüm, sahte seçim). validate_project'e bağlanır → build'i bloklar.
- WARN: pedagojik koku (süs skor, bedava ipucu, dar zorluk, gerekçesiz ceza). `lint_course` aracıyla danışsal.

Mevcut geçerli kurslar bozulmaz: ERROR'lar yalnız NET yapısal bug'lardır; pedagojik kokular WARN kalır.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .project import (
    AdaptivePracticeScreen,
    GameScreen,
    Project,
)

_SCORE_DOS = {"score.correct", "score.wrong", "score.add"}
_PENALTY_DOS = {"lives.lose", "score.wrong"}


@dataclass
class LintIssue:
    severity: str  # "error" | "warn"
    code: str
    message: str
    path: str


def lint_course(project: Project) -> list[LintIssue]:
    """Kurstaki tüm game/adaptive_practice ekranlarını denetle. ERROR + WARN karışık döner."""
    issues: list[LintIssue] = []
    for i, s in enumerate(project.screens):
        path = f"screens[{i}]"
        if isinstance(s, GameScreen):
            issues += _lint_game(s, path)
        elif isinstance(s, AdaptivePracticeScreen):
            issues += _lint_adaptive(s, path)
    return issues


def lint_errors(project: Project) -> list[LintIssue]:
    """Yalnız ERROR şiddeti (validate_project bunları sert hata olarak ekler)."""
    return [i for i in lint_course(project) if i.severity == "error"]


# --- game --------------------------------------------------------------------
def _lint_game(s: GameScreen, path: str) -> list[LintIssue]:
    out: list[LintIssue] = []
    node_ids = [n.id for n in s.nodes]
    start = s.start_node_id or (node_ids[0] if node_ids else None)

    # ERROR: ulaşılamazlık (start'tan choice.to ile gezilemeyen düğüm = ölü içerik)
    reach: set[str] = set()
    if start is not None:
        stack = [start]
        by_id = {n.id: n for n in s.nodes}
        while stack:
            nid = stack.pop()
            if nid in reach or nid not in by_id:
                continue
            reach.add(nid)
            for c in by_id[nid].choices:
                if c.to:
                    stack.append(c.to)
    for n in s.nodes:
        if n.id not in reach:
            out.append(LintIssue("error", "unreachable_node",
                                 f"Ulaşılamaz oyun düğümü (start'tan hiçbir seçimle erişilemiyor): {n.id}",
                                 f"{path}.nodes[{n.id}]"))

    # ERROR: sahte seçim (bir düğümde ≥2 seçim ama hepsi AYNI sonuç → illüzyon seçim)
    for n in s.nodes:
        if len(n.choices) >= 2:
            sigs = {_choice_sig(c) for c in n.choices}
            if len(sigs) == 1:
                out.append(LintIssue("error", "fake_choice",
                                     f"Sahte seçim: '{n.id}' düğümündeki tüm seçimler aynı sonuca götürüyor "
                                     "(hedef + etki özdeş) — anlamlı karar yok",
                                     f"{path}.nodes[{n.id}].choices"))

    # WARN: süs skor (skor mekaniği var ama hiçbir kural/seçim onu değiştirmiyor)
    if s.mechanics.score is not None and not _any_score_action(s):
        out.append(LintIssue("warn", "decorative_score",
                             "Skor mekaniği tanımlı ama hiçbir karara/kurala bağlı değil (süs — içsel-bütünleşme yok)",
                             f"{path}.mechanics.score"))

    # WARN: bedava ipucu (ipucu + skor var ama tüm ipuçları maliyetsiz → scaffolding dengesizliği)
    if s.mechanics.hints is not None and s.mechanics.score is not None:
        if all((h.cost or 0) == 0 for h in s.mechanics.hints.hints):
            out.append(LintIssue("warn", "free_hints",
                                 "Tüm ipuçları bedava (maliyet 0) + skor var: bedava ipucu öğrenmeyi baltalar "
                                 "(en az bir ipucuna puan/zaman maliyeti ver)",
                                 f"{path}.mechanics.hints"))

    # WARN: gerekçesiz ceza (can/skor kaybettiren seçimde feedback yok → 'neden' öğretilmiyor)
    for n in s.nodes:
        for c in n.choices:
            if any(a.do in _PENALTY_DOS for a in c.on_choose) and not (c.feedback_html or "").strip():
                out.append(LintIssue("warn", "penalty_without_rationale",
                                     f"Olumsuz sonuçlu seçim '{n.id}/{c.id}' gerekçe (feedback_html) içermiyor "
                                     "— hata neden yanlış, öğrenci görmeli",
                                     f"{path}.nodes[{n.id}].choices[{c.id}]"))
    return out


def _choice_sig(c) -> str:
    """Bir seçimin SONUÇ imzası: hedef + sıralı aksiyonlar. Aynı imza = aynı sonuç (sahte seçim)."""
    acts = [a.model_dump(exclude_none=True) for a in c.on_choose]
    return json.dumps({"to": c.to, "on": acts}, sort_keys=True, ensure_ascii=False)


def _any_score_action(s: GameScreen) -> bool:
    for r in s.rules:
        if any(a.do in _SCORE_DOS for a in r.then):
            return True
    for n in s.nodes:
        for c in n.choices:
            if any(a.do in _SCORE_DOS for a in c.on_choose):
                return True
    return False


# --- adaptive_practice -------------------------------------------------------
def _lint_adaptive(s: AdaptivePracticeScreen, path: str) -> list[LintIssue]:
    out: list[LintIssue] = []
    diffs = [it.difficulty for it in s.items]

    # WARN: dar zorluk (tüm öğeler ~aynı zorluk → adaptif seçim anlamsız, hep aynı öğe seçilir)
    if len(diffs) >= 2 and (max(diffs) - min(diffs)) < 0.5:
        out.append(LintIssue("warn", "narrow_difficulty",
                             f"Öğe zorlukları çok dar (aralık {max(diffs) - min(diffs):.2f} < 0.5): adaptiflik "
                             "anlamsız — zorlukları yelpazeye yay (kolaydan zora)",
                             f"{path}.items"))

    # WARN: az öğe (kalibrasyon için zayıf sinyal)
    if len(s.items) < 4:
        out.append(LintIssue("warn", "few_items",
                             f"Adaptif pratikte az öğe ({len(s.items)} < 4): tahminci kalibre olamadan biter",
                             f"{path}.items"))

    # WARN: açıklamasız öğe (cevaptan sonra 'neden' yok → pasif geri bildirim)
    for it in s.items:
        if not (it.explain_html or "").strip():
            out.append(LintIssue("warn", "item_without_explanation",
                                 f"Adaptif öğe '{it.id}' açıklama (explain_html) içermiyor — doğru/yanlış neden, gösterilmeli",
                                 f"{path}.items[{it.id}]"))
    return out
