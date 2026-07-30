#!/usr/bin/env python3
"""E2 (#111) — pedagoji paket manifesti üretici (build-time, elle çalıştırılır).

`skills/authoring-scorm-courses/references/pedagogy/*.md` paket dosyalarının YAML ön-maddesini
okur (`_` önekli dosyalar paket DEĞİLDİR — _SCHEMA.md sözleşme, _STUB-* şema örnekleri) ve
E2 denetleyicisinin (core/antislop.py) runtime'da okuduğu vendored PROJEKSİYONU yazar:
`runtime/pedagogy-packs.json`.

Neden vendored: sunucu skill reposunu runtime'da OKUMAZ (deploy'da skills/ dizini garanti
değil; runtime bağımlılığı deterministik olmalı). Manifest commit'lenir; paket eklenince /
değişince bu betik yeniden çalıştırılır (tests/test_pack_conformance.py senkron kopuşunu yakalar).

Projeksiyon (E2'nin okuduğu alanlar — Katman-0 seçici alanları [outcome_types, prior_knowledge,
error_cost] BİLEREK dışarıda: onlar yazarlık-zamanı skill'in işi, sunucu denetimi değil):
- name, version                       — WARN mesajları + sözleşme sürümü
- requires_platform                   — pack_platform_missing denetimi
- conflicts_with                      — pack_conflict_on_screen denetimi (hedef-kapsamlı)
- evidence_phases                     — tekil `evidence_phase` da listeye NORMALİZE edilir
- scoring_allowed_from                — faz-etiketi gelirse (deferred) erken-skor denetimi
- phases[{id, izinli_ekran_tipleri, skorlanabilir}] — kanıt-fazı tip izinleri
  (evidence_type_outside_pack) + gelecekteki faz-etiketi denetimlerinin veri tabanı

Ön-madde ayrıştırma yaklaşımı skill reposundaki scripts/validate_packs.py ile aynıdır
(`---\\n ... \\n---` bloğu + yaml.safe_load); şema doğrulaması BURADA tekrarlanmaz — o,
skill CI'ın işi (pack-frontmatter.schema.json). Çıktı deterministiktir (sort_keys).

Kullanım (repo kökünden):
    python3 -m pip install --quiet pyyaml
    python3 tools/gen_packs_manifest.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PEDAGOGY = ROOT / "skills" / "authoring-scorm-courses" / "references" / "pedagogy"
OUT = ROOT / "runtime" / "pedagogy-packs.json"


def frontmatter(path: pathlib.Path) -> dict | None:
    """validate_packs.py ile aynı ayrıştırma: dosya `---\\n` ile açılır, ilk `\\n---`e dek YAML."""
    import yaml  # pyyaml — yalnız bu betikte (runtime JSON okur, yaml'a bağımlı değil)

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return yaml.safe_load(text[4:end])


def project(fm: dict) -> dict:
    """Tam ön-maddeden E2 projeksiyonu. Tekil `evidence_phase` → `evidence_phases: [x]`."""
    evidence = ([fm["evidence_phase"]] if "evidence_phase" in fm else []) + list(
        fm.get("evidence_phases") or []
    )
    return {
        "name": fm["name"],
        "version": int(fm.get("version", 1)),
        "requires_platform": list(fm.get("requires_platform") or []),
        "conflicts_with": list(fm.get("conflicts_with") or []),
        "evidence_phases": evidence,
        "scoring_allowed_from": fm["scoring_allowed_from"],
        "phases": [
            {
                "id": p["id"],
                "izinli_ekran_tipleri": (
                    "hepsi" if p["izinli_ekran_tipleri"] == "hepsi"
                    else list(p["izinli_ekran_tipleri"])
                ),
                "skorlanabilir": bool(p.get("skorlanabilir", False)),
            }
            for p in fm["phases"]
        ],
    }


def main() -> int:
    targets = sorted(p for p in PEDAGOGY.glob("*.md") if not p.name.startswith("_"))
    if not targets:
        print(f"HATA: paket dosyası bulunamadı: {PEDAGOGY}", file=sys.stderr)
        return 1

    packs: dict[str, dict] = {}
    for path in targets:
        fm = frontmatter(path)
        if fm is None:
            print(f"HATA: {path.name}: YAML ön-maddesi yok (--- ... ---)", file=sys.stderr)
            return 1
        pid = fm.get("pack")
        if not pid or pid != path.stem:
            print(f"HATA: {path.name}: pack id ({pid!r}) dosya adıyla eşleşmiyor", file=sys.stderr)
            return 1
        packs[pid] = project(fm)

    manifest = {
        "_generated_by": "tools/gen_packs_manifest.py — ELLE DÜZENLEME; kaynak: skill paketleri",
        "schema_version": 1,
        "source": "skills/authoring-scorm-courses/references/pedagogy",
        "packs": packs,
    }
    OUT.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OK: {len(packs)} paket → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
