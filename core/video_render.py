"""core/video_render.py — HyperFrames CLI ile kompozisyonu MP4'e render eder (Faz 10).

LAZY/opt-in (zero-load): Node/HyperFrames yoksa açık ToolError; import için gerekmez. Guardrail:
max çözünürlük/süre/fps. Render = `npx hyperframes render` alt-süreci (timeout'lu). Narration sesi
varsa çağıran taraf core.media.mux_audio ile mux'lar.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

from auth.errors import ToolError

NPX = shutil.which("npx")
RENDER_TIMEOUT = 240
MAX_W, MAX_H, MAX_DUR, MAX_FPS = 1920, 1080, 60.0, 60


def hyperframes_available() -> bool:
    return NPX is not None


def check_guardrails(spec) -> None:
    if spec.width > MAX_W or spec.height > MAX_H:
        raise ToolError("video_too_large", f"Çözünürlük en fazla {MAX_W}x{MAX_H}")
    if spec.fps > MAX_FPS:
        raise ToolError("video_bad_fps", f"fps en fazla {MAX_FPS}")
    d = spec.total_duration()
    if d <= 0 or d > MAX_DUR:
        raise ToolError("video_too_long", f"Toplam süre 0–{MAX_DUR:g}sn olmalı (şu an {d:g})")


async def render_composition(html: str, meta: dict, assets: dict[str, bytes],
                             timeout: int = RENDER_TIMEOUT, quality: str = "standard") -> bytes:
    """index.html (+ assets/) yaz → `npx hyperframes render` → mp4 bytes. quality: draft|standard|high."""
    if not NPX:
        raise ToolError("video_unavailable",
                        "Bu sunucuda HyperFrames/Node yok (video render devre dışı)")
    fps = int(meta.get("fps", 30))
    q = quality if quality in ("draft", "standard", "high") else "standard"
    with tempfile.TemporaryDirectory() as d:
        # HyperFrames için sadece index.html (+ assets/) yeterli; boyut/süre #root div'de.
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        adir = os.path.join(d, "assets")
        os.makedirs(adir, exist_ok=True)
        for name, data in assets.items():
            with open(os.path.join(adir, name), "wb") as f:
                f.write(data)
        out = os.path.join(d, "out.mp4")
        proc = await asyncio.create_subprocess_exec(
            NPX, "--yes", "hyperframes", "render", "-o", out, "-f", str(fps),
            "-q", q, "--quiet",
            cwd=d, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "CI": "1"},
        )
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise ToolError("video_timeout", f"Render {timeout}s sınırını aştı")
        if proc.returncode != 0 or not os.path.exists(out):
            msg = err.decode("utf-8", "ignore")
            low = msg.lower()
            if "chromium" in low or ("browser" in low and ("could not find" in low or "install" in low)):
                raise ToolError(
                    "render_unavailable",
                    "Video render motoru (Chromium) bu sunucuda kurulu değil. Alternatifler: "
                    "(1) make_video_from_image_audio ile PNG+TTS→MP4, (2) svg_to_asset/add_asset ile "
                    "statik görsel, (3) tools/local_media.py ile yerelde render edip add_asset.")
            raise ToolError("video_error", f"HyperFrames hata: {msg[-300:]}")
        with open(out, "rb") as f:
            return f.read()
