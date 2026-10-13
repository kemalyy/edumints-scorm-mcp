# CONTRACTS.md — `scorm-mcp` Ortak Sözleşme (v1)

> **Bu dosya tüm modüllerin ve Faz 1 ajanlarının tek doğruluk kaynağıdır.**
> Ajanlar `CONTRACTS.md` dışında birbirinin dosyalarına dokunmaz. Bir tip/araç/env değişikliği
> gerekiyorsa önce **burası** güncellenir, sonra ilgili modül.
>
> Mimari ilke: **Yazar Claude, montajcı sunucu.** Sunucu LLM çağırmaz, içerik üretmez.
> İçeriği Claude tasarlar ve araçlara `spec` olarak aktarır; sunucu yalnızca
> iskele + bileşen kütüphanesi + runtime + paketleme sağlar. Deterministik, ucuz, çok-kullanıcılı.

---

## 0. Sürüm & Uyum Notları

- **Şema sürümü:** `schema_version = "1.0"` (her `Project` ve `CourseSpec` köküne yazılır).
- **SCORM:** `1.2` öncelikli; veri modeli **versiyon-agnostik**. Paketleme anında `1.2 | 2004`.
- Tüm zaman damgaları **UTC ISO-8601** (`2026-06-01T12:00:00Z`).
- Tüm ID'ler sunucu tarafında üretilir: `proj_<ulid>`, `scr_<ulid>`, `asset_<ulid>`, `pkg_<ulid>`, `job_<ulid>`.

---

## 1. Veri Modeli (`core/project.py`)

Pydantic v2. Aşağıdaki şemalar hem in-memory model, hem store serileştirmesi, hem de
tool girdi/çıktısı için kanonik biçimdir.

### 1.1 Tema Token'ları

Görsel kalite (agency-level) bu projenin asıl farklılaştırıcısıdır → tema token'ları sadece renk
değil; **tipografi, renk paleti (skalalı), boşluk skalası, köşe yarıçapı skalası, elevation/gölge
katmanları ve motion (geçiş/animasyon)** token'larını kapsar. Renderer (Ajan B) bu token'ları
CSS custom property (`--xxx`) olarak `:root`'a basar; tüm bileşenler yalnız bu değişkenleri kullanır.

```python
# ---- alt gruplar ----
class Typography(BaseModel):
    font_heading: str = "'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    font_body: str    = "'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    font_mono: str    = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    base_size_px: int = 16                # kök font boyutu
    scale_ratio: float = 1.25             # modüler tipografik ölçek (Major Third)
    weight_heading: int = 700
    weight_body: int = 400
    weight_strong: int = 600
    line_height_tight: float = 1.2        # başlıklar
    line_height_normal: float = 1.6       # gövde metni
    letter_spacing_heading: str = "-0.01em"
    # Türetilen başlık boyutları base_size_px * scale_ratio^n (renderer hesaplar): h1..h4

class ColorPalette(BaseModel):
    # marka
    primary: str = "#2563eb"
    primary_hover: str = "#1d4ed8"
    primary_contrast: str = "#ffffff"     # primary üstü metin
    secondary: str = "#7c3aed"
    accent: str = "#06b6d4"
    # yüzeyler (elevation arttıkça)
    bg: str = "#ffffff"
    surface: str = "#f8fafc"
    surface_alt: str = "#f1f5f9"
    border: str = "#e2e8f0"
    # metin
    text: str = "#0f172a"
    text_muted: str = "#64748b"
    text_on_dark: str = "#f8fafc"
    # semantik (geri bildirim / quiz)
    success: str = "#16a34a"
    success_bg: str = "#dcfce7"
    error: str = "#dc2626"
    error_bg: str = "#fee2e2"
    warning: str = "#d97706"
    info: str = "#0284c7"
    focus_ring: str = "#2563eb"           # erişilebilirlik odak halkası

class Spacing(BaseModel):
    # 4px tabanlı skala; renderer --space-1..--space-12 olarak basar
    base_px: int = 4
    scale: list[int] = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96]  # adım -> px
    content_max_width: str = "880px"      # okuma genişliği (satır uzunluğu kontrolü)
    gutter: str = "clamp(16px, 4vw, 48px)" # slayt iç kenar boşluğu (responsive)

class Radii(BaseModel):
    none: str = "0"
    sm: str = "6px"
    md: str = "12px"
    lg: str = "20px"
    pill: str = "999px"

class Elevation(BaseModel):
    # katmanlı gölge (yükseklik hissi) — kart, popover, modal
    e0: str = "none"
    e1: str = "0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.10)"
    e2: str = "0 4px 6px -1px rgba(15,23,42,.10), 0 2px 4px -2px rgba(15,23,42,.10)"
    e3: str = "0 10px 15px -3px rgba(15,23,42,.10), 0 4px 6px -4px rgba(15,23,42,.10)"
    e4: str = "0 20px 25px -5px rgba(15,23,42,.12), 0 8px 10px -6px rgba(15,23,42,.10)"

class Motion(BaseModel):
    duration_fast: str = "120ms"
    duration_base: str = "220ms"
    duration_slow: str = "400ms"
    easing_standard: str = "cubic-bezier(0.2, 0, 0, 1)"     # giriş/çıkış
    easing_emphasized: str = "cubic-bezier(0.2, 0, 0, 1.2)" # vurgulu (overshoot)
    slide_transition: Literal["fade", "slide", "zoom", "none"] = "slide"  # ekran geçişi
    reduce_motion_respect: bool = True     # prefers-reduced-motion'a uy (erişilebilirlik)

# ---- kök tema ----
class CustomFont(BaseModel):
    family: str             # CSS font-family adı
    asset_id: str           # paketlenmiş .woff2 asset id'si
    weight: int = 400
    style: Literal["normal", "italic"] = "normal"

class ThemeTokens(BaseModel):
    name: str = "default"                  # default | agency | dark | style-minimal | style-playful | style-premium | custom
    typography: Typography = Typography()
    color: ColorPalette = ColorPalette()
    spacing: Spacing = Spacing()
    radii: Radii = Radii()
    elevation: Elevation = Elevation()
    motion: Motion = Motion()
    logo_asset_id: str | None = None       # add_asset ile yüklenmiş logo
    logo_alt: str | None = None            # logo alt-text (W10)
    custom_fonts: list[CustomFont] = []    # paketlenmiş fonttan @font-face üretimi (W10)
    background_pattern: Literal["none", "dots", "grid", "gradient"] = "none"
    custom_css: str | None = None          # ileri kullanıcı için ek CSS (sanitize edilmez; güvenilir key)
```

`themes/` altında `default`, `agency`, `dark` hazır setleri **bu şemaya uygun JSON** olarak bulunur
(agency = yüksek kontrast, belirgin elevation + emphasized motion; dark = koyu yüzey paleti).
`theme="..."` ile seçilir, `set_theme(theme_tokens)` ile üzerine yazılır — **kısmi override derin merge**
edilir (örn. yalnız `color.primary` gönderilirse diğer token'lar korunur).

`theme="..."` bir preset JSON dosyasının adı, ham dosyada opsiyonel bir `"extends": "<başka-preset>"`
anahtarı içerebilir — yükleme zamanında miras alınan preset'in üzerine deep-merge edilir (W10). Bu
yönerge `ThemeTokens` şemasının parçası DEĞİLDİR, yalnızca `_load_theme`'in tükettiği bir dosya-seviyesi
direktiftir.

### 1.2 Takip / Tamamlanma

```python
class CompletionRule(str, Enum):
    viewed_all = "viewed_all"             # tüm ekranlar görüntülendi
    passed_quiz = "passed_quiz"           # geçme notu alındı
    viewed_all_and_passed = "viewed_all_and_passed"

class Tracking(BaseModel):
    completion_rule: CompletionRule = CompletionRule.viewed_all
    passing_score: int = 80               # 0..100, cmi.core.score.raw eşiği
    score_scaling: bool = True            # quiz puanlarını 0..100'e ölçekle
```

### 1.3 Ekranlar (discriminated union, `type` alanı ile)

Ortak taban:

```python
class ScreenBase(BaseModel):
    id: str | None = None                 # add_screen üretirse server doldurur
    type: ScreenType
    title: str
    notes: str | None = None              # yazar notu, runtime'a render edilmez
    duration_hint_sec: int | None = None  # ilerleme/otomatik geçiş ipucu
    node_id: str | None = None            # Senaryo hattı Faz 1 (additive) — ekranın bağlı olduğu
                                          # OutlineNode.id (bkz. §2.1). Sarkan referans SERT hata.
                                          # None → outline'lı kursta menünün sonundaki "düğümsüz
                                          # ekranlar" düz grubunda gösterilir.
```

Zengin metin alanları **kısıtlı HTML alt kümesi** kabul eder (bkz. §6 Güvenlik):
`p,h1..h4,ul,ol,li,strong,em,a,br,img,figure,figcaption,code,pre,blockquote,table,thead,tbody,tr,td,th`.
F2 (#113): `span` ayrıca `data-exploration-ref` attribute'unu taşıyabilir (geri-oynatma yüzeyi —
dar allowlist genişletmesi; runtime bu span'lara yalnız textContent yazar, başka hiçbir `data-*`
attribute'u sanitizasyondan geçmez).

| `type` | Ek alanlar (özet) |
|---|---|
| `title_slide` | `subtitle?`, `background_asset_id?`, `body_html?` |
| `content_slide` | `body_html`, `media_asset_id?`, `layout: "text" \| "text_media" \| "media_text" \| "full_media" = "text"` |
| `mcq` | `prompt_html`, `options: list[Choice]` (≥2), `multi_select: bool=False`, `feedback: Feedback`, `points: int=10` |
| `true_false` | `prompt_html`, `correct: bool`, `feedback: Feedback`, `points: int=10` |
| `fill_blank` | `prompt_html`, `blanks: list[Blank]`, `case_sensitive: bool=False`, `feedback: Feedback`, `points: int=10` |
| `drag_drop` | `prompt_html`, `items: list[DragItem]`, `targets: list[DropTarget]`, `feedback: Feedback`, `points: int=10` |
| `hotspot` | `prompt_html`, `image_asset_id`, `regions: list[HotspotRegion]`, `feedback: Feedback`, `points: int=10` |
| `branching` | `prompt_html`, `choices: list[BranchChoice]` (her biri `goto_screen_id`), `default_goto?` |
| `video` | `video_asset_id \| video_url`, `caption?`, `poster_asset_id?`, `require_complete: bool=False` |
| `summary` | `body_html?`, `show_score: bool=True`, `show_completion: bool=True` |
| `worked_example` | F1 (#112): `steps: list[WEStep]` (≥2; her adım `action_html` + `rationale_html` + ops. `artifact_asset_id`/`artifact_caption`), `fading: "full" \| "partial" \| "problem_only" = "full"`, `intro_html?`, `self_explanation_prompt_html?` (SKORSUZ serbest metin — LMS'e yazılmaz). PUAN ALANI YOK — skorlanamaz kanıt/öğretim ekranı (tam liste `docs/SCREEN_TYPES.md`) |
| `exploration` | F2 (#113): `prompt_html`, `input_kind: "text" \| "choice" \| "prediction" = "text"`, `choices?: list[Choice]` (choice/prediction için ≥2 — model doğrular), `placeholder?`, `min_length?`, `store_key` (`[a-z0-9_-]+`, ≤64; kurs genelinde TEKİL — `validate_project` çakışmayı SERT hatayla keser). Öğrenen girdisi suspend v2 kuyruğundaki `xp` haritasında saklanır (değer 500 karakterde kırpılır — scorm.js `EXPLORATION_VALUE_MAX`); sonraki ekranlar zengin HTML içinde `<span data-exploration-ref="store_key"></span>` ile GERİ OYNATIR (runtime yalnız textContent yazar — innerHTML asla; boş değer i18n yer tutucusu). PUAN ALANI YOK — skorsuz/formatif (A4 skorsuz-erken-deneme istisnasının teknik karşılığı; Z3) |

Alt tipler:

```python
class Choice(BaseModel):
    id: str                               # "a","b",... yazar verir
    text_html: str
    correct: bool = False

class Feedback(BaseModel):
    correct_html: str = "Doğru!"
    incorrect_html: str = "Tekrar deneyin."
    show_correct_answer: bool = True

class Blank(BaseModel):
    id: str
    accepted: list[str]                   # kabul edilen cevap varyantları

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
    coords: list[float]                   # rect:[x,y,w,h] circle:[cx,cy,r] poly:[x1,y1,...]
    correct: bool = True
    label_html: str | None = None

class BranchChoice(BaseModel):
    id: str
    text_html: str
    goto_screen_id: str                   # hedef ekran id'si
```

Quiz tipleri **skoru runtime'a** yazar (`cmi.core.score.raw` / 2004: `cmi.score.raw`+`scaled`).
`branching` durumu `suspend_data`'ya JSON serialize edilir (boyut sınırı için §6).

S2 (2.4) — **tüm puanlı ekran tipleri** (QUIZ_TYPES: mcq, true_false, fill_blank, drag_drop,
hotspot, matching, sorting, simulation, decision_scenario, term_match_race, escape_room,
labeled_diagram, game, adaptive_practice) opsiyonel `objective_ids: list[str] = []` taşır —
kurs düzeyindeki `objectives` listesine referans. Bilinmeyen id `validate_project`'te SERT
hatadır; runtime hedef başına doğru/toplam → `cmi.objectives.n.*` yazar (bkz. §9).

E1 (#110) — aynı puanlı ekran tipleri opsiyonel **`evidence_screen_ids: list[str] = []`** taşır
(ÇOĞUL — bir soru birden çok artefakta yaslanabilir): cevabın türetildiği kurs-içi
kanıt-kaynağı ekran id'leri (skill kuralı K1/T1, `references/core/evidence-binding.md`). Kanıt
bağının TEK geçerli beyanı bu alandır; lint'in heuristik aday keşfi yalnız WARN mesajına öneri
yazar, denetimi geçirmez. Semantik (hepsi `core/antislop.py` E1 bölümü):
- **Sarkan/öz referans** → `evidence_screen_missing` ERROR (bilinmeyen `objective_ids` ile aynı
  sınıf sert hata; alan kullanılmadıkça tetiklenmez → geriye uyumlu).
- **Kanıt-TAŞIYAMAZ hedef** → `evidence_target_not_evidentiary` WARN (strict'te blok). Kanıt
  taşıyabilir ekranlar: accordion / tabs / flashcards / timeline / data_chart / image_compare /
  **worked_example** (F1 #112 — K1 tür 1'in en doğrudan taşıyıcısı: adımların eylem+gerekçe
  çifti artefaktın kendisi, koşulsuz kanıt-taşıyabilir) /
  **exploration** (F2 #113 — K1 tür 2: öğrenenin KENDİ ürettiği tahmin/gözlem çıktısı;
  skorsuzluk yapısal — puan alanı yok, koşulsuz kanıt-taşıyabilir);
  content_slide YALNIZ artefaktlıysa (`blocks` ya da `media_asset_id` — düz iddia metni sayılmaz);
  video/lottie YALNIZ içeriği spec'ten doğrulanabiliyorsa (caption / narration_text / prompt_html);
  quiz/oyun tipleri YALNIZ formatifken (points=0 ve puana yazmıyor — Z3). Taşıyamaz: title_slide,
  summary, results_breakdown, poll, branching ve SKORLU her ekran.
- **Alan boş (skorlu ekranda)** → `unbound_scored_question` WARN (strict'te blok).
- SIRA/faz denetimi YOKTUR (Katman-1 yöntem bağımsızlığı): kanıt ekranının akışta nerede
  durduğu yöntemin seçimidir; dallanan/adaptif kursta ekran indeksi ≠ sunum sırası.

E2 (#111) — **paket uygunluk denetimi** (`core/antislop.py` E2 bölümü; danışsal dalga — TÜM
kodlar WARN, `STRICT_PROMOTED_CODES`'a TERFİSİZ; `Objective.method_pack` beyanı yoksa SIFIR
çıktı → geriye uyumlu):
- **Paket tanımlarının kaynağı:** vendored **`runtime/pedagogy-packs.json`** — skill reposundaki
  paketlerin (`skills/authoring-scorm-courses/references/pedagogy/*.md`, `_` öneklileri hariç)
  YAML ön-maddesinden `tools/gen_packs_manifest.py` ile üretilen deterministik PROJEKSİYON
  (name/version, requires_platform, conflicts_with, evidence_phases [tekil `evidence_phase`
  listeye normalize], scoring_allowed_from, phases[id/izinli_ekran_tipleri/skorlanabilir]).
  Sunucu skill reposunu runtime'da OKUMAZ; paket eklenince/değişince betik yeniden çalıştırılıp
  manifest commit'lenir (`tests/test_pack_conformance.py` senkron kopuşunu yakalar). Manifest
  yok/bozuksa lint crash ETMEZ — beyanlar `unknown_method_pack`a düşer.
- `unknown_method_pack` — beyan edilen pack id manifest'te yok; o hedefin diğer E2 denetimleri
  atlanır (yanlış pakete karşı denetim üretmek yanıltır).
- `pack_conflict_on_screen` — AYNI ekran, paketleri `conflicts_with` ile çelişen iki hedefe
  bağlı (`objective_ids`). Kapsam HEDEFTİR (skill `_SCHEMA.md` B2): çelişen paketler FARKLI
  hedeflerin AYRI ekranlarında meşru birlikte yaşar; ihlal yalnız paylaşılan ekrandır.
  Çift başına tek WARN (yön simetrik).
- `pack_platform_missing` — paketin `requires_platform` tipi hedefin kullanımında yok.
  Karşılanma: (i) o tipte ekran hedefe bağlı (`objective_ids`), YA DA (ii) hedefin skorlu
  ekranlarının `evidence_screen_ids` hedefi o tipte, YA DA (iii) tip HİÇ bağlanamıyorsa
  (`objective_ids` alanı olmayan tipler — worked_example/exploration/branching...) kurs
  genelinde ≥1 ekran. Bağlanabilir tip kümesi Screen union'dan türetilir (elle liste yok).
- `evidence_type_outside_pack` — hedefe bağlı SKORLU ekranın kanıt hedefi (`evidence_screen_ids`),
  paketin kanıt fazlarının (`evidence_phases`) `izinli_ekran_tipleri` birleşimi dışında bir
  tipte. Herhangi bir kanıt fazı `hepsi` ise kısıt yok; sarkan/öz id E1'in işi
  (`evidence_screen_missing` ERROR) — E2 çifte raporlamaz.
- `scoring_allowed_from`'un DOĞRUDAN denetimi ekran-düzeyi faz etiketi ister — bilinçli
  ertelendi (Screen.phase additive alanı aday); platform + kanıt-tipi denetimleri bu beyanın
  faz-etiketsiz yaklaşıklarıdır.

### 1.4 Proje

```python
class Project(BaseModel):
    schema_version: str = "1.0"
    id: str
    title: str
    description: str = ""
    scorm_version: Literal["1.2", "2004"] = "1.2"
    language: str = "tr"
    theme: ThemeTokens = ThemeTokens()
    tracking: Tracking = Tracking()
    screens: list[Screen] = []            # sıralı; sunum sırası = liste sırası
    assets: list[AssetRef] = []
    created_at: datetime
    updated_at: datetime
    owner_key_id: str                     # hangi API anahtarına ait
```

### 1.5 Varlık (Asset)

```python
class AssetRef(BaseModel):
    id: str                               # asset_<ulid>
    filename: str                         # paket içi güvenli ad (sanitize edilmiş)
    mime: str
    size_bytes: int
    sha256: str
    rel_path: str                         # paket içi yol, örn "assets/img1.png"
```

---

## 2. CourseSpec — `build_from_spec` Girdi Şeması (ÖNERİLEN yol)

Tek JSON ile tüm kurs. Token-verimli; Claude bunu tek atışta üretir.

```python
class CourseSpec(BaseModel):
    schema_version: str = "1.0"
    title: str
    description: str = ""
    scorm_version: Literal["1.2", "2004"] = "1.2"
    language: str = "tr"
    theme: str | ThemeTokens = "default"  # ad veya tam token seti
    tracking: Tracking = Tracking()
    metadata: CourseMetadata | None = None  # S7 (2.3) — opsiyonel LOM (imsmd) meta verisi
    objectives: list[Objective] = []      # S2 (2.4) — kurs hedefleri (cmi.objectives.* kaynağı)
    outline: list[OutlineNode] = []       # Senaryo hattı Faz 1 (additive) — hiyerarşik kurs
                                          # iskeleti (bkz. §2.1). Boş = bugünkü düz davranış;
                                          # Project'e aynen taşınır (outline=spec.outline).
    audience_pack: str | None = None      # Senaryo hattı Faz 1 — REZERVE alan (bkz. §2.1);
                                          # yalnız kabul+sakla+makine-dostu doğrulama
                                          # ([a-z0-9_-]{1,64}); davranış Faz 5.
    source_item_count: int | None = None  # E1 (#110) — beyan-temelli: kursun türetildiği kaynak
                                          # dokümanın madde/başlık sayısı (≥1). Project'e aynen
                                          # taşınır; lint `source_item_parity` (1:1 kopya kokusu)
                                          # yalnız beyan varsa çalışır (None = denetim yok).
    screens: list[Screen]                 # ekran id'leri opsiyonel; yoksa server üretir
    assets: list[AssetInput] = []         # inline base64 veya url; build sırasında çekilir

class AssetInput(BaseModel):
    id: str | None = None                 # yazarın atadığı STABİL id; ekranlar *_asset_id ile buna
                                          # referans verir. Verilmezse server üretir (ama o durumda
                                          # ekranlardan referanslanamaz). build_from_spec bunu AssetRef.id yapar.
    filename: str
    source: str                           # "data:<mime>;base64,..." | "https://..."

class CourseMetadata(BaseModel):
    # S7 (2.3) — additive/opsiyonel; boş/None alan → manifest'te ilgili LOM elemanı hiç basılmaz.
    # Ayrıca Project'e de aynı ada/yapıda alan olarak taşınır (build_from_spec: metadata=spec.metadata).
    description: str | None = None
    keywords: list[str] = []
    intended_audience: str | None = None  # LOM'a eşlenmez (kapalı sözlük gerektiren
                                          # imsmd:intendedenduserrole'e serbest metin zorlanmaz);
                                          # yalnız CourseSpec/Project'te taşınır.
    typical_learning_time: str | None = None
    # ISO 8601 süre string'i (ör. "PT1H30M", "P1D") — LOM educational/typicalLearningTime/datetime'a
    # doğrudan yazılır. Hafif regex doğrulaması (en az bir bileşen zorunlu; "P"/"PT" tek başına geçersiz).

class Objective(BaseModel):
    # S2 (2.4) — kurs düzeyinde öğrenme hedefi; Project'e aynen taşınır (objectives=spec.objectives).
    # Puanlı ekranlar `objective_ids: list[str]` ile bağlanır; bilinmeyen id build/validate'te SERT hata.
    id: str                               # makine-dostu [A-Za-z0-9_.-]{1,255} — cmi.objectives.n.id
                                          # ve (2004) imsss:objective/@objectiveID'ye AYNEN yazılır
    description: str | None = None        # yazarlık/dokümantasyon; pakete metin olarak basılmaz
    success_criteria: str | None = None   # yazarlık/dokümantasyon; runtime eşiği kursun
                                          # passing_score'udur (S6 primaryObjective ile tutarlı)
    method_pack: str | None = None        # E2 (#111) — hedefin BEYAN ETTİĞİ pedagoji paketi
                                          # (runtime/pedagogy-packs.json pack id, ör. "gagne-9").
                                          # Additive/opsiyonel: None = E2 denetimleri bu hedef için
                                          # sessiz. Kapsam HEDEFTİR (bir hedef = bir paket; çelişen
                                          # paketler farklı hedeflerde meşru). Bilinmeyen id SERT
                                          # hata DEĞİL — lint `unknown_method_pack` WARN.
```

`build_from_spec(spec)` → projeyi oluşturur, asset'leri çeker, **build job** kuyruğa alır,
`{project_id, download_url}` döner (download_url job bitince hazır olur; durum `validate_package`/poll ile).

### 2.1 Outline — hiyerarşik kurs iskeleti (Senaryo hattı Faz 1)

```python
class OutlineNode(BaseModel):
    id: str                               # makine-dostu [A-Za-z0-9_.-]{1,64}; suspend_data
                                          # kısa-anahtarlarına (Faz 4) ve menü DOM'una aynen yazılır
    parent_id: str | None = None          # None = kök; düz liste + parent_id ile ağaç kurulur
    kind: Literal["unit", "section"]      # "page" KASITLI yok — senaryo sayfaları Faz 2 şeması
    title: str
    objective: Objective | None = None    # düğüm hedefi; kurs hedef AD-ALANINA kaydolur (id'si
                                          # course.objectives ve diğer düğümlerle çakışamaz — SERT
                                          # hata). En-yakın-atadan miras + ORPHAN_PAGE = Faz 2.
    pedagogy_pack: str | None = None      # düğümün beyan ettiği pedagoji paketi (method_pack
                                          # paraleli); Faz 1'de yalnız taşınır, davranış yok
```

- **Yapısal SERT doğrulamalar** (`validate_project`, veri bütünlüğü 3.8): sarkan `parent_id`,
  döngü (self-parent dahil), derinlik > 3 (kök=1), yinelenen düğüm id'si, sarkan
  `screen.node_id`, hedef-ad-alanı çakışması. Outline boş + hiçbir ekranda `node_id` yok →
  doğrulama çıktısında SIFIR yeni kalem.
- **Player**: outline'lı kursta slayt menüsü APG `role="tree"` hiyerarşisi olarak SUNUCUDA
  render edilir (katlanır düğümler, tam klavye, `aria-current="page"`, roving tabindex;
  `node_id`'siz ekranlar sonda i18n başlıklı düz grupta). Outline boşken üretilen HTML
  bugünkü düz menüyle **bayt-bayt aynıdır** (fixture testli — `tests/test_outline_menu.py`).
  Kilit/konum/ilerleme/resume = Faz 4.
- **`Objective.outcome_type`** (additive, ops.): kazanım türü beyanı (`[a-z0-9_-]{1,64}`,
  ör. "knowledge"/"skill"); Faz 1'de davranışsız.
- **`audience_pack` REZERVE**: kitle paketi kimliği (ör. "k12-lise"). Faz 1'de yalnız kabul
  edilir, saklanır, makine-dostu string olarak doğrulanır — hiçbir davranışı yoktur (Faz 5).
  `pedagogy_pack`/`method_pack` ile AYRI kavramdır (3.4: yalın "pack" adı yasak; kitle paketi
  ekran tipini kısıtlayamaz — parametre olur).

---

## 3. Tool İmzaları (`server.py` ↔ FastMCP)

Tüm tool'lar `owner_key_id`'yi auth context'inden alır (parametre değil). Hata durumunda
`ToolError(code, message)` (bkz. §7). Tüm dönüşler pydantic → JSON.

```python
create_project(title: str, description: str = "", scorm_version: Literal["1.2","2004"]="1.2",
               theme: str = "default", language: str = "tr") -> CreateProjectOut
    # CreateProjectOut = { project_id: str }

add_screen(project_id: str, screen: Screen) -> AddScreenOut
    # AddScreenOut = { screen_id: str }

update_screen(project_id: str, screen_id: str, screen: Screen) -> OkOut

list_screens(project_id: str) -> ListScreensOut
    # ListScreensOut = { screens: list[ScreenSummary] }
    # ScreenSummary = { id, type, title, index }

remove_screen(project_id: str, screen_id: str) -> OkOut

set_theme(project_id: str, theme_tokens: ThemeTokens) -> OkOut

set_tracking(project_id: str, completion_rule: CompletionRule, passing_score: int) -> OkOut

add_asset(project_id: str, source: str, filename: str) -> AddAssetOut
    # source: "data:<mime>;base64,..." | "https://..."
    # AddAssetOut = AssetRef

search_images(query: str, source: str = "openverse", limit: int = 5) -> dict
    # W11 — Openverse/Wikimedia CC0/Public-Domain görsel adayı arar (İNDİRME YAPMAZ).
    # dict = { count: int, source: str, images: list[{title, url, thumb_url?, width?, height?,
    #          license, license_url?, creator?, source_page?}] }
    # Seçilen `url`, add_asset(project_id, source=url, filename=...) ile projeye eklenir.

preview(project_id: str) -> PreviewOut
publish_demo(project_id: str, slug: str) -> {url, slug}   # KALICI /demo/{slug} linki (TTL yok, upsert)
    # PreviewOut = { inline_html: str, hosted_url: str }
    # inline_html: TEK dosya, harici bağımlılık YOK (runtime + tema gömülü)
    # hosted_url:  PUBLIC_BASE_URL + "/preview/{token}"
    # 1.2 — metadata (DemoMeta, §4) store'da; sahiplik store'dan doğrulanır (eski yalnız-.owner-
    # dosyalı yayınlar bir kereliğine göç eder — bkz. §4). HTML boyutu owner kotasına dahildir.

list_demos() -> { demos: list[dict] }
    # Sahibin yayınladığı KALICI demo linkleri. Her öğe: { slug, project_id, title, language,
    # size_bytes, created_at, updated_at, url }.

unpublish_demo(slug: str) -> OkOut
    # KALICI demo linkini kaldırır (metadata + HTML). Sonrasında GET /demo/{slug} → 404.
    # Sahiplik doğrulanır (§4 DemoMeta.owner_key_id); yabancı slug → forbidden.

build_package(project_id: str, strict: bool | None = None) -> BuildOut
    # HİBRİT (fast-path). BuildOut = { job_id, status, download_url?, size?, scorm_version,
    #                                  error?, warnings: list[str] }
    # status: "queued" | "running" | "done" | "error"
    # strict (SP-5, §3.2): küratörlü anti-slop WARN kümesi de build'i bloklar; None → sunucu
    #   varsayılanı (ANTISLOP_STRICT env). Varsayılan davranış DEĞİŞMEDİ.
    # warnings (SP-5): bloklamayan artifact uyarıları (ör. schema_unavailable) — in-process,
    #   danışsal; restart sonrası poll'da boş dönebilir.
    # Davranış (bkz. §3.1 Build Fast-Path — A ve C ORTAK uyar):
    #   - Build threadpool'a verilir; çağrı en fazla BUILD_SYNC_TIMEOUT_SEC bekler.
    #   - İş bu süre içinde biterse → status="done", download_url+size DOLU döner (SENKRON).
    #   - Bitmediyse → status="running"/"queued" + job_id döner; çağıran POLL eder.
    #   - download_url done olunca: PUBLIC_BASE_URL + "/files/{token}"
    #   - SP-5 (B1): üretilen zip başarı işaretlenmeden ÖNCE validate_zip'ten geçer; yapısal
    #     hata → job "error" (+ fast-path'te ToolError("build_error")), bozuk zip silinir.

build_status(project_id: str) -> BuildOut
    # Poll aracı (#94, 30. araç): projenin EN SON build job'unun durumu. Yeni build TETİKLEMEZ.
    # Store-backed okuma (Store.active_job_for_project = en yeni job) → restart sonrası da çalışır.
    # status="done" → download_url + size dolu; hiç job yoksa ToolError("not_found").
    # Sahiplik diğer araçlarla aynı (auth context'inden owner; yabancı proje → not_found).

validate_package(project_id: str) -> ValidateOut
    # ValidateOut = { ok: bool, errors: list[ValidationError] }
    # ValidationError = { code, message, path? }

build_from_spec(spec: CourseSpec, strict: bool | None = None) -> BuildFromSpecOut
    # Proje oluştur + asset çek + build. AYNI fast-path (§3.1) + SP-5 strict/zip-kapısı
    # davranışı build_package ile birebir aynı.
    # BuildFromSpecOut = { project_id, job_id, status, download_url?, warnings: list[str] }

lint_course(project_id: str, strict: bool | None = None) -> dict
    # Anti-slop denetim raporu (W6/W9/W11 + E1 kanıt-bağlama kuralları; build TETİKLEMEZ, danışsal).
    # dict = { project_id, strict: bool, error_count, warn_count, clean,
    #          evidence_binding_coverage: float, issues: list[{severity, code, message, path}] }
    # evidence_binding_coverage (E1/#110): geçerli AÇIK `evidence_screen_ids` bağı olan skorlu
    # ekran / toplam skorlu ekran (0..1; skorlu ekran yoksa 1.0). Törensel bağ (sarkan id,
    # kanıt-taşıyamaz hedef) ve heuristik aday SAYILMAZ — oran lint yeşilken düşüyorsa denetim
    # sürükleniyor demektir.
    # E1 (#110) kodları: unbound_scored_question (WARN, strict'te blok), evidence_screen_missing
    # (ERROR), evidence_target_not_evidentiary (WARN, strict'te blok), scored_over_objectives
    # (H3 — skorlu ekran > hedef + 1, WARN; terfi YOK: sınav kursu meşru aşabilir),
    # source_item_parity (kaynak-madde ≈ ekran sayısı → 1:1 kopya kokusu, WARN; beyan-temelli).
    # E2 (#111) kodları (hepsi WARN, terfisiz — danışsal dalga; yalnız Objective.method_pack
    # beyanı varsa üretilir, kaynak: vendored runtime/pedagogy-packs.json — bkz. §1.3 E2):
    # unknown_method_pack, pack_conflict_on_screen, pack_platform_missing,
    # evidence_type_outside_pack.
    # strict=True (SP-5, §3.2): küratörlü WARN kümesi raporda "error" şiddetiyle sayılır —
    # strict build'in bloklayacağı kümenin birebir aynası. None → sunucu varsayılanı.
```

`OkOut = { ok: true }`.

Toplam tool sayısı **38** (senaryo hattı Faz 2: 30 → 38, aşağıdaki 8 senaryo aracı eklendi).

### 3.0 Senaryo araçları (senaryo hattı Faz 2 — `core/scenario.py` mantık)

Senaryo dokümanı = hiyerarşik outline + sayfalar; sahiplik projelerle aynı (auth context'i
`owner_key_id`); doküman store'da tek JSON blob (`schema_version: 1`), boyutu kotaya dahil.
Sayfa şeması, kanıt beyanı ENUM'u (`EvidenceDecl` oneOf) ve medya yuvası sözleşmesi (`MediaSlot`,
Faz-3 için donduruldu) `core/scenario.py`dadır. `fill_media_slot` Faz 3'tür; ŞEKİL burada sabittir.

```python
create_scenario(title: str, outline: list[dict] = [], audience_pack: str | None = None,
                duration_target_sec: int | None = None) -> { scenario_id: str }
    # OutlineNode listesi doğrulanır + yapısal sert denetim (sarkan parent/döngü/derinlik>3/
    # yinelenen id/hedef ad-alanı çakışması). scenario_id "scn_" ön ekli.

scenario_upsert_node(scenario_id: str, node: dict) -> { node_id: str }
    # OutlineNode ek/güncelle (id varsa günceller); doküman yapısal denetimden geçer.

scenario_upsert_page(scenario_id: str, page: dict) -> { page_id: str }
    # Page ekle/güncelle (id yoksa "pg_" üretilir). Kanıt ENUM oneOf + slot rolleri doğrulanır.
    # Boşluk/kanıt kapısı upsert'te DEĞİL derlemededir (scenario_gaps/scenario_compile).

scenario_reorder(scenario_id: str, page_ids_in_order: list[str]) -> OkOut
    # TÜM sayfa id'lerini bire bir içermeli (eksik/fazla → validation_error); order yeniden atanır.

scenario_tree(scenario_id: str) -> dict
    # Kompakt ağaç özeti: { scenario_id, title, node_count, page_count, nodes[…] (children +
    # pages: {id,title,order,screen_type,phase,scored,has_evidence}), ungrouped_pages[…],
    # audience_pack, duration_target_sec }.

scenario_gaps(scenario_id: str) -> dict
    # Derleme KAPISI. { blockers[], warnings[], suggestions[], evidence_binding_coverage_estimate,
    #   blocker_count, warning_count }. Her öğe { code, message, path } (öneri ayrıca
    #   suggested_screen_type). Blocker varken scenario_compile REDDEDER. Denetimler sıra-bağımsız.
    # Blocker (⛔) kodları: ORPHAN_PAGE, DANGLING_NODE_REF, DANGLING_EVIDENCE_FROM,
    #   DANGLING_OBJECTIVE_REF, SCORED_NO_EVIDENCE_FROM, OBJECTIVE_NO_EVIDENCE,
    #   EVIDENCE_KIND_MISSING, PREDICTION_SCORED, AUTO_GRADE_OPEN_TEXT.
    # Warn (⚠) kodları: EMPTY_MEDIA_SLOTS, PHASE_NOT_IN_PACK (runtime/pedagogy-packs.json'a
    #   karşı — E2 _load_packs yeniden kullanımı), DURATION_DRIFT (±%20), NARRATION_ECHO
    #   (token containment ≥0.8, min 5 token). Suggestion: SCREEN_TYPE_SUGGESTION (yalnız öneri —
    #   ASLA otomatik seçilmez; yazar upsert ile kabul eder).

scenario_compile(scenario_id: str, compile_and_build: bool = False,
                 strict: bool | None = None) -> dict
    # Senaryoyu build_from_spec payload'una derler. ⛔ blocker varsa ToolError("compile_refused").
    # Derlenen spec: outline passthrough (düğüm hedefleri KURS düzeyine taşınır + node
    #   pedagogy_pack → Objective.method_pack; outline'dan objective ÇIKARILIR — ad-alanı
    #   çakışması olmasın), sayfalar → ekranlar (screen_type derlemede ZORUNLU — eksik/bilinmeyen
    #   = blocker), copy.body_md → sanitize HTML (deterministik md→html; raw svg/canvas/script
    #   imkânsız 3.10), evidence_from → evidence_screen_ids, inherited+extra → objective_ids,
    #   boş slot → asset omit (model_3d → SLOT_KIND_UNSUPPORTED warn), FAZ ADI ASLA basılmaz (3.2).
    # dict = { scenario_id, spec, compile_warnings[], lint_course{error_count, warn_count,
    #   evidence_binding_coverage, issues[]} }. compile_and_build=True → build_from_spec zinciri
    #   (out["build"]).

scenario_delete_node(scenario_id: str, node_id: str, strategy: "refuse"|"reparent" = "refuse")
    -> OkOut
    # refuse: çocuk düğüm/sayfa varsa reddeder. reparent: çocukları düğümün ebeveynine taşır
    #   (kök düğümde sayfa varsa ebeveynsiz kalır → hata).

scenario_delete_page(scenario_id: str, page_id: str) -> OkOut
    # Sayfayı siler + ona işaret eden evidence_from referanslarını TEMİZLER (sarkma bırakmaz);
    #   boşalan bağ scenario_gaps'te blocker olur (dangle değil).
```

### 3.1 Build Fast-Path — `build_package` / `build_from_spec` (Ajan A ↔ Ajan C ORTAK)

Amaç: küçük kurslarda tek çağrıda sonucu döndürmek (Claude için akıcı), büyük/yavaş build'lerde
event loop'u ve request'i bloklamamak. **Build her zaman threadpool'da çalışır** (request thread'inde
ASLA inline değil); fark yalnız çağıranın ne kadar beklediğidir:

1. **Job oluştur** (`status="queued"`, DB'ye yaz) ve threadpool'a submit et.
2. Tool, job'un tamamlanmasını **en fazla `BUILD_SYNC_TIMEOUT_SEC`** (vars. 4sn) bekler
   (`asyncio.wait_for` / future). Bu bekleme event loop'u bloklamaz.
3. **Bittiyse:** `status="done"`, `download_url`, `size`, `scorm_version` dolu döner. (Senkron yol.)
4. **Hâlâ sürüyorsa:** `status="running"` (veya kuyruktaysa `"queued"`) + `job_id` döner; çağıran POLL eder.
5. **Hata:** `status="error"`, `error` mesajı (ToolError yerine BuildOut.error — kısmi/async hatalar için).

**POLL idempotent:** Aynı `project_id` için aktif/yeni-biten bir job varken `build_package` tekrar
çağrılırsa **yeni build başlatılmaz**; mevcut job'un güncel `status`'u (done ise download_url ile)
döner. (Asıl poll aracı: `build_status(project_id)` — #94; alternatif: `validate_package` veya
`get_job` üzerinden.) Bu kural A (job tekilliği)
ve C (tool dönüşü) için bağlayıcıdır — entegrasyonda uyuşmazlık çıkmaması için ikisi de buraya bakar.

Build çıktısı diske yazılır; kısa metadata DB'ye düşer. **Uzun build işi transaction içinde DEĞİL** (§4).

### 3.2 Strict anti-slop modu (SP-5, opt-in)

Varsayılanda anti-slop yalnız **ERROR** şiddetini bloklar (`unreachable_node`, `fake_choice`);
WARN'lar danışsaldır. `strict=True` ile **küratörlü WARN kümesi** de bloklamaya terfi eder
(`core/antislop.py` `STRICT_PROMOTED_CODES`):

| Kod | Neden küratörlü |
|---|---|
| `penalty_without_rationale` | Sahte-seçim komşusu: olumsuz sonuçlu seçim gerekçesiz (anlamlı-seçim ilkesi) |
| `text_only_run` | ≥4 ardışık görselsiz ekran — metin duvarı |
| `visual_poverty` | ≥8 ekranda görsel oranı <%25 |
| `missing_alt_text` | Görsel var ama alt-text yok (etkileşimli ekranlar dahil tüm görsel alanları) |
| `decorative_score` | Skor mekaniği hiçbir karara bağlı değil (süs) |
| `unbound_scored_question` | E1 (#110) K1/T1 tabanı: skorlu soru açık `evidence_screen_ids` beyanı taşımıyor — strict'te YALNIZ açık beyan geçer (heuristik aday geçirmez) |
| `evidence_target_not_evidentiary` | E1 (#110) K1/K2: beyan edilen kanıt hedefi kanıt taşıyamaz (düz iddia metni / kapak / özet / skorlu ekran) — törensel bağ |

Kurallar:
- `strict` parametresi `lint_course` / `build_package` / `build_from_spec`'te; `None` (varsayılan)
  → sunucu varsayılanı **`ANTISLOP_STRICT`** env'i (§8). Açık `True`/`False` her zaman kazanır.
- Strict build reddi normal `validation_error` ToolError'ıdır; terfi eden kuralların mesajı
  `[strict:<kod>]` önekiyle işaretlenir (aksiyon alınabilir yük).
- **Geriye dönük uyumluluk:** strict verilmedikçe ve env kapalıyken davranış birebir eskisi gibidir
  (regresyon testleri `tests/test_strict_and_zipcheck.py`).

---

## 4. Store Interface (`core/store.py`)

**ZORUNLU soyutlama.** Tüm veri erişimi bu arayüz arkasında. SQLite→Postgres geçişi tek modülde izole.

```python
class Store(ABC):
    # --- projeler ---
    async def create_project(self, p: Project) -> None: ...
    async def get_project(self, project_id: str, owner_key_id: str) -> Project | None: ...
    async def update_project(self, p: Project) -> None: ...
    async def delete_project(self, project_id: str, owner_key_id: str) -> None: ...
    async def list_projects(self, owner_key_id: str) -> list[Project]: ...
    async def count_projects(self, owner_key_id: str) -> int: ...
    async def total_bytes(self, owner_key_id: str) -> int: ...   # kota için; 1.2'den beri projects+packages+demos

    # --- varlıklar (fs + metadata) ---
    async def put_asset(self, project_id: str, data: bytes, meta: AssetRef) -> None: ...
    async def get_asset_bytes(self, project_id: str, asset_id: str) -> bytes: ...

    # --- paketler (build çıktısı) ---
    async def put_package(self, meta: PackageMeta) -> None: ...
    async def get_package_by_token(self, token: str) -> PackageMeta | None: ...
    async def expired_packages(self, now: datetime) -> list[PackageMeta]: ...   # TTL temizleyici
    async def delete_package(self, pkg_id: str) -> None: ...

    # --- preview token'ları ---
    async def put_preview(self, token: str, project_id: str, ttl_sec: int) -> None: ...
    async def get_preview(self, token: str) -> PreviewMeta | None: ...

    # --- kalıcı demo linkleri (1.2) --- HTML DATA_DIR/demos/{slug}.html'de kalır, yalnız
    # metadata store'dadır; upsert republish'te created_at'ı korur, size_bytes değişir.
    async def upsert_demo(self, meta: DemoMeta) -> None: ...
    async def get_demo(self, slug: str) -> DemoMeta | None: ...
    async def list_demos_for_owner(self, owner_key_id: str) -> list[DemoMeta]: ...
    async def delete_demo(self, slug: str) -> None: ...

    # --- api anahtarları & kota (auth/) ---
    async def get_key(self, raw_key: str) -> ApiKey | None: ...   # hash karşılaştırma
    async def touch_key(self, key_id: str) -> None: ...           # last_used_at

    # --- build job ---
    async def put_job(self, job: BuildJob) -> None: ...
    async def get_job(self, job_id: str) -> BuildJob | None: ...
    async def update_job(self, job: BuildJob) -> None: ...
```

Yan tipler:

```python
class PackageMeta(BaseModel):
    id: str                 # pkg_<ulid>
    project_id: str
    owner_key_id: str
    token: str              # /files/{token} için imzalı/rastgele
    rel_path: str           # DATA_DIR altı, örn "packages/pkg_x.zip"
    size_bytes: int
    scorm_version: str
    created_at: datetime
    expires_at: datetime    # created_at + PACKAGE_TTL_DAYS

class PreviewMeta(BaseModel):
    token: str
    project_id: str
    expires_at: datetime

class DemoMeta(BaseModel):        # 1.2 — kalıcı /demo/{slug} (§3 publish_demo/list_demos/unpublish_demo)
    slug: str                     # PK; DATA_DIR/demos/{slug}.html'in anahtarı
    project_id: str
    owner_key_id: str
    title: str                    # yayın anındaki proje başlığı
    language: str
    size_bytes: int               # demo HTML'in boyutu — owner kotasına dahil (total_bytes)
    created_at: datetime          # ilk yayın; republish'te KORUNUR
    updated_at: datetime          # her upsert'te güncellenir

class ApiKey(BaseModel):
    id: str                 # key_<ulid>
    label: str              # "Okul X / Öğretmen Y"
    key_hash: str           # sha256(raw_key) — ham anahtar saklanmaz
    max_projects: int = 100
    max_total_mb: int = 500
    expires_at: datetime | None = None
    disabled: bool = False
    last_used_at: datetime | None = None

class BuildJob(BaseModel):
    id: str                 # job_<ulid>
    project_id: str
    owner_key_id: str
    status: Literal["queued","running","done","error"]
    package_id: str | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
```

**SQLite kuralları:** `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`. `aiosqlite` veya
threadpool. Transaction'lar **kısa**. **Uzun build işi transaction içinde DEĞİL.**

---

## 5. HTTP Route'ları (`server.py`)

`ROOT_PATH` (örn `/scorm`) altında mount edilebilir. Tam URL'ler `PUBLIC_BASE_URL`'den üretilir.

| Route | Amaç | Auth |
|---|---|---|
| `POST {ROOT_PATH}/mcp` | Streamable HTTP MCP endpoint | API key (header) |
| `GET  {ROOT_PATH}/files/{token}` | Build edilmiş `.zip` indirme | token (imzalı/rastgele) |
| `GET  {ROOT_PATH}/preview/{token}` | Önizleme HTML servis | token |
| `GET  {ROOT_PATH}/health` | Healthcheck → 200 `{status:"ok"}` | yok |

- **Transport:** Streamable HTTP (`transport="http"`). SSE **kullanılmaz**. stdio yalnızca lokal test.
- **Auth header:** `Authorization: Bearer <api_key>` (FastMCP `authenticate` hook).
- **Ters proxy notu:** buffering kapalı olmalı (streaming için) — README'ye yazılır.

---

## 6. Güvenlik & Limitler

- **HTML sanitizasyonu:** tüm `*_html` alanları §1.3'teki beyaz listeye göre temizlenir (bleach/nh3).
  `script`, inline `on*` handler, `javascript:` URL **yasak**. Bileşenlerin kendi JS'i şablondan gelir.
- **Asset:** `filename` sanitize (path traversal yok); izinli mime: `image/*`, `video/mp4`,
  `audio/mpeg`, `application/pdf`, `font/*`. Tek asset ≤ `MAX_ASSET_MB` (vars. 25).
- **Kota:** proje sayısı > `MAX_PROJECTS_PER_KEY` veya toplam boyut > `MAX_PROJECT_MB`(/key) → `quota_exceeded`.
- **suspend_data:** SCORM 1.2 limiti 4096 char; branching state bunu aşarsa `validate_package` uyarır.
### 6.1 SSRF Guard — `add_asset` / `AssetInput.source` URL Çekimi (ZORUNLU)

`add_asset` ve `build_from_spec` dış URL çektiği için aşağıdaki kurallar **bağlayıcıdır**:

- **Yalnız `https://`** şeması kabul edilir (`http`, `file`, `ftp`, `gopher`, `data:` URL hariç —
  `data:` base64 ayrı yoldan, fetch'siz işlenir). Kullanıcı:parola içeren URL reddedilir.
- **DNS çözümle, ÇÖZÜLEN IP'yi denetle** (hostname'e güvenme → DNS rebinding'e karşı). Tüm A/AAAA
  kayıtları kontrol edilir; biri bile bloklu aralıktaysa istek reddedilir (`asset_error`).
- **Yönlendirmeleri (3xx) takip etme** — ya tamamen kapalı, ya da her hop için aynı IP denetimi
  tekrar uygulanır. `Location` bloklu IP'ye giderse reddet.
- **Bloklu IP aralıkları** (IPv4 + IPv6, çözülen adrese göre):

  | Kategori | Aralık(lar) |
  |---|---|
  | Loopback / localhost | `127.0.0.0/8`, `::1/128` |
  | Özel (private) IPv4 | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |
  | Link-local | `169.254.0.0/16`, `fe80::/10` |
  | **Cloud metadata** | `169.254.169.254` (AWS/GCP/Azure IMDS), `fd00:ec2::254` (AWS IPv6 IMDS) |
  | Unspecified / "this host" | `0.0.0.0/8`, `::/128` |
  | CGNAT (paylaşımlı) | `100.64.0.0/10` |
  | IPv6 ULA (private) | `fc00::/7` (fc00::/8 + fd00::/8) |
  | Multicast / reserved | `224.0.0.0/4`, `240.0.0.0/4`, `ff00::/8`, `2001:db8::/32` |
  | IPv4-mapped/compat IPv6 | `::ffff:0:0/96`, `::/96` → eşlenen IPv4'e göre yeniden denetlenir |

  Pratikte: `ipaddress` ile parse → `is_private | is_loopback | is_link_local | is_multicast |
  is_reserved | is_unspecified` herhangi biri True ise **VEYA** yukarıdaki metadata/CGNAT/ULA
  açık listesine düşüyorsa → **reddet**.

- **Diğer sertleştirmeler:** bağlantı timeout (vars. 5sn) + toplam timeout (vars. 30sn);
  indirme boyutu `MAX_ASSET_MB`'de **stream sırasında** kesilir (Content-Length'e güvenme);
  yanıt mime izinli listede olmalı (§6 asset kuralları). İhlal → `asset_error`.

---

## 7. Hata Kodları (`ToolError.code`)

| code | anlam |
|---|---|
| `not_found` | proje/ekran/asset yok |
| `unauthorized` | geçersiz/expired/disabled API key |
| `quota_exceeded` | kota aşıldı |
| `validation_error` | spec/şema geçersiz (detay `errors[]`) |
| `asset_error` | indirme/mime/boyut hatası |
| `build_error` | paketleme başarısız |
| `rate_limited` | (opsiyonel) çok fazla eşzamanlı build |

---

## 8. Ortam Değişkenleri (`.env.example`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PUBLIC_BASE_URL` | `https://mcp.edumints.com/scorm` | Tam dış URL kökü (download/preview üretimi) |
| `ROOT_PATH` | `/scorm` | Uygulama path-prefix'i (Traefik strip) |
| `DATA_DIR` | `/data` | SQLite + assets + packages kök dizini |
| `PORT` | `8000` | HTTP port |
| `PACKAGE_TTL_DAYS` | `7` | Build zip otomatik silme süresi |
| `MAX_PROJECT_MB` | `50` | Anahtar başına toplam proje boyutu sınırı |
| `MAX_PROJECTS_PER_KEY` | `100` | Anahtar başına max proje sayısı |
| `MAX_ASSET_MB` | `25` | Tek asset boyut sınırı |
| `BUILD_WORKERS` | `8` | Build threadpool worker sayısı (9-core kutu) |
| `BUILD_SYNC_TIMEOUT_SEC` | `4` | Fast-path: build sonucu bu süre içinde dönerse senkron döner (§3.1) |
| `ANTISLOP_STRICT` | `0` | `1` → sunucu genelinde strict anti-slop varsayılanı (§3.2); tool'daki açık `strict` parametresi kazanır |
| `SCORM_DEFAULT_VERSION` | `1.2` | Varsayılan paketleme sürümü |
| `DB_PATH` | `${DATA_DIR}/scorm.db` | SQLite dosyası |
| `PREVIEW_TTL_MIN` | `60` | Preview token ömrü |
| `LOG_LEVEL` | `INFO` | Log seviyesi |
| `DEMO_FRAME_ANCESTORS` | `'self'` | `/demo/{slug}` `Content-Security-Policy: frame-ancestors` değeri (1.5) — iframe gömme politikası |

`DATA_DIR` alt yapısı: `scorm.db`, `assets/<project_id>/...`, `packages/<pkg>.zip`, `previews/<token>.html`.

---

## 9. Runtime Sözleşmesi (`runtime/` + `components/`)

- **`scorm-again` vendored — PİNLİ SÜRÜM (tekrarlanabilirlik için sabit):**
  - **Sürüm: `scorm-again@3.0.5`** (npm latest @ 2026-06-01). Bu sürüm aynen vendor edilir;
    güncelleme yalnız bu satırı + `runtime/VENDOR.lock`'u değiştirerek yapılır.
  - Kaynak: `https://registry.npmjs.org/scorm-again/-/scorm-again-3.0.5.tgz`
  - Bütünlük (npm dist): `sha512-UW4VvfGrB7+izNtABATQrp6ztPUV43Poyah3CbMdMkeF0gTrKu8RsnYXy2LRGmnIN2rPvQ6fnVk3HPYmAMiyVg==`
    (shasum `94fc187a545768f591b9818543d3dd0268971d24`).
  - Dosya: UMD/IIFE build → `runtime/scorm-again.min.js`.
  - **`runtime/VENDOR.lock` zorunlu:** `{ package, version, source_url, integrity, vendored_at }`
    kaydeder; Faz 1·B vendor anında doğrular. **Elle yazılmış API stub YOK.**
- **Önizleme:** `scorm-again` `Scorm12API` (veya 2004 `Scorm2004API`) bellekte `window.API` /
  `window.API_1484_11` olarak çalışır, kalıcılık yok (LMS yokken no-op commit).
- **Paket:** aynı runtime; gerçek LMS API'sini host frame'de bağlar.
- **Renderer (`components/renderer.py`):** `spec → HTML`. Önizleme ve paket **aynı** renderer'ı kullanır.
  Çıktı tek `index.html` (+ paket modunda `assets/`, `runtime/`, `imsmanifest.xml`).
- **Skor köprüsü:** quiz bileşenleri toplam puanı 0..100'e ölçekler →
  1.2: `cmi.core.score.raw`, `cmi.core.lesson_status`; 2004: `cmi.score.raw/scaled`, `cmi.completion_status`,
  `cmi.success_status`. `set_tracking` kurallarına göre tamamlanma/geçme yazılır.
- **Hedef köprüsü (S2 / 2.4):** kurs `objectives` + ekran `objective_ids` tanımlıysa runtime her skor
  commit'inde (`evaluate()`) hedef başına doğru/toplam toplar (saf mantık `components/engine/scorm.js`:
  `aggregateObjectives`/`objectiveElements`/`objectiveIndices`; vitest'li) ve yazar —
  1.2: `cmi.objectives.n.id`, `.score.raw/min/max` (0–100), `.status`;
  2004: `.id`, `.score.scaled` (0–1), `.success_status`, `.completion_status`.
  POLİTİKA: yalnız ≥1 puanlı ekrana bağlı hedefler yazılır (bağsız hedef = yazarlık hatası,
  antislop `unbound_objective` WARN'ı). Sıra HER ZAMAN kurs hedef sırası; indeksler LMS'te önceden
  var olan kayıtlara (2004 manifest pre-populate) id üzerinden çakışmasız çözülür, mevcut `.id`
  yeniden yazılmaz. Hedef başına geçme eşiği = kursun `passing_score`'u (S6 ile tutarlı).

---

## 10. Manifest Sözleşmesi (`core/manifest.py`)

- Girdi: `Project`. Çıktı: geçerli `imsmanifest.xml` string.
- 1.2: `ADL SCORM 1.2` şeması; tek SCO (v1), `organizations/organization/item`, `resources/resource`
  (`adlcp:scormtype="sco"`), tüm asset'ler `<file>` olarak listelenir.
- 2004: `ADL SCORM 2004 4th Ed`; sequencing **iskelet** (v1 kapsamı), API ayrımı baştan dursun.
- `validate_package` manifest'i XSD/yapısal kontrolden geçirir.
- S7 (2.3) — `<metadata>` içine opsiyonel `imsmd:lom` bloğu (her iki sürüm de IMS Meta-data 1.2.4
  binding'i kullanır, namespace `http://www.imsglobal.org/xsd/imsmd_v1p2`; resmi 1.2.1 binding
  BİLEREK kullanılmadı — UPA/libxml2 altında derlenemiyor, bkz. `core/manifest.py` yorumu).
  `general/title` + `general/language` HER ZAMAN basılır (Project'te zorunlu/varsayılı);
  `description`/`keyword`/`educational/typicalLearningTime` yalnız `project.metadata` doluysa.
  `intended_audience` LOM'a eşlenmez.
- S2 (2.4) — 2004'te kurs hedefleri `imsss:primaryObjective`'den SONRA non-primary
  `imsss:objective/@objectiveID` olarak basılır: yalnız ≥1 puanlı ekrana bağlı hedefler, kurs hedef
  sırasında (runtime cmi.objectives politikasıyla birebir). Rollup/kural eklenmez → leaf item'da
  inert, `controlMode` yine yok ([6022]). KARAR: `passing_score` 0 iken sequencing bloğu hiç
  basılmadığından (2.1 sözleşmesi; `primaryObjective` zorunlu-ilk-çocuk) hedefler o durumda
  RUNTIME-ONLY kalır. 1.2 manifest'inde hedef karşılığı yok (yalnız runtime `cmi.objectives`).

---

## 11. Definition of Done (özet — bkz. ana prompt §6)

- `tests/test_golden.py` yeşil: spec → `build_package` → zip aç → manifest geçerli + `index.html` +
  scorm-again gömülü + en az bir quiz skorlama hook'u çalışıyor.
- `preview` tek-dosya, harici bağımlısız HTML.
- `--transport http` ile kalkıyor; MCP Inspector tool'ları görüyor.
- `Dockerfile` build oluyor; `/health` 200.
- Yük testi (k6/locust) build yolunu dövüyor; kapasite raporu README'de.

---

## 12. Modül Interface Sözleşmesi (Faz 2 entegrasyon — kanonik imzalar)

Faz 1 ajanlarının raporladığı boşlukları kapatır. Modüller **tam olarak** bu imzalara uyar.

### 12.1 Çıktı modellerinin yeri
Tüm `*Out` modelleri (`CreateProjectOut`, `AddScreenOut`, `OkOut`, `ListScreensOut`, `ScreenSummary`,
`AddAssetOut`=`AssetRef`, `PreviewOut`, `BuildOut`, `ValidateOut`, `ValidationError`,
`BuildFromSpecOut`) → **`core/project.py`** içinde tanımlanır (tek import kaynağı; server bunları kullanır).

### 12.2 `core.store`
```python
def create_store(db_path: str, data_dir: str) -> Store: ...   # fabrika
# Store soyut; SqliteStore somut. Kullanım:
store = create_store(DB_PATH, DATA_DIR)
await store.init()                                            # şema/PRAGMA/dizinler
```

### 12.3 `core.packager`
```python
class Packager:
    def __init__(self, store: Store, data_dir: str, *, workers: int,
                 renderer, public_base_url: str, package_ttl_days: int): ...
    async def submit(self, project: Project) -> BuildJob: ...        # idempotent (§3.1)
    async def wait(self, job_id: str, timeout: float) -> BuildJob: ... # fast-path bekleme
    async def get(self, job_id: str) -> BuildJob | None: ...
    async def start_ttl_cleaner(self) -> None: ...                    # arka plan döngü
    def artifact_warnings(self, job_id: str) -> list[str]: ...        # SP-5: bloklamayan uyarılar
    # düşük seviye (threadpool'da çalışır):
    def build_sync(self, project: Project) -> PackageMeta: ...
```
`renderer` parametresi §12.5'teki callable'dır (DI ile geçilir — packager components'a doğrudan
import bağımlısı olmaz; gevşek bağlama).

SP-5 (B1 delta) — **artifact kapısı:** `_run` job'u "done" işaretlemeden önce üretilen zip'i
`validate_zip`'ten geçirir. Doğrulama noktası bilinçli olarak job tamamlanmasıdır: fast-path de
async yol da buradan geçtiği için `build_status`/download hiçbir zaman doğrulanmamış zip göremez.
Yapısal hata → paket DB'ye kaydedilmez, bozuk zip diskten silinir, job `error`
(`ArtifactValidationError: ...`); `schema_unavailable` bloklamaz, `artifact_warnings(job_id)`
üzerinden yanıttaki `warnings`'e taşınır (in-process; restart sonrası boş — danışsal).

### 12.4 `core.validator`
```python
def validate_project(project: Project, *, strict: bool = False) -> list[ValidationError]: ...
    # boş = ok; strict=True (SP-5): antislop.STRICT_PROMOTED_CODES da bloklar (§3.2)
def validate_zip(zip_path: str, scorm_version: str) -> list[ValidationError]: ...
```

### 12.5 `components.renderer`
```python
def render_html(project: Project, *, mode: Literal["preview", "package"],
                runtime_js: str,
                asset_data: dict[str, tuple[str, bytes]] | None = None,
                review: bool = False,
                canonical_url: str | None = None) -> str: ...
# mode="preview": TEK dosya, harici bağımlılık YOK (runtime_js + tema + CSS + JS gömülü);
#                 asset_data verilirse asset'ler data-URI olarak gömülür (gerçek self-contained)
# mode="package": index.html; assets/ ve runtime/scorm-again.min.js'e referans verir
# review (1.1): yalnız gerçek önizleme/inceleme akışında review FAB'ı/paneli basılsın
# canonical_url (1.4): og:url için; yalnız publish_demo geçer (KALICI /demo/{slug} linki)
def load_runtime_js() -> str: ...        # runtime/scorm-again.min.js içeriğini döndürür
```

### 12.6 Asset çekim sorumluluğu (`build_from_spec` / `add_asset`)
- **Server** (Ajan C) çeker: `https://` → `auth.ssrf.safe_fetch_asset(url) -> (bytes, mime)`;
  `data:` → base64 decode (fetch yok). Sonra `store.put_asset(...)` ile yazar.
- **Packager** yalnız montaj yapar; ağ çekimi yapmaz (asset'ler store'da hazır).
