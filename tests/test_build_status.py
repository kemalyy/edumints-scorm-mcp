"""tests/test_build_status.py — #94: build_status aracı (job durumu sorgulama, 30. araç).

build_package/build_from_spec fast-path'i (§3.1) aşınca job_id+status döner; build_status
o job'u proje üzerinden poll eder. Store-backed okuma (active_job_for_project = en yeni job)
→ restart sonrası da çalışır. Sahiplik diğer araçlarla aynı (_owner + _load).
"""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError as MCPToolError

import server
from core.project import new_job_id, new_project_id
from core.store import BuildJob


async def _spec_build(c: Client, title: str) -> str:
    res = await c.call_tool("build_from_spec", {"spec": {
        "title": title, "scorm_version": "1.2",
        "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
    }})
    return res.data.project_id


async def test_done_job_returns_download_url():
    """done job → status='done' + download_url dolu (build_package ile aynı kompozisyon)."""
    async with Client(server.mcp) as c:
        pid = await _spec_build(c, "BS done")
        out = await c.call_tool("build_status", {"project_id": pid})
        d = out.data
        assert d.status == "done"
        assert d.job_id
        assert d.download_url and "/files/" in d.download_url


async def test_pending_job_returns_status_without_url():
    """queued/running job → status döner, download_url YOK (store-backed okuma)."""
    async with Client(server.mcp) as c:
        res = await c.call_tool("create_project", {"title": "BS pending"})
        pid = res.data.project_id
        # store'a doğrudan 'running' job yaz → restart-sonrası/poll senaryosunun aynısı
        job = BuildJob(id=new_job_id(), project_id=pid, owner_key_id="key_local", status="running")
        await server.SVC.store.put_job(job)
        out = await c.call_tool("build_status", {"project_id": pid})
        d = out.data
        assert d.status == "running"
        assert d.job_id == job.id
        assert d.download_url is None


async def test_foreign_owner_rejected():
    """Başkasının projesi → not_found (sahiplik sızdırmaz; diğer araçlarla aynı _load yolu)."""
    from core.project import Project

    await server.SVC.ensure()
    p = Project(id=new_project_id(), title="Yabancı", owner_key_id="key_baskasi")
    await server.SVC.store.create_project(p)
    job = BuildJob(id=new_job_id(), project_id=p.id, owner_key_id="key_baskasi", status="done")
    await server.SVC.store.put_job(job)
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError, match="not_found"):
            await c.call_tool("build_status", {"project_id": p.id})


async def test_no_job_ever_clear_error():
    """Hiç build edilmemiş proje → açık not_found hatası (job yok)."""
    async with Client(server.mcp) as c:
        res = await c.call_tool("create_project", {"title": "BS jobsuz"})
        pid = res.data.project_id
        with pytest.raises(MCPToolError, match="build job"):
            await c.call_tool("build_status", {"project_id": pid})
