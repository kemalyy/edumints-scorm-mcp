"""Kota kontrolü atomik (kilit + çağrı süresince rezervasyon); rate limiter eski kovaları temizler;
/feedback DB'ye bakmadan önce IP başına sınırlanır."""
import asyncio

import httpx

import auth.keys as keys
import server
from auth.errors import ToolError
from auth.ratelimit import RateLimiter
from core.store import ApiKey


class _Store:
    def __init__(self, used_bytes=0, projects=0):
        self.used, self.projects = used_bytes, projects

    async def total_bytes(self, pid):
        await asyncio.sleep(0.01)  # okuma ile yazma arasında araya girilebilir pencere
        return self.used

    async def count_projects(self, pid):
        await asyncio.sleep(0.01)
        return self.projects


def _key(mb=1, projects=1):
    return ApiKey(id="p1", label="t", key_hash="", max_total_mb=mb, max_projects=projects)


async def test_two_parallel_calls_cannot_both_take_last_slot():
    store, key = _Store(used_bytes=0), _key(mb=1)
    half = 700 * 1024

    async def call():
        with keys.reservation_scope():
            try:
                await keys.enforce_size_quota(store, key, half)
                await asyncio.sleep(0.02)  # yazma süresi
                return "ok"
            except ToolError as e:
                return e.code

    assert sorted(await asyncio.gather(call(), call())) == ["ok", "quota_exceeded"]


async def test_reservation_released_after_scope():
    store, key = _Store(used_bytes=0), _key(mb=1)
    with keys.reservation_scope():
        await keys.enforce_size_quota(store, key, 900 * 1024)
    with keys.reservation_scope():  # önceki çağrı bitti (yazmadı) → rezervasyon serbest
        await keys.enforce_size_quota(store, key, 900 * 1024)


async def test_project_quota_parallel():
    store, key = _Store(projects=0), _key(projects=1)

    async def call():
        with keys.reservation_scope():
            try:
                await keys.enforce_project_quota(store, key)
                await asyncio.sleep(0.02)
                return "ok"
            except ToolError as e:
                return e.code

    assert sorted(await asyncio.gather(call(), call())) == ["ok", "quota_exceeded"]


def test_rate_limiter_evicts_idle_buckets(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr("auth.ratelimit.time.monotonic", lambda: t[0])
    rl = RateLimiter(capacity=5, refill_per_sec=1.0)
    for i in range(100):
        rl.allow(f"k{i}")
    t[0] += 3600
    rl.allow("fresh")
    assert len(rl._buckets) <= 2


async def test_feedback_limited_per_ip_before_db_lookup(monkeypatch):
    calls = []
    real = server.SVC.store.get_preview

    async def spy(tok):
        calls.append(tok)
        return await real(tok)

    await server.SVC.ensure()
    monkeypatch.setattr(server.SVC.store, "get_preview", spy)
    monkeypatch.setattr(server, "_FEEDBACK_IP_LIMITER", RateLimiter(capacity=3, refill_per_sec=0.0001))
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        codes = [(await c.post("/feedback", json={"preview_token": f"nope{i}", "comment": "x"})).status_code
                 for i in range(5)]
    assert codes == [404, 404, 404, 429, 429]
    assert len(calls) == 3


async def test_tool_calls_run_inside_reservation_scope(monkeypatch):
    # araç çağrısı kapsamı middleware ile açılır: create_project içinde rezervasyon kaydedilir ve çağrı
    # bitince bırakılır (kalıcı rezervasyon birikmez)
    from fastmcp import Client
    seen = []
    real = keys._reserve

    def spy(pid, b, n):
        seen.append(keys._scope.get() is not None)
        real(pid, b, n)

    monkeypatch.setattr(keys, "_reserve", spy)
    async with Client(server.mcp) as c:
        await c.call_tool("create_project", {"title": "kapsam"})
    assert seen == [True] and keys._reserved == {}
