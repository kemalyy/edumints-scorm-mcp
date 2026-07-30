"""components/i18n.py — oynatıcı kabuğunun dizge tablosu (I1) + yazı yönü (I2).

SORUN: kabuk dizgeleri (çoğu aria-label) renderer.py ve templates.py içinde Türkçe SABİT
kodluydu; `project.language` yalnız <html lang> özniteliğini besliyordu. Sonuç: lang="de"
bildiren bir sayfanın ekran okuyucu etiketleri Türkçe kalıyordu — WCAG 3.1.1/3.1.2 ihlali.

TASARIM
  - `tr` ve `en` depoda BAKIMLI tutulur (tam kapsam garantisi bunlarda).
  - Diğer diller katkıyla gelir; eksik anahtar sessizce düşmez, `en`e geri düşer.
  - Arama zinciri: tam yerel ("pt-BR") → temel dil ("pt") → "en".
    Kasıtlı olarak "tr"ye DEĞİL "en"e düşer: Almanca bir kursta İngilizce etiket
    kabul edilebilir, Türkçe etiket hatadır.
  - Metin YÖNÜ dilden türetilir (RTL betikleri) → <html dir> + CSS logical property'ler.

Yeni dil eklemek: STRINGS'e bir yerel kodu ekleyin. Anahtar kümesi `en` ile aynı olmalı;
tests/test_i18n.py bunu ve depoda sabit kodlu UI dizesi kalmadığını doğrular.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Yazı yönü (I2)
# --------------------------------------------------------------------------- #
# Sağdan sola yazılan betiklerin dil kodları (ISO 639-1). Ülke/betik alt etiketi yok sayılır:
# "ar-EG" → "ar". Kaynak: Unicode CLDR characterOrder=right-to-left.
_RTL_LANGS = frozenset({
    "ar",   # Arapça
    "arc",  # Aramice
    "az-Arab",
    "ckb",  # Sorani Kürtçesi
    "dv",   # Divehi
    "fa",   # Farsça
    "he",   # İbranice
    "iw",   # İbranice (eski kod)
    "ku",   # Kürtçe (Arap betiği)
    "ps",   # Peştuca
    "sd",   # Sindhi
    "ug",   # Uygurca
    "ur",   # Urduca
    "yi",   # Yidiş
})


def normalize(lang: str | None) -> str:
    """'de-DE' → 'de'; boş/None → 'en'. Küçük harfe indirger."""
    if not lang:
        return "en"
    return str(lang).strip().replace("_", "-").lower()


def base_lang(lang: str | None) -> str:
    """Temel dil alt etiketi: 'pt-br' → 'pt'."""
    return normalize(lang).split("-", 1)[0]


def direction(lang: str | None) -> str:
    """<html dir> değeri: 'rtl' | 'ltr'."""
    norm = normalize(lang)
    if norm in _RTL_LANGS or base_lang(lang) in _RTL_LANGS:
        return "rtl"
    return "ltr"


def is_rtl(lang: str | None) -> bool:
    return direction(lang) == "rtl"


# --------------------------------------------------------------------------- #
# Dizge tabloları
# --------------------------------------------------------------------------- #
# `en` REFERANS tablodur: her anahtar burada bulunmak ZORUNDA (test bunu doğrular).
_EN: dict[str, str] = {
    # --- kabuk / gezinme ---
    "skip_to_content": "Skip to content",
    "progress": "Progress",
    "nav_prev": "Previous",
    "nav_next": "Next",
    # --- oynatıcı çubuğu ---
    "player_play_pause": "Play / Pause",
    "player_replay": "Replay from start",
    "player_seek": "Progress bar",
    "player_mute": "Mute / Unmute",
    "player_captions": "Captions",
    "player_menu": "Chapter menu",
    # --- slayt menüsü ---
    "menu_label": "Slide menu",
    "menu_heading": "Contents",
    "menu_close": "Close menu",
    # --- HUD ---
    "hud_lives": "Lives",
    # --- geri bildirim paneli (yalnız önizleme) ---
    "review_open": "Feedback",
    "review_title": "Leave a comment on this screen",
    "review_placeholder": "What should change?",
    "review_cancel": "Cancel",
    "review_send": "Send",
    "review_sending": "Sending…",
    "review_sent": "Sent",
    "review_error": "Error — try again",
    # --- ekran içi kontroller (renderer.py) ---
    "narration_audio": "Narration",
    "quiz_check": "Check",
    "tf_true": "True",
    "tf_false": "False",
    "flashcard_flip": "Flip card",
    "matching_select": "Match",
    "select_placeholder": "— select —",
    "sort_move_up": "Move up",
    "sort_move_down": "Move down",
    "sim_submit": "OK",
    "sim_answer": "Type your answer",
    "scenario_continue": "Continue &rarr;",
    "scenario_score": "Score:",
    "term_race_finish": "Finish",
    "escape_answer": "Type your answer",
    "escape_unlock": "Unlock",
    "diagram_pin": "Marker {n}",
    "diagram_pin_label": "Marker {n} label",
    "diagram_select_placeholder": "— select label —",
    "poll_reflection": "Write your reflection",
    "poll_reflection_placeholder": "Share your thoughts…",
    "poll_thanks": "Thank you for sharing.",
    "poll_submit": "Send",
    "compare_before": "Before",
    "compare_after": "After",
    "compare_slider": "Compare before/after",
    "game_continue": "Continue &rarr;",
    "game_score": "Score:",
    "game_hint": "Hint",
    "game_timer_extend": "+30 s",
    "game_timer_off": "Turn off timer",
    "we_step": "Step {n}",
    "we_show_rationale": "Why this step?",
    "we_show_step": "Show step {n}",
    "we_selfexp_label": "Your explanation",
    "we_selfexp_placeholder": "Explain in your own words…",
    "we_unscored": "Not graded",
    "xp_input_label": "Your answer",
    "xp_input_placeholder": "Write your observation or prediction…",
    "xp_min_hint": "At least {n} characters",
    "xp_saved": "Saved",
    "xp_unscored": "Not graded",
    # --- çalışma anında üretilen metinler (ENGINE_JS) ---
    "xp_not_answered": "not answered yet",
    "summary_passed": "You passed",
    "summary_failed": "Passing score not reached",
    "summary_completed": "Completed",
    "summary_in_progress": "In progress",
    "results_total": "Total: <b>{pct}%</b>",
    "scenario_result_score": "Score: {score}",
    "term_race_result": "{correct}/{total}",
    "term_race_bonus": " · +{bonus} speed bonus",
    "escape_win": "You opened every lock!",
    "escape_lose": "You are out of lives.",
    "game_engine_failed": "Could not load the game engine.",
    "game_result_score": "Score: {score}",
    "adaptive_engine_failed": "Could not load the adaptive engine.",
    "adaptive_mastery": "Mastery: {pct}%",
    "adaptive_ability": "Level: {value}",
    "adaptive_result": "{correct} / {answered} correct · {level}",
    # --- yazar içeriği için varsayılanlar (yazar doldurmazsa) ---
    "feedback_correct": "Correct!",
    "feedback_incorrect": "Try again.",
}

_TR: dict[str, str] = {
    "skip_to_content": "İçeriğe geç",
    "progress": "İlerleme",
    "nav_prev": "Önceki",
    "nav_next": "Sonraki",
    "player_play_pause": "Oynat / Duraklat",
    "player_replay": "Baştan oynat",
    "player_seek": "İlerleme çubuğu",
    "player_mute": "Sesi aç / kapat",
    "player_captions": "Altyazı",
    "player_menu": "Bölüm menüsü",
    "menu_label": "Slayt menüsü",
    "menu_heading": "İçerik",
    "menu_close": "Menüyü kapat",
    "hud_lives": "Can",
    "review_open": "Geri bildirim",
    "review_title": "Bu ekran için yorum bırak",
    "review_placeholder": "Ne değişmeli?",
    "review_cancel": "İptal",
    "review_send": "Gönder",
    "review_sending": "Gönderiliyor…",
    "review_sent": "Gönderildi",
    "review_error": "Hata — tekrar dene",
    "narration_audio": "Seslendirme",
    "quiz_check": "Kontrol Et",
    "tf_true": "Doğru",
    "tf_false": "Yanlış",
    "flashcard_flip": "Kartı çevir",
    "matching_select": "Eşleştir",
    "select_placeholder": "— seç —",
    "sort_move_up": "Yukarı taşı",
    "sort_move_down": "Aşağı taşı",
    "sim_submit": "Tamam",
    "sim_answer": "Cevabını yaz",
    "scenario_continue": "Devam &rarr;",
    "scenario_score": "Skor:",
    "term_race_finish": "Bitir",
    "escape_answer": "Cevabını yaz",
    "escape_unlock": "Aç",
    "diagram_pin": "İşaretçi {n}",
    "diagram_pin_label": "İşaretçi {n} etiketi",
    "diagram_select_placeholder": "— etiket seç —",
    "poll_reflection": "Yansımanı yaz",
    "poll_reflection_placeholder": "Düşünceni yaz…",
    "poll_thanks": "Paylaştığın için teşekkürler.",
    "poll_submit": "Gönder",
    "compare_before": "Önce",
    "compare_after": "Sonra",
    "compare_slider": "Önce/sonra karşılaştır",
    "game_continue": "Devam &rarr;",
    "game_score": "Skor:",
    "game_hint": "İpucu",
    "game_timer_extend": "+30 sn",
    "game_timer_off": "Süreyi kapat",
    "we_step": "Adım {n}",
    "we_show_rationale": "Bu adım neden?",
    "we_show_step": "Adım {n}'i göster",
    "we_selfexp_label": "Senin açıklaman",
    "we_selfexp_placeholder": "Kendi cümlelerinle açıkla…",
    "we_unscored": "Puanlanmaz",
    "xp_input_label": "Senin cevabın",
    "xp_input_placeholder": "Gözlemini ya da tahminini yaz…",
    "xp_min_hint": "En az {n} karakter",
    "xp_saved": "Kaydedildi",
    "xp_unscored": "Puanlanmaz",
    "xp_not_answered": "henüz cevaplamadın",
    "summary_passed": "Başarıyla tamamladınız",
    "summary_failed": "Geçme notuna ulaşılamadı",
    "summary_completed": "Tamamlandı",
    "summary_in_progress": "Devam ediyor",
    "results_total": "Toplam: <b>%{pct}</b>",
    "scenario_result_score": "Skor: {score}",
    "term_race_result": "{correct}/{total}",
    "term_race_bonus": " · +{bonus} hız bonusu",
    "escape_win": "Tüm kilitleri açtın!",
    "escape_lose": "Canların bitti.",
    "game_engine_failed": "Oyun motoru yüklenemedi.",
    "game_result_score": "Skor: {score}",
    "adaptive_engine_failed": "Adaptif motor yüklenemedi.",
    "adaptive_mastery": "Ustalık: {pct}%",
    "adaptive_ability": "Seviye: {value}",
    "adaptive_result": "{correct} / {answered} doğru · {level}",
    "feedback_correct": "Doğru!",
    "feedback_incorrect": "Tekrar deneyin.",
}

STRINGS: dict[str, dict[str, str]] = {
    "en": _EN,
    "tr": _TR,
}

#: Runtime JS'e (ENGINE_JS) gömülecek anahtarlar. Kabuk HTML'i Python tarafında çözülür;
#: bunlar YALNIZ çalışma anında JS'in ürettiği metinlerdir — sayfaya gömülen tablo bu kadarla
#: sınırlı tutulur (gereksiz bayt yok).
RUNTIME_KEYS: tuple[str, ...] = (
    "summary_passed", "summary_failed", "summary_completed", "summary_in_progress",
    "results_total", "scenario_result_score", "term_race_result", "term_race_bonus",
    "escape_win", "escape_lose", "game_engine_failed", "game_result_score",
    "adaptive_engine_failed", "adaptive_mastery", "adaptive_ability", "adaptive_result",
    "review_sending", "review_sent", "review_error",
    "xp_not_answered",  # F2 (#113) — boş exploration referansının yer tutucusu
)


def runtime_table(lang: str | None) -> dict[str, str]:
    """window.__I18N__ olarak sayfaya gömülecek alt tablo."""
    full = table(lang)
    return {k: full[k] for k in RUNTIME_KEYS}


def fmt(template: str, **params: object) -> str:
    """'{n}' yer tutucularını doldurur. Bilinmeyen yer tutucu KeyError vermez, olduğu gibi kalır
    (çeviri hatası sayfayı çökertmemeli)."""
    out = template
    for key, val in params.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def table(lang: str | None) -> dict[str, str]:
    """Dile ait TAM dizge tablosu (en tabanı üzerine yerel değerler bindirilir).

    Eksik anahtar asla KeyError vermez ve asla boş dönmez — en karşılığına düşer.
    """
    out = dict(_EN)
    norm = normalize(lang)
    for key in (base_lang(norm), norm):        # önce 'pt', sonra 'pt-br' bindirilir
        loc = STRINGS.get(key)
        if loc:
            out.update(loc)
    return out


def t(lang: str | None, key: str) -> str:
    """Tek anahtar çözümle. Bilinmeyen anahtar → anahtarın kendisi (sessiz boşluk yerine
    görünür bir sinyal; test bunu yakalar)."""
    return table(lang).get(key, key)


def supported() -> list[str]:
    """Depoda bakımlı yerel kodları."""
    return sorted(STRINGS)
