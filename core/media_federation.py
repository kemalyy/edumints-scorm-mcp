"""core/media_federation.py — Senaryo hattı Faz 3: medya federasyonu ÇEKİRDEĞİ.

Plan: docs/superpowers/plans/2026-07-30-scenario-line-plan.md (Kol B). Sıcak dosyalar
(server.py/scenario.py) İNCE kalsın diye saf mantık bu YENİ modülde: MIME sniff, kind↔MIME
kuralları, provenance normalizasyonu, manifest eşleştirme, PROVENANCE.json kayıtları.

Pazarlık-dışı ilkeler (bu modülde görünür olanlar):
  - SUNUCUDA DİZİN ERİŞİMİ YOK (kabul #10): match_manifest YALNIZ metadata alır
    ({name,size,sha256,mime}) — burada hiçbir dizin-tarama çağrısı (listdir/scandir/
    iterdir/glob türü) kullanılmaz; tests/test_media_tools.py negatif grep testi bunu
    kanıtlar. Yerel klasörü İSTEMCİ tarar: scripts/import_media_folder.py.
  - Eşleştirme ÖNERİR, atamaz: belirsizlikte (yakın skorlar) proposed=None + skorlu aday
    listesi döner. Sıra DETERMİNİSTİKTİR (sayfa order → slot sırası; adaylar -skor, ad).
  - a11y zemin (3.5): kanıt-rolü slot doldurulurken alt_text zorunlu; audio/video için
    transcript_html de (A11Y_NO_TEXT_ALT — veri bütünlüğü sınıfı, sert hata).

Tasarım kararları (PR gövdesinde de belgeli):
  - data_chart slotu = RENDER EDİLMİŞ GÖRSEL taşır (image/*). Gerekçe: data_chart EKRANI
    inline veri taşır (ChartDatum listesi), asset değil — slot mekanizmasıyla veri taşımak
    iki kaynak-of-truth yaratırdı. data_chart slotu diğer ekranlarda image alanlarına
    bağlanır; data_chart ekranında bağlanacak alan yoktur (SLOT_NOT_ATTACHED uyarısı).
  - Sniff "tanımadıysa" (application/octet-stream) kind eşleşmesi BAŞARISIZ sayılır:
    doğrulanamayan bayt kabul edilmez (sert hata istemcide anlaşılır mesajla döner).
  - Token eşleştirmede Türkçe karakterler ASCII'ye katlanır (ü→u, ı→i …) — dosya adları
    çoğunlukla ASCII'dir ("hucre-zari.png"), slot spec'i Türkçedir ("Hücre zarı").
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# MIME sniffing (magic bytes — bildirilen MIME'a değil BAYTA güvenilir)
# --------------------------------------------------------------------------- #
_TR_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")

DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024  # MAX_ASSET_MB varsayılanıyla hizalı


def sniff_mime(data: bytes) -> str:
    """Magic-byte MIME tespiti. Tanınmayan içerik → application/octet-stream (kind
    eşleşmesi başarısız olur — doğrulanamayan bayt kabul edilmez)."""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF":
        if data[8:12] == b"WEBP":
            return "image/webp"
        if data[8:12] == b"WAVE":
            return "audio/wav"
        return "application/octet-stream"
    if data.startswith(b"ID3") or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):
        return "audio/mpeg"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data[4:8] == b"ftyp":
        return "audio/mp4" if data[8:11] == b"M4A" else "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if data.startswith(b"glTF"):
        return "model/gltf-binary"
    head = data[:512].decode("utf-8", "ignore").lstrip().lower()
    if head.startswith("<svg") or (head.startswith("<?xml") and "<svg" in head):
        return "image/svg+xml"
    stripped = data.strip()
    if stripped.startswith(b"{") and stripped.endswith(b"}"):
        return "application/json"
    return "application/octet-stream"


# kind → kabul edilen MIME kuralı. data_chart görsel-render kararı (modül docstring'i).
_KIND_MIME: dict[str, tuple[str, ...]] = {
    "image": ("image/",),
    "data_chart": ("image/",),
    "audio": ("audio/",),
    "video": ("video/",),
    "lottie": ("application/json",),
    "model_3d": ("model/gltf-binary",),
}


def kind_matches_mime(kind: str, mime: str) -> bool:
    """MediaSlot.kind ↔ sniff edilen MIME uyumu. Bilinmeyen kind/MIME → False (sert)."""
    rules = _KIND_MIME.get(kind, ())
    return any(mime == r or (r.endswith("/") and mime.startswith(r)) for r in rules)


_EXT_BY_MIME = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "video/mp4": ".mp4", "video/webm": ".webm",
    "application/json": ".json", "model/gltf-binary": ".glb",
}


def ext_for_mime(mime: str) -> str:
    """Sniff edilen MIME için dosya uzantısı (fill'de rel_path üretimi; bilinmeyen → .bin)."""
    return _EXT_BY_MIME.get(mime, ".bin")


# --------------------------------------------------------------------------- #
# Provenance (plan §5.4: source, tool, ref, generated_at, license_note)
# --------------------------------------------------------------------------- #
def normalize_provenance(prov: dict | None) -> dict:
    """Provenance'ı VERİLDİĞİ GİBİ saklar (bilinmeyen anahtarlar dahil); generated_at yoksa
    sunucu tarafında damgalar (ISO-8601 UTC). dict olmayan girdi → ValueError."""
    if prov is None:
        prov = {}
    if not isinstance(prov, dict):
        raise ValueError("provenance bir JSON nesnesi (dict) olmalı: "
                         "{source, tool, ref, generated_at, license_note}")
    out = dict(prov)
    if not out.get("generated_at"):
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
    return out


def provenance_records(doc) -> list[dict]:
    """Dolu slot başına TEK kayıt (kabul #11 — assets/PROVENANCE.json içeriği).
    Deterministik sıra: sayfa (order, id) → slot beyan sırası. Boş slot kayıt üretmez."""
    sha_by_asset = {a.id: a.sha256 for a in getattr(doc, "assets", [])}
    records: list[dict] = []
    for page in sorted(doc.pages, key=lambda p: (p.order, p.id)):
        for slot in page.media_slots:
            if not slot.asset_id:
                continue
            records.append({
                "page_id": page.id,
                "slot_id": slot.slot_id,
                "asset_id": slot.asset_id,
                "role": slot.role,
                "kind": slot.kind,
                "sha256": sha_by_asset.get(slot.asset_id),
                "provenance": slot.provenance,
            })
    return records


# --------------------------------------------------------------------------- #
# a11y kapısı — fill_media_slot'un veri-bütünlüğü denetimi (3.5/3.8)
# --------------------------------------------------------------------------- #
def missing_a11y(role: str, kind: str, alt_text: str | None,
                 transcript_html: str | None) -> list[str]:
    """Kanıt-rolü slot için eksik a11y alanları. Boş liste = geçer. Açıklayıcı rol burada
    kapılanmaz (taban a11y denetimleri lint katmanında ayrıca çalışır)."""
    if role != "kanit":
        return []
    missing: list[str] = []
    if not (alt_text or "").strip():
        missing.append("alt_text")
    if kind in ("audio", "video") and not (transcript_html or "").strip():
        missing.append("transcript_html")
    return missing


# --------------------------------------------------------------------------- #
# Manifest eşleştirme — YALNIZ metadata (kabul #10); deterministik; önerir-atamaz
# --------------------------------------------------------------------------- #
_CANDIDATE_MIN_SCORE = 0.3   # bu skorun altı aday bile değildir
_PROPOSE_MIN_SCORE = 0.5     # tek-aday netlik eşiği
_PROPOSE_MIN_MARGIN = 0.2    # 1.-2. aday arası net fark yoksa ÖNERİLMEZ (belirsiz)


def _fold_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower().translate(_TR_FOLD)))


def _score_file(slot, slot_tokens: set[str], f: dict, known_sha: set[str],
                max_bytes: int) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    ftok = _fold_tokens(str(f.get("name", "")))
    overlap = ftok & slot_tokens
    if overlap and ftok and slot_tokens:
        ratio = len(overlap) / min(len(ftok), len(slot_tokens))
        score += 0.6 * ratio
        reasons.append("token_overlap:" + "+".join(sorted(overlap)))
    mime = str(f.get("mime") or "")
    if mime and kind_matches_mime(slot.kind, mime):
        score += 0.4
        reasons.append("mime_kind_match")
    size = int(f.get("size") or 0)
    if size <= 0 or size > max_bytes:
        score -= 0.2
        reasons.append("size_suspect")
    if str(f.get("sha256") or "") in known_sha:
        reasons.append("already_ingested_dedup")  # aynı bayt zaten var → fill dedup döner
    return max(0.0, min(1.0, round(score, 3))), reasons


def match_manifest(doc, files: list[dict], *,
                   max_bytes: int = DEFAULT_MAX_FILE_BYTES) -> dict:
    """Metadata manifestini ({name,size,sha256,mime} listesi) senaryonun BOŞ slotlarıyla
    eşleştirir. → {proposals: [{page_id, slot_id, role, kind, spec, proposed, candidates:
    [{name, score, reasons}]}], unmatched_files}. Girdi sırasından bağımsız, kararlı çıktı.
    proposed yalnız NET tek kazanan varsa dolar; belirsizlik = aday listesi (atama YOK)."""
    known_sha = {a.sha256 for a in getattr(doc, "assets", [])}
    proposals: list[dict] = []
    candidate_names: set[str] = set()
    for page in sorted(doc.pages, key=lambda p: (p.order, p.id)):
        for slot in page.media_slots:
            if slot.asset_id:
                continue  # dolu slot yeniden önerilmez (yeniden doldurma bilinçli işlemdir)
            slot_tokens = (_fold_tokens(slot.slot_id) | _fold_tokens(slot.spec)
                           | _fold_tokens(slot.source_hint or ""))
            cands = []
            for f in files:
                score, reasons = _score_file(slot, slot_tokens, f, known_sha, max_bytes)
                if score >= _CANDIDATE_MIN_SCORE:
                    cands.append({"name": str(f.get("name", "")), "score": score,
                                  "reasons": reasons})
            cands.sort(key=lambda c: (-c["score"], c["name"]))
            candidate_names.update(c["name"] for c in cands)
            proposed = None
            if cands and cands[0]["score"] >= _PROPOSE_MIN_SCORE and (
                    len(cands) == 1
                    or cands[0]["score"] - cands[1]["score"] >= _PROPOSE_MIN_MARGIN):
                proposed = cands[0]["name"]
            proposals.append({
                "page_id": page.id, "slot_id": slot.slot_id, "role": slot.role,
                "kind": slot.kind, "spec": slot.spec,
                "proposed": proposed, "candidates": cands,
            })
    unmatched = sorted({str(f.get("name", "")) for f in files} - candidate_names)
    return {"proposals": proposals, "unmatched_files": unmatched}
