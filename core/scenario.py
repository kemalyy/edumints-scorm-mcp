"""core/scenario.py — Senaryo hattı Faz 2: senaryo dokümanı + boşluk raporu + derleyici.

Plan: docs/superpowers/plans/2026-07-30-scenario-line-plan.md (pazarlık-dışı 3.1–3.11).
Sıcak dosyalar (project.py/validator.py) İNCE kalsın diye Faz 2 mantığı bu YENİ modülde.

Katmanlar:
  1. Şema — Page / MediaSlot (Faz-3 sözleşmesi ŞİMDİ donar) / EvidenceDecl (ENUM + oneOf:
     pydantic discriminated union, her tür kendi ZORUNLU alt alanlarıyla, extra=forbid).
  2. Miras — objective EN-YAKIN-atadan (page.node_id'den yukarı yürü); hiç yoksa ORPHAN_PAGE.
     compiled objective_ids = [miras] + extra_objective_refs (dedup, sıra kararlı).
  3. gaps_report — derleme KAPISI: blockers (⛔) / warnings (⚠) / suggestions + kanıt-bağ
     kapsam tahmini. Blocker varken compile REDDEDER.
  4. compile_scenario — build_from_spec payload'u üretir. Faz adı (phase) SPEC'E ASLA
     YAZILMAZ (3.2 — Katman-1'e faz adı girmez; grep testi var).

Tasarım kararları (PR gövdesinde de belgeli):
  - md→html: repoda markdown çevirici YOK → minimal DETERMİNİSTİK çevirici (başlık/paragraf/
    liste/kalın/italik/kod/link). body_md içindeki HAM HTML ÖNCE kaçışlanır (literal görünür),
    çıktı ek olarak nh3 beyaz listesinden (components.renderer.sanitize) geçer → raw
    svg/canvas/script yapısal olarak imkânsız (3.10).
  - screen_type derlemede ZORUNLU: gaps yalnız ÖNERİR (asla otomatik seçmez); yazar öneriyi
    upsert ile kabul eder. Derlemede eksik/bilinmeyen screen_type = blocker.
  - Page.screen_payload: ekran-tipine özgü alanların (ör. mcq options/prompt_html) derlenen
    ekrana geçiş kanalı. Senaryo şeması soru bankası taşımaz; puanlı bir sayfanın otomatik
    puanlanabilir ekrana derlenebilmesi için tip-özgü yük şart. Derleyici temel alanları
    (id/title/type/objective_ids/evidence_screen_ids) OTORİTER yazar, payload kalanı doldurur.
  - Derlenen spec'te düğüm hedefleri KURS DÜZEYİNE taşınır (E2/H1/H3 lint'leri
    project.objectives okur) ve outline'dan çıkarılır (aksi hâlde hedef ad-alanı çakışması —
    core/validator.py sert hata). node pedagogy_pack → Objective.method_pack (E2 bedava).
  - NARRATION_ECHO algoritması: iki metin de HTML/markdown'dan arındırılır, küçük harfe
    çevrilir, \\w+ token kümeleri çıkarılır; örtüşme = |A∩B| / min(|A|,|B|) (containment).
    min(|A|,|B|) ≥ 5 iken oran ≥ 0.8 → WARN (narration gövdenin yankısı).
"""

from __future__ import annotations

import re
import warnings as _warnings
from datetime import datetime
from html import escape as _esc
from typing import Annotated, Literal, Union, get_args

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from ulid import ULID

from core.project import (
    QUIZ_TYPES,
    AssetRef,
    Objective,
    OutlineNode,
    Screen,
    ScreenType,
    utcnow,
)

# --------------------------------------------------------------------------- #
# ID üreticileri (CONTRACTS.md §0 deseni)
# --------------------------------------------------------------------------- #
def new_scenario_id() -> str:
    return f"scn_{ULID()}"


def new_page_id() -> str:
    return f"pg_{ULID()}"


# Sayfa/slot id'leri makine-dostu (outline node id alfabesiyle aynı — suspend/DOM güvenli).
_PAGE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


# --------------------------------------------------------------------------- #
# MediaSlot — Faz-3 sözleşmesi (fill_media_slot Faz 3'te; ŞEKİL burada donar)
# --------------------------------------------------------------------------- #
class MediaSlotA11y(BaseModel):
    """Erişilebilirlik zemin (3.5): kanıt-rolü slot doldurulurken alt_text boş olamaz
    (A11Y_NO_TEXT_ALT — Faz 3 fill_media_slot hatası). Şekil şimdi sabitlenir."""
    alt_text: str | None = None
    transcript_html: str | None = None
    captions_asset_id: str | None = None


class MediaSlot(BaseModel):
    """Sayfanın medya yuvası. role: kanit|aciklayici — DEKORATİF YOK (3.6; süs medya
    reddedilir). kind=model_3d renderer'da henüz desteklenmez → fallback_image_asset_id
    verilmezse SLOT_KIND_UNSUPPORTED uyarısı (gaps + derleme). asset_id None = boş slot
    (derlemede asset alanı hiç basılmaz; ekran anlamlı kalır). provenance Faz 3'te pakete
    gömülür (assets/PROVENANCE.json)."""
    slot_id: str
    role: Literal["kanit", "aciklayici"]
    kind: Literal["image", "audio", "video", "lottie", "model_3d", "data_chart"]
    spec: str
    source_hint: str | None = None
    asset_id: str | None = None
    a11y: MediaSlotA11y = Field(default_factory=MediaSlotA11y)
    provenance: dict | None = None
    # Faz 3 — donmuş sözleşmeye TEK ek (additive; PR'da bayraklı): render yolu olmayan
    # kind'lar (bugün model_3d) için 2D yedek görsel. Derleme, model_3d yuvasını bu görselle
    # image olarak bağlar; yoksa yuva atlanır + SLOT_KIND_UNSUPPORTED uyarısı.
    fallback_image_asset_id: str | None = None

    @field_validator("slot_id")
    @classmethod
    def _validate_slot_id(cls, v: str) -> str:
        if not _PAGE_ID_RE.match(v):
            raise ValueError(f"MediaSlot.slot_id makine-dostu olmalı ([A-Za-z0-9_.-], 1-64): {v!r}")
        return v


# --------------------------------------------------------------------------- #
# EvidenceDecl — kanıt beyanı ENUM'u (oneOf: discriminated union + extra=forbid)
# --------------------------------------------------------------------------- #
class _EvidenceBase(BaseModel):
    # extra=forbid → türler gerçekten AYRIK: bir türün alanı diğerine sızamaz (oneOf).
    model_config = ConfigDict(extra="forbid")


class EvidenceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class IslenmisOrnekEvidence(_EvidenceBase):
    """Çözümlü örnek: ≥2 adım, her adım eylem + gerekçe (Renkl self-explanation)."""
    kind: Literal["islenmis_ornek"] = "islenmis_ornek"
    steps: list[EvidenceStep] = Field(min_length=2)


class AnotasyonluArtefaktEvidence(_EvidenceBase):
    """Anotasyonlu artefakt: slot_id ya da sayfa referansı + ≥1 anotasyon."""
    kind: Literal["anotasyonlu_artefakt"] = "anotasyonlu_artefakt"
    artefakt_ref: str = Field(min_length=1)
    anotasyonlar: list[str] = Field(min_length=1)


class KarsitCiftEvidence(_EvidenceBase):
    """Karşıt çift: doğru örnek + bozuk örnek + aradaki FARK (kritik özellik)."""
    kind: Literal["karsit_cift"] = "karsit_cift"
    dogru: str = Field(min_length=1)
    bozuk: str = Field(min_length=1)
    fark: str = Field(min_length=1)


class OgrenciKesfiEvidence(_EvidenceBase):
    """Öğrenci keşfi: kayıt yöntemi (exploration-benzeri açıklama) + taahhüt istemi.
    SKORLANMAZ — skorlanırsa gaps PREDICTION_SCORED blocker'ı üretir (tahmin-yarışı yasağı)."""
    kind: Literal["ogrenci_kesfi"] = "ogrenci_kesfi"
    kayit_yontemi: str = Field(min_length=1)
    commit_prompt: str = Field(min_length=1)


class HataliOrnekEvidence(_EvidenceBase):
    """Hatalı örnek: hata + NEDEN yanlış + doğru karşılık."""
    kind: Literal["hatali_ornek"] = "hatali_ornek"
    hata: str = Field(min_length=1)
    neden_yanlis: str = Field(min_length=1)
    dogru_karsilik: str = Field(min_length=1)


EvidenceDecl = Annotated[
    Union[
        IslenmisOrnekEvidence,
        AnotasyonluArtefaktEvidence,
        KarsitCiftEvidence,
        OgrenciKesfiEvidence,
        HataliOrnekEvidence,
    ],
    Field(discriminator="kind"),
]

_EVIDENCE_ADAPTER: TypeAdapter = TypeAdapter(EvidenceDecl)


def parse_evidence(data: dict):
    """Kanıt beyanını doğrula (oneOf). Hata → pydantic ValidationError (çağıran sarar)."""
    return _EVIDENCE_ADAPTER.validate_python(data)


# --------------------------------------------------------------------------- #
# Page + ScenarioDocument
# --------------------------------------------------------------------------- #
class PageCopy(BaseModel):
    body_md: str | None = None
    narration: str | None = None


class PageScoring(BaseModel):
    scored: bool = False
    points: int | None = Field(default=None, ge=0)


_warnings.filterwarnings(  # alan adı `copy` plan sözleşmesidir; BaseModel.copy zaten v2'de deprecated
    "ignore", message='Field name "copy" in "Page" shadows an attribute')


class Page(BaseModel):
    """Senaryo sayfası. `phase` YALNIZ yazarlık/gaps katmanındadır — derlenen spec'e ASLA
    yazılmaz (3.2). `screen_type` öneri-kabul modelidir: gaps önerir, yazar upsert ile seçer,
    derleme açık değer İSTER. `screen_payload` tip-özgü ekran alanlarının geçiş kanalıdır
    (modül docstring'ine bakın)."""
    id: str
    node_id: str
    order: int = 0
    title: str
    phase: str | None = None
    screen_type: str | None = None
    copy: PageCopy = Field(default_factory=PageCopy)
    media_slots: list[MediaSlot] = Field(default_factory=list)
    evidence: EvidenceDecl | None = None
    evidence_from: list[str] = Field(default_factory=list)
    scoring: PageScoring = Field(default_factory=PageScoring)
    extra_objective_refs: list[str] = Field(default_factory=list)
    duration_hint_sec: int | None = Field(default=None, ge=0)
    notes: str | None = None
    screen_payload: dict = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _PAGE_ID_RE.match(v):
            raise ValueError(f"Page.id makine-dostu olmalı ([A-Za-z0-9_.-], 1-64): {v!r}")
        return v

    @model_validator(mode="after")
    def _unique_slot_ids(self) -> "Page":
        seen: set[str] = set()
        for s in self.media_slots:
            if s.slot_id in seen:
                raise ValueError(f"Yinelenen media slot_id: {s.slot_id}")
            seen.add(s.slot_id)
        return self


class ScenarioDocument(BaseModel):
    """Senaryo dokümanı — anahtar başına sahipli (owner_key_id, projeler gibi), store'da tek
    JSON blob (schema_version: 1). Boyutu kota hesabına dahildir (Store.total_bytes)."""
    schema_version: int = 1
    id: str
    title: str
    audience_pack: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,64}$")
    duration_target_sec: int | None = Field(default=None, ge=1)
    dial_overrides: dict | None = None
    outline: list[OutlineNode] = Field(default_factory=list)
    pages: list[Page] = Field(default_factory=list)
    # Faz 3 — senaryo VARLIK EVİ: projelerle aynı AssetRef şekli, aynı Store.put_asset
    # mekaniği (ad-alanı = scenario_id). fill_media_slot buraya yazar; sha256 içerik-dedup
    # bu listede yapılır. Derlemede server katmanı bunları build_from_spec assets[]'ine
    # data: URI olarak enjekte eder (asset id'ler korunur → slot referansları geçerli kalır).
    assets: list[AssetRef] = Field(default_factory=list)
    # Faz 4-ek — ID KARARLILIĞI (madde-2 ön koşulu): silinen sayfa/düğüm id'leri buraya
    # yazılır ve YENİDEN KULLANILAMAZ (upsert reddeder — server katmanı). Neden: suspend
    # pozisyon kaydı (z) ve kimlik-tabanlı resume, id'lerin ANLAM DEĞİŞTİRMEMESİNE dayanır;
    # silinip başka içerikle geri gelen bir id, eski öğrencinin devam noktasını/skorunu
    # YANLIŞ içeriğe bağlardı. Derleyici id'leri asla pozisyonel yeniden numaralandırmaz
    # (compile passthrough — testli); bu liste sözleşmenin silme tarafını SERT kılar.
    # Ek alan pydantic'te varsayılanlı → eski store blob'ları migrasyonsuz okunur.
    retired_ids: list[str] = Field(default_factory=list)
    owner_key_id: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def page_by_id(self, page_id: str) -> Page | None:
        return next((p for p in self.pages if p.id == page_id), None)

    def node_by_id(self, node_id: str) -> OutlineNode | None:
        return next((n for n in self.outline if n.id == node_id), None)

    def asset_by_sha256(self, sha256: str) -> AssetRef | None:
        """İçerik-hash indeksi (kabul #9): aynı bayt → aynı asset (dedup fill'de)."""
        return next((a for a in self.assets if a.sha256 == sha256), None)


# --------------------------------------------------------------------------- #
# Yapısal doğrulama (Faz 1 validator kurallarının senaryo-dokümanı izdüşümü)
# --------------------------------------------------------------------------- #
OUTLINE_MAX_DEPTH = 3  # core/validator.OUTLINE_MAX_DEPTH ile aynı sözleşme (kök=1)


def validate_scenario_structure(doc: ScenarioDocument) -> list[str]:
    """Upsert-zamanı SERT yapı denetimi (3.8 veri bütünlüğü): yinelenen düğüm/sayfa id'si,
    sarkan parent_id, döngü, derinlik>3, düğüm-hedef ad-alanı çakışması. Sayfa→düğüm sarkan
    referansı BURADA DEĞİL gaps'tedir (DANGLING_NODE_REF blocker) — yazar sayfayı düğümden
    önce taslaklayabilir; kapı derlemededir."""
    errors: list[str] = []
    node_ids: set[str] = set()
    for n in doc.outline:
        if n.id in node_ids:
            errors.append(f"Yinelenen outline düğüm id'si: {n.id}")
        node_ids.add(n.id)

    by_id = {n.id: n for n in doc.outline}
    for n in doc.outline:
        if n.parent_id is not None and n.parent_id not in node_ids:
            errors.append(f"Bilinmeyen outline parent_id referansı: {n.parent_id} ('{n.id}')")

    for n in doc.outline:
        depth, seen, cur = 1, {n.id}, n
        while cur.parent_id is not None:
            if cur.parent_id in seen:
                errors.append(f"Outline'da döngü: '{n.id}' düğümünün atalar zinciri kendine dönüyor")
                break
            if cur.parent_id not in by_id:
                break  # sarkan parent — yukarıda raporlandı
            cur = by_id[cur.parent_id]
            seen.add(cur.id)
            depth += 1
        else:
            if depth > OUTLINE_MAX_DEPTH:
                errors.append(
                    f"Outline derinlik sınırı aşıldı: '{n.id}' {depth}. kademede "
                    f"(en çok {OUTLINE_MAX_DEPTH}, kök=1)")

    obj_ids: set[str] = set()
    for n in doc.outline:
        if n.objective is not None:
            if n.objective.id in obj_ids:
                errors.append(f"Yinelenen hedef id'si: {n.objective.id} ('{n.id}' düğümü)")
            obj_ids.add(n.objective.id)

    page_ids: set[str] = set()
    for p in doc.pages:
        if p.id in page_ids:
            errors.append(f"Yinelenen sayfa id'si: {p.id}")
        page_ids.add(p.id)
    return errors


# --------------------------------------------------------------------------- #
# Miras — objective en-yakın-atadan; pedagogy_pack aynı yürüyüşle
# --------------------------------------------------------------------------- #
def _node_chain(doc: ScenarioDocument, node_id: str) -> list[OutlineNode]:
    """page.node_id'den köke doğru düğüm zinciri (kendisi dahil). Sarkan/döngülü zincirde
    güvenli durur (yapı denetimi zaten sert hata üretir)."""
    by_id = {n.id: n for n in doc.outline}
    chain: list[OutlineNode] = []
    seen: set[str] = set()
    cur = by_id.get(node_id)
    while cur is not None and cur.id not in seen:
        chain.append(cur)
        seen.add(cur.id)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return chain


def inherited_objective(doc: ScenarioDocument, page: Page) -> Objective | None:
    """EN YAKIN atanın hedefi kazanır (iki atalı zincirde yakın olan gölgeler — testli).
    Zincirde hiç hedef yok → None (gaps ORPHAN_PAGE ⛔ üretir)."""
    for n in _node_chain(doc, page.node_id):
        if n.objective is not None:
            return n.objective
    return None


def resolve_pedagogy_pack(doc: ScenarioDocument, page: Page) -> str | None:
    """Sayfanın düğüm zincirindeki EN YAKIN pedagogy_pack beyanı (phase doğrulaması +
    compile method_pack zenginleştirmesi için)."""
    for n in _node_chain(doc, page.node_id):
        if n.pedagogy_pack:
            return n.pedagogy_pack
    return None


def _nearest_pack_for_node(doc: ScenarioDocument, node: OutlineNode) -> str | None:
    by_id = {n.id: n for n in doc.outline}
    seen: set[str] = set()
    cur: OutlineNode | None = node
    while cur is not None and cur.id not in seen:
        if cur.pedagogy_pack:
            return cur.pedagogy_pack
        seen.add(cur.id)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return None


def compiled_objective_ids(doc: ScenarioDocument, page: Page) -> list[str]:
    """[miras edilen] + extra_objective_refs — dedup, sıra kararlı (koordinatör düzeltmesi:
    çoğul hedef korunur)."""
    out: list[str] = []
    inh = inherited_objective(doc, page)
    if inh is not None:
        out.append(inh.id)
    for r in page.extra_objective_refs:
        if r not in out:
            out.append(r)
    return out


def objective_namespace(doc: ScenarioDocument) -> list[str]:
    """Senaryo dokümanının hedef AD-ALANI = outline düğüm hedefleri (beyan sırasıyla)."""
    return [n.objective.id for n in doc.outline if n.objective is not None]


# --------------------------------------------------------------------------- #
# gaps_report — derleme KAPISI
# --------------------------------------------------------------------------- #
_SCOREABLE_TYPE_VALUES = frozenset(t.value for t in QUIZ_TYPES)
_SCREEN_TYPE_VALUES = frozenset(t.value for t in ScreenType)

# NARRATION_ECHO parametreleri (belgeli algoritma — modül docstring'i)
_ECHO_MIN_TOKENS = 5
_ECHO_THRESHOLD = 0.8


def _tokens(text: str) -> set[str]:
    text = re.sub(r"<[^>]+>", " ", text)          # HTML etiketleri
    text = re.sub(r"[#*_`>\[\]()!-]", " ", text)  # markdown süsleri
    return set(re.findall(r"\w+", text.lower()))


def _narration_echo_ratio(narration: str, body_md: str) -> float:
    a, b = _tokens(narration), _tokens(body_md)
    if min(len(a), len(b)) < _ECHO_MIN_TOKENS:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _item(code: str, message: str, path: str) -> dict:
    return {"code": code, "message": message, "path": path}


def suggest_screen_type(page: Page) -> str:
    """Deterministik öneri (faz+slot+skor+kanıt türünden) — YALNIZ öneri, asla otomatik
    seçilmez (plan: screen_type önerir-seçmez)."""
    if page.evidence is not None:
        k = page.evidence.kind
        if k == "islenmis_ornek":
            return "worked_example"
        if k == "ogrenci_kesfi":
            return "exploration"
        if k == "karsit_cift" and any(s.kind == "image" for s in page.media_slots):
            return "image_compare"
        return "content_slide"
    if page.scoring.scored:
        return "mcq"
    kinds = {s.kind for s in page.media_slots}
    for kind, st in (("video", "video"), ("lottie", "lottie"), ("data_chart", "data_chart")):
        if kind in kinds:
            return st
    return "content_slide"


def gaps_report(doc: ScenarioDocument) -> dict:
    """{blockers, warnings, suggestions, evidence_binding_coverage_estimate}.

    Blocker (⛔ — derlemeyi reddettirir): ORPHAN_PAGE, DANGLING_NODE_REF,
    DANGLING_EVIDENCE_FROM, DANGLING_OBJECTIVE_REF, SCORED_NO_EVIDENCE_FROM,
    OBJECTIVE_NO_EVIDENCE, EVIDENCE_KIND_MISSING, PREDICTION_SCORED, AUTO_GRADE_OPEN_TEXT.
    Warning (⚠ — danışsal): EMPTY_MEDIA_SLOTS, PHASE_NOT_IN_PACK, DURATION_DRIFT,
    NARRATION_ECHO. Suggestion: SCREEN_TYPE_SUGGESTION (asla otomatik seçilmez).
    Tüm denetimler SIRA-BAĞIMSIZDIR (3.9 — pozisyon denetimi yok; kabul #8)."""
    blockers: list[dict] = []
    warnings: list[dict] = []
    suggestions: list[dict] = []

    node_ids = {n.id for n in doc.outline}
    obj_ns = set(objective_namespace(doc))
    page_ids = {p.id for p in doc.pages}
    by_page = {p.id: p for p in doc.pages}

    for p in doc.pages:
        path = f"pages[{p.id}]"

        # düğüm bağı + hedef mirası
        if p.node_id not in node_ids:
            blockers.append(_item(
                "DANGLING_NODE_REF",
                f"Sayfa '{p.id}' bilinmeyen düğüme bağlı: '{p.node_id}'", f"{path}.node_id"))
        elif inherited_objective(doc, p) is None:
            blockers.append(_item(
                "ORPHAN_PAGE",
                f"Sayfa '{p.id}' hedefsiz (⛔): '{p.node_id}' düğüm zincirinde hiçbir atada "
                "objective yok — en yakın ataya hedef ekle ya da sayfayı hedefli düğüme taşı",
                path))

        # sarkan referanslar
        for eid in p.evidence_from:
            if eid == p.id:
                blockers.append(_item(
                    "DANGLING_EVIDENCE_FROM",
                    f"Sayfa '{p.id}' kendi kendinin kanıtı olamaz (evidence_from: '{eid}')",
                    f"{path}.evidence_from"))
            elif eid not in page_ids:
                blockers.append(_item(
                    "DANGLING_EVIDENCE_FROM",
                    f"Sayfa '{p.id}' kanıt referansı sarkıyor: '{eid}' dokümanda yok",
                    f"{path}.evidence_from"))
        for r in p.extra_objective_refs:
            if r not in obj_ns:
                blockers.append(_item(
                    "DANGLING_OBJECTIVE_REF",
                    f"Sayfa '{p.id}' bilinmeyen hedefe referans veriyor: '{r}' (hedef ad-alanı "
                    "= outline düğüm hedefleri)", f"{path}.extra_objective_refs"))

        # skor ↔ kanıt bağı
        if p.scoring.scored and not p.evidence_from:
            blockers.append(_item(
                "SCORED_NO_EVIDENCE_FROM",
                f"Puanlı sayfa '{p.id}' hiçbir kanıt sayfasına bağlı değil (evidence_from boş) "
                "— cevabı ÜRETEN sayfayı beyan et (K1)", f"{path}.evidence_from"))

        # kanıt beyanı tutarlılığı
        if p.evidence is None and any(s.role == "kanit" for s in p.media_slots):
            blockers.append(_item(
                "EVIDENCE_KIND_MISSING",
                f"Sayfa '{p.id}' kanıt-rolü medya yuvası taşıyor ama EvidenceDecl yok — "
                "kanıt türünü (islenmis_ornek|anotasyonlu_artefakt|karsit_cift|ogrenci_kesfi|"
                "hatali_ornek) beyan et", f"{path}.evidence"))
        if p.evidence is not None and p.evidence.kind == "ogrenci_kesfi" and p.scoring.scored:
            blockers.append(_item(
                "PREDICTION_SCORED",
                f"Sayfa '{p.id}' öğrenci keşfini PUANLIYOR — tahmin taahhüdü skorlanamaz "
                "(keşfi tahmin-yarışına çevirir; 3.8)", f"{path}.scoring"))
        if p.scoring.scored and p.screen_type and p.screen_type not in _SCOREABLE_TYPE_VALUES:
            blockers.append(_item(
                "AUTO_GRADE_OPEN_TEXT",
                f"Puanlı sayfa '{p.id}' otomatik puanlanamayan ekran tipinde: "
                f"'{p.screen_type}' (seçeneksiz/açık-metin içerik makinece puanlanamaz) — "
                "quiz tipi seç ya da scored=false yap", f"{path}.screen_type"))

        # ⚠ faz ↔ paket
        if p.phase:
            pack_id = resolve_pedagogy_pack(doc, p)
            if pack_id:
                from core.antislop import _load_packs  # E2 vendored manifest (yeniden kullanım)
                pack = _load_packs().get(pack_id)
                if pack is not None:
                    phase_ids = {ph.get("id") for ph in pack.get("phases") or []}
                    if p.phase not in phase_ids:
                        warnings.append(_item(
                            "PHASE_NOT_IN_PACK",
                            f"Sayfa '{p.id}' fazı '{p.phase}' beyan edilen '{pack_id}' "
                            f"paketinin fazlarında yok ({', '.join(sorted(filter(None, phase_ids)))})",
                            f"{path}.phase"))

        # ⚠ render yolu olmayan kind (Faz 3): model_3d, fallback görsel ister
        for s in p.media_slots:
            if s.kind == "model_3d" and not s.fallback_image_asset_id:
                warnings.append(_item(
                    "SLOT_KIND_UNSUPPORTED",
                    f"Sayfa '{p.id}' yuvası '{s.slot_id}' model_3d — renderer'da render yolu "
                    "yok; fallback_image_asset_id (2D yedek görsel) ekle, yoksa derlemede "
                    "yuva atlanır", f"{path}.media_slots[{s.slot_id}]"))

        # ⚠ narration ↔ gövde yankısı
        if p.copy.narration and p.copy.body_md:
            ratio = _narration_echo_ratio(p.copy.narration, p.copy.body_md)
            if ratio >= _ECHO_THRESHOLD:
                warnings.append(_item(
                    "NARRATION_ECHO",
                    f"Sayfa '{p.id}' seslendirmesi gövde metninin yankısı (token örtüşmesi "
                    f"{ratio:.2f} ≥ {_ECHO_THRESHOLD}) — narration gövdeyi OKUMAMALI, "
                    "tamamlamalı (modality ilkesi)", f"{path}.copy"))

        # öneri: screen_type (yalnız öneri — asla otomatik seçim)
        if p.screen_type is None:
            st = suggest_screen_type(p)
            suggestions.append({**_item(
                "SCREEN_TYPE_SUGGESTION",
                f"Sayfa '{p.id}' için öneri: '{st}' (faz+slot+skor+kanıt türünden; derleme "
                "açık screen_type ister — kabul edersen upsert ile yaz)",
                f"{path}.screen_type"), "suggested_screen_type": st})

    # ⛔ hedef başına: ≥1 puanlı sayfa ama SIFIR kanıt-taşıyan sayfa
    obj_pages: dict[str, list[Page]] = {oid: [] for oid in obj_ns}
    for p in doc.pages:
        for oid in compiled_objective_ids(doc, p):
            if oid in obj_pages:
                obj_pages[oid].append(p)
    for oid in objective_namespace(doc):
        plist = obj_pages.get(oid, [])
        if any(p.scoring.scored for p in plist) and not any(p.evidence for p in plist):
            blockers.append(_item(
                "OBJECTIVE_NO_EVIDENCE",
                f"Hedef '{oid}' puanlı sayfa içeriyor ama HİÇ kanıt-taşıyan sayfası yok — "
                "kanıt beyanlı (EvidenceDecl) bir sayfa ekle", f"objectives[{oid}]"))

    # ⚠ boş medya yuvaları (sayı)
    empty = [(p.id, s.slot_id) for p in doc.pages for s in p.media_slots if s.asset_id is None]
    if empty:
        warnings.append(_item(
            "EMPTY_MEDIA_SLOTS",
            f"{len(empty)} boş medya yuvası var (doldurma Faz 3 fill_media_slot): "
            + ", ".join(f"{pid}/{sid}" for pid, sid in empty[:10])
            + ("…" if len(empty) > 10 else ""), "pages"))

    # ⚠ süre toplamı vs hedef (±%20)
    if doc.duration_target_sec:
        total = sum(p.duration_hint_sec or 0 for p in doc.pages)
        if total > 0 and abs(total - doc.duration_target_sec) > 0.2 * doc.duration_target_sec:
            warnings.append(_item(
                "DURATION_DRIFT",
                f"Sayfa süre ipuçları toplamı ({total}s) hedeften ({doc.duration_target_sec}s) "
                "±%20'den fazla sapıyor", "duration_target_sec"))

    # kanıt-bağ kapsam TAHMİNİ: puanlı sayfaların kaçı kanıt-beyanlı bir sayfaya bağlı
    scored = [p for p in doc.pages if p.scoring.scored]
    if not scored:
        coverage = 1.0
    else:
        ok = sum(1 for p in scored
                 if any(eid in by_page and by_page[eid].evidence is not None
                        and eid != p.id for eid in p.evidence_from))
        coverage = ok / len(scored)

    return {
        "blockers": blockers,
        "warnings": warnings,
        "suggestions": suggestions,
        "evidence_binding_coverage_estimate": round(coverage, 3),
    }


# --------------------------------------------------------------------------- #
# md → html (minimal deterministik; ham HTML kaçışlanır; çıktı nh3'ten geçer)
# --------------------------------------------------------------------------- #
_INLINE_RULES = (
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
)
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_UL_ITEM_RE = re.compile(r"^[-*]\s+")
_OL_ITEM_RE = re.compile(r"^\d+[.)]\s+")


def _md_inline(text: str) -> str:
    out = _esc(text, quote=False)
    out = _LINK_RE.sub(r'<a href="\2">\1</a>', out)
    for rx, rep in _INLINE_RULES:
        out = rx.sub(rep, out)
    return out


def md_to_html(md: str) -> str:
    """Minimal DETERMİNİSTİK markdown→HTML: #..###### başlık, -/* liste, 1. sıralı liste,
    paragraf; satır içi **kalın** *italik* `kod` [metin](https://…). Ham HTML KAÇIŞLANIR
    (literal görünür — tek zengin kanal markdown'dur); çıktı ek olarak
    components.renderer.sanitize (nh3 beyaz listesi) süzgecinden geçer → raw
    svg/canvas/script yapısal olarak imkânsız (3.10)."""
    blocks = re.split(r"\n\s*\n", md.strip())
    parts: list[str] = []
    for block in blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", lines[0])
        if m and len(lines) == 1:
            level = len(m.group(1))
            parts.append(f"<h{level}>{_md_inline(m.group(2))}</h{level}>")
            continue
        if all(_UL_ITEM_RE.match(ln) for ln in lines):
            items = "".join(f"<li>{_md_inline(_UL_ITEM_RE.sub('', ln))}</li>" for ln in lines)
            parts.append(f"<ul>{items}</ul>")
            continue
        if all(_OL_ITEM_RE.match(ln) for ln in lines):
            items = "".join(f"<li>{_md_inline(_OL_ITEM_RE.sub('', ln))}</li>" for ln in lines)
            parts.append(f"<ol>{items}</ol>")
            continue
        parts.append(f"<p>{_md_inline(' '.join(lines))}</p>")
    html = "".join(parts)
    from components.renderer import sanitize  # lazy: core→components döngüsüz tek yön
    return sanitize(html)


# --------------------------------------------------------------------------- #
# compile_scenario — build_from_spec payload'u
# --------------------------------------------------------------------------- #
class ScenarioCompileError(Exception):
    """⛔ blocker'lar varken derleme REDDEDİLİR — blocker listesi taşınır."""

    def __init__(self, blockers: list[dict]):
        self.blockers = blockers
        super().__init__("; ".join(f"{b['code']}: {b['message']}" for b in blockers[:8]))


_SCREEN_ADAPTER: TypeAdapter = TypeAdapter(Screen)


def _screen_classes() -> dict[str, type[BaseModel]]:
    union = get_args(Screen)[0]
    out: dict[str, type[BaseModel]] = {}
    for cls in get_args(union):
        t = cls.model_fields["type"].default
        out[str(getattr(t, "value", t))] = cls
    return out


_SCREEN_CLASSES = _screen_classes()


def _evidence_blocks(ev) -> list[dict]:
    """content_slide'a derlenen kanıt beyanından ARTEFAKT blokları üret (K1: düz iddia-metni
    slaytı kanıt taşıyamaz — bloklu content_slide taşır)."""
    e = _esc
    if ev.kind == "karsit_cift":
        return [{"html": f"<h3>Doğru örnek</h3><p>{e(ev.dogru, quote=False)}</p>"},
                {"html": f"<h3>Bozuk örnek</h3><p>{e(ev.bozuk, quote=False)}</p>"},
                {"html": f"<h3>Fark</h3><p>{e(ev.fark, quote=False)}</p>"}]
    if ev.kind == "hatali_ornek":
        return [{"html": f"<h3>Hatalı örnek</h3><p>{e(ev.hata, quote=False)}</p>"},
                {"html": f"<h3>Neden yanlış?</h3><p>{e(ev.neden_yanlis, quote=False)}</p>"},
                {"html": f"<h3>Doğrusu</h3><p>{e(ev.dogru_karsilik, quote=False)}</p>"}]
    if ev.kind == "anotasyonlu_artefakt":
        notes = "".join(f"<li>{e(a, quote=False)}</li>" for a in ev.anotasyonlar)
        return [{"html": f"<h3>Artefakt: {e(ev.artefakt_ref, quote=False)}</h3><ul>{notes}</ul>"}]
    return []


def _store_key_from(page_id: str) -> str:
    key = re.sub(r"[^a-z0-9_-]", "-", page_id.lower())[:64]
    return key or "kesif"


def _attach_slots(page: Page, scr: dict, cls: type[BaseModel], warnings: list[dict]) -> None:
    """Dolu slotları ekran alanlarına bağla; BOŞ slot → asset alanı hiç basılmaz (ekran
    anlamlı kalır). Kind→alan eşlemesi (Faz 3): image VE data_chart → görsel alanları
    (data_chart slotu render edilmiş GRAFİK GÖRSELİ taşır — data_chart EKRANI veri taşır,
    orada bağlanacak alan yoktur → SLOT_NOT_ATTACHED); model_3d → fallback_image_asset_id
    görsel olarak bağlanır, yoksa SLOT_KIND_UNSUPPORTED uyarısıyla atlanır."""
    fields = cls.model_fields
    for s in page.media_slots:
        path = f"pages[{page.id}].media_slots[{s.slot_id}]"
        kind, asset_id = s.kind, s.asset_id
        if kind == "model_3d":
            if s.fallback_image_asset_id:
                kind, asset_id = "image", s.fallback_image_asset_id  # render yolu = 2D yedek
            else:
                warnings.append(_item(
                    "SLOT_KIND_UNSUPPORTED",
                    f"'{s.slot_id}' yuvası model_3d — render yolu yok; "
                    "fallback_image_asset_id ekle (yuva atlandı)", path))
                continue
        if not asset_id:
            continue  # boş slot → omit (fill_media_slot dolduracak)
        attached = False
        if kind in ("image", "data_chart"):
            for fld, alt in (("media_asset_id", "media_alt"), ("image_asset_id", "image_alt")):
                if fld in fields and not scr.get(fld):
                    scr[fld] = asset_id
                    if alt in fields and s.a11y.alt_text:
                        scr[alt] = s.a11y.alt_text
                    attached = True
                    break
        elif kind == "audio":
            if not scr.get("narration_asset_id"):
                scr["narration_asset_id"] = asset_id
                attached = True
        elif kind == "video":
            if "video_asset_id" in fields and not scr.get("video_asset_id"):
                scr["video_asset_id"] = asset_id
                attached = True
        elif kind == "lottie":
            if "lottie_asset_id" in fields and not scr.get("lottie_asset_id"):
                scr["lottie_asset_id"] = asset_id
                attached = True
        if not attached:
            warnings.append(_item(
                "SLOT_NOT_ATTACHED",
                f"Dolu yuva '{s.slot_id}' ({s.kind}) '{page.screen_type}' ekranında uygun boş "
                "alan bulamadı — yuva atlandı", path))


def _page_to_screen(doc: ScenarioDocument, page: Page, warnings: list[dict]) -> dict:
    st = page.screen_type or ""
    cls = _SCREEN_CLASSES[st]
    fields = cls.model_fields

    scr = dict(page.screen_payload)
    scr.pop("phase", None)  # 3.2 — faz adı Katman-1'e HİÇBİR kanaldan giremez (grep testi)
    scr["type"] = st
    scr["id"] = page.id
    scr["title"] = page.title
    scr["node_id"] = page.node_id
    if page.duration_hint_sec is not None:
        scr["duration_hint_sec"] = page.duration_hint_sec
    if page.notes:
        scr["notes"] = page.notes
    if page.copy.narration and not scr.get("narration_text"):
        scr["narration_text"] = page.copy.narration

    # copy.body_md → sanitize edilmiş HTML (tipin taşıyabildiği ilk gövde alanına)
    body_html = md_to_html(page.copy.body_md) if page.copy.body_md else None
    if body_html:
        for fld in ("body_html", "prompt_html", "intro_html"):
            if fld in fields and not scr.get(fld):
                scr[fld] = body_html
                break

    # kanıt beyanından içerik türet (payload verilmişse payload kazanır)
    ev = page.evidence
    if ev is not None:
        if st == "worked_example" and ev.kind == "islenmis_ornek" and not scr.get("steps"):
            scr["steps"] = [{"action_html": _esc(s.action, quote=False),
                             "rationale_html": _esc(s.reasoning, quote=False)}
                            for s in ev.steps]
        elif st == "exploration" and ev.kind == "ogrenci_kesfi":
            scr.setdefault("prompt_html", _esc(ev.commit_prompt, quote=False))
            scr.setdefault("store_key", _store_key_from(page.id))
            scr.setdefault("input_kind", "text")
        elif st == "content_slide" and not scr.get("blocks"):
            blocks = _evidence_blocks(ev)
            if blocks:
                if scr.get("body_html"):
                    blocks = [{"html": scr.pop("body_html")}] + blocks
                scr["blocks"] = blocks

    # hedef + kanıt bağları (yalnız alanı TAŞIYAN tiplere; derleyici otoriter)
    if "objective_ids" in fields:
        oids = compiled_objective_ids(doc, page)
        for extra in scr.get("objective_ids") or []:
            if extra not in oids:
                oids.append(extra)
        scr["objective_ids"] = oids
    if "evidence_screen_ids" in fields and page.evidence_from:
        scr["evidence_screen_ids"] = list(page.evidence_from)

    # skor: puanlı → points (verilmişse), puansız quiz-tipi → formatif (points=0, Z3)
    if "points" in fields:
        if page.scoring.scored:
            if page.scoring.points is not None:
                scr["points"] = page.scoring.points
        else:
            scr["points"] = 0

    _attach_slots(page, scr, cls, warnings)
    return scr


def compile_scenario(doc: ScenarioDocument) -> tuple[dict, list[dict]]:
    """Senaryo dokümanını build_from_spec payload'una derler → (spec, warnings).

    ⛔ blocker varsa (gaps_report + derleme-zamanı MISSING_SCREEN_TYPE/UNKNOWN_SCREEN_TYPE
    + geçersiz ekran yükü) ScenarioCompileError fırlatır — derleme REDDEDİLİR (testli).
    phase spec'e ASLA yazılmaz (3.2). Outline passthrough'dur ama düğüm hedefleri KURS
    DÜZEYİNE taşınır ve outline'dan çıkarılır (ad-alanı çakışması olmasın; E2/H1/H3
    lint'leri project.objectives okur); node pedagogy_pack → Objective.method_pack."""
    report = gaps_report(doc)
    blockers = list(report["blockers"])
    for p in doc.pages:
        if not p.screen_type:
            blockers.append(_item(
                "MISSING_SCREEN_TYPE",
                f"Sayfa '{p.id}' screen_type beyan etmiyor — derleme açık tip İSTER "
                "(gaps yalnız önerir; öneriyi upsert ile kabul et)", f"pages[{p.id}].screen_type"))
        elif p.screen_type not in _SCREEN_TYPE_VALUES:
            blockers.append(_item(
                "UNKNOWN_SCREEN_TYPE",
                f"Sayfa '{p.id}' bilinmeyen screen_type: '{p.screen_type}' "
                "(geçerli tipler: list_screen_types)", f"pages[{p.id}].screen_type"))
    if blockers:
        raise ScenarioCompileError(blockers)

    warnings: list[dict] = []

    # hedefler: outline düğümlerinden KURS düzeyine (method_pack zenginleştirmesiyle)
    objectives: list[dict] = []
    for n in doc.outline:
        if n.objective is None:
            continue
        o = n.objective.model_copy(deep=True)
        if o.method_pack is None:
            pk = _nearest_pack_for_node(doc, n)
            if pk:
                o.method_pack = pk
        objectives.append(o.model_dump(mode="json", exclude_none=True))

    screens: list[dict] = []
    for p in sorted(doc.pages, key=lambda x: x.order):  # kararlı sıralama
        scr = _page_to_screen(doc, p, warnings)
        try:
            _SCREEN_ADAPTER.validate_python(scr)
        except Exception as e:  # pydantic ValidationError → blocker olarak reddet
            raise ScenarioCompileError([_item(
                "COMPILE_SCREEN_INVALID",
                f"Sayfa '{p.id}' '{p.screen_type}' ekranına derlenemedi: {e} — eksik tip-özgü "
                "alanları screen_payload ile ver", f"pages[{p.id}]")])
        screens.append(scr)

    spec: dict = {
        "schema_version": "1.0",
        "title": doc.title,
        "outline": [n.model_dump(mode="json", exclude={"objective"}, exclude_none=True)
                    for n in doc.outline],
        "objectives": objectives,
        "screens": screens,
    }
    if doc.audience_pack:
        spec["audience_pack"] = doc.audience_pack
    # Faz 3 — kabul #11: dolu slot başına provenance kaydı (paketleyici
    # assets/PROVENANCE.json yazar). Boş → anahtar HİÇ basılmaz (düz kurs bayt-paritesi).
    from core.media_federation import provenance_records
    records = provenance_records(doc)
    if records:
        spec["media_provenance"] = records
    return spec, warnings
