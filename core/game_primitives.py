"""core/game_primitives.py — W2 mekanik primitif yapılandırma şemaları (Pydantic).

Bu modeller, oyun primitiflerinin GameSpec içinde nasıl DEKLARE edildiğini tanımlar; saf-mantık
JS karşılıkları components/engine/primitives/*.js'te (vitest). W3'te `game` düğümü bunları besler.
ŞU AN ADDITIVE: hiçbir mevcut şemaya bağlı değil, mevcut 26 ekran tipini etkilemez.

Her primitif bir a11y SÖZLEŞMESİ taşır (docs/GAME-A11Y.md):
- timer: süre uzat/kapat/duraklat (WCAG 2.2.1)
- hint_ladder: ipuçları METİN (ekran-okuyucu)
- branch_graph: seçimle navigasyon (klavye)
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


# --- timer -------------------------------------------------------------------
class TimerSpec(BaseModel):
    """Süre primitifi. Deterministik tick (runtime sürer). a11y: uzat/kapat zorunlu."""
    kind: Literal["timer"] = "timer"
    id: str
    duration_sec: int = Field(ge=0)
    mode: Literal["down", "up"] = "down"
    auto_expire: bool = True
    allow_extend: bool = True  # a11y 2.2.1 — kapalıysa validator (W6) uyarır
    allow_disable: bool = True


# --- score -------------------------------------------------------------------
class ScoreSpec(BaseModel):
    """Skor + streak + çarpan. İçsel-bütünleşme: çarpan öğrenme davranışını ödüllendirir."""
    kind: Literal["score"] = "score"
    id: str
    start: int = 0
    streak_step: int = Field(default=3, ge=1)  # kaç ardışık doğru → +1 çarpan
    max_multiplier: int = Field(default=3, ge=1)


# --- lives -------------------------------------------------------------------
class LivesSpec(BaseModel):
    kind: Literal["lives"] = "lives"
    id: str
    start: int = Field(default=3, ge=0)
    max: int | None = None


# --- hint_ladder -------------------------------------------------------------
class HintStep(BaseModel):
    text: str  # a11y: METİN (ekran-okuyucu erişilebilir)
    cost: int = 0  # puan/zaman maliyeti (scaffolding dengesi)


class HintLadderSpec(BaseModel):
    """Kademeli, maliyetli ipucu merdiveni (fading scaffolding)."""
    kind: Literal["hint_ladder"] = "hint_ladder"
    id: str
    hints: list[HintStep] = Field(min_length=1)


# --- item_bank (parametrik soru) ---------------------------------------------
class VarRange(BaseModel):
    min: int
    max: int


class AnswerExpr(BaseModel):
    op: Literal["add", "sub", "mul", "min", "max"] = "add"
    operands: list[str] = Field(min_length=1)  # değişken adları


class DistractorRule(BaseModel):
    offsets: list[int] = Field(default_factory=lambda: [-2, -1, 1, 2])


class StaticItem(BaseModel):
    id: str
    prompt: str
    answer: str
    distractors: list[str] = Field(default_factory=list)


class ParametricItem(BaseModel):
    id: str
    template: str  # "{{a}} + {{b}}"
    vars: dict[str, VarRange]
    answer: AnswerExpr
    distractors: DistractorRule = Field(default_factory=DistractorRule)


class ItemBankSpec(BaseModel):
    """Parametrik/statik soru bankası. Determinizm seed'li RNG'den (üretilebilir madde)."""
    kind: Literal["item_bank"] = "item_bank"
    id: str
    items: list[Union[ParametricItem, StaticItem]] = Field(min_length=1)


# --- branch_graph ------------------------------------------------------------
class BranchCondition(BaseModel):
    var: str
    cmp: Literal["==", "!=", ">", "<", ">=", "<="] = "=="
    value: Union[int, float, str, bool]


class BranchEffect(BaseModel):
    var: str
    op: Literal["set", "add"] = "add"
    value: Union[int, float, str, bool]


class BranchChoice(BaseModel):
    id: str
    to: str | None = None
    condition: BranchCondition | None = None
    effects: list[BranchEffect] = Field(default_factory=list)


class BranchNode(BaseModel):
    id: str
    choices: list[BranchChoice] = Field(default_factory=list)


class BranchGraphSpec(BaseModel):
    """Koşullu düğüm grafiği — dallanan senaryo/istasyon/quest substratı.
    W6 kuralı: her dalın sonuç farkı olmalı (sahte-seçim yasak)."""
    kind: Literal["branch_graph"] = "branch_graph"
    id: str
    nodes: list[BranchNode] = Field(min_length=1)
    start: str | None = None


# Primitif birliği — GameSpec `mechanics` ile kullanılır.
GamePrimitive = Union[
    TimerSpec, ScoreSpec, LivesSpec, HintLadderSpec, ItemBankSpec, BranchGraphSpec,
]

PRIMITIVE_KINDS = ("timer", "score", "lives", "hint_ladder", "item_bank", "branch_graph")


# --- W3: kural dili (when <olay> if <koşul> then <aksiyon>) -------------------
# Aksiyonlar deklaratif: `do` + parametreler. components/engine/rules.js ACTIONS ile eşleşir.
ACTION_DOS = (
    "score.correct", "score.wrong", "score.add",
    "lives.lose", "lives.gain", "timer.extend", "timer.disable",
    "hint.reveal", "var.set", "var.add", "emit",
)


class GameAction(BaseModel):
    do: Literal[
        "score.correct", "score.wrong", "score.add",
        "lives.lose", "lives.gain", "timer.extend", "timer.disable",
        "hint.reveal", "var.set", "var.add", "emit",
    ]
    # opsiyonel parametreler (aksiyona göre kullanılır)
    points: int | None = None
    value: Union[int, float, str, bool, None] = None
    var: str | None = None
    n: int | None = None
    sec: int | None = None
    event: str | None = None


class GameRule(BaseModel):
    """when <olay> if <koşul> then <aksiyonlar>. rules.js'in eşi."""
    when: str  # olay tipi (ör. "answer.correct", "choice.taken", "timer.expired")
    if_: BranchCondition | None = Field(default=None, alias="if")
    then: list[GameAction] = Field(min_length=1)

    model_config = {"populate_by_name": True}


class GameMechanics(BaseModel):
    """Bir oyunun kullandığı primitifler (hepsi opsiyonel — kompozisyon)."""
    score: ScoreSpec | None = None
    lives: LivesSpec | None = None
    timer: TimerSpec | None = None
    hints: HintLadderSpec | None = None
    item_bank: ItemBankSpec | None = None
    branch_graph: BranchGraphSpec | None = None


class GameDefinition(BaseModel):
    """Mekanik + kuralların kompozisyonu = bir oyunun MANTIK tanımı (sunumdan bağımsız).
    W3b GameScreen bunu bir ekran tipine + renderer'a bağlayacak; ECD üç-modeli docs'ta."""
    mechanics: GameMechanics = Field(default_factory=GameMechanics)
    rules: list[GameRule] = Field(default_factory=list)
    seed: str | None = None  # üretilebilir oynanış (None → kurs id'sinden türetilir)
