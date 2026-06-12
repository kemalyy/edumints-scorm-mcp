"""core/engine_bundle.py — W3 köprü: vitest-test edilen oyun motoru ESM modüllerini
(components/engine/) runtime paketine inline edilecek tek bir JS string'ine derler.

DRİFT RİSKİNİ ÇÖZER: motor mantığının TEK kaynağı components/engine/*.js (vitest'le test).
templates.py ENGINE_JS'i bu mantığı KOPYALAMAZ — `game` ekranı varsa bu bundle lazy inline edilir.

Her modül KENDİ IIFE kapsamına sarılır (modül-içi const'lar — örn. iki modülde de `CMP` — izole
kalır, çakışmaz); yalnız `export` edilen adlar paylaşılan __E objesine açılır → window.SCORMGame.
Modüller birbirini import etmez (bağımlılıkları parametre alır), bu yüzden sıra serbest.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "components" / "engine"

_ORDER = [
    "rng.js", "eventbus.js", "state.js",
    "primitives/timer.js", "primitives/score.js", "primitives/lives.js",
    "primitives/hint.js", "primitives/itembank.js", "primitives/branchgraph.js",
    "rules.js",
]

_IMPORT_RE = re.compile(r"^\s*import\s.*?;\s*$", re.MULTILINE)
_EXPORT_KW_RE = re.compile(r"^(\s*)export\s+(function|const|let|var|class)\s+(\w+)", re.MULTILINE)
_EXPORT_NAME_RE = re.compile(r"\bexport\s+(?:function|const|let|var|class)\s+(\w+)")


def _compile_module(src: str) -> tuple[str, list[str]]:
    """import'ları sil; `export` anahtarını kaldır; export edilen adları topla."""
    src = _IMPORT_RE.sub("", src)
    names = _EXPORT_NAME_RE.findall(src)
    src = _EXPORT_KW_RE.sub(r"\1\2 \3", src)  # `export function X` → `function X`
    return src, names


@lru_cache(maxsize=1)
def load_engine_bundle() -> str:
    """Tüm motor modüllerini per-modül IIFE'ye sarıp birleştir; export'ları window.SCORMGame'e aç.
    Yalnız `game` ekranı olan pakette lazy inline edilir (lottie deseni gibi)."""
    blocks: list[str] = []
    for rel in _ORDER:
        p = ENGINE_DIR / rel
        if not p.exists():
            continue
        body, names = _compile_module(p.read_text(encoding="utf-8"))
        assign = "; ".join(f"__E.{n} = {n}" for n in names)
        blocks.append(f"/* engine/{rel} */\n(function(){{\n{body}\n{assign};\n}})();")
    inner = "\n".join(blocks)
    return f"(function(){{\nvar __E = {{}};\n{inner}\nwindow.SCORMGame = __E;\n}})();"
