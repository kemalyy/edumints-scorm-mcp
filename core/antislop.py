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
import re
from dataclasses import dataclass

from .project import (
    AccordionScreen,
    AdaptivePracticeScreen,
    DecisionScenarioScreen,
    FlashcardsScreen,
    GameScreen,
    HotspotScreen,
    LabeledDiagramScreen,
    Project,
    ScreenType,
    SimulationScreen,
    TabsScreen,
    TimelineScreen,
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
    """Kurstaki tüm ekranları denetle. ERROR + WARN karışık döner."""
    issues: list[LintIssue] = []
    for i, s in enumerate(project.screens):
        path = f"screens[{i}]"
        if isinstance(s, GameScreen):
            issues += _lint_game(s, path)
        elif isinstance(s, AdaptivePracticeScreen):
            issues += _lint_adaptive(s, path)
        issues += _lint_missing_alt(s, path)
        issues += _lint_generic_title(s, path)
        issues += _lint_list_items(s, path)
        issues += _lint_default_feedback(s, path)
    issues += _lint_consecutive_content_slides(project)
    issues += _lint_theme_logo_alt(project)
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


# --- erişilebilirlik: eksik alt-text (W9 P0) ------------------------------
def _lint_missing_alt(s, path: str) -> list[LintIssue]:
    """Görsel taşıyan alanlarda alt-text eksikse WARN (yapıyı bozmaz, danışsal)."""
    out: list[LintIssue] = []

    def check(asset_id, alt, sub_path):
        if asset_id and not (alt or "").strip():
            out.append(LintIssue("warn", "missing_alt_text",
                                 f"Görsel var ama alt-text yok ({sub_path}) — ekran okuyucu kullanıcılar "
                                 "için görselin içeriğini kısaca anlatan bir alt metni ekle",
                                 sub_path))

    if isinstance(s, HotspotScreen):
        check(s.image_asset_id, s.image_alt, f"{path}.image_asset_id")
    elif isinstance(s, LabeledDiagramScreen):
        check(s.image_asset_id, s.image_alt, f"{path}.image_asset_id")
    elif isinstance(s, SimulationScreen):
        for i, st in enumerate(s.steps):
            check(st.image_asset_id, st.image_alt, f"{path}.steps[{i}]")
    elif isinstance(s, DecisionScenarioScreen):
        for n in s.nodes:
            check(n.image_asset_id, n.image_alt, f"{path}.nodes[{n.id}]")
    elif isinstance(s, GameScreen):
        for n in s.nodes:
            check(n.image_asset_id, n.image_alt, f"{path}.nodes[{n.id}]")
    elif isinstance(s, AccordionScreen):
        for i, it in enumerate(s.items):
            check(it.image_asset_id, it.image_alt, f"{path}.items[{i}]")
    elif isinstance(s, TabsScreen):
        for i, t in enumerate(s.tabs):
            check(t.image_asset_id, t.image_alt, f"{path}.tabs[{i}]")
    elif isinstance(s, TimelineScreen):
        for i, e in enumerate(s.events):
            check(e.image_asset_id, e.image_alt, f"{path}.events[{i}]")
    elif isinstance(s, FlashcardsScreen):
        for i, c in enumerate(s.cards):
            check(c.front_asset_id, c.front_alt, f"{path}.cards[{i}].front_asset_id")
            check(c.back_asset_id, c.back_alt, f"{path}.cards[{i}].back_asset_id")
    else:
        media_asset_id = getattr(s, "media_asset_id", None)
        if media_asset_id:
            check(media_asset_id, getattr(s, "media_alt", None), f"{path}.media_asset_id")
        # W9 review fix — ContentSlide.blocks görselleri de kapsanmalı: renderer
        # (components/renderer.py) block görselleri için b.caption'ı alt-text olarak
        # kullanıyor; bu blok yoksa lint'in gözden kaçırdığı bir alt-text boşluğu oluşuyordu.
        for i, b in enumerate(getattr(s, "blocks", None) or []):
            check(b.asset_id, b.caption, f"{path}.blocks[{i}]")
    return out


# --- içerik yapısı: A1/A2/A3, B3 (W9 P1) ------------------------------------
# Kalıp: (prefix kelime) + ops. sayı + ops. ':' + ops. jenerik betimleyici, başka hiçbir şey yok.
# "Modül 1: Giriş" / "Bölüm 2: Genel Bakış" / "Konu 3" / "Ünite: Temeller" hepsini karşılar; içinde
# bu kelimelerden biri geçen ama ANLAMLI ek içerik taşıyan başlıklarla eşleşmez (ör. "Neden 8
# saniyede karar veriyoruz?" hiçbiriyle başlamadığı için hiç eşleşmez).
_GENERIC_TITLE_RE = re.compile(
    r"^\s*(modül|bölüm|konu|ünite)\s*\d*\s*:?\s*(giriş|genel bakış|özet|temeller)?\s*$",
    re.IGNORECASE,
)


def _is_generic_title(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    return bool(_GENERIC_TITLE_RE.match(t))


def _lint_generic_title(s, path: str) -> list[LintIssue]:
    title = getattr(s, "title", None)
    if title and _is_generic_title(title):
        return [LintIssue("warn", "generic_title",
                          f"Jenerik başlık ('{title}') — başlık ekranın tek çıkarımını taşımalı "
                          "(mümkünse soru/iddia), 'Modül N: Giriş' gibi içeriksiz etiket değil",
                          f"{path}.title")]
    return []


def _lint_list_items(s, path: str) -> list[LintIssue]:
    body = getattr(s, "body_html", None)
    if not body:
        return []
    count = len(re.findall(r"<li[\s>]", body, re.IGNORECASE))
    if count > 4:
        return [LintIssue("warn", "too_many_list_items",
                          f"Ekranda {count} <li> var (>4) — bir ekran bir fikir taşımalı; "
                          "listeyi bölmeyi ya da accordion/flashcards'a çevirmeyi düşün",
                          f"{path}.body_html")]
    return []


def _lint_default_feedback(s, path: str) -> list[LintIssue]:
    fb = getattr(s, "feedback", None)
    if fb is None:
        return []
    # I1 — varsayılan artık None (dil-nötr); metin karşılaştırması yerine "yazar doldurdu mu"ya bak.
    if not fb.correct_html and not fb.incorrect_html:
        return [LintIssue("warn", "default_feedback",
                          "Feedback yazılmamış, jenerik varsayılana bırakılmış — "
                          "her feedback nedeni açıklamalı ve doğru modele bağlanmalı",
                          f"{path}.feedback")]
    return []


def _lint_theme_logo_alt(project: Project) -> list[LintIssue]:
    """Tema logosu var ama alt-text yoksa WARN — missing_alt_text ile aynı kod, tema seviyesi
    (diğer tüm alt-text kontrolleri _lint_missing_alt'te ekran seviyesinde çalışır)."""
    t = project.theme
    if t.logo_asset_id and not (t.logo_alt or "").strip():
        return [LintIssue("warn", "missing_alt_text",
                           "Tema logosu var ama alt-text yok (theme.logo_alt) — ekran okuyucu "
                           "kullanıcılar için logonun kime ait olduğunu kısaca anlatan bir alt "
                           "metni ekle", "theme.logo_asset_id")]
    return []


def _lint_consecutive_content_slides(project: Project) -> list[LintIssue]:
    out: list[LintIssue] = []
    run_start = None
    run_len = 0
    for i, s in enumerate(project.screens):
        if s.type == ScreenType.content_slide:
            if run_start is None:
                run_start = i
            run_len += 1
        else:
            if run_len > 2:
                out.append(LintIssue("warn", "consecutive_content_slides",
                                     f"{run_len} ardışık content_slide (screens[{run_start}]..[{i - 1}]) "
                                     "— araya bir etkileşim ekranı (mcq/hotspot/accordion/vb.) sok",
                                     f"screens[{run_start}]..[{i - 1}]"))
            run_start = None
            run_len = 0
    if run_len > 2:  # kurs content_slide zinciriyle bitiyorsa
        out.append(LintIssue("warn", "consecutive_content_slides",
                             f"{run_len} ardışık content_slide (screens[{run_start}]..sonuncu) "
                             "— araya bir etkileşim ekranı sok",
                             f"screens[{run_start}]..end"))
    return out
