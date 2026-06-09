"""core/project.py — Kanonik veri modeli (CONTRACTS.md §1, §2, §12.1).

Pydantic v2. Hem in-memory model, hem store serileştirmesi, hem tool girdi/çıktısı.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field
from ulid import ULID


# --------------------------------------------------------------------------- #
# ID üreticileri (CONTRACTS.md §0)
# --------------------------------------------------------------------------- #
def _ulid() -> str:
    return str(ULID())


def new_project_id() -> str:
    return f"proj_{_ulid()}"


def new_screen_id() -> str:
    return f"scr_{_ulid()}"


def new_asset_id() -> str:
    return f"asset_{_ulid()}"


def new_package_id() -> str:
    return f"pkg_{_ulid()}"


def new_job_id() -> str:
    return f"job_{_ulid()}"


def new_key_id() -> str:
    return f"key_{_ulid()}"


def new_feedback_id() -> str:
    return f"fb_{_ulid()}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Tema token'ları (CONTRACTS.md §1.1) — 6 alt-grup
# --------------------------------------------------------------------------- #
class Typography(BaseModel):
    font_heading: str = "'Outfit', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    font_body: str = "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    font_mono: str = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    base_size_px: int = 16
    scale_ratio: float = 1.25
    weight_heading: int = 700
    weight_body: int = 400
    weight_strong: int = 600
    line_height_tight: float = 1.15
    line_height_normal: float = 1.6
    letter_spacing_heading: str = "-0.025em"


class ColorPalette(BaseModel):
    primary: str = "#4f46e5"
    primary_hover: str = "#4338ca"
    primary_contrast: str = "#ffffff"
    secondary: str = "#7c3aed"
    accent: str = "#0d9488"
    bg: str = "#fafafa"
    surface: str = "#ffffff"
    surface_alt: str = "#f4f4f5"
    border: str = "#e4e4e7"
    text: str = "#18181b"
    text_muted: str = "#71717a"
    text_on_dark: str = "#fafafa"
    success: str = "#16a34a"
    success_bg: str = "#dcfce7"
    error: str = "#dc2626"
    error_bg: str = "#fee2e2"
    warning: str = "#d97706"
    info: str = "#0284c7"
    focus_ring: str = "#4f46e5"


class Spacing(BaseModel):
    base_px: int = 4
    scale: list[int] = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96]
    content_max_width: str = "880px"
    gutter: str = "clamp(16px, 4vw, 48px)"


class Radii(BaseModel):
    none: str = "0"
    sm: str = "6px"
    md: str = "12px"
    lg: str = "20px"
    pill: str = "999px"


class Elevation(BaseModel):
    e0: str = "none"
    e1: str = "0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.10)"
    e2: str = "0 4px 6px -1px rgba(15,23,42,.10), 0 2px 4px -2px rgba(15,23,42,.10)"
    e3: str = "0 10px 15px -3px rgba(15,23,42,.10), 0 4px 6px -4px rgba(15,23,42,.10)"
    e4: str = "0 20px 25px -5px rgba(15,23,42,.12), 0 8px 10px -6px rgba(15,23,42,.10)"


class Motion(BaseModel):
    duration_fast: str = "120ms"
    duration_base: str = "220ms"
    duration_slow: str = "400ms"
    easing_standard: str = "cubic-bezier(0.2, 0, 0, 1)"
    easing_emphasized: str = "cubic-bezier(0.2, 0, 0, 1.2)"
    slide_transition: Literal["fade", "slide", "zoom", "none"] = "slide"
    reduce_motion_respect: bool = True


class ThemeTokens(BaseModel):
    name: str = "default"
    typography: Typography = Field(default_factory=Typography)
    color: ColorPalette = Field(default_factory=ColorPalette)
    spacing: Spacing = Field(default_factory=Spacing)
    radii: Radii = Field(default_factory=Radii)
    elevation: Elevation = Field(default_factory=Elevation)
    motion: Motion = Field(default_factory=Motion)
    logo_asset_id: str | None = None
    background_pattern: Literal["none", "dots", "grid", "gradient"] = "none"
    custom_css: str | None = None


# --------------------------------------------------------------------------- #
# Takip / tamamlanma (CONTRACTS.md §1.2)
# --------------------------------------------------------------------------- #
class CompletionRule(str, Enum):
    viewed_all = "viewed_all"
    passed_quiz = "passed_quiz"
    viewed_all_and_passed = "viewed_all_and_passed"


class Tracking(BaseModel):
    completion_rule: CompletionRule = CompletionRule.viewed_all
    passing_score: int = 80
    score_scaling: bool = True


# --------------------------------------------------------------------------- #
# Ekran alt tipleri (CONTRACTS.md §1.3)
# --------------------------------------------------------------------------- #
class Choice(BaseModel):
    id: str
    text_html: str
    correct: bool = False


class Feedback(BaseModel):
    correct_html: str = "Doğru!"
    incorrect_html: str = "Tekrar deneyin."
    show_correct_answer: bool = True


class Blank(BaseModel):
    id: str
    accepted: list[str]


class DragItem(BaseModel):
    id: str
    text_html: str
    correct_target_id: str


class DropTarget(BaseModel):
    id: str
    label_html: str


class HotspotRegion(BaseModel):
    id: str
    shape: Literal["rect", "circle", "poly"]
    coords: list[float]
    correct: bool = True
    label_html: str | None = None


# --------------------------------------------------------------------------- #
# Değişken/durum + koşullu (Faz 5 — triggers temeli)
# --------------------------------------------------------------------------- #
VarValue = Union[float, str, bool]


class Variable(BaseModel):
    name: str
    type: Literal["number", "text", "bool"] = "number"
    default: VarValue = 0


class VarAction(BaseModel):
    """Bir değişkeni değiştirir (ekran girişinde / dallanma seçiminde)."""
    var: str
    op: Literal["set", "add"] = "set"
    value: VarValue = 0


class Condition(BaseModel):
    """Değişkene bağlı koşul (ekran görünürlüğü için)."""
    var: str
    cmp: Literal["==", "!=", ">", "<", ">=", "<="] = "=="
    value: VarValue = 0


class BranchChoice(BaseModel):
    id: str
    text_html: str
    goto_screen_id: str
    set_vars: list[VarAction] = Field(default_factory=list)  # seçimde değişken ata (Faz 5)


# --------------------------------------------------------------------------- #
# Ekran tipleri (discriminated union, `type` alanı ile)
# --------------------------------------------------------------------------- #
class ScreenType(str, Enum):
    title_slide = "title_slide"
    content_slide = "content_slide"
    mcq = "mcq"
    true_false = "true_false"
    fill_blank = "fill_blank"
    drag_drop = "drag_drop"
    hotspot = "hotspot"
    branching = "branching"
    video = "video"
    summary = "summary"
    # Faz 1b — içerik etkileşim tipleri
    accordion = "accordion"
    tabs = "tabs"
    flashcards = "flashcards"
    matching = "matching"
    sorting = "sorting"
    timeline = "timeline"
    lottie = "lottie"  # Faz 7 — animasyon (opt-in/lazy)
    simulation = "simulation"  # Faz 8 — çok-adımlı yazılım simülasyonu (Uygula/try-mode)
    decision_scenario = "decision_scenario"  # Faz 12 (G2) — dallanan karar senaryosu (anlatı try-mode)
    term_match_race = "term_match_race"  # Faz 13 (G3) — süreli terim↔tanım eşleştirme oyunu
    escape_room = "escape_room"  # Faz 13 (G3) — kilitli bulmaca zinciri (ipucu/can)
    labeled_diagram = "labeled_diagram"  # Faz 13 — etiketli diyagram (görsel öğrenme)
    data_chart = "data_chart"  # Faz 13 — veri-görseli (bar/line/pie, içerik)


class ScreenBase(BaseModel):
    id: str | None = None
    title: str
    notes: str | None = None
    duration_hint_sec: int | None = None
    # Faz 3 — opsiyonel ekran seslendirmesi (TTS/audio asset; her ekranda ses oynatıcı)
    narration_asset_id: str | None = None
    # Faz 5 — koşullu görünürlük (koşul false ise ekran atlanır) + girişte değişken atama
    visible_if: Condition | None = None
    on_enter: list[VarAction] = Field(default_factory=list)
    # Faz 6 — oyunlaştırma: geri sayım + süre dolunca aksiyon/yönlendirme; quiz doğru/yanlış aksiyonları
    timer_sec: int | None = None
    on_timeout: list[VarAction] = Field(default_factory=list)
    timeout_goto: str | None = None
    on_correct: list[VarAction] = Field(default_factory=list)  # quiz doğru → değişken (puan vb.)
    on_wrong: list[VarAction] = Field(default_factory=list)
    # Faz 9 — sabit-sahne/timeline (slayt-tarzı oynatıcı)
    narration_text: str | None = None  # altyazı metni (CC) — timeline süre kaynağı da olabilir
    reveal: Literal["auto", "click", "none"] | None = None  # None → ekran tipinden türetilir
    animation: str | None = None  # blok giriş preset'i: fade-up(vars.)|fade|zoom|slide-left
    block_sec: float | None = None  # ses yokken paced reveal aralığı (vars. 2.5)
    lock_until_complete: bool = False  # timeline bitmeden İleri kilitli
    section: str | None = None  # Faz 9.1 — bölüm/ünite adı (menü bölümlere göre gruplanır)


class TitleSlide(ScreenBase):
    type: Literal[ScreenType.title_slide] = ScreenType.title_slide
    subtitle: str | None = None
    background_asset_id: str | None = None
    body_html: str | None = None


class ContentSlide(ScreenBase):
    type: Literal[ScreenType.content_slide] = ScreenType.content_slide
    body_html: str
    media_asset_id: str | None = None
    layout: Literal["text", "text_media", "media_text", "full_media"] = "text"


class MCQScreen(ScreenBase):
    type: Literal[ScreenType.mcq] = ScreenType.mcq
    prompt_html: str
    options: list[Choice] = Field(min_length=2)
    multi_select: bool = False
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class TrueFalseScreen(ScreenBase):
    type: Literal[ScreenType.true_false] = ScreenType.true_false
    prompt_html: str
    correct: bool
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class FillBlankScreen(ScreenBase):
    type: Literal[ScreenType.fill_blank] = ScreenType.fill_blank
    prompt_html: str
    blanks: list[Blank] = Field(min_length=1)
    case_sensitive: bool = False
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class DragDropScreen(ScreenBase):
    type: Literal[ScreenType.drag_drop] = ScreenType.drag_drop
    prompt_html: str
    items: list[DragItem] = Field(min_length=1)
    targets: list[DropTarget] = Field(min_length=1)
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class HotspotScreen(ScreenBase):
    type: Literal[ScreenType.hotspot] = ScreenType.hotspot
    prompt_html: str
    image_asset_id: str
    regions: list[HotspotRegion] = Field(min_length=1)
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class BranchingScreen(ScreenBase):
    type: Literal[ScreenType.branching] = ScreenType.branching
    prompt_html: str
    choices: list[BranchChoice] = Field(min_length=1)
    default_goto: str | None = None


class VideoScreen(ScreenBase):
    type: Literal[ScreenType.video] = ScreenType.video
    video_asset_id: str | None = None
    video_url: str | None = None
    caption: str | None = None
    poster_asset_id: str | None = None
    require_complete: bool = False


class SummaryScreen(ScreenBase):
    type: Literal[ScreenType.summary] = ScreenType.summary
    body_html: str | None = None
    show_score: bool = True
    show_completion: bool = True


# --- Faz 1b: içerik etkileşim tipleri (skorlanmaz) ---
class AccordionItem(BaseModel):
    title: str
    body_html: str


class AccordionScreen(ScreenBase):
    type: Literal[ScreenType.accordion] = ScreenType.accordion
    prompt_html: str | None = None
    items: list[AccordionItem] = Field(min_length=1)


class TabItem(BaseModel):
    label: str
    body_html: str


class TabsScreen(ScreenBase):
    type: Literal[ScreenType.tabs] = ScreenType.tabs
    prompt_html: str | None = None
    tabs: list[TabItem] = Field(min_length=1)


class Flashcard(BaseModel):
    front_html: str
    back_html: str


class FlashcardsScreen(ScreenBase):
    type: Literal[ScreenType.flashcards] = ScreenType.flashcards
    prompt_html: str | None = None
    cards: list[Flashcard] = Field(min_length=1)


# --- Faz 1b dalga 2: matching/sorting (skorlanır) + timeline (içerik) ---
class MatchPair(BaseModel):
    id: str
    left_html: str
    right_html: str


class MatchingScreen(ScreenBase):
    type: Literal[ScreenType.matching] = ScreenType.matching
    prompt_html: str
    pairs: list[MatchPair] = Field(min_length=2)
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class SortItem(BaseModel):
    id: str
    text_html: str


class SortingScreen(ScreenBase):
    type: Literal[ScreenType.sorting] = ScreenType.sorting
    prompt_html: str
    items: list[SortItem] = Field(min_length=2)  # DOĞRU sıra (yazarın verdiği); runtime karıştırır
    feedback: Feedback = Field(default_factory=Feedback)
    points: int = 10


class TimelineEvent(BaseModel):
    date: str
    title: str
    body_html: str | None = None


class TimelineScreen(ScreenBase):
    type: Literal[ScreenType.timeline] = ScreenType.timeline
    prompt_html: str | None = None
    events: list[TimelineEvent] = Field(min_length=1)


class LottieScreen(ScreenBase):
    """Faz 7 — Lottie animasyonu (JSON asset). Lazy: yalnız bu tip varsa lottie lib yüklenir."""
    type: Literal[ScreenType.lottie] = ScreenType.lottie
    prompt_html: str | None = None
    lottie_asset_id: str
    loop: bool = True
    autoplay: bool = True


class SimStep(BaseModel):
    """Bir simülasyon adımı: ekran görüntüsü + ('şuraya tıkla' bölgesi VEYA 'şunu yaz' input'u) + ipucu.

    `input_accepted` verilirse adım YAZMA adımıdır (input alanı; kabul edilen cevaplardan biri yazılınca
    geçilir). Verilmezse TIKLAMA adımıdır (correct=True bölgeye tıklanınca geçilir). Faz 8.1 (Wooclap deseni).
    """
    image_asset_id: str
    instruction_html: str
    regions: list[HotspotRegion] = Field(default_factory=list)  # tıklama adımı için hedef(ler)
    input_accepted: list[str] | None = None  # verilirse YAZMA adımı: kabul edilen cevaplar
    input_label: str | None = None  # input için etiket/placeholder
    hint_html: str | None = None


class SimulationScreen(ScreenBase):
    """Faz 8 — rehberli çok-adımlı yazılım simülasyonu (İzle→Uygula→Sıra Sizde'nin 'Uygula'sı).
    Öğrenci her adımda doğru bölgeye tıklar; yanlışta ipucu, doğruda sonraki adıma geçer."""
    type: Literal[ScreenType.simulation] = ScreenType.simulation
    prompt_html: str | None = None
    steps: list[SimStep] = Field(min_length=1)
    points: int = 10
    feedback: Feedback = Field(default_factory=Feedback)


# --- Faz 12 (G2): dallanan karar senaryosu (skorlanır) -----------------------
class ScenarioChoice(BaseModel):
    """Bir düğümdeki karar seçeneği: metin + sonuç (gerekçe) + skor etkisi + sonraki düğüm.

    `goto_node_id` None ise bu seçim senaryoyu BİTİRİR (sonuç ekranı). `score_delta` negatif
    olabilir (kötü karar puan düşürür). Sonuç (`feedback_html`) seçimden SONRA gösterilir."""
    id: str
    text_html: str
    feedback_html: str  # seçimin sonucu/gerekçesi (NEDEN) — boş bırakma (anti-slop B3)
    score_delta: int = 0
    goto_node_id: str | None = None


class ScenarioNode(BaseModel):
    """Senaryonun bir karar noktası: durum metni (+ ops. görsel) + ≥2 seçenek."""
    id: str
    prompt_html: str
    image_asset_id: str | None = None
    choices: list[ScenarioChoice] = Field(min_length=2)


class DecisionScenarioScreen(ScreenBase):
    """Faz 12 (G2) — dallanan karar senaryosu: tek ekranda çok-adımlı, durum (skor) taşıyan
    anlatı 'try-mode'. Öğrenci kararlar verir; her kararın sonucu/gerekçesi + puan etkisi gösterilir;
    senaryo bir uç düğümde biter ve toplam skor `pass_score`'a göre geçer/kalır olarak skorlanır.
    `simulation` (yazılım dene) ve `branching` (ekranlar-arası dallanma) ile tamamlayıcı."""
    type: Literal[ScreenType.decision_scenario] = ScreenType.decision_scenario
    intro_html: str | None = None
    nodes: list[ScenarioNode] = Field(min_length=1)
    start_node_id: str | None = None  # None → ilk düğüm
    pass_score: int | None = None  # None → skor > 0 geçer; verilirse skor ≥ pass_score geçer
    points: int = 20
    feedback: Feedback = Field(default_factory=Feedback)


# --- Faz 13 (G3): yeni oyun + görsel ekran tipleri ---------------------------
class TermPair(BaseModel):
    """Terim ↔ tanım çifti (term_match_race)."""
    id: str
    term_html: str
    definition_html: str


class TermMatchRaceScreen(ScreenBase):
    """Faz 13 (G3) — süreli terim↔tanım eşleştirme oyunu. Öğrenci her terime doğru tanımı
    atar; geri sayım dolmadan eşleştirir. Skor = doğru oranı × points (+ kalan süre bonusu).
    `matching`in oyunlaştırılmış, süreli sürümü."""
    type: Literal[ScreenType.term_match_race] = ScreenType.term_match_race
    prompt_html: str | None = None
    pairs: list[TermPair] = Field(min_length=2)
    time_limit_sec: int = 60
    points: int = 15
    feedback: Feedback = Field(default_factory=Feedback)


class Puzzle(BaseModel):
    """Escape-room bulmacası: soru + kabul edilen cevap(lar) + ops. ipucu."""
    id: str
    prompt_html: str
    accepted: list[str] = Field(min_length=1)
    hint_html: str | None = None
    case_sensitive: bool = False


class EscapeRoomScreen(ScreenBase):
    """Faz 13 (G3) — kilitli bulmaca zinciri. Her bulmacayı çöz → sonraki açılır; yanlış →
    can azalır + ipucu. Tüm bulmacalar çözülürse geçer; can biterse kalır. Skorlanır."""
    type: Literal[ScreenType.escape_room] = ScreenType.escape_room
    intro_html: str | None = None
    puzzles: list[Puzzle] = Field(min_length=1)
    lives: int = 3
    points: int = 20
    feedback: Feedback = Field(default_factory=Feedback)


class DiagramLabel(BaseModel):
    """Etiketli diyagram işaretçisi: görseldeki bir noktaya (x,y; 0–1000 norm.) doğru etiket."""
    id: str
    text: str
    x: int  # 0–1000 normalize yatay
    y: int  # 0–1000 normalize dikey


class LabeledDiagramScreen(ScreenBase):
    """Faz 13 — etiketli diyagram: görseldeki numaralı işaretçilere doğru etiketi ata
    (anatomi/şema/harita). Görsel öğrenme; skorlanır."""
    type: Literal[ScreenType.labeled_diagram] = ScreenType.labeled_diagram
    prompt_html: str | None = None
    image_asset_id: str
    labels: list[DiagramLabel] = Field(min_length=2)
    points: int = 15
    feedback: Feedback = Field(default_factory=Feedback)


class ChartDatum(BaseModel):
    label: str
    value: float


class DataChartScreen(ScreenBase):
    """Faz 13 — veri-görseli (bar/line/pie). Sunucuda deterministik inline-SVG üretilir
    (dış lib/ağ YOK). İçerik ekranı (skorlanmaz) — pasif veri sunumu/karşılaştırma."""
    type: Literal[ScreenType.data_chart] = ScreenType.data_chart
    prompt_html: str | None = None
    chart_type: Literal["bar", "line", "pie"] = "bar"
    data: list[ChartDatum] = Field(min_length=1)
    caption: str | None = None


Screen = Annotated[
    Union[
        TitleSlide,
        ContentSlide,
        MCQScreen,
        TrueFalseScreen,
        FillBlankScreen,
        DragDropScreen,
        HotspotScreen,
        BranchingScreen,
        VideoScreen,
        SummaryScreen,
        AccordionScreen,
        TabsScreen,
        FlashcardsScreen,
        MatchingScreen,
        SortingScreen,
        TimelineScreen,
        LottieScreen,
        SimulationScreen,
        DecisionScenarioScreen,
        TermMatchRaceScreen,
        EscapeRoomScreen,
        LabeledDiagramScreen,
        DataChartScreen,
    ],
    Field(discriminator="type"),
]

QUIZ_TYPES = {
    ScreenType.mcq,
    ScreenType.true_false,
    ScreenType.fill_blank,
    ScreenType.drag_drop,
    ScreenType.hotspot,
    ScreenType.matching,
    ScreenType.sorting,
    ScreenType.simulation,
    ScreenType.decision_scenario,
    ScreenType.term_match_race,
    ScreenType.escape_room,
    ScreenType.labeled_diagram,
}


# --------------------------------------------------------------------------- #
# Varlık (CONTRACTS.md §1.5)
# --------------------------------------------------------------------------- #
class AssetRef(BaseModel):
    id: str
    filename: str
    mime: str
    size_bytes: int
    sha256: str
    rel_path: str


# --------------------------------------------------------------------------- #
# Proje (CONTRACTS.md §1.4)
# --------------------------------------------------------------------------- #
class Project(BaseModel):
    schema_version: str = "1.0"
    id: str
    title: str
    description: str = ""
    scorm_version: Literal["1.2", "2004"] = "1.2"
    language: str = "tr"
    theme: ThemeTokens = Field(default_factory=ThemeTokens)
    tracking: Tracking = Field(default_factory=Tracking)
    variables: list[Variable] = Field(default_factory=list)  # Faz 5
    points_var: str | None = None  # Faz 6 — header puan HUD'u (gösterilecek değişken adı)
    layout_mode: Literal["stage", "flow"] = "stage"  # Faz 9 — sabit-sahne (vars.) | tam-akış
    stage_width: int = 960   # Faz 9.1 — tasarım tuvali genişliği (px); 16:9 için 960×540
    stage_height: int = 540
    screens: list[Screen] = Field(default_factory=list)
    assets: list[AssetRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    owner_key_id: str = ""

    def asset_by_id(self, asset_id: str) -> AssetRef | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def screen_by_id(self, screen_id: str):
        return next((s for s in self.screens if s.id == screen_id), None)


# --------------------------------------------------------------------------- #
# CourseSpec — build_from_spec girdisi (CONTRACTS.md §2)
# --------------------------------------------------------------------------- #
class AssetInput(BaseModel):
    # Yazarın atadığı stabil id (ekranlar *_asset_id ile buna referans verir). Yoksa server üretir
    # ama o durumda ekranlardan referans verilemez. CONTRACTS.md §2.
    id: str | None = None
    filename: str
    source: str  # "data:<mime>;base64,..." | "https://..."


class CourseSpec(BaseModel):
    schema_version: str = "1.0"
    title: str
    description: str = ""
    scorm_version: Literal["1.2", "2004"] = "1.2"
    language: str = "tr"
    theme: Union[str, ThemeTokens] = "default"
    tracking: Tracking = Field(default_factory=Tracking)
    variables: list[Variable] = Field(default_factory=list)  # Faz 5
    points_var: str | None = None  # Faz 6
    layout_mode: Literal["stage", "flow"] = "stage"  # Faz 9 — sabit-sahne (vars.) | tam-akış
    stage_width: int = 960   # Faz 9.1 — ayarlanabilir tuval ölçüsü (px)
    stage_height: int = 540
    screens: list[Screen]
    assets: list[AssetInput] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Tool çıktı modelleri (CONTRACTS.md §3, §12.1)
# --------------------------------------------------------------------------- #
class CreateProjectOut(BaseModel):
    project_id: str


class AddScreenOut(BaseModel):
    screen_id: str


class OkOut(BaseModel):
    ok: bool = True


class ScreenSummary(BaseModel):
    id: str
    type: ScreenType
    title: str
    index: int


class ListScreensOut(BaseModel):
    screens: list[ScreenSummary]


class PreviewOut(BaseModel):
    inline_html: str
    hosted_url: str


class BuildOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    download_url: str | None = None
    size: int | None = None
    scorm_version: str
    error: str | None = None


class ValidationError(BaseModel):
    code: str
    message: str
    path: str | None = None


class ValidateOut(BaseModel):
    ok: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)  # Faz 1 — bloklamayan uyarılar


class BuildFromSpecOut(BaseModel):
    project_id: str
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    download_url: str | None = None


# AddAssetOut = AssetRef (CONTRACTS.md §3)
AddAssetOut = AssetRef
