"""get_guide (spec 2026-10-14) — sunucuya bağlı rehberler + skill sürüm kontrolü.

Tek kaynak `guides/` dizini: konu başına bir markdown + `_meta.json` (konu özetleri, skill sürümleri,
değişiklik özeti, indirme adresi). Saf fonksiyonlar; araç katmanı `server.get_guide`."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

GUIDES_DIR = Path(__file__).resolve().parent.parent / "guides"
MAX_GUIDE_BYTES = 25 * 1024
_VER = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")


@lru_cache(maxsize=1)
def load_meta() -> dict:
    return json.loads((GUIDES_DIR / "_meta.json").read_text(encoding="utf-8"))


def normalize_topic(name: str) -> str:
    return (name or "").strip().lower()


def topics() -> list[dict]:
    meta = load_meta()
    return [{"name": n, "summary": meta["topics"][n],
             "size_bytes": (GUIDES_DIR / f"{n}.md").stat().st_size}
            for n in sorted(meta["topics"])]


def read_topic(name: str) -> str:
    if name not in load_meta()["topics"]:
        raise KeyError(name)
    return (GUIDES_DIR / f"{name}.md").read_text(encoding="utf-8")


def parse_version(v: str | None) -> tuple[int, int, int] | None:
    m = _VER.match((v or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def download_url(meta: dict) -> str:
    return (os.environ.get("SKILL_DOWNLOAD_URL") or "").strip() or meta["download_url"]


def _changes_since(v: tuple[int, int, int], meta: dict) -> str:
    latest = parse_version(meta["skill_latest"])
    rows = sorted(((parse_version(k), k, txt) for k, txt in meta.get("changes", {}).items()
                   if parse_version(k) and v < parse_version(k) <= latest), reverse=True)
    return " ".join(f"[{k}] {txt}" for _, k, txt in rows)


def skill_status(v: str | None, meta: dict) -> tuple[str, str | None]:
    """→ (status, notice). notice yalnız current dışında; hiçbir aracı bloklamaz (spec §5.2)."""
    latest, url = meta["skill_latest"], download_url(meta)
    pv = parse_version(v)
    if pv is None:
        return "unknown", (f"authoring-scorm-courses skill'i kullanıyorsan güncel sürüm {latest}: {url}. "
                           f"Skill'in ilk adımı get_guide(skill_version=…) olmalı.")
    if pv >= parse_version(latest):
        return "current", None
    changes = _changes_since(pv, meta)
    if pv < parse_version(meta["skill_min_compatible"]):
        return "incompatible", (f"Bu skill ({v.strip()}) sunucuyla UYUMSUZ — kullanıcıya güncellemesini "
                                f"söyle: {url} (güncel {latest}). Değişenler: {changes}")
    return "outdated", f"Daha yeni skill var ({v.strip()} → {latest}): {changes} İndir: {url}"


MAX_SCHEMA_BYTES = 8 * 1024


def _screen_classes() -> dict:
    from typing import get_args

    from core.project import Screen
    out = {}
    for cls in get_args(get_args(Screen)[0]):
        t = cls.model_fields["type"].default
        out[str(getattr(t, "value", t))] = cls
    return out


def _type_name(ann) -> str:
    s = re.sub(r"\bcore\.[a-z_]+\.", "", str(ann).replace("typing.", ""))
    return re.sub(r"<class '([^']+)'>", r"\1", s)


def _models_of(ann) -> list:
    """Anotasyondaki TÜM BaseModel'ler (Optional / list / Union içinden; sıra korunur)."""
    from typing import get_args

    from pydantic import BaseModel
    out: list = []
    for a in (ann, *get_args(ann)):
        for b in (a, *get_args(a)):
            if isinstance(b, type) and issubclass(b, BaseModel) and b not in out:
                out.append(b)
    return out


def _variant_label(model) -> str:
    """Union varyant etiketi: Literal ayrımcı alanın değeri (ör. strategy='bkt' → 'bkt'), yoksa sınıf adı."""
    from typing import Literal, get_args, get_origin
    for f in model.model_fields.values():
        if get_origin(f.annotation) is Literal and isinstance(f.default, str):
            return f.default
        if get_origin(f.annotation) is Literal and len(get_args(f.annotation)) == 1:
            return str(get_args(f.annotation)[0])
    return model.__name__.lower()


def _field_lines(model, prefix: str = "", depth: int = 0, only: set[str] | None = None) -> list[str]:
    lines = []
    for name, f in model.model_fields.items():
        if (name == "type" and not prefix) or (only is not None and name not in only):
            continue
        req = "zorunlu" if f.is_required() else "ops."
        desc = (f.description or "").replace("\n", " ").strip()
        lines.append(f"- {prefix}{name}: {_type_name(f.annotation)} — {req}" + (f" — {desc}" if desc else ""))
        subs = _models_of(f.annotation) if depth == 0 else []
        for sub in subs:  # Union[A, B] → her varyant kendi önekiyle (adaptive[elo].k, adaptive[bkt].p_slip)
            tag = f"[{_variant_label(sub)}]" if len(subs) > 1 else ""
            lines += _field_lines(sub, prefix=f"{prefix}{name}{tag}.", depth=1)
    return lines


def screen_schema(screen_type: str) -> str:
    """Ekran tipinin alanları, sunucu modelinden (elle yazılmaz → eskiyemez). Bilinmeyen tip → KeyError."""
    t = normalize_topic(screen_type)
    classes = _screen_classes()
    if t not in classes:
        raise KeyError(t)
    from core.project import ScreenBase
    cls = classes[t]
    common = set(ScreenBase.model_fields)
    own = _field_lines(cls, only=set(cls.model_fields) - common)
    base = _field_lines(cls, only=common, depth=1)  # ortak alanlar yalnız üst düzey
    head = f"# {t}\nAlanlar (ad: tip — zorunlu|ops. — açıklama); kaynak: sunucu modeli.\n"
    tail = "\n## Ortak alanlar (tüm ekranlar)\n" + "\n".join(base) + "\n"
    out = head + "\n".join(own) + "\n" + tail
    if len(out.encode()) > MAX_SCHEMA_BYTES:  # iç içe açılım sınırı aşarsa yalnız üst düzey
        own = [ln for ln in own if "." not in ln.split(":")[0]]
        out = head + "\n".join(own) + "\n" + tail
    return out
