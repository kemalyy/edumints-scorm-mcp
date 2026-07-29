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
    QUIZ_TYPES,
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

# SP-5 (B4-strict) — opt-in strict modda bloklamaya TERFİ eden küratörlü WARN kodları.
# Seçim gerekçesi (BACKLOG SP-5): metin duvarı + görsel yoksulluk + eksik alt-text + süs skor +
# sahte-seçim-komşusu kural. Not: `fake_choice`in kendisi zaten ERROR (her modda bloklar);
# "fake-choice-adjacent" için en yakın gerçek WARN kuralı `penalty_without_rationale`dir
# (olumsuz sonuçlu seçimin gerekçesizliği — anlamlı-seçim ilkesinin danışsal yarısı).
# Varsayılan davranış DEĞİŞMEZ: bu küme yalnız lint_errors(strict=True)'da devreye girer.
STRICT_PROMOTED_CODES = frozenset({
    "penalty_without_rationale",
    "text_only_run",
    "visual_poverty",
    "missing_alt_text",
    "decorative_score",
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
        issues += _lint_missing_alt(s, path)
        issues += _lint_generic_title(s, path)
        issues += _lint_list_items(s, path)
        issues += _lint_default_feedback(s, path)
    issues += _lint_consecutive_content_slides(project)
    issues += _lint_theme_logo_alt(project)
    issues += _lint_text_only_runs(project)
    issues += _lint_visual_poverty(project)
    issues += _lint_suspend_size(project)
    issues += _lint_unbound_objectives(project)
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
_SUSPEND_WARN_RATIO = 0.9         # sınıra "yaklaşınca" da uyar (öğrenci verisi büyümeden önce)


def _b36_len(n: int) -> int:
    """n sayısının base36 gösteriminin uzunluğu (indeks genişliği)."""
    n = max(0, int(n))
    length = 1
    while n >= 36:
        n //= 36
        length += 1
    return length


def estimate_suspend_size(project: Project) -> int:
    """v2 kodlanmış suspend_data için yaklaşık üst-sınır tahmini (karakter, kesin garanti değil).

    Varsayımlar (hepsi kötü-durum yönünde):
    - her ekran ziyaret edilmiş, her ekran bir kez back-stack'te (history),
    - her puanlı ekran cevaplanmış (results + interaction indeksi ix),
    - tüm indeksler maksimum base36 genişliğinde,
    - değişkenler tail JSON'da adı + değeriyle taşınır.

    Runtime'daki var büyümesi (öğrenci ilerledikçe tail JSON şişer) ya da encoder zarfına eklenen
    yeni sabit alanlar bu tahmini aşabilir — WARN eşiği bu yüzden %90'da (bkz. _SUSPEND_WARN_RATIO),
    tam sınırda değil.
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
        size += 8 + sum(len(v.name) + len(str(v.default)) + 8 for v in project.variables)
    return size


def _lint_suspend_size(project: Project) -> list[LintIssue]:
    """WARN — 1.2 hedefinde tahmini suspend_data boyutu 4096 sınırına yaklaşıyor/aşıyor.

    FAIL değil: tahmin kötü-durum üst sınırıdır ve runtime encodeSuspendFit history düşürerek
    çoğu kursu yine sığdırır — ama yazar sınırı ÖNCEDEN bilmeli (kursu bölme / 2004'e geçme kararı)."""
    if project.scorm_version != "1.2":
        return []
    est = estimate_suspend_size(project)
    threshold = int(_SUSPEND_LIMIT_12 * _SUSPEND_WARN_RATIO)
    if est < threshold:
        return []
    return [LintIssue(
        "warn", "suspend_size_risk",
        f"Tahmini suspend_data boyutu ~{est} karakter — SCORM 1.2 sınırı {_SUSPEND_LIMIT_12} "
        f"(eşik {threshold}). Runtime sığdırmak için gezinme geçmişini düşürebilir; kursu bölmeyi "
        "ya da scorm_version='2004' hedeflemeyi düşün "
        f"({len(project.screens)} ekran, {sum(1 for s in project.screens if s.type in QUIZ_TYPES)} puanlı).",
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


def _lint_visual_poverty(project: Project) -> list[LintIssue]:
    """Kural 2 (W11) — visual_poverty: ekran sayısı ≥8 VE görsel ekran oranı <%25 WARN. Kısa
    kurslar (<8) muaf — mikro kurslarda oran gürültülü."""
    screens = project.screens
    total = len(screens)
    if total < 8:
        return []
    visual_count = sum(1 for s in screens if _has_visual(s))
    share = visual_count / total
    if share < 0.25:
        return [LintIssue(
            "warn", "visual_poverty",
            f"Kursta {total} ekranın yalnızca %{share * 100:.1f}'i görsel taşıyor (<%25) — görsel "
            "yoksulluk: content_slide'lara blok görseli, quiz'lere hotspot/image_compare, "
            "istatistiklere data_chart ekle",
            "screens",
        )]
    return []
