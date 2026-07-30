"""tests/test_import_media_script.py — Faz 3 istemci betiği: scripts/import_media_folder.py.

Betiğin SAF kısımları test edilir (manifest kurulumu, öneri tablosu, onay filtresi) —
ağ/etkileşim kısmı değil. Ayrıca bağımsızlık kanıtı: betik sunucu koduna import ile
BAĞLANMAZ (yerel klasörü İSTEMCİ tarar; sunucu yalnız metadata görür — kabul #10'un
istemci yarısı).
"""

import hashlib
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "import_media_folder.py"
FIXTURES = REPO / "tests" / "fixtures" / "media_folder"


def _load_module():
    spec = importlib.util.spec_from_file_location("import_media_folder", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["import_media_folder"] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Bağımsızlık: sunucu import'u YOK; import yan-etkisiz
# --------------------------------------------------------------------------- #
def test_script_is_standalone_no_server_imports():
    src = SCRIPT.read_text(encoding="utf-8")
    for banned in ("import server", "from server", "from core", "import core",
                   "from components", "from auth"):
        assert banned not in src, f"betik sunucu koduna bağlanmış: {banned}"


def test_script_import_has_no_side_effects():
    mod = _load_module()  # main() guard'lı olmalı — import ağ/IO başlatmaz
    assert callable(mod.main)


# --------------------------------------------------------------------------- #
# build_manifest — fixture klasöründen deterministik metadata
# --------------------------------------------------------------------------- #
def test_build_manifest_from_fixture_folder():
    mod = _load_module()
    manifest = mod.build_manifest(FIXTURES)
    names = [f["name"] for f in manifest]
    assert names == sorted(names)  # deterministik sıra
    assert set(names) == {"hucre-zari.png", "mitoz_anlatim.mp3", "notlar.txt"}
    by_name = {f["name"]: f for f in manifest}
    png = by_name["hucre-zari.png"]
    raw = (FIXTURES / "hucre-zari.png").read_bytes()
    assert png["size"] == len(raw) == 70
    assert png["sha256"] == hashlib.sha256(raw).hexdigest()
    assert png["mime"] == "image/png"
    assert by_name["mitoz_anlatim.mp3"]["mime"] == "audio/mpeg"
    assert by_name["notlar.txt"]["mime"] == "text/plain"
    # her giriş yalnız metadata taşır — yerel YOL sunucuya gitmez
    assert set(png) == {"name", "size", "sha256", "mime"}


def test_build_manifest_skips_hidden_files(tmp_path):
    mod = _load_module()
    (tmp_path / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    names = [f["name"] for f in mod.build_manifest(tmp_path)]
    assert names == ["a.png"]


def test_build_manifest_missing_folder_raises():
    mod = _load_module()
    import pytest
    with pytest.raises(SystemExit):
        mod.build_manifest(Path("/yok/boyle/klasor"))


# --------------------------------------------------------------------------- #
# render_proposals_table — öneri tablosu (insan onayı için)
# --------------------------------------------------------------------------- #
_RESULT = {
    "proposals": [
        {"page_id": "p1", "slot_id": "hucre_zari", "role": "aciklayici", "kind": "image",
         "spec": "Hücre zarı diyagramı", "proposed": "hucre-zari.png",
         "candidates": [{"name": "hucre-zari.png", "score": 0.8,
                         "reasons": ["token_overlap:hucre+zari", "mime_kind_match"]}]},
        {"page_id": "p1", "slot_id": "mitoz_anlatim", "role": "kanit", "kind": "audio",
         "spec": "Mitoz seslendirme", "proposed": None,
         "candidates": [{"name": "v1.mp3", "score": 0.4, "reasons": ["mime_kind_match"]},
                        {"name": "v2.mp3", "score": 0.4, "reasons": ["mime_kind_match"]}]},
    ],
    "unmatched_files": ["notlar.txt"],
}


def test_render_proposals_table():
    mod = _load_module()
    out = mod.render_proposals_table(_RESULT)
    assert "hucre_zari" in out and "hucre-zari.png" in out
    assert "mitoz_anlatim" in out
    assert "0.8" in out           # skorlar görünür
    assert "notlar.txt" in out    # eşleşmeyen dosyalar da raporlanır
    # belirsiz slotta otomatik atama önerilmediği görünür olmalı
    assert "belirsiz" in out.lower() or "?" in out


def test_approved_matches_only_proposed():
    mod = _load_module()
    approved = mod.approved_matches(_RESULT)
    # yalnız NET önerililer doldurulur; belirsiz slot (proposed=None) atlanır
    assert approved == [("p1", "hucre_zari", "hucre-zari.png")]
