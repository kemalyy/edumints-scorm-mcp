"""tests/test_docs_a11y_matrix.py — docs/ACCESSIBILITY-CONFORMANCE.md §2 matrisi ↔ ScreenType.

Neden: uygunluk belgesi kurumsal/kamu alıcısına verilen DÜRÜST beyandır ve a11y yol haritası
(#145-#149) tek doğruluk kaynağı olarak onu kullanır. Matris elle tutuluyordu ve kaydı:
`embed_html` tipi eklendiğinde (dd3be4d) matrise hiç girmedi, başlıktaki tip sayısı da satır
sayısıyla tutmuyordu. Bu testler kaymayı bir daha sessiz bırakmaz — yeni bir ScreenType eklemek,
matrise satır eklemeyi ZORUNLU kılar.

Kapsam bilinçli olarak DAR: satırın VARLIĞI ve sayının tutarlılığı denetlenir, satırın içeriği
(Supports/Partial) denetlenmez — o insan yargısıdır ve teste kilitlenmesi yanlış olur.
"""
import re
from pathlib import Path

from core.project import ScreenType

DOC = Path("docs/ACCESSIBILITY-CONFORMANCE.md")

# "| 7 | `hotspot` | Supports | ..." → (7, "hotspot")
_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([a-z_]+)`\s*\|", re.MULTILINE)
_HEADING = re.compile(r"^## 2\. Conformance matrix — (\d+) screen types\s*$", re.MULTILINE)


def _matrix_rows() -> list[tuple[int, str]]:
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## 2. Conformance matrix")[1].split("\n## 3.")[0]
    return [(int(n), name) for n, name in _ROW.findall(section)]


def test_every_screen_type_has_a_matrix_row():
    documented = {name for _, name in _matrix_rows()}
    missing = {t.value for t in ScreenType} - documented
    assert not missing, (
        f"a11y uygunluk matrisinde satırı olmayan ekran tipi: {sorted(missing)} — "
        "yeni tip eklerken docs/ACCESSIBILITY-CONFORMANCE.md §2'ye dürüst bir satır ekle"
    )


def test_matrix_has_no_unknown_screen_type():
    documented = {name for _, name in _matrix_rows()}
    unknown = documented - {t.value for t in ScreenType}
    assert not unknown, (
        f"matriste modelde olmayan ekran tipi: {sorted(unknown)} — tip silindiyse satırı da sil"
    )


def test_matrix_heading_count_matches_rows_and_model():
    text = DOC.read_text(encoding="utf-8")
    m = _HEADING.search(text)
    assert m, "§2 başlığı '## 2. Conformance matrix — N screen types' biçiminde değil"
    claimed = int(m.group(1))
    rows = _matrix_rows()
    assert claimed == len(rows) == len(ScreenType), (
        f"başlık {claimed} tip diyor, matriste {len(rows)} satır var, modelde {len(ScreenType)} tip"
    )


def test_matrix_row_numbers_are_sequential():
    """Satır numaraları 1..N kesintisiz — araya satır eklenirken numaralar kaymasın."""
    nums = [n for n, _ in _matrix_rows()]
    assert nums == list(range(1, len(nums) + 1)), f"matris satır numaraları bozuk: {nums}"
