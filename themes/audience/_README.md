# Kitle (audience) tema override katmanı — sözleşme (Faz 5)

Bu dizin `audience_pack` kimliğine karşılık gelen **tema override dosyalarını** barındırır:
`themes/audience/<pack>.json` (ör. `k12-lise.json`). Faz 5 yalnız MEKANİZMAYI sevk eder;
paket seti (6'lı) henüz tanımlı değildir — bu dizinde `_README.md` dışında dosya yoktur.

## Katman sırası (CONTRACTS §1.1)

```
_tokens  →  stil preseti (extends zinciri)  →  audience override  →  kurs custom
(taban)      themes/<preset>.json               themes/audience/       spec.theme inline /
                                                <pack>.json            set_theme
```

Çözüm `server._load_theme(theme, audience=<audience_pack>)` içindedir; merge alan-bazlı
derin merge'dür (yalnız dosyada AÇIKÇA verilen alanlar alttaki katmanı ezer).

## Kurallar (pazarlık dışı)

1. **Override dosyasıdır, sıfırdan tema DEĞİL.** `extends` içeremez → `AUDIENCE_NO_EXTENDS`
   hatası. Varsayılan tema SEÇİMİ + dar token override'ı yapabilir; tam tema tanımlayamaz.
2. **`name` tema kimliğini değiştiremez** — yok sayılır. Kitle paketi ≠ tema; ayrıca
   `audience_pack` ≠ `pedagogy_pack`, yalın "pack" adı yasak (3.4).
3. **Ekran tipi kısıtlayamaz (3.7).** Bu dosyalar YALNIZ ThemeTokens alt kümesidir; ekran
   tipi/şablon/davranış alanı taşıyamaz (bilinmeyen alan şema hatası verir).
4. **Erişilebilirlik zemindir (3.5).** Buraya eklenen her paket, `tests/test_theme_contrast.py`
   AA kapısına otomatik girer: her sevk edilen preset × her audience override kombinasyonu
   tüm çift-matrisinden geçmek zorundadır. AA'yı bozan paket sevk edilemez.
5. **Dosya yoksa no-op.** `audience_pack` tema-dışı davranışlar da taşıyabilir; tema override'ı
   sevk etmemiş bir paket sessiz düşüş değil, sözleşmeli yokluktur (bu README sözleşmedir).

## Gelecek (Faz 5 DIŞI)

- Varsayılan tema SEÇİMİ alanı (`"default_theme": "<preset>"`): pakete varsayılan preset
  bağlamak — mekanizması eklendiğinde bu README güncellenir ve şemaya alan olarak girer.
- 6'lı paket seti tanımı ve içerik/pedagoji davranışları (ayrı iş; tema sözleşmesini değiştirmez).
