"""tests/test_rng_rule.py — #159: rastgelelik kuralının kapsamı ve denetimi.

`components/engine/rng.js` "tüm rastgelelik buradan türer (Math.random YASAK)" diyordu ama
kuralı hiçbir şey denetlemiyordu; `components/templates.py` iki yerde ham `Math.random()`
çağırıyordu ve kimse fark etmemişti. Kayma, görsel regresyon harness'ı (#150) kurulurken
`screen-sorting` snapshot'ı her koşuda değişince ortaya çıktı.

Bu testler kuralı **denetlenebilir** hâle getirir:

1. **Motor bundle'ında istisna YOK.** `components/engine/**` ölçmeyi çalıştırır — aynı seed →
   aynı dizi → golden-test edilebilir oynanış. Orada tek bir `Math.random(` bile olmamalı.
2. **İnline motorda TAM İKİ belgelenmiş istisna var.** Her ikisi de sunum karıştırması
   (term_match_race `<select>` sırası, sorting başlangıç sırası) ve `createRng`e erişemiyorlar:
   o yalnız `window.SCORMGame` üzerinden gelir, bundle ise sadece game/adaptive_practice ya da
   xAPI'li kurslara inline edilir. Gerekçenin tamamı `rng.js` başlığında.
   Üçüncü bir çağrı eklenirse bu test düşer — kural sessizce genişlemesin.
3. **İstisna listesi bayatlamasın.** İki bilinen çağrı da hâlâ orada olmalı; biri tohumlu RNG'ye
   taşınırsa bu test düşer ve allowlist'in daraltılması gerektiğini söyler.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "components" / "engine"
TEMPLATES = ROOT / "components" / "templates.py"

_CALL = re.compile(r"Math\.random\s*\(")

# İnline motordaki iki belgelenmiş istisna, satır numarasına DEĞİL satırın kendi imzasına
# bağlanır — kod kayınca test kırılmasın, ama başka bir çağrı eklenince kırılsın.
ALLOWED = {
    "term_match_race <select> sırası": "sel.appendChild(opts[j]); opts.splice(j,1);",
    "sorting başlangıç sırası": "var tmp=arr[i];arr[i]=arr[j];arr[j]=tmp;",
}


def _lines_with_calls(text: str) -> list[str]:
    """`Math.random(` GEÇEN satırlar — ama `//` yorumları elenir.

    Yorumlar elenmezse kuralın KENDİSİNİ anlatan bir yorum (rng.js başlığı gibi) ihlal
    sayılır; bu test yazılırken tam olarak bu oldu. Yorumu kırpmak, kuralı ANLATABİLMEYİ
    kuralı ÇİĞNEMEKTEN ayırır."""
    out = []
    for ln in text.split("\n"):
        if _CALL.search(ln.split("//", 1)[0]):
            out.append(ln)
    return out


@pytest.mark.parametrize("js", sorted(ENGINE_DIR.rglob("*.js")), ids=lambda p: p.name)
def test_engine_bundle_has_no_raw_math_random(js):
    """Bundle'da istisna yok: rastgelelik ölçmeyi sürüyor, seed'siz olamaz.

    rng.js'in KENDİSİ hariç — orada `Math.random` yalnız kuralı anlatan yorumda geçer,
    çağrı olarak değil (regex `Math.random(` arar, yorumdaki düz metin eşleşmez).
    """
    hits = _lines_with_calls(js.read_text(encoding="utf-8"))
    assert not hits, (
        f"{js.relative_to(ROOT)} ham Math.random() çağırıyor — motor bundle'ında istisna yok; "
        f"rng.js'ten createRng kullanın:\n  " + "\n  ".join(h.strip() for h in hits)
    )


def test_inline_engine_has_exactly_the_documented_exceptions():
    lines = _lines_with_calls(TEMPLATES.read_text(encoding="utf-8"))
    unexpected = [ln.strip() for ln in lines
                  if not any(sig in ln for sig in ALLOWED.values())]
    assert not unexpected, (
        "components/templates.py'de BELGELENMEMİŞ Math.random() çağrısı:\n  "
        + "\n  ".join(unexpected)
        + "\n\nYeni rastgelelik motor bundle'ının seed'li RNG'sinden türemeli "
          "(components/engine/rng.js). Gerçekten istisna gerekiyorsa gerekçesini rng.js "
          "başlığına yazın ve bu testin ALLOWED listesine ekleyin — sessizce geçmesin."
    )


@pytest.mark.parametrize("name,signature", sorted(ALLOWED.items()))
def test_documented_exception_still_exists(name, signature):
    """Allowlist bayatlamasın: istisna tohumlu RNG'ye taşındıysa listeden de düşmeli."""
    text = TEMPLATES.read_text(encoding="utf-8")
    matching = [ln for ln in _lines_with_calls(text) if signature in ln]
    assert matching, (
        f"'{name}' istisnası artık templates.py'de Math.random() çağırmıyor — iyi haber. "
        "ALLOWED listesinden kaldırın ve rng.js başlığındaki istisna açıklamasını güncelleyin."
    )


def test_rule_scope_is_documented_in_rng_js():
    """Kural metni 'koşulsuz yasak' iddiasına geri dönmesin — kapsamı yazılı kalsın."""
    text = (ENGINE_DIR / "rng.js").read_text(encoding="utf-8")
    assert "KURALIN KAPSAMI" in text and "BELGELENMİŞ İKİ İSTİSNA" in text, \
        "rng.js kuralın kapsamını ve istisnalarını artık anlatmıyor (#159)"
