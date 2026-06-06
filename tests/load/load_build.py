"""tests/load/load_build.py — build yolu yük ve regresyon testi (CONTRACTS.md §11).

Eşzamanlı build_from_spec çağrılarıyla build yolunu döver; throughput + p50/p95/p99 ölçer.
Ayrıca 10/50/100 ekranlı sentetik kurslar için build süresi ve paket boyutu ölçer.

İki mod:
  - in-memory (vars.): server.mcp'ye doğrudan bağlanır (ağ yok) → çekirdek build kapasitesi
  - remote: MCP_URL ayarlıysa HTTP üzerinden gerçek sunucuya bağlanır

Kullanım:
  python tests/load/load_build.py --concurrency 16 --requests 200
  python tests/load/load_build.py --regression
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import csv
from typing import Any

# repo kökünü import yoluna ekle (script tests/load/ içinden çalıştırılabilsin)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

SMALL_SPEC = {
    "title": "Yük Testi Kursu",
    "scorm_version": "1.2",
    "tracking": {"completion_rule": "viewed_all_and_passed", "passing_score": 50},
    "screens": [
        {"type": "title_slide", "title": "Başlık"},
        {"type": "content_slide", "title": "İçerik", "body_html": "<p>Metin</p>"},
        {"type": "mcq", "title": "Soru", "prompt_html": "<p>?</p>",
         "options": [{"id": "a", "text_html": "A", "correct": True},
                     {"id": "b", "text_html": "B"}], "points": 10},
        {"type": "summary", "title": "Özet"},
    ],
}

# Varsayılan eşikler (yapılandırılabilir)
DEFAULT_THRESHOLDS = {
    "10": {"time": 2.0, "size_kb": 600},
    "50": {"time": 5.0, "size_kb": 1200},
    "100": {"time": 10.0, "size_kb": 2500},
}


def make_synthetic_spec(num_screens: int) -> dict:
    screens = []
    for i in range(num_screens):
        if i == 0:
            screens.append({"type": "title_slide", "title": f"Başlık {i}"})
        elif i == num_screens - 1:
            screens.append({"type": "summary", "title": "Özet"})
        elif i % 10 == 0:
            screens.append({
                "type": "mcq", "title": f"Soru {i}", "prompt_html": f"<p>Soru {i}?</p>",
                "options": [{"id": "a", "text_html": "A", "correct": True},
                            {"id": "b", "text_html": "B"}], "points": 10
            })
        else:
            screens.append({
                "type": "content_slide", "title": f"Slayt {i}",
                "body_html": f"<p>Bu {i}. sentetik ekran içeriğidir.</p>"
            })
    return {
        "title": f"Sentetik Kurs {num_screens}",
        "scorm_version": "2004",  # 1.2 has small suspend_data limit (4KB)
        "tracking": {"completion_rule": "viewed_all_and_passed", "passing_score": 50},
        "screens": screens,
    }


def _make_client():
    from fastmcp import Client

    url = os.environ.get("MCP_URL")
    if url:
        key = os.environ.get("API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        return Client(url, headers=headers), f"remote:{url}"
    os.environ.setdefault("SCORM_AUTH_ENABLED", "0")
    import server

    return Client(server.mcp), "in-memory"


async def _get_package_size(mode: str, res: Any, client: Any) -> int:
    if mode == "in-memory":
        import server
        job_id = res.data.job_id
        job = await server.SVC.store.get_job(job_id)
        if job and job.package_id:
            pkg = await server.SVC.store.get_package(job.package_id)
            if pkg:
                return pkg.size_bytes
    elif mode.startswith("remote:"):
        import httpx
        url = res.data.download_url
        if url:
            async with httpx.AsyncClient() as hclient:
                # API_KEY varsa başlığa ekle
                headers = {}
                key = os.environ.get("API_KEY", "")
                if key:
                    headers["Authorization"] = f"Bearer {key}"
                # remote modda download_url dışa açık olmalı
                try:
                    resp = await hclient.head(url, headers=headers, follow_redirects=True)
                    size = resp.headers.get("Content-Length")
                    if size:
                        return int(size)
                except Exception:
                    return 0
    return 0


async def _worker(client, queue: asyncio.Queue, lat: list[float], errs: list[str]):
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        t0 = time.perf_counter()
        try:
            res = await client.call_tool("build_from_spec", {"spec": SMALL_SPEC})
            if res.data.status not in ("done", "running", "queued"):
                errs.append(res.data.status)
        except Exception as e:  # noqa: BLE001
            errs.append(type(e).__name__)
        lat.append(time.perf_counter() - t0)
        queue.task_done()


async def run_regression(client, mode: str, thresholds: dict):
    print(f"Regresyon testi başlatılıyor [{mode}]...")
    results = []
    failed = False

    for n in [10, 50, 100]:
        spec = make_synthetic_spec(n)
        t0 = time.perf_counter()
        res = await client.call_tool("build_from_spec", {"spec": spec})
        duration = time.perf_counter() - t0
        
        size = await _get_package_size(mode, res, client)
        size_kb = size / 1024

        thresh = thresholds.get(str(n), {})
        time_limit = thresh.get("time", 999)
        size_limit = thresh.get("size_kb", 9999)

        status = "PASS"
        if duration > time_limit or size_kb > size_limit:
            status = "FAIL"
            failed = True

        res_data = {
            "screens": n,
            "duration_s": round(duration, 3),
            "size_kb": round(size_kb, 1),
            "threshold_time": time_limit,
            "threshold_size_kb": size_limit,
            "status": status
        }
        results.append(res_data)
        print(f"{n:>3} ekran: {duration:5.2f}s, {size_kb:7.1f}KB | {status}")

    # JSON yaz
    with open("tests/load/regression_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    # CSV yaz
    with open("tests/load/regression_results.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    if failed:
        print("\nHATA: Bazı regresyon eşikleri aşıldı!")
        sys.exit(1)
    else:
        print("\nBAŞARI: Tüm regresyon testleri eşiklerin altında.")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--concurrency", type=int, default=16)
    ap.add_argument("-n", "--requests", type=int, default=200)
    ap.add_argument("--regression", action="store_true", help="10/50/100 ekranlı regresyon testi")
    ap.add_argument("--thresholds", type=str, help="Eşik JSON dosyası")
    args = ap.parse_args()

    client, mode = _make_client()
    
    thresholds = DEFAULT_THRESHOLDS
    if args.thresholds and os.path.exists(args.thresholds):
        with open(args.thresholds, "r") as f:
            thresholds.update(json.load(f))

    async with client:
        if args.regression:
            await run_regression(client, mode, thresholds)
            return

        lat: list[float] = []
        errs: list[str] = []
        queue: asyncio.Queue = asyncio.Queue()
        for _ in range(args.requests):
            queue.put_nowait(1)

        # warm-up (lazy init + ilk build)
        await client.call_tool("build_from_spec", {"spec": SMALL_SPEC})
        t0 = time.perf_counter()
        workers = [asyncio.create_task(_worker(client, queue, lat, errs))
                   for _ in range(args.concurrency)]
        await asyncio.gather(*workers)
        wall = time.perf_counter() - t0

    lat_ms = sorted(x * 1000 for x in lat)
    def pct(p):
        if not lat_ms:
            return 0.0
        return lat_ms[min(len(lat_ms) - 1, int(len(lat_ms) * p))]

    print("=" * 56)
    print(f" scorm-mcp build yük raporu  [{mode}]")
    print("=" * 56)
    print(f" concurrency      : {args.concurrency}")
    print(f" toplam istek     : {args.requests}")
    print(f" hata             : {len(errs)} {set(errs) if errs else ''}")
    print(f" süre (wall)      : {wall:.2f}s")
    print(f" throughput       : {args.requests / wall:.1f} build/s")
    print(f" gecikme p50      : {pct(0.50):.0f} ms")
    print(f" gecikme p95      : {pct(0.95):.0f} ms")
    print(f" gecikme p99      : {pct(0.99):.0f} ms")
    print(f" gecikme max      : {lat_ms[-1]:.0f} ms" if lat_ms else "")
    print("=" * 56)


if __name__ == "__main__":
    asyncio.run(main())
