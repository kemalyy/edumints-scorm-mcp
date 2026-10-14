# Themes — konuya göre FARKLI görünüm seç

E-öğrenme standardı = açık/nötr zemin, yüksek-kontrast metin, 1-2 vurgu rengi, ferah boşluk, WCAG AA.
**Keyfi koyu tema YOK** (marka gerçekten istemedikçe).

> **EN ÖNEMLİ KURAL (anti-tekdüze):** Her kursu `default`/`modern-light` ile YAPMA. Arayüz **konuya göre
> farklılaşmalı** — çocuk kursu, akademik ders ve kurumsal uyum eğitimi birbirine benzemesin. Eğitim
> Okumasındaki kitle/ton + VISUAL_RICHNESS dial'ına göre **konuya uygun bir görsel kimlik seç** (aşağıdaki
> eşleme), gerekirse vurgu rengini markayla override et. Tema sadece renk değil: başlık fontu, köşe
> yuvarlaklığı (radii), arka plan deseni ve `custom_css` ile his değişir.

## Konu → tema eşlemesi (önce buradan seç)

| Konu / kitle | Tema | Kimlik |
|---|---|---|
| Çocuk / K12 / oyunlaştırılmış | **playground** | yuvarlak köşeler, canlı mor-pembe, zıplayan butonlar, dot deseni |
| Üniversite / beşeri bilimler / tarih / edebiyat | **editorial** | serif başlık, düz çift-çizgi kart (gölgesiz), drop-cap, ferah |
| Akademik/bilimsel (klasik) | **academic** | serif başlık, lacivert/altın, sıcak nötr |
| Sağlık / klinik CPD | **clinical-calm** | teal, sakin, ferah, profesyonel |
| Kurumsal uyum / onboarding | **corporate** marka paketi (themes/corporate/*) ya da **default** | rafine, marka rengi, logo alanı |
| Ürün/yazılım eğitimi (modern) | **modern-light** | teal vurgu, crisp |
| Pazarlama / yaratıcı | **agency** | cesur indigo |
| Erişilebilirlik-kritik | **high-contrast** | WCAG AA+, Atkinson Hyperlegible |
| Sıcak/ilkokul, dil öğrenimi | **warm-education** | sıcak turuncu, dostane |
| Dev/IT (istenirse koyu) | **dark** | ölçülü koyu — yalnız bilinçli |

Eğitim Okuması farklı bir ton söylüyorsa onu izle; ama **bilinçli bir kimlik seç** — varsayılana düşme.

## Özelleştirme (preset + marka override)
Preset seç, sonra yalnız gereken token'ı `set_theme` ile override et (deep-merge), ya da `theme` olarak
tam ThemeTokens objesi geç.
```jsonc
set_theme(project_id, { "color": { "primary": "#FF6B00", "primary_hover": "#e85f00" } })
```
**Görünümü gerçekten ayrıştırmak için renk yetmez** — şu kaldıraçları kullan (hepsi render'da bağlı):
- `typography.font_heading` — serif (Georgia stack) / rounded-sans / refined-sans → ayrı his.
- `radii` — keskin (2-4px editöryel) vs yuvarlak (20-28px çocuk) → karakter.
- `background_pattern` — none (yoğun okuma) / dots / grid / gradient.
- `custom_css` — bileşen tedavisini ez: kart stili (gölge vs çizgi), buton şekli, başlık dekoru,
  drop-cap. (editorial/playground temalarına örnek olarak bak.)

## İpuçları
- Vurgu rengini markaya uydur; metni açık zeminde neredeyse-siyah tut (kontrast).
- Aşırı override edip kontrastı bozma — emin değilsen high-contrast taban çizgisine karşı doğrula.
- WCAG AA: metin/zemin ≥ 4.5:1. Yeni custom_css ile kontrastı düşürme.
