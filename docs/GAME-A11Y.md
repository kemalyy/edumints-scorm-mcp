# Oyun Erişilebilirliği — Mekanik Primitif Sözleşmeleri (WCAG 2.2 AA)

> "Oyun ekranları a11y'den muaftır" varsayımı YASAKTIR. Her mekanik primitif aşağıdaki sözleşmeyi
> taşır; W6 oyun anti-slop kapısı bunları otomatik denetler. Primitif çekirdekleri:
> `components/engine/primitives/*.js` · şemalar: `core/game_primitives.py`.

## Çapraz-kesen kurallar (tüm primitifler)
- **Klavye-yalnız oynanabilirlik** (WCAG 2.1.1): her etkileşim klavyeden tetiklenebilir. Sürükle-bırak
  mekaniklerinde **tek-işaretçi/klavye alternatifi** zorunlu (2.5.7 Dragging Movements).
- **reduced-motion** (2.3.3 + `prefers-reduced-motion`): animasyon/parçacık degrade eder; mekanik
  hareket-bağımsız çalışır.
- **Renk-yalnız bilgi yok** (1.4.1): doğru/yanlış, takım, durum metin/ikon/desenle de gösterilir.
- **Kontrast** (1.4.3/1.4.11): metin ≥ 4.5:1, UI bileşeni ≥ 3:1 (temalar AA garantiler).
- **Odak görünür** (2.4.7) + **dokunma hedefi** ≥ 44px (2.5.8).

## Primitif başına sözleşme
| Primitif | a11y sözleşmesi | İlgili WCAG |
|---|---|---|
| **timer** | Süre **uzatılabilir** (`extend`), **kapatılabilir** (`disable`), **duraklatılabilir** (`pause`). `allow_extend`/`allow_disable` kapalıysa build reddedilir (W6). Geri sayım `aria-live="polite"`. | 2.2.1 Timing Adjustable |
| **score** | Skor değişimi `aria-live` ile duyurulur; çarpan/streak metinle gösterilir (renk-yalnız değil). | 4.1.3, 1.4.1 |
| **lives** | Can sayısı metin + ikon (yalnız kalp-rengi değil); tükenme `aria-live`. | 1.4.1, 4.1.3 |
| **hint_ladder** | İpuçları **METİN** (ekran-okuyucu okur), görsel-yalnız değil; açılan ipucu odağa alınır/duyurulur. | 1.1.1, 4.1.3 |
| **item_bank** | Üretilen sorular standart erişilebilir quiz olarak render edilir (label/fieldset/klavye). | 1.3.1, 2.1.1 |
| **branch_graph** | Seçimler klavye-operable buton/liste; düğüm girişi `aria-live` ya da odak yönetimiyle duyurulur; "sahte seçim" yok (her dal anlamlı). | 2.1.1, 2.4.3 |

## Süreli mekanik — zorunlu alternatif kalıbı
Süreli bir oyun build edilirken `timer` spec'i `allow_extend=true` VEYA `allow_disable=true`
taşımalı; öğrenci süreyi uzatabilmeli/kapatabilmeli. Yarışma bağlamı (brief açıkça isterse) tek
istisna — o zaman da süre **görünür** ve uyarı verir.

## Sürükle-bırak alternatifi
Sürükle mekaniği eklenirse, aynı hedefe **klavye/tek-tık** yolu (örn. "öğeyi seç → hedefi seç")
sağlanmalı (mevcut drag_drop ekran tipindeki dokunma fallback'i + select tabanlı matching deseni).

## Denetim (W6 pre-flight'a eklenecek)
- [ ] Süreli mekanikte uzat/kapat var mı?
- [ ] Tüm mekanikler klavye-yalnız oynanabilir mi (sürüklede alternatif)?
- [ ] reduced-motion'da mekanik bozulmadan çalışıyor mu?
- [ ] Durum/sonuç renk-yalnız değil mi (metin/ikon de)?
- [ ] İpuçları metin olarak ekran-okuyucuya açık mı?
