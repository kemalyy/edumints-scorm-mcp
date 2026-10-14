# Programatik video üretimi (Faz 10 — HyperFrames)

Sunucu, **sahne-spec JSON**'unu temaya-uygun bir HyperFrames kompozisyonuna derler ve
**MP4** render eder (headless Chrome + ffmpeg). Çıktı bir **video asset**'tir → `video`
ekranında `video_asset_id` ile kullanılır → her LMS'te çevrimdışı oynar.

İki araç:
- `render_motion_video(project_id, video_spec, filename)` → motion-graphic / veri-viz MP4.
- `render_screen_video(project_id, screen_id, filename, duration_sec)` → mevcut bir stage
  ekranını (Faz 9 timeline'ıyla) MP4'e döker (indirilebilir özet / LMS oynatıcı).

## Ne zaman video, ne zaman etkileşim?
Video **pasiftir** — açıklama/giriş/duygu/özet için güçlü, ama yoklama/uygulama için değil.
- ✅ Açıklayıcı giriş, kavram animasyonu, veri-görselleştirme, kapanış/özet.
- ❌ Bilgi yoklaması, uygulama, dallanma → bunlar etkileşimli ekran tipleridir (mcq, simulation…).
Kural: video bir şey **öğretiyorsa/duygu katıyorsa** ekle; dekoratif video ekleme.

## VideoSpec şeması (render_motion_video → `video_spec`)

```jsonc
{
  "width": 1280, "height": 720, "fps": 30,        // varsayılanlar; guardrail ≤1920x1080, ≤60fps
  "scenes": [
    {
      "duration_sec": 4,                            // sahne süresi
      "narration_text": "...",                      // opsiyonel (altyazı/refs)
      "narration_asset_id": "vo1",                  // opsiyonel → MP4'e ses mux'lanır
      "background": "#0f1622",                       // opsiyonel; yoksa tema yüzeyi
      "elements": [ /* aşağıdaki katalog */ ]
    }
  ]
}
```
**Toplam süre ≤ 60 sn** (guardrail). Konumlar **yüzde** (x,y,w = 0-100) → çözünürlükten bağımsız.

## Element kataloğu (`scenes[].elements[]`)
Ortak alanlar: `x`,`y` (% konum), `w` (opsiyonel % genişlik), `color`,
`animation: {preset, at, dur}`. Preset'ler: `fade` · `slide` · `zoom` · `typewriter` ·
`count-up` · `none`. `at`= sahne içi başlama (sn), `dur`= animasyon süresi.

```jsonc
{ "type": "text",  "text": "Başlık", "size": 64, "weight": 800, "align": "center",
  "x": 10, "y": 30, "animation": {"preset": "slide", "at": 0.2, "dur": 0.6} }
{ "type": "shape", "shape": "rect|circle|line", "x": 5, "y": 70, "w": 40, "h": 6, "fill": "#3b82f6" }
{ "type": "image", "asset_id": "logo", "x": 70, "y": 10, "w": 20 }   // add_asset ile yüklenmiş görsel
{ "type": "icon",  "name": "star", "size": 64, "x": 45, "y": 40 }     // lucide ikon adı
{ "type": "chart", "kind": "bar", "x": 10, "y": 30, "w": 60,
  "data": [ {"label": "2023", "value": 30}, {"label": "2024", "value": 70} ] }
{ "type": "chart", "kind": "counter", "x": 35, "y": 35, "suffix": "%",
  "data": [ {"label": "oran", "value": 80} ] }
```

## Veri-viz reçeteleri
- **Büyüyen oran/sayı:** `counter` chart + `count-up` animasyon (ör. "%80 insan hatası").
- **Karşılaştırma:** `bar` chart (yatay barlar, değerlere göre ölçekli) + `fade`/`slide`.
- **Vurgu:** büyük `text` + `shape` alt-çizgi (`slide` ile soldan).

## Örnek — 2 sahnelik açıklayıcı (intro + veri-viz)
```jsonc
render_motion_video(project_id, {
  "scenes": [
    { "duration_sec": 3, "narration_asset_id": "vo1", "elements": [
      { "type": "text", "text": "Siber Güvenlik", "size": 72, "weight": 800, "align": "center",
        "x": 10, "y": 40, "w": 80, "animation": {"preset": "zoom", "at": 0, "dur": 0.7} } ] },
    { "duration_sec": 4, "elements": [
      { "type": "text", "text": "İhlallerin nedeni", "size": 40, "x": 10, "y": 12 },
      { "type": "chart", "kind": "counter", "suffix": "%", "x": 35, "y": 38,
        "data": [ {"label": "insan", "value": 80} ],
        "animation": {"preset": "count-up", "at": 0.3, "dur": 1.2} } ] }
  ]
}, "intro.mp4")
```
Dönen `AssetRef.id`'yi bir `video` ekranında kullan:
`{ "type": "video", "title": "Giriş", "video_asset_id": "<dönen id>" }`

## Slayttan otomatik video
```
render_screen_video(project_id, screen_id, "ozet.mp4", duration_sec=8)
```
Mevcut stage ekranını (timeline reveal dahil) MP4'e çevirir. İndirilebilir özet veya bir
`video` ekranı için.

## Sınırlar / guardrail (önemli)
- Çözünürlük ≤ **1920×1080**, fps ≤ **60**, toplam süre ≤ **60 sn**.
- Render **sunucuda** çalışır (headless Chrome) — birkaç saniye sürebilir; **async**.
- HyperFrames yoksa araç net hata verir (zero-load: video kullanmayan kurslar etkilenmez).
- Görsel asset'leri önce `add_asset` ile yükle; `image` elementte `asset_id` ile referans ver.
