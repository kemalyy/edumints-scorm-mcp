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
from functools import lru_cache
from pathlib import Path

from .project import (
    QUIZ_TYPES,
    AccordionScreen,
    AdaptivePracticeScreen,
    DecisionScenarioScreen,
    FlashcardsScreen,
    GameScreen,
    HotspotScreen,
    LabeledDiagramScreen,
    LottieScreen,
    Project,
    ScreenType,
    SimulationScreen,
    TabsScreen,
    TimelineScreen,
    VideoScreen,
    WorkedExampleScreen,
)

_SCORE_DOS = {"score.correct", "score.wrong", "score.add"}
_PENALTY_DOS = {"lives.lose", "score.wrong"}

# SP-5 (B4-strict) — opt-in strict modda bloklamaya TERFİ eden küratörlü WARN kodları.
# Seçim gerekçesi (BACKLOG SP-5): metin duvarı + görsel yoksulluk + eksik alt-text + süs skor +
# sahte-seçim-komşusu kural. Not: `fake_choice`in kendisi zaten ERROR (her modda bloklar);
# "fake-choice-adjacent" için en yakın gerçek WARN kuralı `penalty_without_rationale`dir
# (olumsuz sonuçlu seçimin gerekçesizliği — anlamlı-seçim ilkesinin danışsal yarısı).
# Varsayılan davranış DEĞİŞMEZ: bu küme yalnız lint_errors(strict=True)'da devreye girer.
# E1 (#110): `unbound_scored_question` + `evidence_target_not_evidentiary` (K1/K2/T1 tabanları)
# eklendi — sert şartlar ama mevcut kursları kırmamak için varsayılanda WARN kalırlar (Değişmez
# kural: geriye uyumluluk), strict'te bloklarlar. Strict'te YALNIZ açık `evidence_screen_ids`
# beyanı geçer — heuristik aday keşfi hiçbir modda denetimi susturmaz.
STRICT_PROMOTED_CODES = frozenset({
    "penalty_without_rationale",
    "text_only_run",
    "visual_poverty",
    "missing_alt_text",
    "decorative_score",
    "unbound_scored_question",
    "evidence_target_not_evidentiary",
    # Faz 6b (düzen ölçüm raporu §5.2) — kalite WARN'ı, E1 emsaliyle strict'e terfi:
    # veri bütünlüğü değil öğretim kalitesi → varsayılanda danışsal kalır.
    "MEDIA_NO_CAPTION",
})


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
        elif isinstance(s, WorkedExampleScreen):
            issues += _lint_worked_example(s, path)
        issues += _lint_missing_alt(s, path)
        issues += _lint_generic_title(s, path)
        issues += _lint_list_items(s, path)
        issues += _lint_default_feedback(s, path)
    issues += _lint_media_no_caption(project)
    issues += _lint_consecutive_content_slides(project)
    issues += _lint_theme_logo_alt(project)
    issues += _lint_text_only_runs(project)
    issues += _lint_visual_poverty(project)
    issues += _lint_suspend_size(project)
    issues += _lint_unbound_objectives(project)
    issues += _lint_evidence_binding(project)
    issues += _lint_scored_over_objectives(project)
    issues += _lint_source_parity(project)
    issues += _lint_pack_conformance(project)
    return issues


def lint_errors(project: Project, strict: bool = False) -> list[LintIssue]:
    """Build'i bloklayan issue'lar. Varsayılan: yalnız ERROR şiddeti (davranış değişmedi).
    strict=True (SP-5): küratörlü WARN kümesi (STRICT_PROMOTED_CODES) de bloklamaya terfi eder."""
    issues = lint_course(project)
    if strict:
        return [i for i in issues if i.severity == "error" or i.code in STRICT_PROMOTED_CODES]
    return [i for i in issues if i.severity == "error"]


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


# --- worked_example (F1 #112) ------------------------------------------------
def _lint_worked_example(s: WorkedExampleScreen, path: str) -> list[LintIssue]:
    """WARN: gerekçesiz adım — çözümlü örneğin öğretici gücü adımın 'neden'inde (self-explanation
    etkisi); yalnız eylem listelemek tarif kartıdır, çözümlü örnek değil. Şemayı kırmaz (WARN)."""
    out: list[LintIssue] = []
    for i, st in enumerate(s.steps):
        if not (st.rationale_html or "").strip():
            out.append(LintIssue("warn", "step_without_rationale",
                                 f"Çözümlü örnek adımı {i} gerekçe (rationale_html) içermiyor — "
                                 "her adım NEDEN öyle yapıldığını göstermeli; gerekçesiz adım "
                                 "listesi tarif kartıdır, çözümlü örnek değil",
                                 f"{path}.steps[{i}]"))
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
    elif isinstance(s, WorkedExampleScreen):
        # F1 (#112) — artefakt görseli için artifact_caption hem figcaption hem alt-text kaynağı
        # (renderer ContentBlock.caption paraleli); boşsa alt-text boşluğu.
        for i, st in enumerate(s.steps):
            check(st.artifact_asset_id, st.artifact_caption, f"{path}.steps[{i}]")
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


# --- Faz 6b: dar düzen korkuluğu (ölçüm raporu 2026-07-30 §5.2) ---------------
# NOT (bilinçli eksik): genel split-attention lint'i ölçümle GEREKÇELENDİRİLEMEDİ ve
# yazılmadı (rapor §5 — mekanik vekiller ölçülen 6 vakanın hiçbirini yakalamıyor, sınıf-a
# ekranlar yanlış-pozitif olurdu). Buradaki kural raporun önerdiği DAR, sayılabilir biçimdir.
_MEDIA_NO_CAPTION_WORDS = 80
_TAG_RE = re.compile(r"<[^>]+>")


def _word_count(html: str | None) -> int:
    return len(_TAG_RE.sub(" ", html or "").split())


def _lint_media_no_caption(project: Project) -> list[LintIssue]:
    """MEDIA_NO_CAPTION — content_slide `blocks` içinde caption'sız görsel bloğu + ekranın
    >80 kelimelik düzyazısı → WARN. Uzun gövdenin yanında yorumsuz figür, görsel↔metin göz
    gidiş-gelişi üretir (Mayer/Sweller uzamsal bitişiklik); caption yorumu görselin bitişiğine
    taşır. Ölçümde bugün 0 isabet (mevcut yazarlık captionlı) — geleceğe korkuluk.
    Kelime sayımı ekranın DÜZYAZI toplamıdır: html blokları + body_html (renderer blocks'u
    basar ama gövde metni body_html'de bırakılmış olabilir). Kapsam yalnız `blocks`tur:
    eski media_asset_id yolunda caption alanı yok — çıkışsız ceza kesilmez (rapor §5.3
    affordans işi). caption ayrıca alt-text kaynağıdır; missing_alt_text'ten farkı eşikli
    düzen perspektifidir (a11y değil bitişiklik)."""
    out: list[LintIssue] = []
    for i, s in enumerate(project.screens):
        if s.type != ScreenType.content_slide:
            continue
        blocks = getattr(s, "blocks", None) or []
        if not any(b.asset_id and not (b.caption or "").strip() for b in blocks):
            continue
        words = _word_count(getattr(s, "body_html", None)) + sum(_word_count(b.html) for b in blocks)
        if words <= _MEDIA_NO_CAPTION_WORDS:
            continue
        for j, b in enumerate(blocks):
            if b.asset_id and not (b.caption or "").strip():
                out.append(LintIssue(
                    "warn", "MEDIA_NO_CAPTION",
                    f"Ekranın düzyazısı {words} kelime (> {_MEDIA_NO_CAPTION_WORDS}) ama "
                    f"blocks[{j}] görseli caption taşımıyor — figürün yorumu gövdede kalırsa "
                    "öğrenci görsel↔metin arasında gidip gelir (uzamsal bitişiklik). Görselin "
                    "yorumunu 1-2 cümlelik caption'a taşı",
                    f"screens[{i}].blocks[{j}]"))
    return out


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


# --- W11: görsel yoğunluk (text_only_run / visual_poverty) -------------------
# Tipi doğası gereği görsel olan ekranlar (adımları/etkileşimi görsel zorunlu kılar).
_INHERENTLY_VISUAL_TYPES = {
    ScreenType.image_compare,
    ScreenType.hotspot,
    ScreenType.labeled_diagram,
    ScreenType.data_chart,
    ScreenType.video,
    ScreenType.lottie,
    ScreenType.simulation,
    ScreenType.results_breakdown,  # skor çubukları çizer — grafik ekran
}


def _has_visual(s) -> bool:
    """Ekran görsel taşıyor mu? Doğası gereği görsel tipler VEYA herhangi bir görsel-alanı dolu
    olan ekranlar True döner. Alan yüzeyi `_lint_missing_alt` ile PARALEL tutulur (aynı ekran
    tiplerini, aynı alt-alanları gezer) — DRY yerine okunabilirlik tercih edildi; biri değişirse
    öteki elle senkron kalmalı (testler bunu yakalar)."""
    if s.type in _INHERENTLY_VISUAL_TYPES:
        return True
    if isinstance(s, AccordionScreen):
        return any(it.image_asset_id for it in s.items)
    if isinstance(s, TabsScreen):
        return any(t.image_asset_id for t in s.tabs)
    if isinstance(s, TimelineScreen):
        return any(e.image_asset_id for e in s.events)
    if isinstance(s, FlashcardsScreen):
        return any(c.front_asset_id or c.back_asset_id for c in s.cards)
    if isinstance(s, (GameScreen, DecisionScenarioScreen)):
        return any(n.image_asset_id for n in s.nodes)
    if isinstance(s, WorkedExampleScreen):
        # F1 (#112) — _INHERENTLY_VISUAL_TYPES üyesi DEĞİL: artefakt opsiyonel (metin-adımlı
        # çözümlü örnek meşru ama görsel sayılmaz); artefaktlı adım varsa görsel taşır.
        return any(st.artifact_asset_id for st in s.steps)
    if getattr(s, "media_asset_id", None):
        return True
    for b in getattr(s, "blocks", None) or []:
        if b.asset_id:
            return True
    return False


def _lint_text_only_runs(project: Project) -> list[LintIssue]:
    """Kural 1 (W11) — text_only_run: ≥4 ardışık görselsiz ekran WARN. 2-3 metin-ağırlıklı ekran
    meşru (içerik→içerik→mcq); 4+ süreklilik v1 teşhisindeki 'metin duvarı' desenidir."""
    out: list[LintIssue] = []
    run_start = None
    run_len = 0

    def flush(end_idx: int) -> None:
        if run_len >= 4:
            out.append(LintIssue(
                "warn", "text_only_run",
                f"{run_len} ardışık görselsiz ekran (screens[{run_start}..{end_idx - 1}]) — metin "
                "duvarı: birine blok görseli ekle, birini data_chart'a çevir, ya da "
                "flashcards/accordion öğelerine görsel ver",
                f"screens[{run_start}..{end_idx - 1}]",
            ))

    for i, s in enumerate(project.screens):
        if not _has_visual(s):
            if run_start is None:
                run_start = i
            run_len += 1
        else:
            flush(i)
            run_start = None
            run_len = 0
    flush(len(project.screens))
    return out


# --- S5 (2.2b): suspend_data boyut tahmini (SCORM 1.2 — 4096 karakter SPM) -----
# components/engine/scorm.js v2 kodlayıcısının maliyet modelinin yaklaşık üst-sınır aynası:
# gerçek payload'dan BÜYÜK ya da eşit olacak şekilde tasarlanmıştır (yanlış-negatif WARN istemiyoruz),
# ama kesin garanti DEĞİLDİR — runtime'daki değişken (vars) büyümesi ya da encoder'a eklenen yeni
# sabit alanlar (örn. S5 order-fingerprint) tahmini aşabilir. Kodlayıcı değişirse burası elle
# senkron kalmalı (encoder alan düzeni yorumu scorm.js'te).
_SUSPEND_LIMIT_12 = 4096          # scorm.js SUSPEND_LIMIT_12 ile senkron
_SUSPEND_BUDGET_12 = 3500         # Faz 4-ek — scorm.js SUSPEND_BUDGET_12 ile senkron (BAYT;
                                  # 4096-3500 LMS kaçışlama ek yüküne rezerv)
_SUSPEND_WARN_RATIO = 0.9         # sınıra "yaklaşınca" da uyar (öğrenci verisi büyümeden önce)
_EXPLORATION_VALUE_MAX = 500      # F2 (#113) — scorm.js EXPLORATION_VALUE_MAX ile senkron


def _b36_len(n: int) -> int:
    """n sayısının base36 gösteriminin uzunluğu (indeks genişliği)."""
    n = max(0, int(n))
    length = 1
    while n >= 36:
        n //= 36
        length += 1
    return length


def estimate_suspend_size(project: Project) -> int:
    """v2 kodlanmış suspend_data için KÖTÜ-DURUM projeksiyonu — UTF-8 BAYT (kesin garanti değil).

    Faz 4-ek: ölçü birimi karakterden BAYTA çevrildi (Türkçe çok-bayt tuzağı — runtime
    byteLen ile aynı ilke) ve zarfın Faz 4-ek alanları eklendi (z pozisyon kaydı + t bayrağı).
    Varsayımlar (madde-1 sözleşmesi — hepsi kötü-durum yönünde):
    - her ekran ziyaret edilmiş, her ekran bir kez back-stack'te (history),
    - TÜM sayfalar cevaplanmış (results + interaction indeksi ix), tüm hedefler tamam,
    - keşif (xp) alanları tavanda (500 bayt — runtime bayt-kırpar),
    - tüm indeksler maksimum base36 genişliğinde,
    - değişkenler tail JSON'da adı + değeriyle taşınır (UTF-8 bayt sayımıyla).

    Runtime'daki var büyümesi bu tahmini yine aşabilir — erken uyarı eşiği bu yüzden %90'da
    (bkz. _SUSPEND_WARN_RATIO); bütçe aşımı ayrıca SUSPEND_OVERFLOW üretir (_lint_suspend_size).
    """
    n = len(project.screens)
    scored = [s for s in project.screens if s.type in QUIZ_TYPES]
    iw = _b36_len(max(0, n - 1))                    # ekran indeksi genişliği
    size = 16                                        # zarf: "2|" + ayraçlar + bayrak + inext
    size += 11                                       # S5 order-fingerprint alanı: djb2 hash (≤7 taban36
                                                       # hane) + "_" + uzunluk (≤2 hane) + ayraç "|"
    size += iw                                       # cursor
    size += (n + 3) // 4                             # visited hex bitfield
    size += n * (iw + 1)                             # history: i36 + virgül
    for s in scored:
        digits = len(str(getattr(s, "points", 0) or 0))
        size += iw + digits * 2 + 5                  # results: i36:puan:max:bayrak + virgül
        size += iw * 2 + 2                           # ix: i36:n36 + virgül
    if project.variables:
        size += 8 + sum(len(v.name.encode("utf-8")) + len(str(v.default).encode("utf-8")) + 8
                        for v in project.variables)
    # F2 (#113) — exploration girdileri kuyruk JSON'unda kimlik-anahtarlı taşınır:
    # kötü-durum = değer tavanı (runtime 500 BAYTTA kırpar — scorm.js EXPLORATION_VALUE_MAX
    # ile senkron sabit) + anahtar + JSON zarf payı (tırnaklar/iki nokta/virgül).
    for s in project.screens:
        if s.type == ScreenType.exploration:
            size += _EXPLORATION_VALUE_MAX + len(s.store_key.encode("utf-8")) + 8
    # Faz 4-ek — z pozisyon kaydı {"z":{"s":…,"n":…,"v":…}} + t bayrağı ("t":4). Kimlikler
    # makine-dostu ASCII'dir; en uzun ekran + düğüm id'si ve 7 haneli sürümle kötü durum.
    max_sid = max((len(s.id or "") for s in project.screens), default=0)
    max_nid = max((len(nd.id) for nd in project.outline), default=0)
    size += 26 + max_sid + max_nid + 7               # z zarf payı + içerik
    size += 8                                        # "t":4 + virgül payı
    return size


def _lint_suspend_size(project: Project) -> list[LintIssue]:
    """WARN — 1.2 hedefinde kötü-durum suspend projeksiyonu bütçeyi aşıyor/yaklaşıyor.

    Faz 4-ek (madde 1, yazar-görünür yarı): projeksiyon 3500 BAYT çalışma bütçesine karşı —
    aşarsa SUSPEND_OVERFLOW (projeksiyon sayısıyla; runtime kırpma merdiveni SON ÇAREDİR,
    yazar sınırı ÖNCEDEN bilmeli: kursu bölme / 2004'e geçme kararı). Bütçenin %90'ına
    yaklaşınca erken uyarı suspend_size_risk. FAIL değil: tahmin kötü-durum üst sınırıdır.
    scenario_compile bu lint'i derlenen spec üzerinden otomatik görür (lint_course raporu)."""
    if project.scorm_version != "1.2":
        return []
    est = estimate_suspend_size(project)
    n_scored = sum(1 for s in project.screens if s.type in QUIZ_TYPES)
    if est > _SUSPEND_BUDGET_12:
        return [LintIssue(
            "warn", "SUSPEND_OVERFLOW",
            f"Kötü-durum suspend_data projeksiyonu ~{est} BAYT — SCORM 1.2 çalışma bütçesi "
            f"{_SUSPEND_BUDGET_12} bayt (sınır {_SUSPEND_LIMIT_12}; kalan pay LMS kaçışlama "
            "rezervi). Runtime kırpma merdiveni (history→serbest metin→cevaplar) veri düşürerek "
            "sığdırır ama bu SON ÇAREDİR — kursu bölmeyi ya da scorm_version='2004' hedeflemeyi "
            f"düşün ({len(project.screens)} ekran, {n_scored} puanlı).",
            "screens",
        )]
    threshold = int(_SUSPEND_BUDGET_12 * _SUSPEND_WARN_RATIO)
    if est < threshold:
        return []
    return [LintIssue(
        "warn", "suspend_size_risk",
        f"Kötü-durum suspend_data projeksiyonu ~{est} bayt — {_SUSPEND_BUDGET_12} bayt "
        f"çalışma bütçesine yaklaşıyor (eşik {threshold}; SCORM 1.2 sınırı {_SUSPEND_LIMIT_12}). "
        "Öğrenci verisi büyüyünce kırpma merdiveni devreye girebilir; kursu bölmeyi ya da "
        f"scorm_version='2004' hedeflemeyi düşün ({len(project.screens)} ekran, {n_scored} puanlı).",
        "screens",
    )]


# --- S2 (2.4): bağsız kurs hedefi ------------------------------------------
def _lint_unbound_objectives(project: Project) -> list[LintIssue]:
    """WARN — hedef tanımlı ama HİÇBİR puanlı ekran ona bağlanmamış. Runtime politikası gereği
    bağsız hedef için cmi.objectives kaydı YAZILMAZ (LMS'e boş/ölü hedef gitmez) — yani bu hedef
    raporlarda hiç görünmeyecek; yazar ya bağlamayı unuttu ya da hedef gereksiz."""
    if not project.objectives:
        return []
    bound = {oid for s in project.screens
             for oid in (getattr(s, "objective_ids", None) or [])}
    return [
        LintIssue("warn", "unbound_objective",
                  f"Hedef '{o.id}' hiçbir puanlı ekrana bağlanmamış (objective_ids) — bu hedef "
                  "için LMS'e cmi.objectives kaydı yazılmayacak; bir quiz/oyun ekranına bağla "
                  "ya da hedefi kaldır",
                  f"objectives[{o.id}]")
        for o in project.objectives if o.id not in bound
    ]


def _is_teaching_visual(s) -> bool:
    """E1 (#110) — görsel-yoksulluk ÖĞRETEN artefakta bağlanır: süs görseli sayılmaz.
    Çıplak `video` dış varlık kabıdır (K1: dış medya kanıt sayılır YALNIZ içeriği spec'ten
    doğrulanabiliyorsa — caption/narration_text); prompt'suz `lottie` salt dekor animasyondur.
    Kalan her şey `_has_visual` ile aynı (hotspot/data_chart/image_compare... doğası gereği öğretir)."""
    if isinstance(s, VideoScreen):
        return bool((s.caption or "").strip() or (s.narration_text or "").strip())
    if isinstance(s, LottieScreen):
        return bool((s.prompt_html or "").strip())
    return _has_visual(s)


def _lint_visual_poverty(project: Project) -> list[LintIssue]:
    """Kural 2 (W11) — visual_poverty: ekran sayısı ≥8 VE görsel ekran oranı <%25 WARN. Kısa
    kurslar (<8) muaf — mikro kurslarda oran gürültülü.
    E1 (#110): oran ÖĞRETEN görselle hesaplanır (`_is_teaching_visual`) — süs sayılmaz."""
    screens = project.screens
    total = len(screens)
    if total < 8:
        return []
    visual_count = sum(1 for s in screens if _is_teaching_visual(s))
    share = visual_count / total
    if share < 0.25:
        return [LintIssue(
            "warn", "visual_poverty",
            f"Kursta {total} ekranın yalnızca %{share * 100:.1f}'i ÖĞRETEN görsel taşıyor (<%25; "
            "süs görseli — caption'sız video, prompt'suz lottie — sayılmaz): content_slide'lara "
            "blok görseli, quiz'lere hotspot/image_compare, istatistiklere data_chart ekle",
            "screens",
        )]
    return []


# --- E1 (#110): kanıt bağlama denetimleri (Katman-1: K1–K3, H3, Z1/Z3, T1) ---
# Yöntem bağımsızlığı: bu denetimler kanıtın VARLIĞINA bakar, kurs akışındaki SIRASINA/fazına
# ASLA bakmaz ("önce öğret sonra sor" dayatması YOK — sıra seçilen öğretim yönteminin işidir;
# dallanan/adaptif kursta ekran indeksi ≠ sunum sırası, koşullu kanıt ekranı geç indeksli olabilir).

# Kanıt-TAŞIYABİLİR içerik tipleri (K1 tür 1/2/4/6'nın ekran izdüşümü). Ek koşullular
# _is_evidentiary_target'ta: content_slide artefakt (blocks/media) taşımalı — düz iddia metni
# kanıt hedefi olamaz; video/lottie spec'ten doğrulanabilir içerik taşımalı; skorlu tipler
# YALNIZ formatifken (points=0, puana yazmıyor) kanıt olabilir (K1 tür 3/5, Z3).
_EVIDENCE_CONTENT_TYPES = {
    ScreenType.accordion,
    ScreenType.tabs,
    ScreenType.flashcards,
    ScreenType.timeline,
    ScreenType.data_chart,
    ScreenType.image_compare,
    # F1 (#112) — çözümlü örnek K1 tür 1/4'ün EN doğrudan taşıyıcısı: adımların eylem+gerekçe
    # çifti artefaktın kendisidir (görsel şart değil) → koşulsuz kanıt-taşıyabilir. Şema zaten
    # ≥2 adım + zorunlu gerekçe ister; boş gerekçe ayrıca step_without_rationale WARN'ı üretir.
    ScreenType.worked_example,
    # F2 (#113) — keşif: öğrenenin KENDİ ürettiği tahmin/gözlem çıktısı (K1 tür 2) →
    # koşulsuz kanıt-taşıyabilir. Skorsuz (puan alanı yok) — Z1 formatiflik şartı yapısal
    # olarak garanti; sonraki ekran data-exploration-ref ile bu çıktıya atıf yapar.
    ScreenType.exploration,
}


def _is_scored(s, project: Project) -> bool:
    """Z1 — summatif (skorlu) ekran: `points` > 0 YA DA `on_correct` ile puan değişkenine yazan.
    points=0 + puana yazmayan = formatif (deneme-güvenli), kanıt şartı uygulanmaz (Z3)."""
    if s.type not in QUIZ_TYPES:
        return False
    if (getattr(s, "points", 0) or 0) > 0:
        return True
    if project.points_var:
        return any(a.var == project.points_var for a in (getattr(s, "on_correct", None) or []))
    return False


def _is_evidentiary_target(s, project: Project) -> bool:
    """Ekran kanıt hedefi olarak TAŞIYABİLİR mi? (K1 türlerinin ekran-taksonomisi izdüşümü.)

    Kanıt-taşıyabilir:
    - accordion / tabs / flashcards / timeline — etkileşimin bizzat gösterdiği olgu (K1 tür 2)
    - data_chart / image_compare — veri görseli / yan-yana karşılaştırma (K1 tür 6)
    - content_slide YALNIZ artefakt taşıyorsa (blocks ya da media_asset_id) — vaka dosyası /
      çözümlü örnek görseli (K1 tür 1/4); düz iddia-metni slaytı kanıt hedefi OLAMAZ (bağ
      törenselleşir: en yakın ekrana işaret et → alan dolu → denetim geçer → öğrenme yine yok)
    - video / lottie YALNIZ içeriği spec'ten doğrulanabiliyorsa (caption/narration_text ya da
      prompt_html) — "videoda anlatılıyordur" varsayımı kanıt değildir (K1 dış-medya şartı)
    - quiz/oyun tipleri YALNIZ formatifken (points=0, puana yazmıyor) — deneme çıktısı /
      başarısız deneme + kanonik çözüm (K1 tür 3/5, Z3)
    Kanıt-taşıyamaz: title_slide, summary, results_breakdown, poll, branching, SKORLU her ekran."""
    if s.type in _EVIDENCE_CONTENT_TYPES:
        return True
    if s.type == ScreenType.content_slide:
        return bool(getattr(s, "blocks", None) or getattr(s, "media_asset_id", None))
    if isinstance(s, (VideoScreen, LottieScreen)):
        return _is_teaching_visual(s)
    return s.type in QUIZ_TYPES and not _is_scored(s, project)


def _explicit_evidence_ok(s, project: Project, by_id: dict) -> bool:
    """Açık beyan geçerli mi: ≥1 id çözülüyor + kendisi değil + hedef kanıt-taşıyabilir."""
    return any(
        eid in by_id and eid != (s.id or "") and _is_evidentiary_target(by_id[eid], project)
        for eid in (getattr(s, "evidence_screen_ids", None) or [])
    )


def evidence_binding_coverage(project: Project) -> float:
    """E1 (#110) — açık-beyan kapsam metriği: geçerli `evidence_screen_ids` bağı olan skorlu
    ekran / toplam skorlu ekran. Törensel bağ (sarkan id, kanıt-taşıyamaz hedef) SAYILMAZ —
    metrik şişmesin; heuristik aday keşfi de sayılmaz (yalnız açık beyan). Skorlu ekran yoksa
    vakum: 1.0. Oran lint yeşilken düşüyorsa denetim sürükleniyor demektir."""
    scored = [s for s in project.screens if _is_scored(s, project)]
    if not scored:
        return 1.0
    by_id = {s.id: s for s in project.screens if s.id}
    return sum(1 for s in scored if _explicit_evidence_ok(s, project, by_id)) / len(scored)


def _evidence_candidates(s, project: Project) -> list[str]:
    """Heuristik ADAY keşfi — yalnız WARN mesajına öneri yazar, denetimi ASLA susturmaz
    (aksi halde alan hiç doldurulmaz ve denetim "yakında artefaktımsı ekran var mı"ya geriler).
    Kanallar (ikisi de sıra-bağımsız): (a) aynı hedefe bağlı formatif ekran (K1 tür 5),
    (b) aynı `section`'daki kanıt-taşıyabilir ekran."""
    cands: list[str] = []
    oids = set(getattr(s, "objective_ids", None) or [])
    for t in project.screens:
        if t is s or not t.id:
            continue
        shared_obj = bool(
            oids and t.type in QUIZ_TYPES and not _is_scored(t, project)
            and oids & set(getattr(t, "objective_ids", None) or [])
        )
        same_section = bool(
            s.section and t.section == s.section and _is_evidentiary_target(t, project)
        )
        if shared_obj or same_section:
            cands.append(t.id)
    return cands[:3]


def _lint_evidence_binding(project: Project) -> list[LintIssue]:
    """K1–K3 / T1 — skorlanan her sorunun kurs-içi kanıt kaynağı VAR olmalı.

    Bağın beyanı (tasarım kararı, revize c): tek geçerli bağ AÇIK `evidence_screen_ids` beyanıdır.
    1. Alan doluysa: sarkan/öz referans ERROR (`evidence_screen_missing` — bilinmeyen
       objective_ids ile aynı sınıf sert hata; alan kullanılmadıkça tetiklenmez → geriye uyumlu);
       çözülen ama kanıt-TAŞIYAMAZ hedef WARN `evidence_target_not_evidentiary` (strict'te
       bloklar) — bağ törensel olamaz.
    2. Alan boşsa: HER ZAMAN WARN `unbound_scored_question` (strict'te bloklar). Heuristik aday
       keşfi yalnız mesaja öneri ekler — hiçbir modda denetimi geçirmez.
    """
    out: list[LintIssue] = []
    screens = project.screens
    by_id = {s.id: s for s in screens if s.id}
    for i, s in enumerate(screens):
        if not _is_scored(s, project):
            continue
        path = f"screens[{i}]"
        ev = getattr(s, "evidence_screen_ids", None) or []
        if ev:
            for eid in ev:
                if eid not in by_id:
                    out.append(LintIssue("error", "evidence_screen_missing",
                                         f"Kanıt referansı sarkıyor: '{eid}' kursta yok (K1 — kanıt "
                                         "kaynağı kursun KENDİSİNİN ürettiği bir ekran olmalı)",
                                         f"{path}.evidence_screen_ids"))
                elif s.id and eid == s.id:
                    out.append(LintIssue("error", "evidence_screen_missing",
                                         f"Kanıt referansı ekranın kendisi: '{eid}' — soru kendi "
                                         "kendinin kanıtı olamaz (K2: cevabı ÜRETEN ayrı bir kaynak göster)",
                                         f"{path}.evidence_screen_ids"))
                elif not _is_evidentiary_target(by_id[eid], project):
                    out.append(LintIssue("warn", "evidence_target_not_evidentiary",
                                         f"Kanıt hedefi '{eid}' kanıt taşıyamaz (tip: {by_id[eid].type}) "
                                         "— düz iddia metni / kapak / özet / skorlu ekran cevabı ÜRETMEZ "
                                         "(K1). Hedef bir gösterim/artefakt ekranı olmalı: bloklu/görselli "
                                         "content_slide, accordion/tabs/flashcards/timeline, data_chart, "
                                         "image_compare, caption'lı video ya da formatif (points:0) deneme.",
                                         f"{path}.evidence_screen_ids"))
            continue  # alan beyan edilmiş: bulgular yukarıda; unbound AYRICA verilmez
        cands = _evidence_candidates(s, project)
        hint = (f" Muhtemel adaylar (beyan edilmemiş): {', '.join(cands)} — uygunsa "
                "`evidence_screen_ids` ile beyan et." if cands else "")
        out.append(LintIssue("warn", "unbound_scored_question",
                             f"Skorlanan soru '{s.id or i}' kurs-içi bir kanıt kaynağına bağlı değil "
                             "(K1/T1). K2 denetimi: 'kursu hiç görmemiş ama alanı bilen biri bunu zaten "
                             "cevaplayabilir mi?' Evet ise bu öğretim değil ankettir. K3 — bağla ya da at: "
                             "cevabı üreten ekranı `evidence_screen_ids` ile beyan et, kanıt ekranı ekle, "
                             f"soruyu points:0 yap ya da sil.{hint}",
                             path))
    return out


def _lint_scored_over_objectives(project: Project) -> list[LintIssue]:
    """H3 — `skorlanan ekran sayısı > hedef sayısı + 1` → WARN (fail DEĞİL: summatif sınav
    kursları hedef başına çok soruyu meşru içerebilir; gerekçe pre-flight'a yazılır). Hedef
    beyan edilmemişse eşik uygulanamaz (H3 beyana bağlıdır) — denetim sessiz kalır."""
    if not project.objectives:
        return []
    scored = sum(1 for s in project.screens if _is_scored(s, project))
    limit = len(project.objectives) + 1
    if scored <= limit:
        return []
    return [LintIssue(
        "warn", "scored_over_objectives",
        f"Skorlanan ekran sayısı ({scored}) hedef sayısı + 1'i ({limit}) aşıyor (H3) — ya fazla "
        "soruları hedefe eşle/at (H1: hedefsiz ölçme yasak) ya da bilinçli sınav-kursu gerekçesini "
        "pre-flight'a tek cümle yaz",
        "screens",
    )]


# --- E2 (#111): paket uygunluk denetimleri (danışsal dalga — hepsi WARN, strict-terfisiz) ---
# Beyan birimi: `Objective.method_pack` (paket id) — kapsam HEDEFTİR (_SCHEMA.md conflicts_with
# sözleşmesi). Ekran-düzeyi faz etiketi YOK (bilinçli erteleme): faz etiketi olmadan doğrulanabilir
# üç yaklaşık denetim + bilinmeyen-paket sağlamlığı. Paket tanımları vendored
# `runtime/pedagogy-packs.json`dan okunur (tools/gen_packs_manifest.py üretir; sunucu skill
# reposunu runtime'da OKUMAZ). Beyan yoksa SIFIR çıktı — geriye uyumluluk değişmezi.

_PACKS_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "runtime" / "pedagogy-packs.json"


@lru_cache(maxsize=1)
def _load_packs() -> dict:
    """Vendored paket manifesti (pack id → E2 projeksiyonu). Dosya yoksa/bozuksa {} — denetim
    `unknown_method_pack`a düşer (lint asla crash ile susmaz; manifest yokluğu deploy hatasıdır,
    kurs hatası değil)."""
    try:
        data = json.loads(_PACKS_MANIFEST_PATH.read_text(encoding="utf-8"))
        packs = data.get("packs")
        return packs if isinstance(packs, dict) else {}
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _objective_bindable_types() -> frozenset[str]:
    """`objective_ids` alanı TAŞIYAN ekran tipleri (Screen union'dan türetilir — elle liste
    sürüklenmez). Bağ modeli gerçeği: content_slide/worked_example/exploration/branching gibi
    tipler hedefe bağlanamaz; platform denetimi bu tipler için kurs-geneli varlığa düşer."""
    from typing import get_args

    from .project import Screen
    union = get_args(Screen)[0]
    out: set[str] = set()
    for cls in get_args(union):
        if "objective_ids" in cls.model_fields:
            t = cls.model_fields["type"].default
            out.add(str(getattr(t, "value", t)))
    return frozenset(out)


def _screen_type_str(s) -> str:
    t = s.type
    return str(getattr(t, "value", t))


def _evidence_allowed_types(pack: dict) -> set[str] | None:
    """Paketin kanıt fazlarında izinli ekran tiplerinin birleşimi; herhangi bir kanıt fazı
    `hepsi` ise None (= kısıt yok, denetim uygulanamaz)."""
    allowed: set[str] = set()
    evidence = set(pack.get("evidence_phases") or [])
    for ph in pack.get("phases") or []:
        if ph.get("id") not in evidence:
            continue
        ekr = ph.get("izinli_ekran_tipleri")
        if ekr == "hepsi":
            return None
        allowed |= set(ekr or [])
    return allowed


def _lint_pack_conformance(project: Project) -> list[LintIssue]:
    """E2 (#111) — kursun BEYAN ETTİĞİ paket(ler)in sözleşmesine uygunluk. Faz etiketi olmadan
    doğrulanabilir yaklaşık denetimler (hepsi WARN, danışsal):

    1. `unknown_method_pack` — beyan edilen paket manifest'te yok (yazım hatası / manifest bayat);
       o hedef için diğer denetimler çalıştırılamaz, atlanır.
    2. `pack_conflict_on_screen` — AYNI ekran, paketleri `conflicts_with` ile çelişen iki hedefe
       bağlı (objective_ids). Kapsam hedeftir: çelişen paketler AYRI hedeflerin AYRI ekranlarında
       meşru birlikte yaşar (B2 — karma kurs); ihlal yalnız paylaşılan ekrandır.
    3. `pack_platform_missing` — paket `requires_platform` beyan ediyor ama gerekli tip hedefin
       kullanımında yok (faz-etiketsiz yaklaşık: paketin akış iskeleti kurulmamış). Karşılanma:
       (i) o tipte ekran hedefe bağlı (objective_ids), YA DA (ii) o tipte ekran hedefin skorlu
       ekranlarının kanıt hedefi (evidence_screen_ids), YA DA (iii) tip HİÇ bağlanamıyorsa
       (`objective_ids` alanı yok — worked_example/exploration/branching...) kurs genelinde ≥1.
    4. `evidence_type_outside_pack` — hedefe bağlı SKORLU ekranın `evidence_screen_ids` hedefi,
       paketin kanıt fazlarında izinli olmayan tipte (yaklaşık-2: kanıt, paketin kanıt-üreten
       fazının dışından geliyor). Sarkan/öz id E1'in işi (`evidence_screen_missing` ERROR) —
       burada çifte raporlanmaz; kanıt fazı `hepsi` ise kısıt yok.
    """
    declared = {o.id: o.method_pack for o in project.objectives if o.method_pack}
    if not declared:
        return []
    out: list[LintIssue] = []
    packs = _load_packs()

    for oid, pid in declared.items():
        if pid not in packs:
            out.append(LintIssue("warn", "unknown_method_pack",
                                 f"Hedef '{oid}' bilinmeyen paket beyan ediyor: '{pid}' — "
                                 "runtime/pedagogy-packs.json'da yok (yazım hatası mı, manifest "
                                 "bayat mı? tools/gen_packs_manifest.py ile yeniden üret)",
                                 f"objectives[{oid}]"))
    known = {oid: pid for oid, pid in declared.items() if pid in packs}

    # 2 — pack_conflict_on_screen: paylaşılan ekranda çelişen paketli hedef çifti
    for i, s in enumerate(project.screens):
        oids = [oid for oid in (getattr(s, "objective_ids", None) or []) if oid in known]
        seen_pairs: set[frozenset[str]] = set()
        for a_idx, oa in enumerate(oids):
            for ob in oids[a_idx + 1:]:
                pa, pb = known[oa], known[ob]
                pair = frozenset((pa, pb))
                if pa == pb or pair in seen_pairs:
                    continue
                if pb in (packs[pa].get("conflicts_with") or []) or \
                        pa in (packs[pb].get("conflicts_with") or []):
                    seen_pairs.add(pair)
                    out.append(LintIssue(
                        "warn", "pack_conflict_on_screen",
                        f"Ekran '{s.id or i}' çelişen paketli iki hedefe bağlı: '{oa}' "
                        f"({pa}) + '{ob}' ({pb}) — bu paketler AYNI hedef/ekran üzerinde "
                        "birleştirilemez (conflicts_with). Farklı hedeflerde ayrı ekranlarla "
                        "meşrudur; ekranı tek pakete ait hedefe bırak ya da hedef beyanını gözden "
                        "geçir", f"screens[{i}]"))

    # hedef → bağlı ekranlar (3 ve 4 için tek geçiş)
    bound: dict[str, list] = {oid: [] for oid in known}
    for s in project.screens:
        for oid in getattr(s, "objective_ids", None) or []:
            if oid in bound:
                bound[oid].append(s)

    by_id = {s.id: s for s in project.screens if s.id}
    course_types = {_screen_type_str(s) for s in project.screens}
    for oid, pid in known.items():
        pack = packs[pid]

        # 3 — pack_platform_missing: gerekli tip hedefin kullanımında yok (kurallar i/ii/iii)
        bound_types = {_screen_type_str(s) for s in bound[oid]}
        evidence_ref_types = {
            _screen_type_str(by_id[eid])
            for s in bound[oid] if _is_scored(s, project)
            for eid in (getattr(s, "evidence_screen_ids", None) or []) if eid in by_id
        }
        for req in pack.get("requires_platform") or []:
            if req in bound_types or req in evidence_ref_types:
                continue
            if req not in _objective_bindable_types() and req in course_types:
                continue  # tip hedefe bağlanamıyor → kurs-geneli varlık yeter
            out.append(LintIssue(
                "warn", "pack_platform_missing",
                f"Hedef '{oid}' paketi '{pid}' zorunlu platform yeteneği istiyor: "
                f"'{req}' — ama bu tipte ekran hedefe bağlı değil (objective_ids), hedefin "
                "kanıt hedeflerinde yok" + (
                    "" if req in _objective_bindable_types()
                    else " ve kursta hiç yok") +
                f". Bir '{req}' ekranı ekle ve hedefin akışına bağla ya da paketi yeniden seç "
                "(paket iskeleti bu yetenek üstüne kurulu)", f"objectives[{oid}]"))

        # 4 — evidence_type_outside_pack: skorlu ekranın kanıt hedefi, kanıt fazı tipleri dışında
        allowed = _evidence_allowed_types(pack)
        if allowed is None:
            continue
        for s in bound[oid]:
            if not _is_scored(s, project):
                continue
            si = project.screens.index(s)
            for eid in getattr(s, "evidence_screen_ids", None) or []:
                target = by_id.get(eid)
                if target is None or eid == (s.id or ""):
                    continue  # sarkan/öz referans E1'in işi (ERROR) — çifte raporlama yok
                ttype = str(target.type.value if hasattr(target.type, "value") else target.type)
                if ttype not in allowed:
                    out.append(LintIssue(
                        "warn", "evidence_type_outside_pack",
                        f"Skorlu ekran '{s.id or si}' kanıtı '{eid}' (tip: {ttype}) — bu tip, "
                        f"'{pid}' paketinin kanıt fazlarında "
                        f"({', '.join(pack.get('evidence_phases') or [])}) izinli değil "
                        f"(izinli: {', '.join(sorted(allowed))}). Kanıt, paketin kanıt-üreten "
                        "fazından gelmeli — kanıt ekranının tipini paket fazına uydur ya da bağı "
                        "doğru ekrana taşı", f"screens[{si}].evidence_screen_ids"))
    return out


def _lint_source_parity(project: Project) -> list[LintIssue]:
    """E1 (#110) — kaynak-doküman madde sayısı ≈ ekran sayısı → 1:1 kopya kokusu (WARN).
    Beyan-temelli: yazar/iş-akışı `source_item_count` beyan etmedikçe denetim yok (geriye uyumlu).
    Eşik: |ekran − madde| ≤ max(1, %10) VE madde ≥ 5 (mikro kaynakta oran gürültülü)."""
    src = project.source_item_count
    if not src or src < 5:
        return []
    total = len(project.screens)
    tolerance = max(1, round(src * 0.1))
    if abs(total - src) > tolerance:
        return []
    return [LintIssue(
        "warn", "source_item_parity",
        f"Ekran sayısı ({total}) kaynak dokümanın madde sayısına ({src}) ≈ eşit — 1:1 kopya kokusu: "
        "kaynak maddeleri ekrana bire bir aktarmak öğretim tasarımı değildir; maddeleri hedefe göre "
        "birleştir/böl, kanıt üreten etkileşimlere dönüştür (K1 türleri)",
        "screens",
    )]
