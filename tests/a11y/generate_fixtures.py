"""tests/a11y/generate_fixtures.py — examples/games/*.json'ı gerçek HTML'e render edip
tests/a11y/fixtures/ altına yazar (W9 P1 / W8c). Playwright+axe-core denetimi bu dosyaları okur.
Sunucuda LLM yok — bu script yalnızca mevcut build_from_spec/preview yolunu kullanır."""
import asyncio
import json
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="a11y-fixtures-")
os.environ.setdefault("SCORM_AUTH_ENABLED", "0")
os.environ.setdefault("DATA_DIR", _TMP)
os.environ.setdefault("DB_PATH", os.path.join(_TMP, "scorm.db"))
os.environ.setdefault("PUBLIC_BASE_URL", "https://mcp.test/scorm")
os.environ.setdefault("BUILD_SYNC_TIMEOUT_SEC", "20")
os.environ.setdefault("SCORM_NO_TTL_CLEANER", "1")
os.environ.setdefault("SCORM_SCHEMA_DIR", os.path.join(_TMP, "no_schemas"))
os.environ.setdefault("RATE_LIMIT_PER_MIN", "100000")

import server
from fastmcp import Client

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "games"
OUT_DIR = Path(__file__).resolve().parent / "fixtures"


async def render_one(client, spec_path: Path) -> str:
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    res = await client.call_tool("build_from_spec", {"spec": spec})
    data = res.data
    project_id = data.project_id if hasattr(data, "project_id") else data["project_id"]
    res2 = await client.call_tool("preview", {"project_id": project_id})
    data2 = res2.data
    return data2.inline_html if hasattr(data2, "inline_html") else data2["inline_html"]


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    spec_files = sorted(EXAMPLES_DIR.glob("*.json"))
    if not spec_files:
        raise SystemExit(f"örnek bulunamadı: {EXAMPLES_DIR}")
    async with Client(server.mcp) as client:
        for spec_path in spec_files:
            html = await render_one(client, spec_path)
            out_path = OUT_DIR / f"{spec_path.stem}.html"
            out_path.write_text(html, encoding="utf-8")
            print(f"wrote {out_path} ({len(html)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
