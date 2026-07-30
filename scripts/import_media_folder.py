#!/usr/bin/env python3
"""import_media_folder.py — Faz 3 İSTEMCİ betiği: yerel medya klasörünü senaryo yuvalarına aktar.

SUNUCU HİÇBİR ZAMAN DOSYA YOLU GÖRMEZ (kabul #10): klasörü BU betik tarar, sunucuya yalnız
metadata manifesti gider ({name, size, sha256, mime}); eşleşme önerileri döner; onaylanan
eşleşmeler dosya İÇERİĞİ base64 data: URI olarak fill_media_slot'a gönderilir.

Bağımsız: yalnız stdlib (requests kuruluysa onu kullanır ama şart değil). Sunucu koduna
import ile BAĞLANMAZ (tests/test_import_media_script.py bunu doğrular).

Kullanım:
    python scripts/import_media_folder.py ./medya --scenario-id scn_… \
        --url https://scorm.example.com/mcp --api-key sk_…  [--dry-run] [--yes]

    # Sunucu bilgisi verilmezse: manifesti basar + elle çağrı talimatı gösterir.
Ortam değişkenleri: SCORM_MCP_URL, SCORM_MCP_API_KEY (bayraklar önceliklidir).

Not: kanıt-rolü (role="kanit") yuvalar alt_text (audio/video için transcript) olmadan
DOLDURULAMAZ (A11Y_NO_TEXT_ALT). Betik bu hatayı gösterir; metinleri fill_media_slot'un
alt_text/transcript_html parametreleriyle (ör. Claude üzerinden) vererek doldurun.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import sys
import urllib.request
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"


# --------------------------------------------------------------------------- #
# Saf kısımlar (unit-testli)
# --------------------------------------------------------------------------- #
def build_manifest(folder: Path) -> list[dict]:
    """Klasördeki (gizli olmayan) dosyalardan metadata manifesti — ada göre kararlı sıra.
    Yerel YOL manifeste girmez: yalnız name/size/sha256/mime."""
    folder = Path(folder)
    if not folder.is_dir():
        raise SystemExit(f"HATA: klasör bulunamadı: {folder}")
    entries: list[dict] = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name):
        if not p.is_file() or p.name.startswith("."):
            continue
        data = p.read_bytes()
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        entries.append({"name": p.name, "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "mime": mime})
    return entries


def render_proposals_table(result: dict) -> str:
    """match_media_manifest sonucunu insan-onayı tablosuna çevirir."""
    lines = ["", "slot                      kind        öneri / adaylar",
             "-" * 72]
    for p in result.get("proposals", []):
        head = f"{p['slot_id']:<25} {p['kind']:<11} "
        if p.get("proposed"):
            top = p["candidates"][0]
            lines.append(head + f"→ {p['proposed']}  (skor {top['score']}; "
                                f"{', '.join(top['reasons'])})")
        elif p.get("candidates"):
            lines.append(head + "? BELİRSİZ — otomatik atama yok; adaylar:")
            for c in p["candidates"]:
                lines.append(f"{'':<38}- {c['name']}  (skor {c['score']}; "
                             f"{', '.join(c['reasons'])})")
        else:
            lines.append(head + "— aday yok")
    unmatched = result.get("unmatched_files", [])
    if unmatched:
        lines.append("")
        lines.append("Eşleşmeyen dosyalar: " + ", ".join(unmatched))
    lines.append("")
    return "\n".join(lines)


def approved_matches(result: dict) -> list[tuple[str, str, str]]:
    """Yalnız NET önerileri (proposed dolu) doldurma listesine çevirir:
    [(page_id, slot_id, dosya_adı)]. Belirsiz slotlar bilinçli atlanır."""
    return [(p["page_id"], p["slot_id"], p["proposed"])
            for p in result.get("proposals", []) if p.get("proposed")]


# --------------------------------------------------------------------------- #
# Minimal MCP streamable-HTTP istemcisi (stdlib; requests varsa o)
# --------------------------------------------------------------------------- #
class McpClient:
    def __init__(self, url: str, api_key: str | None):
        self.url = url
        self.api_key = api_key
        self.session_id: str | None = None
        self._init()

    def _post(self, payload: dict) -> tuple[dict | None, dict]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        body = json.dumps(payload).encode("utf-8")
        try:
            import requests  # opsiyonel — kuruluysa TLS/proxy yönetimi daha rahat
            r = requests.post(self.url, data=body, headers=headers, timeout=120)
            raw, ctype = r.content, r.headers.get("content-type", "")
            resp_headers = {k.lower(): v for k, v in r.headers.items()}
        except ImportError:
            req = urllib.request.Request(self.url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                ctype = resp.headers.get("content-type", "")
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        return self._parse_body(raw, ctype), resp_headers

    @staticmethod
    def _parse_body(raw: bytes, ctype: str) -> dict | None:
        if not raw:
            return None
        text = raw.decode("utf-8", "ignore")
        if "text/event-stream" in ctype:  # SSE: son data: satırı JSON-RPC yanıtıdır
            datas = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]
            return json.loads(datas[-1]) if datas else None
        return json.loads(text)

    def _init(self) -> None:
        resp, headers = self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION,
                       "capabilities": {},
                       "clientInfo": {"name": "import_media_folder", "version": "1.0"}}})
        if resp is None or "error" in resp:
            raise SystemExit(f"HATA: MCP initialize başarısız: {resp}")
        self.session_id = headers.get("mcp-session-id")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_tool(self, name: str, arguments: dict) -> dict:
        resp, _ = self._post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": name, "arguments": arguments}})
        if resp is None:
            raise SystemExit(f"HATA: {name} yanıtsız kaldı")
        if "error" in resp:
            raise RuntimeError(f"{name}: {resp['error'].get('message')}")
        result = resp.get("result", {})
        if result.get("isError"):
            texts = [c.get("text", "") for c in result.get("content", [])]
            raise RuntimeError(f"{name}: {' '.join(texts)}")
        if "structuredContent" in result:
            return result["structuredContent"]
        for c in result.get("content", []):
            if c.get("type") == "text":
                return json.loads(c["text"])
        return result


# --------------------------------------------------------------------------- #
# Akış
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    import os

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", help="taranacak yerel medya klasörü")
    ap.add_argument("--scenario-id", help="hedef senaryo (scn_…)")
    ap.add_argument("--url", default=os.environ.get("SCORM_MCP_URL"),
                    help="MCP endpoint (ör. https://…/mcp); yoksa yalnız manifest basılır")
    ap.add_argument("--api-key", default=os.environ.get("SCORM_MCP_API_KEY"))
    ap.add_argument("--dry-run", action="store_true",
                    help="önerileri göster, HİÇBİR yuvayı doldurma")
    ap.add_argument("--yes", action="store_true", help="onay sorusunu atla")
    args = ap.parse_args(argv)

    manifest = build_manifest(Path(args.folder))
    print(f"{len(manifest)} dosya tarandı: {args.folder}")

    if not args.url or not args.scenario_id:
        print("\nSunucu bilgisi yok (--url/--scenario-id) — manifest aşağıda; "
              "match_media_manifest aracına 'files' olarak verin:\n")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    client = McpClient(args.url, args.api_key)
    result = client.call_tool("match_media_manifest",
                              {"scenario_id": args.scenario_id, "files": manifest})
    print(render_proposals_table(result))

    matches = approved_matches(result)
    if not matches:
        print("Doldurulacak NET eşleşme yok (belirsiz adayları fill_media_slot ile elle doldurun).")
        return 0
    if args.dry_run:
        print("KURU ÇALIŞMA — doldurulacaktı: "
              + ", ".join(f"{pid}/{sid} ← {name}" for pid, sid, name in matches))
        return 0
    if not args.yes:
        cevap = input(f"{len(matches)} yuva doldurulacak. Onaylıyor musunuz? [e/H] ").strip().lower()
        if cevap not in ("e", "evet", "y", "yes"):
            print("Vazgeçildi.")
            return 1

    by_name = {f["name"]: f for f in manifest}
    hata = 0
    for page_id, slot_id, name in matches:
        data = (Path(args.folder) / name).read_bytes()
        uri = f"data:{by_name[name]['mime']};base64," + base64.b64encode(data).decode()
        try:
            out = client.call_tool("fill_media_slot", {
                "scenario_id": args.scenario_id, "page_id": page_id,
                "slot_id": slot_id, "source": uri,
                "provenance": {"source": "local_folder", "tool": "import_media_folder",
                               "ref": name}})
            dedup = " (dedup)" if out.get("deduped") else ""
            print(f"✓ {page_id}/{slot_id} ← {name} → {out.get('asset_id')}{dedup}")
        except RuntimeError as e:
            hata += 1
            print(f"✗ {page_id}/{slot_id} ← {name}: {e}")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
