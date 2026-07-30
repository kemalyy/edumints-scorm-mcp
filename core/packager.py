"""core/packager.py — Build-as-job + fast-path + TTL temizleyici (CONTRACTS.md §3.1, §12.3).

Build her zaman threadpool'da çalışır (request thread'inde inline DEĞİL). Fast-path: çağıran
en fazla BUILD_SYNC_TIMEOUT_SEC bekler; bitmezse job_id ile poll eder. Idempotent: proje
değişmediyse mevcut/biten job döner, yeni build başlatılmaz.

renderer DI ile geçilir (components'a doğrudan import bağımlılığı yok). renderer arayüzü:
    renderer.render_html(project, *, mode, runtime_js) -> str
    renderer.load_runtime_js() -> str
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from .manifest import build_manifest
from .project import Project, new_job_id, new_package_id, utcnow
from .schema_validate import SCHEMA_UNAVAILABLE
from .store import BuildJob, PackageMeta, Store
from .validator import validate_zip

RUNTIME_REL = "runtime/scorm-again.min.js"
PROVENANCE_REL = "assets/PROVENANCE.json"  # Faz 3 — yalnız media_provenance doluysa yazılır

_ARTIFACT_WARN_CAP = 512  # in-process uyarı defteri sınırı (job başına küçük string listesi)


class ArtifactValidationError(Exception):
    """SP-5 (B1 delta) — üretilen zip yapısal doğrulamadan geçemedi; build başarısız sayılır."""


class Packager:
    def __init__(
        self,
        store: Store,
        data_dir: str,
        *,
        workers: int,
        renderer,
        public_base_url: str,
        package_ttl_days: int,
    ):
        self.store = store
        self.data_dir = Path(data_dir)
        self.renderer = renderer
        self.public_base_url = public_base_url.rstrip("/")
        self.ttl_days = package_ttl_days
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="build")
        self._tasks: dict[str, asyncio.Task] = {}
        self._cleaner_task: asyncio.Task | None = None
        # SP-5 — job başına bloklamayan artifact uyarıları (ör. schema_unavailable). Bilinçli
        # olarak in-process (DB şeması değişmedi): danışsaldır, restart sonrası kaybolması kabul.
        self._artifact_warnings: dict[str, list[str]] = {}

    # ----------------------------------------------------------------- #
    # Public API (§12.3)
    # ----------------------------------------------------------------- #
    async def submit(self, project: Project) -> BuildJob:
        """Idempotent build tetikleyici (§3.1)."""
        existing = await self.store.active_job_for_project(project.id)
        if existing:
            if existing.status in ("queued", "running"):
                return existing
            if existing.status == "done" and project.updated_at <= existing.created_at:
                return existing  # proje değişmedi → mevcut paket geçerli

        job = BuildJob(
            id=new_job_id(),
            project_id=project.id,
            owner_key_id=project.owner_key_id,
            status="queued",
        )
        await self.store.put_job(job)
        # asset bytes'ı async tarafta topla (threadpool'da DB/await yok)
        assets = {}
        for a in project.assets:
            try:
                assets[a.id] = await self.store.get_asset_bytes(project.id, a.id)
            except FileNotFoundError:
                pass
        task = asyncio.create_task(self._run(job, project, assets))
        self._tasks[job.id] = task
        return job

    async def wait(self, job_id: str, timeout: float) -> BuildJob:
        """Fast-path bekleme: en fazla `timeout` sn; sonra güncel job döner."""
        task = self._tasks.get(job_id)
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            except asyncio.TimeoutError:
                pass
        job = await self.store.get_job(job_id)
        return job  # type: ignore[return-value]

    async def get(self, job_id: str) -> BuildJob | None:
        return await self.store.get_job(job_id)

    def download_url(self, token: str) -> str:
        return f"{self.public_base_url}/files/{token}"

    def artifact_warnings(self, job_id: str) -> list[str]:
        """Job'un bloklamayan artifact uyarıları (SP-5; in-process, restart sonrası boş)."""
        return list(self._artifact_warnings.get(job_id, []))

    async def start_ttl_cleaner(self, interval_sec: int = 3600) -> None:
        # Testlerde başlatma: sonsuz arka-plan task'i event-loop teardown'ında pending kalıp
        # pytest'i askıda bırakabiliyor (CI hang). conftest SCORM_NO_TTL_CLEANER=1 set eder.
        if os.environ.get("SCORM_NO_TTL_CLEANER") == "1":
            return
        if self._cleaner_task is None:
            self._cleaner_task = asyncio.create_task(self._ttl_loop(interval_sec))

    async def shutdown(self) -> None:
        if self._cleaner_task:
            self._cleaner_task.cancel()
        self.executor.shutdown(wait=False)

    # ----------------------------------------------------------------- #
    # Job runner
    # ----------------------------------------------------------------- #
    async def _run(self, job: BuildJob, project: Project, assets: dict[str, bytes]) -> None:
        job.status = "running"
        await self.store.update_job(job)
        try:
            loop = asyncio.get_running_loop()
            meta = await loop.run_in_executor(
                self.executor, self.build_sync, project, assets
            )
            # SP-5 (B1 delta) — artifact kapısı: zip'i BAŞARI işaretlemeden önce doğrula.
            # Doğrulama noktası bilinçli olarak job tamamlanması (_run): hem fast-path hem async
            # yol buradan geçer → build_status/download hiçbir zaman doğrulanmamış zip göremez.
            # Bloklayan hata → paket kaydedilmez, bozuk dosya silinir, job "error" olur.
            # schema_unavailable BLOKLAMAZ; yanıtta uyarı olarak taşınır (artifact_warnings).
            zip_path = self.data_dir / meta.rel_path
            zerrs = await loop.run_in_executor(
                self.executor, validate_zip, str(zip_path), meta.scorm_version
            )
            if len(self._artifact_warnings) >= _ARTIFACT_WARN_CAP:
                self._artifact_warnings.pop(next(iter(self._artifact_warnings)))
            self._artifact_warnings[job.id] = [
                e.message for e in zerrs if e.code == SCHEMA_UNAVAILABLE
            ]
            blocking = [e for e in zerrs if e.code != SCHEMA_UNAVAILABLE]
            if blocking:
                zip_path.unlink(missing_ok=True)
                raise ArtifactValidationError("; ".join(e.message for e in blocking[:5]))
            await self.store.put_package(meta)
            job.status = "done"
            job.package_id = meta.id
            job.finished_at = utcnow()
            await self.store.update_job(job)
        except Exception as e:  # noqa: BLE001
            job.status = "error"
            job.error = f"{type(e).__name__}: {e}"
            job.finished_at = utcnow()
            await self.store.update_job(job)
        finally:
            self._tasks.pop(job.id, None)

    # ----------------------------------------------------------------- #
    # Düşük seviye build (threadpool'da çalışır — DB/ağ YOK)
    # ----------------------------------------------------------------- #
    def build_sync(self, project: Project, assets: dict[str, bytes]) -> PackageMeta:
        runtime_js = self.renderer.load_runtime_js()
        index_html = self.renderer.render_html(project, mode="package", runtime_js=runtime_js)

        # opt-in/lazy ek runtime dosyaları (ör. lottie) — yalnız kullanılıyorsa (zero-load)
        extra = (self.renderer.extra_runtime_files(project)
                 if hasattr(self.renderer, "extra_runtime_files") else [])
        file_list = ["index.html", RUNTIME_REL] + [rel for rel, _ in extra]
        for a in project.assets:
            file_list.append(a.rel_path)
        # Faz 3 (kabul #11) — dolu medya yuvası provenance'ı pakete gömülür. YALNIZ kayıt
        # varsa: düz (senaryosuz) kurslar bu dosyayı KAZANMAZ (geriye-uyum/bayt-parite).
        prov = getattr(project, "media_provenance", None) or []
        prov_json = None
        if prov:
            prov_json = json.dumps(prov, ensure_ascii=False, sort_keys=True, indent=2)
            file_list.append(PROVENANCE_REL)
        manifest_xml = build_manifest(project, file_list=file_list)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", index_html)
            zf.writestr("imsmanifest.xml", manifest_xml)
            zf.writestr(RUNTIME_REL, runtime_js)
            for rel, content in extra:
                zf.writestr(rel, content)
            for a in project.assets:
                data = assets.get(a.id)
                if data is not None:
                    zf.writestr(a.rel_path, data)
            if prov_json is not None:
                zf.writestr(PROVENANCE_REL, prov_json)
        data = buf.getvalue()

        pkg_id = new_package_id()
        token = secrets.token_urlsafe(24)
        rel_path = f"packages/{pkg_id}.zip"
        out = self.data_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)

        return PackageMeta(
            id=pkg_id,
            project_id=project.id,
            owner_key_id=project.owner_key_id,
            token=token,
            rel_path=rel_path,
            size_bytes=len(data),
            scorm_version=project.scorm_version,
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(days=self.ttl_days),
        )

    # ----------------------------------------------------------------- #
    # TTL temizleyici
    # ----------------------------------------------------------------- #
    async def _ttl_loop(self, interval_sec: int) -> None:
        while True:
            try:
                await self._clean_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(interval_sec)

    async def _clean_once(self) -> None:
        now = utcnow()
        expired = await self.store.expired_packages(now)
        for meta in expired:
            path = self.data_dir / meta.rel_path
            try:
                if path.exists():
                    await asyncio.to_thread(path.unlink)
            except OSError:
                pass
            await self.store.delete_package(meta.id)
        # O2: süresi geçmiş preview'ları temizle (dosya + DB satırı; previews/ sınırsız büyümesin)
        for pv in await self.store.expired_previews(now):
            ppath = self.data_dir / "previews" / f"{pv.token}.html"
            try:
                if ppath.exists():
                    await asyncio.to_thread(ppath.unlink)
            except OSError:
                pass
            await self.store.delete_preview(pv.token)
