"""tools/local_media.py — lokal media yardımcısı (Faz 11).

Kendi makinende Piper TTS + HyperFrames video render yapar, opsiyonel olarak sonucu projeye
add_asset ile yükler. Sunucudaki yavaş (GPU'suz) render'ı by-pass eder; lokalde hızlıdır.

Gereksinim: piper-tts (pip install ".[tts]") + tr_TR ses modeli (PIPER_VOICE ya da --voice);
render için Node 22 + hyperframes (npx).

Kullanım:
  python tools/local_media.py tts --text "Merhaba" --out a.mp3 [--voice yol.onnx]
  python tools/local_media.py render --spec spec.json --out v.mp4 [--quality high]
  ... --upload --project <proj_id> --key sk_... [--base-url https://scorm.edumints.com]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="local_media")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", required=True)
    common.add_argument("--upload", action="store_true")
    common.add_argument("--project")
    common.add_argument("--key")
    common.add_argument("--base-url", default="https://scorm.edumints.com")
    t = sub.add_parser("tts", parents=[common])
    t.add_argument("--text", required=True)
    t.add_argument("--voice")
    r = sub.add_parser("render", parents=[common])
    r.add_argument("--spec", required=True)
    r.add_argument("--quality", default="standard")
    return p


async def _do_tts(ns) -> bytes:
    from core import tts, media
    wav = await tts.synthesize(ns.text, voice=ns.voice)
    return await media.normalize_audio(wav, ext="wav")


async def _do_render(ns) -> bytes:
    from core.video import VideoSpec
    from components.video_compiler import compile_composition
    from core.video_render import render_composition, check_guardrails
    spec = VideoSpec.model_validate(json.load(open(ns.spec)))
    check_guardrails(spec)
    comp = compile_composition(spec, theme=None)
    return await render_composition(comp.html, comp.meta, {}, quality=ns.quality)


def _upload(ns, data: bytes, mime: str) -> None:
    import httpx
    src = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    r = httpx.post(
        f"{ns.base_url}/mcp", timeout=120,
        headers={"Authorization": f"Bearer {ns.key}",
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "add_asset",
                         "arguments": {"project_id": ns.project, "source": src,
                                       "filename": os.path.basename(ns.out)}}})
    print("upload:", r.status_code, r.text[:200])


def main(argv=None) -> int:
    ns = build_parser().parse_args(argv)
    mime = "audio/mpeg" if ns.cmd == "tts" else "video/mp4"
    data = asyncio.run(_do_tts(ns) if ns.cmd == "tts" else _do_render(ns))
    with open(ns.out, "wb") as f:
        f.write(data)
    print(f"yazıldı {ns.out} ({len(data) // 1024} KB)")
    if ns.upload:
        if not (ns.project and ns.key):
            print("--upload için --project ve --key gerekli", file=sys.stderr)
            return 2
        _upload(ns, data, mime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
