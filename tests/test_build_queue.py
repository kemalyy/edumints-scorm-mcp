"""Build kuyruğu: atomik tekilleştirme, kapasite + principal başına eşzamanlılık, restart kurtarması,
asset'ler kuyrukta değil çalışırken yüklenir."""
import asyncio

import pytest

import server
from auth.errors import ToolError
from core.project import ContentSlide, Project, new_job_id, new_project_id
from core.store import BuildJob


async def _setup(monkeypatch=None):
    await server.SVC.ensure()
    pk = server.SVC.packager
    if monkeypatch is not None:  # testler aynı packager'ı paylaşır → kuyruk sayaçlarını izole et
        monkeypatch.setattr(pk, "_tasks", {})
        monkeypatch.setattr(pk, "_task_owner", {})
    return pk


async def _drain(pk):
    """Testin başlattığı arka plan görevlerini sınırlı süre bekle (event loop kapanırken asılı görev kalmasın)."""
    tasks = list(pk._tasks.values())
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=20)


def _project(owner="key_local"):
    p = Project(id=new_project_id(), title="Q", owner_key_id=owner)
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    return p


async def test_concurrent_submits_for_same_project_create_one_job(monkeypatch):
    pk = await _setup(monkeypatch)
    gate = asyncio.Event()

    async def slow_run(job, project):
        await gate.wait()

    monkeypatch.setattr(pk, "_run", slow_run)
    p = _project()
    a, b = await asyncio.gather(pk.submit(p), pk.submit(p))
    assert a.id == b.id
    gate.set()
    await _drain(pk)


async def test_queue_capacity_and_per_principal_limit(monkeypatch):
    pk = await _setup(monkeypatch)
    gate = asyncio.Event()

    async def slow_run(job, project):
        await gate.wait()

    monkeypatch.setattr(pk, "_run", slow_run)
    monkeypatch.setattr(pk, "per_principal", 2)
    monkeypatch.setattr(pk, "queue_max", 3)
    await pk.submit(_project("ownerA"))
    await pk.submit(_project("ownerA"))
    with pytest.raises(ToolError) as e:
        await pk.submit(_project("ownerA"))
    assert e.value.code == "queue_full" and "eşzamanlı" in e.value.message
    await pk.submit(_project("ownerB"))
    with pytest.raises(ToolError) as e:
        await pk.submit(_project("ownerC"))
    assert e.value.code == "queue_full"
    gate.set()
    await _drain(pk)


async def test_orphaned_jobs_marked_failed_on_recovery():
    pk = await _setup()
    job = BuildJob(id=new_job_id(), project_id=new_project_id(), owner_key_id="x", status="running")
    await server.SVC.store.put_job(job)
    n = await pk.recover_orphans()
    assert n >= 1
    got = await server.SVC.store.get_job(job.id)
    assert got.status == "error" and "yeniden başlatıldı" in got.error


async def test_assets_not_loaded_at_submit(monkeypatch):
    pk = await _setup(monkeypatch)
    calls = []
    real = server.SVC.store.get_asset_bytes

    async def spy(pid, aid):
        calls.append(aid)
        return await real(pid, aid)

    gate = asyncio.Event()
    orig_run = pk._run

    async def gated(job, project):
        await gate.wait()
        await orig_run(job, project)

    monkeypatch.setattr(server.SVC.store, "get_asset_bytes", spy)
    monkeypatch.setattr(pk, "_run", gated)
    from core.project import AssetRef
    p = _project()
    p.assets = [AssetRef(id="a1", filename="a.png", mime="image/png", size_bytes=1, sha256="0",
                         rel_path="assets/a.png")]
    await pk.submit(p)
    assert calls == []  # kuyruktaki iş belleğe asset taşımaz
    gate.set()
    await _drain(pk)
