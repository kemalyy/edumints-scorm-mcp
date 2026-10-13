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

class ColorPalette(BaseModel):        # OTORİTER varsayılanlar: themes/_tokens.json (Faz 5 AA-uyumlu; testle senkron)
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
    text_muted: str = "#6c6c75"
    text_on_dark: str = "#f8fafc"
    # semantik (geri bildirim / quiz)
    success: str = "#168139"
    success_bg: str = "#dcfce7"
    error: str = "#cb2323"
    error_bg: str = "#fee2e2"
    warning: str = "#975606"
    info: str = "#0284c7"
    focus_ring: str = "#2563eb"           # erişilebilirlik odak halkası
    # Faz 6b — data_chart seri renkleri (düzen ölçüm raporu §4.1: sabit hex → token).
    # Renderer YALNIZ data_chart içeren kursa --chart-N basar (3.3 bayt-parite); SVG
    # var(--chart-N, <fallback>) kullanır. Her seri × her sevk edilen yüzey 1.4.11 ≥3:1
    # AA matris kapısındadır (tests/test_theme_contrast.py).
    chart_series: list[str] = [...]       # 8 renk; otoriter değerler themes/_tokens.json

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

**Tema katman sırası (Faz 5 — senaryo hattı Kol D):**

```
_tokens (themes/_tokens.json, taban semantik set — ThemeTokens model varsayılanlarıyla senkron)
  → stil preseti (themes/<preset>.json, extends zinciri; HER preset _tokens'a ulaşır)
  → kitle override'ı (themes/audience/<audience_pack>.json — VARSA; sözleşme:
    themes/audience/_README.md — sıfırdan tema olamaz [extends yasak, AUDIENCE_NO_EXTENDS],
    tema kimliğini/ekran tiplerini değiştiremez [3.4/3.7], dosya yoksa no-op)
  → kurs custom (spec.theme inline ThemeTokens / set_theme — yalnız AÇIKÇA verilen alanlar)
```

Her katman alan-bazlı derin merge'dür. `audience_pack` verilmediğinde çözüm eski davranışla
bayt-bayt aynıdır (3.3). Sevk edilen her preset ve her preset×audience kombinasyonu
`tests/test_theme_contrast.py` otomatik AA kontrast kapısından geçmek ZORUNDADIR (3.5 —
erişilebilirlik zemindir; ayrıntılı çift matrisi test dosyasında belgelidir).

**Karanlık mod ekseni (Faz 6b — plan 7.3: kozmetik mod, preset'lere ORTOGONAL):**

`theme_mode: "light" | "dark" | "auto" = "light"` (CourseSpec + Project). Karanlık mod ayrı
preset DEĞİLDİR; katman zincirinin ÇÖZÜLMÜŞ çıktısının üstüne render anında compose edilir
(`core/theme_dark.derive_dark_theme`):

```
çözülmüş tema (yukarıdaki 4 katman)
  → themes/_dark-overlay.json  (nötr zeminler + durum renkleri + koyu chart_series + elevation;
    overlay bir tema değildir: name/extends YASAK — audience disipliniyle aynı)
  → en-yakın-uyumlu oturtma    (preset kimlik mürekkepleri primary/primary_hover/focus_ring
    korunur; koyu zeminlerde AA'yı tutturan ASGARİ beyaz karışımına deterministik çekilir —
    zaten geçen renk DEĞİŞMEZ)
```

Emisyon: `light` → bugünkü çıktı BAYT-BAYT (sıfır davranış değişikliği, test kilidi);
`dark` → `:root` koyu değişkenler + `color-scheme:dark`; `auto` → aydınlık `:root` +
`@media (prefers-color-scheme: dark)` bloğu (saf CSS — JS/koşul yok, işletim sistemi seçer).
AA kapısı mod ekseniyle büyür: her preset(×audience) hem `light` hem `dark` varyantıyla tüm
çiftleri geçmek ZORUNDADIR; yeni preset eklendiğinde koyu türevi otomatik matrise girer.
Bilinçli sınırlama: kurs yazarının kendi SVG asset'leri tek-şemadır — tema tersine dönünce
uyum sağlamaz (ölçüm raporu §4.1'de kayıtlı).

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
| `exploration` | F2 (#113): `prompt_html`, `input_kind: "text" \| "choice" \| "prediction" = "text"`, `choices?: list[Choice]` (choice/prediction için ≥2 — model doğrular), `placeholder?`, `min_length?`, `store_key` (`[a-z0-9_-]+`, ≤64; kurs genelinde TEKİL — `validate_project` çakışmayı SERT hatayla keser). Öğrenen girdisi suspend v2 kuyruğundaki `xp` haritasında saklanır (değer **500 UTF-8 BAYTTA** kırpılır — scorm.js `EXPLORATION_VALUE_MAX`; Faz 4-ek: ölçüm karakterce değil baytça, Türkçe 2 bayt/harf); sonraki ekranlar zengin HTML içinde `<span data-exploration-ref="store_key"></span>` ile GERİ OYNATIR (runtime yalnız textContent yazar — innerHTML asla; boş değer i18n yer tutucusu). PUAN ALANI YOK — skorsuz/formatif (A4 skorsuz-erken-deneme istisnasının teknik karşılığı; Z3) |

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

#126 (Faz 6b, Kol D) — **`labeled_diagram.mode: "quiz" | "display" = "quiz"`.** `quiz`
(varsayılan) bugünkü etkileşimli/skorlu davranış, **bayt-bayt** korunur (3.3). `display` =
**salt-gösterim callout** modu: her işaretçinin `text`'i görsel ÜSTÜNDE statik callout
(koordinat @num dot + leader line + metin kutusu) olarak render edilir — split-attention
"exhibit" deseninin çözümü (ölçüm raporu §5.3). select/skor/feedback YOK; metin gerçek DOM
metni (tooltip değil → klavye/dokunma/SR erişilebilir); renkler AA-gated token'dan (matris
deltası 0). `display` ekranı **skorlanmaz** (`total_points` dışı, `is_quiz=false`,
`_has_scored_content` tek-başına saymaz) ama **kanıt-taşıyabilir** hedeftir (E1, yukarı).
Tek doğruluk kaynağı `core/project.py::is_display_diagram` — tüm skor/etkileşim kapıları
(`_is_scored`, `_is_evidentiary_target`, `_course_config`, manifest) bu helper'ı çağırır.

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
  quiz/oyun tipleri YALNIZ formatifken (points=0 ve puana yazmıyor — Z3);
  **display-modlu `labeled_diagram`** (#126 — annotasyon yorumu taşıyan salt-gösterim exhibit;
  KOŞULSUZ kanıt-taşıyabilir, skorlanmaz). Taşıyamaz: title_slide,
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
    theme_mode: Literal["light", "dark", "auto"] = "light"  # Faz 6b — kozmetik mod ekseni (§1.1)
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

### 1.6 Kompozisyon + vurgu kademeleri (K1)

**Yalnız `Project.composition == "auto"`
iken render edilir**; `classic` projelerin çıktısı bayt-aynıdır.

```python
Project.composition: Literal["classic", "auto"] = "classic"   # model varsayılanı: eski projeler classic
CourseSpec.composition: Literal["classic", "auto"] = "auto"   # yeni kurslar auto
# ScreenBase (31 tipin hepsi alır; K1'de yalnız title_slide + content_slide render eder):
kicker: str | None            # ≤40 karakter — E3 üst etiket
lead: str | None              # E1 — ekranın tek ana mesajı (≤20 kelime önerilir)
composition: str | CompositionSpec | None   # desen adı veya nesne
class CompositionSpec(BaseModel):            # extra="forbid"
    preset: str | None; mirror: bool | None
    grid: str | None                         # "thirds" | "halves" | "a:b" (1-9)
    areas: dict[str, str] | None             # yuva (support|focal|aux|steps) → "c1r1-c2r3"
    focal: str | None                        # yuva adı veya hücre "r1c3"
    flow: "z"|"f"|"center"|None; whitespace: "low"|"normal"|"high"|None
    intensity: "calm"|"normal"|"high"|None
ThemeTokens.emphasis: Emphasis | None        # e1..e5 {color,size,weight} + e3_bg; yoksa paletten türetilir
```

- **Desen kataloğu:** `compositions/*.json` (7: centered, split-thirds, split-halves, hero-focal, statement,
  z-flow, f-flow). Yeni desen = yeni JSON dosyası; `applies_to` hangi ekran tiplerine uygulanabileceğini söyler.
- **Otomatik seçim:** yazar `composition` vermezse içerik sinyallerinden (medya, blok, kelime, liste, `lead`)
  deterministik desen + kurs ritmi (ilk/son/ünite açılışı `high`, içerik `calm`, soru `normal`; ≥3 `high`
  art arda yok; aynı desen art arda >3 yok). Açık parametre her zaman kazanır.
- **Render:** `<section data-comp data-focal data-flow data-ws data-intensity data-sym style="--comp-cols;--comp-rows">`
  + `.comp-grid > .slot.slot-<yuva>` (DOM sırası odak-önce → mobil okuma sırası). CSS `--em1…--em5`, `--em3-bg`
  (`--e1…--e4` elevation'dır). `<mark>` yalnız auto'da beyaz listede (E3).
- **Tema:** "default" adı yalnız auto projede `mint`'e yönlenir (`themes/default.json` değişmez). Yeni
  paletler: `mint` (varsayılan), `ink`, `slate`. Koyu modda kademeler koyu paletten türetilir.
- **Fontlar (#160):** auto projede temanın kullandığı Inter/Outfit/JetBrains Mono (OFL) `runtime/fonts/`
  altından pakete (preview'da data-URI) gömülür.
- **K2 (görsel etkileşimli tipler):** `hotspot`, `labeled_diagram`, `image_compare`, `data_chart`,
  `video`, `lottie`, `simulation` da yuvalarla render edilir. Görsel öğe `focal`, metin + soru denetimleri
  `support`. Yeni desen `visual-stack` (metin üstte bant, görsel 2/3). Varsayılan: `lead` var veya metin
  ağırlığı (`lead` + istem + video anlatımı) > 30 kelime → `split-thirds`, aksi → `visual-stack`.
  Soru kipinde (`hotspot` quiz, `labeled_diagram` quiz, `simulation`) `dom_order="support-first"` (mobilde
  soru görselden önce). JS'in beklediği kaplar korunur: `.labeled-diagram` içindeki `.ld-select`'ler,
  `.simulation` içindeki adım yönergeleri.
- **K3 (soru ailesi):** `mcq`, `true_false`, `fill_blank`, `drag_drop`, `matching`, `sorting`,
  `adaptive_practice` yuvalarla render edilir. Opsiyonel **`stimulus`** (`Stimulus{asset_id?, alt?,
  text_html?, caption?}`, `extra="forbid"`, `asset_id` veya `text_html` zorunlu) — altı tipte ekran
  düzeyinde, `adaptive_practice`'te **öğe başına** (`AdaptiveItem.stimulus`). Uyaran varsa `focal` =
  uyaran, `support` = başlık + istem + cevap alanı + kontrol; yoksa `support` = başlık + istem, `focal` =
  cevap alanı. Yeni desen `question-column` (tek okunaklı sütun ≈ 64ch; uyaransız soruların varsayılanı).
  Uyaranlı: metin > 40 kelime ya da görsel + metin → `split-thirds`, aksi → `visual-stack`. `dom_order`:
  uyaranlı focal-first, uyaransız support-first. Uzun listeler iki sütun (`mcq` > 6 şık, `matching` > 5
  çift; `data-many` — `sorting` tek sütun kalır, kurulan sıra belirsizleşmesin). Classic'te uyaran istemin üstünde blok olarak basılır (uyaransız
  classic çıktı bayt-aynı). Uyaran **uygulama kanıtıdır**: soru yine `evidence_screen_ids` ile kavramı
  öğreten ekranlara bağlanır. Uyaransız soru dizisi monotonluk kırıcıdan muaftır (tutarlılık).
- **K4 (içerik etkileşimleri):** `accordion`, `tabs`, `flashcards`, `timeline`, `summary`,
  `results_breakdown`, `poll`, `worked_example`, `exploration` yuvalarla render edilir. Etkileşimli gövde
  (classic ile aynı yardımcıdan) `focal`'da `<div class="c-body" data-k4="<tip>">` içinde; başlık + `kicker`
  + `lead` + tipin giriş metni (`prompt_html`/`intro_html`/`body_html`) `support`. Varsayılanlar:
  accordion/timeline/worked_example/poll/exploration `question-column`, tabs/flashcards `visual-stack`
  (`lead` veya giriş > 30 kelime → `split-thirds`), summary `centered`, results_breakdown `split-thirds`.
  **Tabs ana–detay:** auto'da `.tab-list` `aria-orientation="vertical"` alır; odak yuvası ≥ 600px ise liste
  solda dikey, panel sağda (container query), daha darda yatay. ↑/↓ koşullu `TABS_V_JS` ile (yalnız auto +
  tabs; `ENGINE_JS` değişmez, ←/→ çalışmaya devam eder). Accordion yerinde açılan liste kalır.
  `poll` ve `exploration` K3 `stimulus` alır (uyaranlı: vaka odak, focal-first; K3 seçim kuralı).
  İçerik gövdeli ekranlarda ızgara içerik boyundadır, sahnede ortalanır; uzun içerikte sahne kaydırılır,
  yan sütun başlığı yapışık kalır.
- **K5 (oyun / senaryo / gömülü) — 31 tipin tamamı:** `game`, `decision_scenario`, `escape_room`,
  `term_match_race`, `branching`, `embed_html`. Gövde `.c-body` içinde odakta (embed_html hariç: iframe
  yuvanın yüksekliğini doldurur). Varsayılanlar: game/decision_scenario/embed_html `visual-stack`,
  escape_room/term_match_race/branching `question-column`; `lead` veya giriş > 30 kelime → `split-thirds`
  (embed_html her zaman `visual-stack`). **Yan yana sahne:** odak yuvası ≥ 640px ve düğümde görsel varsa
  `game-node`/`scen-node` ızgara olur (görsel solda, anlatı + seçenekler sağda); dar ekranda DOM sırası
  (anlatı → görsel → seçenekler). HUD kabın üstünde tam genişlikte. `branching` K3 `stimulus` alır.
- **Uzun içerik (K6):** yuvalar `justify-content:safe center` (visual-stack destek bandı `safe
  flex-end`) — sığmayan içerik üstten başlar, sahne kaydırılır; başlık kaybolmaz.
- **Vakalı `visual-stack` (masaüstü):** vaka üst satırda, soru altta; satırlar içerikten, uzunsa sahne
  kaydırılır (K3 soru + K4 poll/exploration + K5 branching).
- **Kurs düzeyi tercih:** `Project/CourseSpec.composition_defaults: {visual?, question?} | None`, her alan
  `"auto"|"stack"|"split"|None` (None = sorulmadı). `visual` K2 tiplerinin, `question` uyaranlı K3/K4
  ekranlarının (soru tipleri + poll/exploration) otomatik seçimini ezer; ekranın açık `composition`'ı kazanır.
- **Üretim-anı soruları:** `lint_course` ve `preview` `composition_questions` döndürür (yalnız auto):
  kurs soruları (`id:"visual_layout"`: ≥3 K2 ekranı ve `visual` None; `id:"question_layout"`: ≥3 uyaranlı
  soru ekranı ve `question` None — apply `{"mode":"auto","question":"$value"}`) + ekran soruları
  (`id:"screen:<id>"`; K2 metin ağırlığı 23–37 kelime, K3 uyaran metni 30–50 kelime; **toplam** en fazla 3).
  Metinler kursun diline (`project.language`) çevrilir. Her soru `{id, scope, screen_id?,
  question, options[{value,label,description?}], default, apply}`; `apply` cevabın nasıl uygulanacağını
  söyler: kurs sorusu `{"tool":"set_composition","args":{"mode":"auto","visual":"$value"}}`, ekran sorusu
  `{"tool":"set_screen_composition","args":{"screen_id":…,"composition":"$value"}}`. Kullanıcı tercihi
  (`visual`/`question` ≠ auto/None) monotonluk kırıcıdan muaftır ve o seriler `composition_monotony`
  uyarısı üretmez. `centered` K2 tiplerine uygulanmaz (görsel her zaman odak). Şema MRTR `inputRequests`'e
  eşlenebilir (klasik elicitation kullanılmaz — `json_response=True`).
- **Lint (yalnız auto):** `composition_unknown`/`focal_area_empty` (error); `multiple_focal_points`,
  `emphasis_inflation`, `mark_overuse`, `lead_too_long`, `composition_monotony`, `intensity_run` (warn →
  strict'te error); `composition_ignored_classic` (info, classic projede alan doluysa).
- **Lint (K3, her modda):** `stimulus_without_alt` (error — görsel uyaran `alt`sız);
  `stimulus_answer_leak` (warn → strict'te error — doğru şık / kabul edilen cevap / doğru `true_false`
  önermesi uyaran metninde birebir geçiyor; HTML, noktalama, büyük/küçük harf ve boşluk normalize, kelime
  sınırlı). Validator: `stimulus.asset_id` (ekran + adaptive öğe) proje asset'lerinde olmalı.

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
    theme_mode: Literal["light", "dark", "auto"] = "light"  # Faz 6b — Project aynası (§1.1);
                                          # light = bayt-parite (mevcut kurslar değişmez)
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

Senaryo hattı Faz 3 (additive): `media_provenance: list[dict] = []` — `scenario_compile`'ın
ürettiği dolu-slot provenance kayıtları (`Project.media_provenance`'a taşınır). Boş DEĞİLSE
paketleyici zip'e `assets/PROVENANCE.json` yazar + manifest'e ekler; boş = bugünkü davranış
birebir (düz kurslar dosya KAZANMAZ — geriye-uyum/bayt-parite, testli).

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
    unlock_rule: Literal["free", "sequential"] = "free"
                                          # Faz 4 (§6.1): "sequential" = önceki KARDEŞİN alt-ağacındaki
                                          # tüm bağlı ekranlar ziyaret edilmeden düğüm kilitli.
                                          # "Tamamlandı" = ziyaret; skor eşiği GEZİNMEYİ kilitleyemez
                                          # (erişilebilirlik zemini — sonuç kapıları results tarafında).
                                          # Runtime konfige yalnız "sequential" iken serileşir.
```

- **Yapısal SERT doğrulamalar** (`validate_project`, veri bütünlüğü 3.8): sarkan `parent_id`,
  döngü (self-parent dahil), derinlik > 3 (kök=1), yinelenen düğüm id'si, sarkan
  `screen.node_id`, hedef-ad-alanı çakışması. Outline boş + hiçbir ekranda `node_id` yok →
  doğrulama çıktısında SIFIR yeni kalem. **Faz 4:** `UNREACHABLE_NODE` SERT hata —
  `sequential` düğümün önceki kardeşinin alt-ağacında bağlı ekran yoksa düğüm asla açılamaz
  (içerik tuzağı; runtime aynı durumda savunmacı olarak AÇIK bırakır).
- **Player**: outline'lı kursta slayt menüsü APG `role="tree"` hiyerarşisi olarak SUNUCUDA
  render edilir (katlanır düğümler, tam klavye, `aria-current="page"`, roving tabindex;
  `node_id`'siz ekranlar sonda i18n başlıklı düz grupta). Outline boşken üretilen HTML
  bugünkü düz menüyle **bayt-bayt aynıdır** (fixture testli — `tests/test_outline_menu.py`).
- **Player Faz 4 — konum/ilerleme/kilit/devam** (saf mantık `components/engine/progress.js`
  → `window.SCORMP`, YALNIZ outline'lı pakete inline; DOM katmanı OUTLINE_JS):
  - **Konum şeridi**: başlıkta `#posStrip` — "Ünite 1 · Bölüm 1.1 · 2/4" (düğüm zinciri +
    düğüm-içi n/m); `aria-live="polite"` yalnız metin değişince duyurur; n/m parçası
    `dir="ltr"` (RTL-güvenli); düğümsüz ekranların başlığı sunucudan i18n ile gelir.
  - **Düğüm ilerlemesi**: menüde düğüm başına alt-ağaç kümülatif `n/m` (`.mtree-progress`);
    results_breakdown bölüm tamamlanması AYNI `data-screens` mekanizmasından `.rb-comp`
    olarak basılır (**ikinci bir hedef-ilerleme makinesi YOK**).
  - **Kilit** (`unlock_rule="sequential"`): düğüm GÖRÜNÜR + `aria-disabled="true"` +
    sunucu-render sebep metni görünür (engelleyen düğümü ADIYLA anar, butonun erişilebilir
    adının parçası → SR odakta okur) + dal katlanır; odaklanılır ama etkinleştirilemez,
    klavye tuzağı yok. Kilit alt-ağaca yayılır (sebep kökteki engelleyici).
  - **Düğüme devam**: resume'da kaldığı ekran + düğüm zinciri `aria-expanded` ile açılır +
    `aria-current` oturur (kullanıcının el katlaması ezilmez — yalnız aktif zincir açılır).
  - **Hiyerarşik suspend (3.11 — Faz 4-ek REVİZYONU)**: v2 zarfı artık `z` POZİSYON KAYDI
    taşır (aşağıdaki Faz 4-ek sözleşmesi — 3.11'in "alan girmedi" kararı republish
    dayanıklılığı için bilinçli güncellendi). Serbest metin (düğüm başlığı, kilit sebebi) ve
    menünün el katla/aç durumu suspend'e YİNE ASLA girmez; outline'ın tek zarf maliyeti `z.n`
    düğüm id'sidir (testli). 3 kademe × 30 sayfa gerçekçi durum **3500 bayt bütçenin altında**
    (vitest kabul #12 — ölçüm UTF-8 bayt). Taşmada grep'lenebilir `SUSPEND_OVERFLOW` uyarısı +
    xAPI `suspend.trouble` izi (sessiz kırpma yok).
- **Faz 4-ek — suspend taşma merdiveni + republish-resume dayanıklılığı**:
  - **Bütçe = 3500 BAYT (1.2)**: `SUSPEND_BUDGET_12` çalışma bütçesidir; 4096 sınırının kalanı
    LMS kaçışlama ek yüküne REZERV. 2004'te aynı oran (`suspendBudget`). **TÜM ölçüm UTF-8
    BAYT** (`byteLen`/`byteSlice`; Türkçe ç ğ ı ö ş ü = 2 bayt — `.length` ölçümü yasak).
    Zarfın kendi alanları ASCII'dir (kısa anahtar, id, base36/int — testli); Türkçe yalnız tail
    serbest metnine (vars/xp) girebilir. Sunucu projeksiyonu `estimate_suspend_size` aynı
    birimde; bütçe aşımı yazar `SUSPEND_OVERFLOW` WARN'ı (projeksiyon sayısıyla; derleme
    engellenmez — runtime merdiveni SON ÇAREDİR).
  - **Kırpma merdiveni** (`encodeSuspendFit`; üst korunur, alt önce düşer; her basamak sonrası
    yeniden ölçüm): korunan tepe = pozisyon kaydı `z` + cursor + `reachedEnd` + `inext`
    (ASLA düşmez) › rung 1 `history` › rung 2 `xp` (öğrenen serbest metni) › rung 3 sayfa
    cevapları (`results`/`ix`/`vars`) — düşmeden önce hedef toplamları + toplam puan **`g`/`e`
    tabanı** olarak tail'e alınır › rung 4 `g`/`e` + `visited` (yalnız pozisyon). Basamak zarfa
    **`t`** kısa anahtarıyla yazılır; oynatıcı basamağa göre davranır: t≥1 geri tuşu lineere
    düşer, t≥2 keşif yer tutucuya döner, t≥3 skor/hedef `g`/`e` tabanından yazılır (canlı cevap
    gelen hedefte canlı kazanır — `mergeObjectiveSnapshot`, skor geriye gitmez), t=4 decode
    `visited`'ı LİNEER YAKLAŞIMLA kurar (cursor'a kadarki ekranlar gezilmiş sayılır — kilit
    tuzağı/tamamlanma sıfırlanması olmasın; belgeli yaklaşıklık). Kayıp SESSİZ DEĞİL:
    `console.warn` HER ZAMAN (bayt+bütçe+rung; xAPI/LRS'e bağımsız), xAPI `suspend.trouble`
    yalnız LRS varsa EK; SCORM'da öğrenciye görünmeyen ucuz LMS hata kanalı YOKTUR (belgeli
    karar — konsol+xAPI ile sınırlı). Öğrenciye teknik hata asla gösterilmez.
  - **Pozisyon kaydı `z` = `{s: ekranId, n: düğümId, v: content_version}`** — KİMLİK-tabanlı
    (pozisyonel değil), tail JSON'da; merdivenin tepesi. `COURSE.content_version` = sıralı
    (outline düğüm id'leri + ekran id'leri) djb2 özeti, 20-bit küçük int (KARAR: monoton sayaç
    değil — kaynaktan bağımsız/deterministik/mutasyonsuz; semantiği yalnız EŞİTLİK).
  - **orderFp × v etkileşimi (yeniden tasarım)**: orderFp uyuşmazlığı artık TOPTAN SIFIRLAMA
    değildir. `resumeSuspend` okuma merdiveni: fp eşleşir → TAM resume SESSİZ (fp eşleşmesi
    ekran kümesi+sırası aynı demektir; v farkı — yalnız düğüm kümesi değişimi — tam resume'u
    etkilemez). fp uyuşmaz → POZİSYONEL alanlar atılır (cursor idx, visited bitfield, history,
    indeksli results/ix — eski order bilinmediği için id'ye çevrilemez; yanlış-atıf koruması
    KORUNUR), KİMLİK-tabanlı alanlar yaşar (tail: vars/xp/id'li results + `z`/`g`/`e` + `inext`)
    ve `z` üzerinden: düğüm yaşıyor → düğüme devam SESSİZ (tam ekran varsa o, yoksa düğümün
    yeni ilk ekranı); düğüm gitmiş + ekran yaşıyor → ekranın YENİ düğümünde devam + BİLDİRİM;
    ikisi de gitmiş (ya da `z`'siz eski payload) → kurs başı + BİLDİRİM (sessiz sıfırlama YOK).
    Bildirim dostane/teknik-olmayan, i18n tr+en (`resume_updated`/`resume_restart`),
    `role=status` + `aria-live=polite`, kapatılabilir. Fallback devamda hedefe kadarki ekranlar
    lineer yaklaşımla visited işaretlenir.
  - **ID kararlılığı (ön koşul)**: `compile_scenario` id'leri ASLA pozisyonel yeniden
    numaralandırmaz (passthrough — outline ortasına ekleme/reorder mevcut id'leri değiştirmez;
    testli). Silinen sayfa/düğüm id'leri `ScenarioDocument.retired_ids`'e yazılır ve YENİDEN
    KULLANILAMAZ (`scenario_upsert_page`/`scenario_upsert_node` yeni kaydın emekli id'sini
    `validation_error` ile reddeder; mevcut kaydı güncellemek serbest). Konvansiyon: id'ler
    yazar-verilidir ve içerik anlamı değişmeden yaşar — geri dönen id eski öğrencinin devam
    noktasını/skorunu yanlış içeriğe bağlar.
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

Toplam tool sayısı **40** (senaryo hattı Faz 2: 30 → 38, 8 senaryo aracı; Faz 3: 38 → 40,
`fill_media_slot` + `match_media_manifest` — §3.0.1).

### 3.0.0 Kompozisyon araçları (K1)

```python
list_compositions() -> {"count": int, "compositions": [{"name", "description", "symmetry", "applies_to"}]}
set_composition(project_id: str, mode: "classic" | "auto",
                visual: "auto" | "stack" | "split" | None = None,             # TEK yükseltme yolu; K2 tercih
                question: "auto" | "stack" | "split" | None = None) -> OkOut  # K3 — vakalı soru tercihi
create_project(..., composition: "classic" | "auto" = "auto")         # yeni parametre
set_screen_composition(project_id: str, screen_id: str,
                       composition: str | dict | None) -> OkOut   # K2 — yalnız ekranın kompozisyonu;
                                                                 # diğer alanlara dokunmaz (soru cevapları)
```
`lint_course` ve `preview` yanıtları `compositions: [{screen_id, preset, focal, intensity, auto}]` ve
(K2) `composition_questions: [...]` taşır.

### 3.0 Senaryo araçları (senaryo hattı Faz 2 — `core/scenario.py` mantık)

Senaryo dokümanı = hiyerarşik outline + sayfalar; sahiplik projelerle aynı (auth context'i
`owner_key_id`); doküman store'da tek JSON blob (`schema_version: 1`), boyutu kotaya dahil
(Faz 3: senaryo varlık baytları da kotaya sayılır). Sayfa şeması, kanıt beyanı ENUM'u
(`EvidenceDecl` oneOf) ve medya yuvası sözleşmesi (`MediaSlot`, Faz-2'de donduruldu)
`core/scenario.py`dadır. Faz 3'te donmuş sözleşmeye TEK additive ek yapıldı:
`MediaSlot.fallback_image_asset_id: str | None` — render yolu olmayan kind'lar (bugün
`model_3d`) için 2D yedek görsel. Ayrıca `ScenarioDocument.assets: list[AssetRef]` —
senaryonun VARLIK EVİ (projelerle aynı `AssetRef` şekli + `Store.put_asset` mekaniği,
ad-alanı = `scenario_id`; `fill_media_slot` buraya yazar).

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
    #   (token containment ≥0.8, min 5 token), SLOT_KIND_UNSUPPORTED (Faz 3: model_3d yuvası
    #   fallback_image_asset_id beyan etmiyor — render yolu yok, derlemede atlanır).
    #   Suggestion: SCREEN_TYPE_SUGGESTION (yalnız öneri — ASLA otomatik seçilmez; yazar
    #   upsert ile kabul eder).

scenario_compile(scenario_id: str, compile_and_build: bool = False,
                 strict: bool | None = None) -> dict
    # Senaryoyu build_from_spec payload'una derler. ⛔ blocker varsa ToolError("compile_refused").
    # Derlenen spec: outline passthrough (düğüm hedefleri KURS düzeyine taşınır + node
    #   pedagogy_pack → Objective.method_pack; outline'dan objective ÇIKARILIR — ad-alanı
    #   çakışması olmasın), sayfalar → ekranlar (screen_type derlemede ZORUNLU — eksik/bilinmeyen
    #   = blocker), copy.body_md → sanitize HTML (deterministik md→html; raw svg/canvas/script
    #   imkânsız 3.10), evidence_from → evidence_screen_ids, inherited+extra → objective_ids,
    #   boş slot → asset omit, FAZ ADI ASLA basılmaz (3.2).
    # Faz 3 slot→alan eşlemesi: image VE data_chart → görsel alanları (media_asset_id/
    #   image_asset_id + alt; data_chart yuvası RENDER EDİLMİŞ GRAFİK GÖRSELİ taşır —
    #   data_chart EKRANI inline veri taşır, orada bağlanacak alan yok → SLOT_NOT_ATTACHED
    #   warn); audio → narration_asset_id; video → video_asset_id; lottie → lottie_asset_id;
    #   model_3d → fallback_image_asset_id görsel olarak bağlanır, yoksa SLOT_KIND_UNSUPPORTED
    #   warn + yuva atlanır. role="kanit" yuvalı content_slide media taşıdığı için kanıt-hedefi
    #   kalır (E1 koşullu kanıt kuralıyla hizalı).
    # Faz 3 varlık enjeksiyonu: REFERANSLI senaryo varlıkları (slot asset_id / fallback /
    #   captions) spec.assets[]'e data: URI olarak, id KORUNARAK eklenir; dolu slot başına
    #   provenance kaydı spec.media_provenance[]'a yazılır (boşsa anahtar hiç basılmaz).
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

### 3.0.1 Medya federasyonu araçları (senaryo hattı Faz 3 — `core/media_federation.py` mantık)

```python
fill_media_slot(scenario_id: str, page_id: str, slot_id: str, source: str,
                provenance: dict | None = None, alt_text: str | None = None,
                transcript_html: str | None = None) -> dict
    # source: "data:<mime>;base64,..." | https URL — ingest add_asset ile AYNI iç yol
    #   (decode_data_uri / safe_fetch_asset §6.1 SSRF + kota). Varlık SENARYO evine yazılır
    #   (ScenarioDocument.assets + Store.put_asset, ad-alanı = scenario_id).
    # SERT kapılar (3.8 veri bütünlüğü):
    #   - kind_mime_mismatch: SNIFF edilen MIME (magic bytes — bildirilene GÜVENİLMEZ) yuva
    #     kind'ıyla uyuşmuyor. kind kuralları: image|data_chart→image/*, audio→audio/*,
    #     video→video/*, lottie→application/json, model_3d→model/gltf-binary; tanınmayan
    #     bayt (octet-stream) = uyuşmazlık.
    #   - A11Y_NO_TEXT_ALT: role="kanit" yuvada alt_text yok (audio/video için ek olarak
    #     transcript_html) — bayt çekilmeden reddedilir. Parametre > yuvadaki mevcut a11y değeri.
    # sha256 İÇERİK-DEDUP (kabul #9): aynı bayt daha önce eklendiyse AYNI asset_id döner
    #   (deduped=true), yeni depolama yapılmaz (içerik-hash indeksi senaryo-varlık düzeyinde).
    # provenance (plan §5.4 şeması: source, tool, ref, generated_at, license_note) VERİLDİĞİ
    #   GİBİ saklanır (bilinmeyen anahtar dahil); generated_at yoksa sunucu damgalar (ISO-8601).
    # → { asset_id, deduped, sha256, mime, size_bytes, rel_path }
    # Dolu yuvayı yeniden doldurmak asset_id'yi değiştirir (bilinçli işlem; eski varlık evde kalır,
    #   derleme yalnız REFERANSLI varlıkları pakete alır).

match_media_manifest(scenario_id: str, files: list[dict]) -> dict
    # files: [{ name, size, sha256, mime }] — YALNIZ METADATA (kabul #10): şemada yol alanı
    #   YOKTUR; sunucu hiçbir dosya yoluna dokunmaz, hiçbir dizin-tarama çağrısı içermez
    #   (negatif testler: şema + kaynak grep). Yerel klasörü İSTEMCİ tarar:
    #   scripts/import_media_folder.py (bağımsız, stdlib; --dry-run destekli).
    # Eşleştirme sinyalleri: dosya adı ↔ slot_id/spec/source_hint token örtüşmesi (Türkçe
    #   karakter ASCII katlamalı), MIME ↔ kind, boyut makullüğü (0/kota-üstü → size_suspect),
    #   sha256 zaten içeride → "already_ingested_dedup" (fill aynı id'yi döndürür).
    # ÖNERİR-ATAMAZ: proposed yalnız NET tek kazanan varsa dolar (skor ≥0.5 ve 2. adaydan
    #   ≥0.2 farklı); belirsizlik = proposed null + skorlu aday listesi. Sıra deterministik
    #   (sayfa order → slot sırası; adaylar -skor, ad).
    # → { scenario_id, proposals: [{ page_id, slot_id, role, kind, spec, proposed,
    #     candidates: [{name, score, reasons[]}] }], unmatched_files[] }
```

Paket gömme (kabul #11): derlenen kursta dolu slot varsa zip `assets/PROVENANCE.json` içerir —
dolu slot başına TEK kayıt `{ page_id, slot_id, asset_id, role, kind, sha256, provenance }`,
deterministik sıra, manifest'te listeli. Düz (senaryosuz) kurslar bu dosyayı KAZANMAZ.

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
| `MEDIA_NO_CAPTION` | Faz 6b (düzen ölçüm raporu §5.2): content_slide `blocks` içinde caption'sız görsel bloğu + ekranın >80 kelimelik düzyazısı — figürün yorumu gövdede kalırsa göz gidiş-gelişi (uzamsal bitişiklik). Bugün 0 isabet — geleceğe korkuluk |

Faz 6b notu: raporun geçici önerisi `CHART_VALUES_UNREADABLE` lint OLARAK YAZILMADI — render
düzeltmesi (çizgi grafik y-ekseni + uç değer etiketleri, aşağıda §12.5) etiketleri koşulsuz
ürettiği için spec-düzeyi lint ölü kod olurdu; nihai biçimi test-düzeyi render değişmezidir
(`tests/test_charts.py::test_chart_values_unreadable_invariant`). Genel `SPLIT_ATTENTION`
lint'i ölçümle gerekçelendirilemedi ve YAZILMADI (rapor §5; test kilidi
`tests/test_layout_lint.py`).

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

`ROOT_PATH` altında mount edilebilir (prod'da boş: `scorm.edumints.com` kökü). Tam URL'ler `PUBLIC_BASE_URL`'den üretilir.

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
- **suspend_data:** SCORM 1.2 limiti 4096; Faz 4-ek ÇALIŞMA BÜTÇESİ **3500 UTF-8 BAYT** (kalan pay LMS kaçışlama rezervi). Kötü-durum projeksiyonu bütçeyi aşarsa yazar `SUSPEND_OVERFLOW` WARN'ı görür; runtime kırpma merdiveni (§2.1 Faz 4-ek) son çaredir.
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
| `kind_mime_mismatch` | Faz 3 `fill_media_slot`: sniff edilen MIME yuva `kind`'ıyla uyuşmuyor |
| `A11Y_NO_TEXT_ALT` | Faz 3 `fill_media_slot`: kanıt-rolü yuvada alt_text/transcript eksik (3.5) |
| `compile_refused` | `scenario_compile`: ⛔ blocker varken derleme reddedildi |

---

## 8. Ortam Değişkenleri (`.env.example`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PUBLIC_BASE_URL` | `http://localhost:8000` (prod: `https://scorm.edumints.com`) | Tam dış URL kökü (download/preview üretimi) |
| `ROOT_PATH` | `""` (prod: boş) | Opsiyonel path-prefix. Prod subdomain-per-MCP kullanır — OAuth protected-resource metadata (RFC 9728) host kökünde olmalı, path-prefix + Traefik strip bunu kırar |
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
- **`embed_html` artifact köprüsü (task-4, postMessage → SCORM):** `embed_html` ekranı sandbox'lı
  `<iframe class="embed-frame" data-asset data-completion data-min-seconds>` içinde keyfi HTML
  artifact'i barındırır (`components/renderer.py:_r_embed_html`). Artifact yazarı iframe içinden
  `window.parent.postMessage({scorm: "complete" | "setScore" | "passed" | "failed" | "setStatus",
  value?}, "*")` gönderir. Saf eşleme mantığı `components/engine/embed.js:bridgeToScorm(msg, is2004)`
  (vitest'li, `tests/js/embed.test.js`) — `[{key, value}, ...]` cmi yazımı listesi döner (geçersiz/
  bilinmeyen mesaj → `[]`).
  ⚠️ **`bridgeToScorm` CANLI YOL DEĞİLDİR (task-5 / FIX 7 — çağrı yeri ARAMAYIN).** Paketlenmiş
  bir kursta onu çağıran hiçbir kod yoktur; canlı yol iki adımdır: `embedStateFromMsg(msg)` →
  KOMPAKT `state.eb` yaması, sonra `embedWrites(eb, is2004)` → cmi yazımları. `bridgeToScorm`
  tam olarak bu ikisinin kompozisyonudur (`embedWrites(embedStateFromMsg(msg, is2004), is2004)`)
  ve BİLEREK korunur: bu sözleşme belgesinin ve testlerin çoğunun eşlemeyi anlattığı TEK-ADIMLI
  imzadır (fix round 3 / FINDING F). Bakım yükü yok, paket maliyeti ~3 satır. `setScore.value` **yalnız `number` tip** kabul eder (`null`/`""`/`[]`/
  `true`/`Infinity` reddedilir — fix round 1 / MINOR 4), 0–100'e kırpılır; 2004'te ayrıca `.scaled`
  (4 ondalık) yazılır. `setStatus.value` yalnız `completed|incomplete|passed|failed|browsed|
  not attempted` kabul eder; **2004'te sözlük ayrılır** (fix round 1 / IMPORTANT 1):
  `completed|incomplete|not attempted` → `cmi.completion_status`, `passed|failed` →
  `cmi.success_status` (2004'te `cmi.completion_status`'a `passed`/`failed`/`browsed` yazmak
  geçersiz vokabüler → LMS 406, yazım sessizce düşer), `browsed` 2004'te REDDEDİLİR (yalnız 1.2
  vokabülerinde geçerli, orada davranış değişmedi). DOM tarafı `components/templates.py:EMBED_JS` —
  `message` olayında `ev.source`'u kendi iframe pencereleriyle DOĞRULAR (origin değil, çünkü
  artifact'in kendi origin'i yoktur/`sandbox`lıdır); mesajı `embed.js:embedStateFromMsg` ile
  KOMPAKT kayda çevirip `state.eb`'ye işler, cmi yazımlarını `embed.js:embedWrites(eb, is2004)`
  ile TÜRETİP `sSet` + `sCommit` yapar.
  **Kalıcı kayıt `state.eb` (fix round 2 / FINDING 2):** `{s: skor 0–100, c: tamamlanma/lesson
  durumu, k: success durumu (yalnız 2004), d: {ekranId: 1} eşiği aşılmış time_threshold ekranları,
  m: {ekranId: 1} artifact'i "tamamlandı" bildirmiş on_message ekranları (fix round 3)}`.
  **`time_threshold` SAYAÇ SEMANTİĞİ (task-5 / FIX 7 — yazarlar için, iki yönlü sınır):** sayaç
  ekrana GİRİŞTE kurulan DURAKSIZ bir duvar-saati `setTimeout`'udur (`EMBED_JS:enterScreen`).
  (a) **Fazla sayar:** öğrenci başka bir ekrana geçse de, sekmeyi arka plana atsa da, iframe'e hiç
  bakmasa da eşik dolduğunda kapı AÇILIR — "ekranda geçirilen süre" DEĞİL, "ekrana ilk girişten
  sonra geçen süre" ölçülür. (Dikkat: `ENGINE_JS` oturum süresini `visibilitychange`'de
  DURAKLATIR; yani bu iki saat birbirini tutmaz — `cmi.*session_time` duraklar, kapı saati
  duraklamaz.) (b) **Eksik sayar:** defter `eb.d[ekranId]` YALNIZ sayaç ATEŞLENDİĞİNDE yazılır,
  ara ilerleme kaydedilmez — 5:00'lık bir eşikte 4:59'da yeniden yüklenen bir oturum sayacı
  SIFIRDAN başlatır. Her iki yön de bilinçlidir (ara ilerlemeyi kaydetmek suspend bütçesine
  ekran başına bir sayaç yazmak demektir); kapı bir "asgari maruz kalma" sinyalidir, denetim
  düzeyinde bir süre ölçümü DEĞİLDİR.
  cmi ANAHTARI state'te SAKLANMAZ — her zaman `embedWrites` ile türetilir. Böylece (a) 1.2'nin dar
  suspend bütçesi boşa harcanmaz, (b) `suspend_data`'dan geri okunan kayıt YENİDEN doğrulanır
  (yalnız beyaz listedeki cmi anahtarları oluşabilir), (c) 1.2'de tek kanal olan `lesson_status`
  için "son yazan kazanır" sırası korunur. Kayıt `scorm.js:encodeSuspend`'in BİLİNMEYEN state
  alanlarını kuyruğun `o` sözlüğüne taşıyan mevcut ileri-uyum yolu sayesinde suspend/resume'da
  hayatta kalır — **suspend ŞEMASI DEĞİŞMEZ** (`decodeSuspend`/`_salvageV2` geri kurar; kırpma
  merdiveni `o`'yu düşürmez, bu yüzden kayıt küçük kalmalıdır). Oturum başında `EMBED_JS` bir kez
  sarmalanmış `evaluate()` çağırır: init'in yazdığı `score.raw=0` düzeltilir ve commit edilir.
  `completion` modları: `on_view` (ekrana GİRİLDİĞİNDE — ilk sayfa yüklemesinde değil, fix round 1 /
  IMPORTANT 2), `time_threshold` (ekrana giriş + `min_seconds` sonra; `min_seconds` `ge=0`
  doğrulanır — core/project.py, fix round 1 / MINOR 5), `on_message` (yalnız artifact'in
  `{scorm:'complete'}` — ya da `setStatus:'completed'` — bildirimiyle; fix round 3'e kadar
  UYGULANMIYORDU).
  **Yazımlar motorun evaluate() döngüsünden SAĞ ÇIKAR (fix round 1 / CRITICAL):** motorun kendi
  `evaluate()`'i (`components/templates.py` ENGINE_JS) her `showAt` + exit'te skoru/tamamlanmayı
  `COURSE.total_points`'ten yeniden hesaplayıp cmi'yi ezer; embed_html'li kurs skorsuzdur
  (`total_points<=0`) → köprünün yazımı bir SONRAKİ `evaluate()`'te sıfırlanırdı (1.2'de HİÇ kalıcı
  olmuyordu — bkz. fix round 1 raporu). Çözüm ENGINE_JS gövdesine DOKUNMADAN (bayt-parite):
  `EMBED_JS`, motorun `evaluate` bağlamasını `embed.js:wrapEvaluate(origEvaluate, sSet, getWrites,
  commit)` (saf, vitest'li) ile DEĞİŞTİRİR — orijinal `evaluate()` → `getWrites()` yazımları
  yeniden uygulanır (son yazan kazanır, LMS `SetValue` idempotent) → yazım varsa AYRICA `sCommit()`
  (fix round 2 / FINDING 3: yeniden yazım `persist()` içindeki commit'ten SONRA olur, katı bir
  LMS'te aksi hâlde kaybolabilirdi).
  **KURAL (fix round 2 / FINDING 1): `evaluate()`'i YALNIZ artifact'in kendi postMessage komutları
  YUKARI yönde ezebilir.** Launcher'ın KENDİ otomatik tamamlanması cmi'ye "completed" YAZMAZ:
  `on_view` için ek iş yoktur (motor `showAt`'te `state.visited[id]=true` yapar, tamamlanmayı
  `evaluate()` türetir).
  **TAMAMLANMA KİLİDİ (fix round 3 — `time_threshold` + `on_message`):** kapılı bir ekranın koşulu
  sağlanmadıkça kurs tamamlanmış RAPORLANMAZ. `getWrites()` sırası: önce
  `embed.js:holdBackWrites(pending, is2004)` (kapı bekliyorsa `completion_status`/`lesson_status`
  → `"incomplete"` ve `exit` → `"suspend"`), SONRA `state.eb`'den türetilen artifact yazımları →
  artifact'in kendi komutu kilidin ÜSTÜNDE kalır — **ama tamamlanma İMA EDENLER hariç, bkz. fix
  round 4 / FIX 2 aşağıda** (`failed`/`browsed`, skor ve 2004 `success_status` pinleri üstte kalır).
  Kilit YALNIZ GERİ ÇEKER: hiçbir girdi için
  `completed`/`passed` üretemez, skora ve `success_status`'a HİÇ dokunmaz (yanlış sonuç yalnız
  "henüz tamamlanmadı" yönünde olabilir). `exit`'in de geri çekilmesinin nedeni: motor
  `exit = complete ? "normal" : "suspend"` yazar; kilit tam da "motor complete diyor" durumunda
  devreye girdiği için aksi hâlde `status=incomplete` + `exit=normal` çifti oluşur ve katı bir 1.2
  LMS'i `suspend_data`'yı atmakta serbest kalır. Kapı durumu `embed.js:gatesPending(gates, eb)`
  ile sorulur: `time_threshold` → `eb.d[ekran]`, `on_message` → `eb.m[ekran]` (EKRAN BAŞINA defter;
  `eb.c` global bir değerdir, ekran atfı yapamaz). `visible_if` ile o an GÖRÜNMEYEN ekranın kapısı
  sayılmaz (erişilemeyen ekran kursu sonsuza dek kilitlemesin).
  Round 2 bunu motorun GİRDİSİNİ (`state.visited`) geri çekerek yapıyordu (`gateVisited`); motorun
  `viewedAll()`'ı `state.reachedEnd`'i de kabul ettiğinden bu TEK ekranlı (ve embed'i son ekranda
  olan) kursta hiçbir şey yapmıyor, ayrıca ilerleme çubuğunu şişiriyordu — **kaldırıldı**.
  `time_threshold` sayacı o ekranın DOM'a GİRİŞİNDE (`data-screen-id`) kurulur, init'te DEĞİL;
  kanca `showAt` değil **`updateChrome`**'dur: `prev()`'in history hızlı yolu `showAt`'i hiç
  çağırmaz (ve `prev` sarmalanamaz — `btnPrev` dinleyicisi referansı sentinel'den ÖNCE bağlar),
  ama `updateChrome` her gezinme yolunda adıyla çağrılır (OUTLINE_JS aynı tekniği kullanır).
  **KİLİT ARTIK YAZIMDAN ÖNCE DEVREDE (fix round 4 / FIX 1 — `sSet` sarmalanır):** round 3'te kilit
  `origEvaluate()`'ten SONRA çalışıyordu, ama `origEvaluate` → `persist()` → `sCommit()` motorun
  `completed`'ini kilit devreye girmeden ÖNCE **COMMIT** ediyordu; yani geçici `completed` yalnız
  açılışta değil, kapı beklerken **HER `evaluate()`'te** LMS'e gidiyordu. Tamamlanmayı ilk
  commit'te MANDALLAYAN bir LMS'te (1.2 raporlaması, 2004 rollup) kapı özelliği sessizce hiç
  çalışmıyordu. `EMBED_JS` bu yüzden motorun `sSet` bağlamasını `embed.js:wrapSet(sSet, pending,
  is2004)` ile DEĞİŞTİRİR (wrapEvaluate satırından ÖNCE — o `sSet`'i değer olarak saklar): kapı
  beklerken TAMAMLANMA İDDİASI içeren yazım cmi'ye HİÇ gönderilmez. Yüklem tek yerdedir —
  `embed.js:isCompletionAssertion(key, value, is2004)` ve kapsamı BİLEREK dardır: 1.2
  `cmi.core.lesson_status` = `completed`|`passed` (bu anahtar 1.2'nin TEK başarı kanalıdır ve
  `passed` tamamlanmayı ima eder), 2004 `cmi.completion_status` = `completed`. Anahtar eşleşmesi
  TAM eşitliktir (alt-dize/regex DEĞİL): `cmi.objectives.N.completion_status`, `cmi.success_status`,
  skor/`exit`/`session_time` anahtarları ve `cmi.suspend_data` (o `sSetChecked` ile yazılır,
  sarmalayıcıdan hiç geçmez) ASLA bastırılmaz. `holdBackWrites` geri çekmesi KALIR (iki katman:
  yazılmaz + yine de tutarlı `incomplete`/`suspend` yazılır).
  **AÇILIŞ PENCERESİ DE KAPANDI (fix round 5 — LMS-adaptör vekili):** yukarıdaki sarmalayıcı
  sentinel'de (`_REVIEW_JS_SLOT`) kurulur, ama ENGINE_JS'in bootstrap `showAt(startIdx,false)`'u
  sentinel'den ÖNCE koşar: kapılı TEK ekranlı (ya da embed'i son ekranda olan) kursta tam olarak
  bir `completed` + `Commit` LMS'e gidiyordu — mandallayan LMS'te kapı açılıştan itibaren
  yeniliyordu. ENGINE_JS'in iç sırası bayt-parite yüzünden değiştirilemediği için kapı motorun
  ALTINA, SCORM API katmanına kurulur: `components/templates.py:EMBED_SHIM_JS` (KOŞULLU satır-içi
  script, `extras` üzerinden — `{extra_runtime}` SHELL'de `{engine_js}`'ten ÖNCE basılır ve DOM
  o an ayrıştırılmıştır). Kapı yapılandırması DOM'dan okunur (`iframe.embed-frame[data-completion]`
  — EMBED_JS ile aynı kaynak; `data-min-seconds` gerekmez, çünkü 0 saniyelik bir eşik bile senkron
  init'ten SONRA dolar → açılışta her kapı tanım gereği bekliyordur). Vekil, `EMBED_JS` gerçek
  kilidi kurar kurmaz `window.__SCORM_EMBED_SHIM__.release()` ile ÇEKİLİR (çift bastırma yok; ayrıca
  vekil `eb.d`/`eb.m` defterini bilemediği için devam eden bir oturumda ZATEN AŞILMIŞ kapıyı da
  tutardı — devirden sonraki `evaluate()` doğru durumu yazar) ve `DOMContentLoaded` failsafe'i
  kilit hiç kurulmazsa kursun sonsuza dek kilitli kalmasını engeller (fix round 6: `setTimeout(0)`
  DEĞİL — o görev, vekil ile `{engine_js}` arasına düşen bir parser yield'inde motorun
  bootstrap'inden ÖNCE koşup bastırmayı erken emekli edebilirdi). Güven sınırı etkisi §9'un
  sonundaki GÜVEN SINIRI bloğunda.
  **GEÇİCİ `exit=normal` DE BASTIRILIR (fix round 5):** motor `exit = complete ? "normal" :
  "suspend"` yazar ve bunu `persist()`→`sCommit()`'ten ÖNCE yapar; kapı beklerken "complete"
  hesaplandığı için her `evaluate()` önce geçici bir `exit=normal` COMMIT ediyor, kilidin
  `exit=suspend`'i ancak ondan sonra geliyordu (FIX 1'in kusurunun `exit` biçimi; ilk commit edilen
  `exit`e göre davranan bir LMS `suspend_data`'yı atmakta serbest kalır). Yüklem AYRI durur —
  `embed.js:isTransientExit` — ve `isCompletionAssertion` ile birlikte
  `embed.js:isGatedCompletionWrite` altında toplanır; `wrapSet` ve `EMBED_SHIM_JS` ikisini de
  ONDAN okur. (fix round 5'te ayrıca bir artifact pin süzgeci vardı ve o YALNIZ
  `isCompletionAssertion` kullanıyordu; task-5 / FIX 3'te süzgeç silindi — aşağıya bakın.)
  Yalnız `"normal"` bastırılır; `suspend`/`logout`/`time-out`/`""`
  aynen geçer. AYRI BİLET (burada DEĞİL): `"normal"` 1.2 `cmi.core.exit` vokabülerinde HİÇ yoktur
  (1.2: `time-out | suspend | logout | ""`); düzeltmesi `components/engine/scorm.js`'tedir ve o
  modül koşulsuz inline edildiği için bayt-parite kapsamı dışındadır.
  **KAPI, ARTIFACT PİNİNDEN ÜSTÜNDÜR (fix round 4 / FIX 2):** round 3'te `getWrites()` pini EN SONA
  koyduğu için, A ekranının artifact'i `{scorm:'complete'}` gönderince B ekranının kapısı hâlâ
  beklerken kurs `completed` raporluyordu (2004'te üstelik `exit=suspend` ile tutarsız çiftle) —
  yani "her embed ekranının artifact'i, BAŞKA bir ekranın yazarlık-zamanı kapısını atlatabilir".
  Kural şudur: kapı beklerken TAMAMLANMA İDDİASI içeren pin LMS'e GİTMEZ. **KABUL EDİLEN
  BEDEL:** 1.2'de `lesson_status` tek başarı kanalı olduğundan artifact'in bildirdiği `passed` de
  kapı beklerken TUTULUR. Kayıp değildir: değer `state.eb.c`'de durur, `suspend_data`'ya persist
  edilir ve kapı açılınca ilk `evaluate()`'te geri konur. 2004'te `passed` ayrı kanaldadır
  (`cmi.success_status`) ve HİÇ tutulmaz.
  **task-5 / FIX 3 — bunu UYGULAYAN KATMAN DEĞİŞTİ (davranış AYNI).** round 4 bunu `EMBED_JS:
  ebWrites()`'ta ayrı bir süzgeçle (`embed.js:suppressCompletionWrites`) yapıyordu. round 4'ün
  KENDİ FIX 1'i (`sSet = EMB.wrapSet(sSet, pending, !!S2004)`) o süzgeci tamamen KAPSADI: ikisi de
  aynı `pending()`'e bakar, `wrapSet`'in yüklemi (`isGatedCompletionWrite` = `isCompletionAssertion`
  ∪ `isTransientExit`) süzgecinkinin KATI ÜST KÜMESİDİR ve pin listesinin uygulandığı HER İKİ yol
  da (`wrapEvaluate` ve `message` dinleyicisindeki `applyWrites`) `sSet` üzerinden geçer. Süzgeç
  bu yüzden SİLİNDİ (mutasyonla kanıtlandı: çağrıyı `return w;` ile değiştirmek 90/90 vitest +
  24/24 pytest'i yeşil bırakıyordu; aynı mutasyon `holdBackWrites`'ta 9 vitest kırıyor → koşum
  takımı ayırt edebiliyor, ayıran bir test yoktu). TEK gözlemlenebilir yan etki: `wrapEvaluate`'in
  `if (writes.length && commit) commit()` koşulu artık süzülmemiş listeyi görür — ama `pending()`
  doğruyken `holdBackWrites` zaten 2 yazım koyduğu için liste hiçbir zaman boşalmıyordu, yani
  Commit sayısı da değişmez.
  **YAZARLAR İÇİN — kapıların üç sınırı (fix round 4 / FIX 3):**
  1. **`visible_if` muafiyeti bir BYPASS'tır:** o an görünmeyen ekranın kapısı sayılmaz (yoksa
     erişilemeyen ekran kursu sonsuza dek kilitlerdi). Sonuç: kapılı bir ekran GİZLİYKEN kurs
     `completed` raporlayabilir; ekran sonradan görünür olursa kapı yeniden devreye girer ve kurs
     `incomplete`'e döner. Tamamlanmayı ilk `completed`'te mandallayan bir LMS'te bu geri dönüş
     GÖRÜLMEZ — kurs tamamlanmış kalır. Muafiyet yine de doğru karardır (kalıcı kilit daha kötü);
     kapılı ekranı `visible_if` ile koşullu yapmak, tamamlanma garantisini zayıflatır.
  2. **2004 + `on_message`: yalnız `{scorm:'passed'}` göndermek kursu TAMAMLAMAZ.** Kapı defteri
     (`eb.m`) yalnız `patch.c === "completed"` ile açılır; 2004'te `passed` `{k:'passed'}` üretir
     (`embed.js:embedStateFromMsg`) ve `c`'ye HİÇ dokunmaz. 2004 `on_message` artifact'i AYRICA
     `{scorm:'complete'}` (ya da `{scorm:'setStatus', value:'completed'}`) göndermelidir. (1.2'de
     `passed` `c`'ye yazılır ama `"completed"` olmadığı için kapıyı yine AÇMAZ — kural her iki
     sürümde aynıdır: kapıyı yalnız açık bir "tamamlandı" bildirimi açar.)
  3. **Kapılar outline kilidini/ilerlemesini ETKİLEMEZ.** `components/engine/progress.js`
     `lockedNodes`/`nodeProgress` yalnız `state.visited`'a bakar (kilit round 3'te motorun
     GİRDİSİNİ değiştirmeyi bıraktı) → `unlock_rule: "sequential"` bir outline'da `time_threshold`
     ekranı GÖRÜLDÜĞÜ anda bir sonraki düğümün kilidini açar, eşik beklenmez. Kapı YALNIZ kursun
     cmi tamamlanma raporunu tutar. Outline kilidinin de kapıyı beklemesi gerekiyorsa bu ayrı bir
     iştir (henüz yapılmadı).
  **SINIR — her `evaluate()`'te GEÇİCİ `score.raw=0` (task-5 / FIX 7, analitik hattı olanlar için):**
  `ENGINE_JS:writeScore()` skoru KURSTAN (`state.results`) hesaplar; skorsuz bir embed kursunda bu
  `0`'dır ve `evaluate()` içinde `persist()`→`sCommit()` ile COMMIT edilir. Köprünün pini
  (`eb.s`, ör. 85) ancak ondan SONRA, `wrapEvaluate` sarmalayıcısında yeniden yazılıp yeniden
  commit edilir. Sonuç: HER gezinmede LMS `score.raw` için `0` → `85` çifti görür. "Son yazan
  kazanır" davranan bir LMS'te ZARARSIZDIR (kalıcı değer doğru), ama HER Commit'i kaydeden bir
  analitik hattında skor her ekran geçişinde `0`'a düşüp geri çıkıyormuş gibi görünür. Yüklemi
  skor anahtarlarını da bastıracak şekilde genişletmek AYRI bir karardır (burada YAPILMADI:
  `wrapSet`'in kapsamı bilerek dar tutulmuştur — bkz. `embed.js:isCompletionAssertion`).
  **SINIR — `passing_score` artifact skorunu GÖRMEZ (fix round 3 / FINDING E, yazarlar için):**
  motorun `isComplete()`/`quizPassed()`'ı skoru `state.results`'tan (quiz ekranlarının cevapları)
  hesaplar; köprünün `setScore`'u `cmi`ye YAZILIR ama `state.results`'a girmez. Dolayısıyla
  `completion_rule: "passed_quiz"` (veya `viewed_all_and_passed`) + yalnızca artifact skoru olan
  bir kurs **hiçbir zaman tamamlanmaz** (`cmi.core.score.raw=95` + `lesson_status=incomplete`
  kalıcıdır) — `passing_score` bu kurslarda ETKİSİZDİR. Artifact'in skoru geçme kararını da
  belirleyecekse artifact'in AYRICA `{scorm:'passed'}`/`{scorm:'complete'}` göndermesi gerekir;
  yoksa kursun `completion_rule`'u `viewed_all` bırakılmalıdır (bu sınır bilinçlidir: aksi hâlde
  köprü bir kursu tamamlanmış YAPABİLİRDİ — F1 değişmezi).
  **YERLEŞİM — `EMBED_CSS` + `aspect` (task-5 / FIX 1):** `_r_embed_html` `<div class="embed-wrap"
  data-aspect>` + `<iframe class="embed-frame">` üretir; bu seçicileri TANIMLAYAN kurallar
  `components/templates.py:EMBED_CSS`'tedir. `aspect` (`EmbedHtmlScreen.aspect`, varsayılan
  `"fill"`) TEK tüketicisi budur: `fill` sahnenin kalan yüksekliğini tamamen kaplar
  (`.video-wrap{flex:1;min-height:0}` presedanı), `16:9`/`4:3` iframe'i oranında ortalar
  (mektup-kutusu). Dar/kısa ekranda stage modu `data-fit="flow"`a düştüğünde kırpma açılır ve
  `fill` sarmalayıcısına taban yükseklik verilir. Kurallar BASE_CSS'e KONULMAZ (aşağıdaki
  koşullu-inline gerekçesi).
  **KOŞULLU inline (bayt-parite):** `load_embed_bundle()` (`core/engine_bundle.py` →
  `window.SCORMEMBED`), `EMBED_JS` (mevcut `_REVIEW_JS_SLOT` sentineliyle enjekte) ve `EMBED_CSS`
  (`base_css` birleşimine eklenir) YALNIZ projede ≥1 `embed_html` ekranı varsa
  (`_uses_embed(project)`) basılır — `progress.js`/`OUTLINE_CSS` presedanının aynısı. Köprü `components/engine/scorm.js`'e KONULMAZ: o modül HER pakete koşulsuz
  inline edilir, oraya eklemek embed'siz kursların çıktısını da değiştirirdi (ölçüldü: +87 bayt).
  `tests/test_embed_html.py:test_bridge_inlined_only_for_embed_courses` + kritik kapı
  `tests/test_golden.py`/`tests/test_outline_menu.py` bunu kilitler.
  **GÜVEN SINIRI (fix round 1 / IMPORTANT 3 — açıkça belgelenir):** `sandbox="allow-scripts
  allow-same-origin allow-forms allow-popups"` + aynı-origin `src` demek, artifact
  `window.parent`'a VE (findAPI zinciriyle) doğrudan gerçek LMS API'sine erişebilir demektir —
  köprünün `{scorm: "complete"|"setScore"|...}` komut listesi bir GÜVENLİK SINIRI DEĞİLDİR, yalnız
  bir KOLAYLIK API'sidir. Gömülü artifact, kursla AYNI ayrıcalıkla çalışır (yazarın kendi içeriği,
  yazarın kendi LMS'i — v1 kapsamında sandbox öznitelikleri BİLEREK değiştirilmedi). Bu sınır
  burada belgelenir; artifact yazarı köprüyü atlayıp `window.API`/`window.API_1484_11`'i doğrudan
  çağırabilir, bu BEKLENEN bir davranıştır, açık DEĞİLDİR.

  ⚠️ **AMA BU YALNIZ `package` MODUNDA GEÇERLİDİR (task-5 / FIX 7).** Yukarıdaki "aynı-origin"
  varsayımı iframe'in `src`'sinin ne olduğuna bağlıdır ve renderer bunu MODA GÖRE çözer
  (`components/renderer.py`, `assetSrc`):
  - **`mode="package"`** (`build_package` → LMS): `src` GÖRELİ bir yoldur (`assets/app.html`), yani
    artifact kursun kendi origin'inden servis edilir. `allow-same-origin` gerçekten aynı-origin
    demektir → `window.parent.API` ERİŞİLEBİLİR. Yukarıdaki paragraf AYNEN geçerlidir.
  - **`mode="preview"`** (`preview` VE `publish_demo` — ikisi de `_render_preview_html` üzerinden
    tek-dosya render eder): asset'ler `data:<mime>;base64,…` URI olarak GÖMÜLÜR. Bir `data:`
    iframe'in origin'i OPAK'tır; `allow-same-origin` opak origin'i "ana sayfayla aynı" YAPMAZ →
    `window.parent.API` okumak SecurityError ATAR ve `findAPI` zinciri hiçbir şey bulamaz.
    Yani önizleme/demo'da artifact'in tek kanalı köprüdür.
  - **postMessage köprüsü HER İKİ MODDA da çalışır:** `EMBED_JS` `ev.origin`'e DEĞİL `ev.source`
    KİMLİĞİNE bakar (kendi iframe pencerelerinin listesiyle karşılaştırır) ve artifact `"*"` hedefi
    ile gönderir — ikisi de origin'den bağımsızdır, opak origin'de de doğru çalışır.

  YAZAR İÇİN SONUÇ: köprüyü atlayıp doğrudan `window.API`'ye yazan bir artifact ÖNİZLEMEDE
  SESSİZCE HİÇBİR ŞEY yapmaz ama paketlendiğinde çalışır — yani "önizlemede raporlamıyor" bir hata
  DEĞİL, bu sınırın beklenen görünümü olabilir. Taşınabilir yol: her zaman `postMessage` köprüsü.

  **GÜVEN SINIRI — fix round 5 ile DEĞİŞEN kısım (LMS-adaptör vekili).** Kapılı bir embed kursta
  (`completion: time_threshold | on_message`) artık `components/templates.py:EMBED_SHIM_JS` adlı
  KOŞULLU bir satır-içi script basılır; bu script kursun KENDİ `window`'una bir **vekil SCORM
  adaptörü** koyar (`window.API` ve/veya `window.API_1484_11`) ve tüm çağrıları yukarıda bulduğu
  GERÇEK adaptöre devreder. Sonuç: `findAPI` zincirini yürüyen bir çocuk iframe (yani artifact'in
  kendisi) o pencerede gerçek adaptör yerine **bizim vekilimizi** bulabilir.

  Kapsam ve süre — vekil bir güvenlik önlemi DEĞİLDİR, tek amacı kapı bütünlüğüdür:
  - **YALNIZ SENKRON AÇILIŞ PENCERESİNDE zincirin başındadır.** `EMBED_JS` gerçek kilidi kurar
    kurmaz `__SCORM_EMBED_SHIM__.release()` çağrılır; vekil şeffaflaşır ve `window`'a koyduğu ad
    SİLİNİR (zincir şekli aynen eski hâline döner). Kilit hiç kurulmazsa `DOMContentLoaded`
    aynısını yapar. Pratikte artifact'in `src`'si `loading="lazy"` ile ve ayrı bir görevde yüklenir,
    yani artifact kodu vekili çoğu zaman zaten göremez.
  - **NEYİ SÜZER:** yalnız kapı beklerken ve yalnız `SetValue`/`LMSSetValue` üzerinde, yalnız
    `components/engine/embed.js:isGatedCompletionWrite` yüklemi — 1.2 `cmi.core.lesson_status`
    `completed`/`passed`, 2004 `cmi.completion_status` `completed`, ve her iki sürümde geçici
    `exit=normal`. Bastırılan çağrı üst akışa HİÇ gitmez ve `"true"` döner.
  - **NEYİ SÜZMEZ:** `GetValue`, `Commit`, `Initialize`/`Terminate`, hata metotları ve DİĞER TÜM
    `SetValue` anahtarları — skor, `cmi.success_status`, `cmi.suspend_data`, `cmi.objectives.*`,
    `cmi.interactions.*`, `session_time` — aynen geçer. `failed`/`incomplete`/`browsed`/
    `not attempted` de geçer. Yani vekil, artifact'in LMS'e erişimini **kısıtlamaz**; kapı
    beklerken TAMAMLANMA İDDİASINI geciktirir, o kadar. Devirden sonra hiçbir şeyi süzmez.
  - **LMS'in kendi adaptörü ASLA yamalanmaz:** metotları değiştirilmez, nesnesine dokunulmaz;
    çağrılar `f.apply(real, arguments)` ile `this` korunarak devredilir. Üst akışta adaptör
    YOKSA vekil HİÇ kurulmaz (aksi hâlde ENGINE_JS'in LMS'siz yerel `Scorm12API` fallback'i
    bozulurdu). **fix round 6:** vekil 8 SCORM metodunu KOŞULSUZ tanımlar ve `typeof real[m]`
    kontrolünü KURULUM'da değil ÇAĞRI anında yapar — eski başlatıcılar `window.API`'yi yer tutucu
    bir nesne/applet olarak yayınlayıp metotları sonradan ekler; ad kümesini dondurmak sıfır-metotlu
    bir vekili motorun `api` değişkenine kalıcı olarak sokup TÜM raporlamayı yok ederdi. Metot
    çağrı anında hâlâ yoksa vekil `TypeError` ATAR (uydurma dönüş değeri YOK) — vekilsiz hâldeki
    davranışın aynısı; motorun `sSet`/`sGet`/`sInit`/`sCommit`'i bunu zaten yutar. Bunun bedeli:
    vekil, gerçek adaptörün o an sahip OLMADIĞI metotları da "var" gösterir; boot penceresinde
    özellik-yoklaması (feature detection) yapan üçüncü taraf kod için bu bir sınırdır. Adaptörün
    metot-dışı özellikleri (ör. scorm-again'in `cmi` nesnesi) vekilde YOKTUR — ENGINE_JS yalnız
    bu 8 metodu çağırır, ama vekili gören üçüncü taraf kod için bu da bir sınırdır.
  - Kapısız (`on_view`) embed kurslarda ve embed'siz kurslarda vekil **hiç basılmaz** —
    fix round 6'dan itibaren bu karar `components/renderer.py:_uses_gated_embed()` ile
    PYTHON'da verilir (önce yalnız şablon içinde no-op'tu, script yine de basılıyordu).
    Karar KURS başınadır: karışık bir kursta (bir `on_view` + bir `time_threshold`) basılır.

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

**data_chart render sözleşmesi (Faz 6b — düzen ölçüm raporu §5.1):** `_build_chart_svg`
deterministik inline-SVG üretir (dış lib/ağ yok) ve OKUNABİLİRLİK garantileri verir:
- `line`: y-ekseni + 'güzel' adımlı (1/2/5×10^k) sayısal tick etiketleri + hafif grid +
  İLK/SON nokta değer etiketi (bar'ın çubuk-üstü değeriyle simetri; veri modeli tek seri).
- `bar`: çubuk-üstü değer etiketleri (regresyon-kilitli). `pie`: legend ham değer + yüzde.
- Sayısal metinler `direction="ltr"` taşır (RTL belgede text-anchor uçları ters çözülür).
- Seri renkleri `var(--chart-N, <fallback>)` ile ColorPalette.chart_series token'ından akar;
  `--chart-N` YALNIZ data_chart içeren kursta basılır (3.3 bayt-parite).
Bu garantiler `tests/test_charts.py` ile kilitlidir (CHART_VALUES_UNREADABLE'ın nihai biçimi
= test-düzeyi değişmez; §3.2 notu).

### 12.6 Asset çekim sorumluluğu (`build_from_spec` / `add_asset`)
- **Server** (Ajan C) çeker: `https://` → `auth.ssrf.safe_fetch_asset(url) -> (bytes, mime)`;
  `data:` → base64 decode (fetch yok). Sonra `store.put_asset(...)` ile yazar.
- **Packager** yalnız montaj yapar; ağ çekimi yapmaz (asset'ler store'da hazır).
