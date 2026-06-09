"""core/store.py — Soyut Store arayüzü + SQLite(WAL)+fs implementasyonu.

CONTRACTS.md §4, §12.2. Tüm veri erişimi bu arayüz arkasında — SQLite→Postgres geçişi
tek modülde izole. Uzun build işi ASLA transaction içinde değildir; bu modül yalnız kısa
metadata transaction'ları yapar.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Literal

import aiosqlite
from pydantic import BaseModel, Field

from .project import Project, utcnow


# --------------------------------------------------------------------------- #
# Yan tipler (CONTRACTS.md §4)
# --------------------------------------------------------------------------- #
class PackageMeta(BaseModel):
    id: str
    project_id: str
    owner_key_id: str
    token: str
    rel_path: str  # DATA_DIR altı, örn "packages/pkg_x.zip"
    size_bytes: int
    scorm_version: str
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class PreviewMeta(BaseModel):
    token: str
    project_id: str
    expires_at: datetime


class Feedback(BaseModel):
    id: str
    project_id: str
    screen_id: str | None = None
    comment: str
    status: Literal["open", "resolved"] = "open"
    created_at: datetime = Field(default_factory=utcnow)


class ApiKey(BaseModel):
    id: str
    label: str
    key_hash: str
    max_projects: int = 100
    max_total_mb: int = 500
    expires_at: datetime | None = None
    disabled: bool = False
    last_used_at: datetime | None = None
    # Kota/sahiplik principal'ı. NULL → eski davranış (principal=key.id). Portaldan üretilen
    # key'ler burada "logto:<sub>" taşır → OAuth (Claude) ve API-key (Antigravity) aynı projeleri görür.
    owner_principal: str | None = None
    created_at: datetime | None = None
    preview: str | None = None  # maskeli gösterim için (örn "sk_AbCd…wXyZ"); ham key saklanmaz


class BuildJob(BaseModel):
    id: str
    project_id: str
    owner_key_id: str
    status: Literal["queued", "running", "done", "error"]
    package_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Soyut arayüz
# --------------------------------------------------------------------------- #
class Store(ABC):
    # projeler
    @abstractmethod
    async def init(self) -> None: ...

    async def close(self) -> None:  # opsiyonel; kısa-ömürlü süreçlerde bağlantı temizliği
        return None

    # principal/tier (PORTAL_SPEC §6.1) — varsayılan no-op olmayan; alt sınıf uygular
    async def get_or_create_principal(self, principal_id: str, default_tier: str = "standard") -> str:
        return default_tier

    async def set_principal_tier(self, principal_id: str, tier: str) -> None:
        return None

    # bir projenin son (süresi geçmemiş) preview token'ı (portal panel listesi için)
    async def latest_preview_for_project(self, project_id: str) -> "PreviewMeta | None":
        return None

    # preview TTL temizliği (O2) — alt sınıf uygular
    async def expired_previews(self, now: datetime) -> "list[PreviewMeta]":
        return []

    async def delete_preview(self, token: str) -> None:
        return None

    # key yönetimi (portal /app) — alt sınıf uygular
    async def get_key_by_id(self, key_id: str) -> "ApiKey | None":
        return None

    async def list_keys_for_principal(self, principal: str) -> "list[ApiKey]":
        return []

    async def delete_key(self, key_id: str) -> None:
        return None

    # feedback (Faz 2 — preview annotation) — alt sınıf uygular
    async def add_feedback(self, fb: "Feedback") -> None:
        return None

    async def list_feedback(self, project_id: str, only_open: bool = True) -> "list[Feedback]":
        return []

    async def resolve_feedback(self, feedback_id: str, project_id: str) -> bool:
        return False

    async def count_open_feedback(self, project_id: str) -> int:
        return 0

    async def list_open_feedback_for_owner(self, owner_key_id: str) -> "list[dict]":
        return []

    @abstractmethod
    async def create_project(self, p: Project) -> None: ...
    @abstractmethod
    async def get_project(self, project_id: str, owner_key_id: str) -> Project | None: ...
    @abstractmethod
    async def update_project(self, p: Project) -> None: ...
    @abstractmethod
    async def delete_project(self, project_id: str, owner_key_id: str) -> None: ...
    @abstractmethod
    async def list_projects(self, owner_key_id: str) -> list[Project]: ...
    @abstractmethod
    async def count_projects(self, owner_key_id: str) -> int: ...
    @abstractmethod
    async def total_bytes(self, owner_key_id: str) -> int: ...

    # varlıklar (fs + metadata)
    @abstractmethod
    async def put_asset(self, project_id: str, data: bytes, meta) -> None: ...
    @abstractmethod
    async def get_asset_bytes(self, project_id: str, asset_id: str) -> bytes: ...

    # paketler
    @abstractmethod
    async def put_package(self, meta: PackageMeta) -> None: ...
    @abstractmethod
    async def get_package_by_token(self, token: str) -> PackageMeta | None: ...
    @abstractmethod
    async def get_package(self, pkg_id: str) -> PackageMeta | None: ...
    @abstractmethod
    async def latest_package_for_project(self, project_id: str) -> PackageMeta | None: ...
    @abstractmethod
    async def expired_packages(self, now: datetime) -> list[PackageMeta]: ...
    @abstractmethod
    async def delete_package(self, pkg_id: str) -> None: ...

    # preview token'ları
    @abstractmethod
    async def put_preview(self, token: str, project_id: str, ttl_sec: int) -> None: ...
    @abstractmethod
    async def get_preview(self, token: str) -> PreviewMeta | None: ...

    # api anahtarları
    @abstractmethod
    async def get_key(self, raw_key: str) -> ApiKey | None: ...
    @abstractmethod
    async def upsert_key(self, key: ApiKey, raw_key: str | None = None) -> None: ...
    @abstractmethod
    async def touch_key(self, key_id: str) -> None: ...

    # build job
    @abstractmethod
    async def put_job(self, job: BuildJob) -> None: ...
    @abstractmethod
    async def get_job(self, job_id: str) -> BuildJob | None: ...
    @abstractmethod
    async def update_job(self, job: BuildJob) -> None: ...
    @abstractmethod
    async def active_job_for_project(self, project_id: str) -> BuildJob | None: ...


# --------------------------------------------------------------------------- #
# SQLite(WAL) + filesystem implementasyonu
# --------------------------------------------------------------------------- #
def _hash_key(raw_key: str) -> str:
    import hashlib

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class SqliteStore(Store):
    def __init__(self, db_path: str, data_dir: str):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self._db: aiosqlite.Connection | None = None
        self._wlock = asyncio.Lock()  # kısa yazma transaction'ları için

    # -- altyapı --
    async def init(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "assets").mkdir(exist_ok=True)
        (self.data_dir / "packages").mkdir(exist_ok=True)
        (self.data_dir / "previews").mkdir(exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects(
                id TEXT PRIMARY KEY, owner_key_id TEXT NOT NULL, data TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_projects_owner ON projects(owner_key_id);

            CREATE TABLE IF NOT EXISTS packages(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_key_id TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE, rel_path TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                scorm_version TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_pkg_project ON packages(project_id);
            CREATE INDEX IF NOT EXISTS ix_pkg_owner ON packages(owner_key_id);

            CREATE TABLE IF NOT EXISTS previews(
                token TEXT PRIMARY KEY, project_id TEXT NOT NULL, expires_at TEXT NOT NULL);

            CREATE TABLE IF NOT EXISTS api_keys(
                id TEXT PRIMARY KEY, label TEXT NOT NULL, key_hash TEXT NOT NULL UNIQUE,
                max_projects INTEGER NOT NULL, max_total_mb INTEGER NOT NULL,
                expires_at TEXT, disabled INTEGER NOT NULL DEFAULT 0, last_used_at TEXT,
                owner_principal TEXT, created_at TEXT, preview TEXT);
            CREATE INDEX IF NOT EXISTS ix_keys_owner ON api_keys(owner_principal);

            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, owner_key_id TEXT NOT NULL,
                status TEXT NOT NULL, package_id TEXT, error TEXT,
                created_at TEXT NOT NULL, finished_at TEXT);
            CREATE INDEX IF NOT EXISTS ix_jobs_project ON jobs(project_id);

            CREATE TABLE IF NOT EXISTS principals(
                principal_id TEXT PRIMARY KEY, tier TEXT NOT NULL DEFAULT 'standard',
                created_at TEXT NOT NULL);

            CREATE TABLE IF NOT EXISTS feedback(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, screen_id TEXT,
                comment TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_feedback_project ON feedback(project_id);
            """
        )
        # geriye dönük migration: eski api_keys tablosunda owner_principal yoksa ekle (nullable;
        # eski key'ler NULL kalır → principal=key.id ile aynen çalışır). SQLite ADD COLUMN güvenli.
        async with self._db.execute("PRAGMA table_info(api_keys)") as cur:
            cols = {r[1] for r in await cur.fetchall()}
        for col in ("owner_principal", "created_at", "preview"):
            if col not in cols:
                await self._db.execute(f"ALTER TABLE api_keys ADD COLUMN {col} TEXT")
        await self._db.commit()

    # -- principal (kota sahibi: API-key id VEYA logto:<sub>) + tier --
    async def get_or_create_principal(self, principal_id: str, default_tier: str = "standard") -> str:
        """principal kaydını döndürür/oluşturur; tier'ını döndürür (CONTRACTS/PORTAL_SPEC §6.1)."""
        async with self.db.execute(
            "SELECT tier FROM principals WHERE principal_id=?", (principal_id,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            return row["tier"]
        async with self._wlock:
            await self.db.execute(
                "INSERT OR IGNORE INTO principals(principal_id,tier,created_at) VALUES(?,?,?)",
                (principal_id, default_tier, utcnow().isoformat()),
            )
            await self.db.commit()
        return default_tier

    async def set_principal_tier(self, principal_id: str, tier: str) -> None:
        async with self._wlock:
            await self.db.execute(
                "INSERT INTO principals(principal_id,tier,created_at) VALUES(?,?,?) "
                "ON CONFLICT(principal_id) DO UPDATE SET tier=excluded.tier",
                (principal_id, tier, utcnow().isoformat()),
            )
            await self.db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Store.init() çağrılmadı")
        return self._db

    # -- projeler --
    async def create_project(self, p: Project) -> None:
        async with self._wlock:
            await self.db.execute(
                "INSERT INTO projects(id,owner_key_id,data,size_bytes,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?)",
                (p.id, p.owner_key_id, p.model_dump_json(), _project_bytes(p),
                 p.created_at.isoformat(), p.updated_at.isoformat()),
            )
            await self.db.commit()

    async def get_project(self, project_id: str, owner_key_id: str) -> Project | None:
        async with self.db.execute(
            "SELECT data FROM projects WHERE id=? AND owner_key_id=?",
            (project_id, owner_key_id),
        ) as cur:
            row = await cur.fetchone()
        return Project.model_validate_json(row["data"]) if row else None

    async def update_project(self, p: Project) -> None:
        p.updated_at = utcnow()
        async with self._wlock:
            await self.db.execute(
                "UPDATE projects SET data=?,size_bytes=?,updated_at=? WHERE id=? AND owner_key_id=?",
                (p.model_dump_json(), _project_bytes(p), p.updated_at.isoformat(),
                 p.id, p.owner_key_id),
            )
            await self.db.commit()

    async def delete_project(self, project_id: str, owner_key_id: str) -> None:
        async with self._wlock:
            await self.db.execute(
                "DELETE FROM projects WHERE id=? AND owner_key_id=?", (project_id, owner_key_id)
            )
            await self.db.commit()

    async def list_projects(self, owner_key_id: str) -> list[Project]:
        async with self.db.execute(
            "SELECT data FROM projects WHERE owner_key_id=? ORDER BY created_at", (owner_key_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [Project.model_validate_json(r["data"]) for r in rows]

    async def count_projects(self, owner_key_id: str) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) c FROM projects WHERE owner_key_id=?", (owner_key_id,)
        ) as cur:
            row = await cur.fetchone()
        return int(row["c"])

    async def total_bytes(self, owner_key_id: str) -> int:
        async with self.db.execute(
            "SELECT COALESCE(SUM(size_bytes),0) s FROM projects WHERE owner_key_id=?",
            (owner_key_id,),
        ) as cur:
            pr = await cur.fetchone()
        async with self.db.execute(
            "SELECT COALESCE(SUM(size_bytes),0) s FROM packages WHERE owner_key_id=?",
            (owner_key_id,),
        ) as cur:
            pk = await cur.fetchone()
        return int(pr["s"]) + int(pk["s"])

    # -- varlıklar (fs) --
    def _asset_path(self, project_id: str, asset_id: str) -> Path:
        return self.data_dir / "assets" / project_id / asset_id

    async def put_asset(self, project_id: str, data: bytes, meta) -> None:
        path = self._asset_path(project_id, meta.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # fs yazımı bloklamasın → threadpool
        await asyncio.to_thread(path.write_bytes, data)

    async def get_asset_bytes(self, project_id: str, asset_id: str) -> bytes:
        path = self._asset_path(project_id, asset_id)
        return await asyncio.to_thread(path.read_bytes)

    # -- paketler --
    async def put_package(self, meta: PackageMeta) -> None:
        async with self._wlock:
            await self.db.execute(
                "INSERT INTO packages(id,project_id,owner_key_id,token,rel_path,size_bytes,"
                "scorm_version,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (meta.id, meta.project_id, meta.owner_key_id, meta.token, meta.rel_path,
                 meta.size_bytes, meta.scorm_version, meta.created_at.isoformat(),
                 meta.expires_at.isoformat()),
            )
            await self.db.commit()

    async def _pkg_row(self, where: str, args: tuple) -> PackageMeta | None:
        async with self.db.execute(
            f"SELECT * FROM packages WHERE {where}", args
        ) as cur:
            row = await cur.fetchone()
        return _row_to_pkg(row) if row else None

    async def get_package_by_token(self, token: str) -> PackageMeta | None:
        return await self._pkg_row("token=?", (token,))

    async def get_package(self, pkg_id: str) -> PackageMeta | None:
        return await self._pkg_row("id=?", (pkg_id,))

    async def latest_package_for_project(self, project_id: str) -> PackageMeta | None:
        return await self._pkg_row(
            "project_id=? ORDER BY created_at DESC LIMIT 1", (project_id,)
        )

    async def expired_packages(self, now: datetime) -> list[PackageMeta]:
        async with self.db.execute(
            "SELECT * FROM packages WHERE expires_at < ?", (now.isoformat(),)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_pkg(r) for r in rows]

    async def delete_package(self, pkg_id: str) -> None:
        async with self._wlock:
            await self.db.execute("DELETE FROM packages WHERE id=?", (pkg_id,))
            await self.db.commit()

    # -- preview --
    async def put_preview(self, token: str, project_id: str, ttl_sec: int) -> None:
        from datetime import timedelta

        exp = utcnow() + timedelta(seconds=ttl_sec)
        async with self._wlock:
            await self.db.execute(
                "INSERT OR REPLACE INTO previews(token,project_id,expires_at) VALUES(?,?,?)",
                (token, project_id, exp.isoformat()),
            )
            await self.db.commit()

    async def get_preview(self, token: str) -> PreviewMeta | None:
        async with self.db.execute(
            "SELECT * FROM previews WHERE token=?", (token,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return PreviewMeta(token=row["token"], project_id=row["project_id"],
                           expires_at=_dt(row["expires_at"]))

    async def latest_preview_for_project(self, project_id: str) -> PreviewMeta | None:
        async with self.db.execute(
            "SELECT * FROM previews WHERE project_id=? AND expires_at > ? "
            "ORDER BY expires_at DESC LIMIT 1",
            (project_id, utcnow().isoformat()),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return PreviewMeta(token=row["token"], project_id=row["project_id"],
                           expires_at=_dt(row["expires_at"]))

    async def expired_previews(self, now: datetime) -> list[PreviewMeta]:
        async with self.db.execute(
            "SELECT * FROM previews WHERE expires_at < ?", (now.isoformat(),)
        ) as cur:
            rows = await cur.fetchall()
        return [PreviewMeta(token=r["token"], project_id=r["project_id"],
                            expires_at=_dt(r["expires_at"])) for r in rows]

    async def delete_preview(self, token: str) -> None:
        async with self._wlock:
            await self.db.execute("DELETE FROM previews WHERE token=?", (token,))
            await self.db.commit()

    # -- feedback (preview annotation) --
    async def add_feedback(self, fb: Feedback) -> None:
        async with self._wlock:
            await self.db.execute(
                "INSERT INTO feedback(id,project_id,screen_id,comment,status,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (fb.id, fb.project_id, fb.screen_id, fb.comment, fb.status, fb.created_at.isoformat()),
            )
            await self.db.commit()

    async def list_feedback(self, project_id: str, only_open: bool = True) -> list[Feedback]:
        sql = "SELECT * FROM feedback WHERE project_id=?"
        if only_open:
            sql += " AND status='open'"
        sql += " ORDER BY created_at"
        async with self.db.execute(sql, (project_id,)) as cur:
            rows = await cur.fetchall()
        return [Feedback(id=r["id"], project_id=r["project_id"], screen_id=r["screen_id"],
                         comment=r["comment"], status=r["status"], created_at=_dt(r["created_at"]))
                for r in rows]

    async def resolve_feedback(self, feedback_id: str, project_id: str) -> bool:
        async with self._wlock:
            cur = await self.db.execute(
                "UPDATE feedback SET status='resolved' WHERE id=? AND project_id=?",
                (feedback_id, project_id),
            )
            await self.db.commit()
            return cur.rowcount > 0

    async def count_open_feedback(self, project_id: str) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) c FROM feedback WHERE project_id=? AND status='open'", (project_id,)
        ) as cur:
            row = await cur.fetchone()
        return int(row["c"])

    async def list_open_feedback_for_owner(self, owner_key_id: str) -> list[dict]:
        """Sahibin TÜM projelerindeki açık yorumlar (keşif için; project_id + başlıkla)."""
        import json as _json

        async with self.db.execute(
            "SELECT f.id,f.project_id,f.screen_id,f.comment,f.created_at,p.data "
            "FROM feedback f JOIN projects p ON f.project_id=p.id "
            "WHERE p.owner_key_id=? AND f.status='open' ORDER BY f.created_at",
            (owner_key_id,),
        ) as cur:
            rows = await cur.fetchall()
        out = []
        for r in rows:
            try:
                title = _json.loads(r["data"]).get("title", "")
            except Exception:  # noqa: BLE001
                title = ""
            out.append({"id": r["id"], "project_id": r["project_id"], "project_title": title,
                        "screen_id": r["screen_id"], "comment": r["comment"], "created_at": r["created_at"]})
        return out

    # -- api anahtarları --
    async def get_key(self, raw_key: str) -> ApiKey | None:
        kh = _hash_key(raw_key)
        async with self.db.execute(
            "SELECT * FROM api_keys WHERE key_hash=?", (kh,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_key(row) if row else None

    async def get_key_by_id(self, key_id: str) -> ApiKey | None:
        async with self.db.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)) as cur:
            row = await cur.fetchone()
        return _row_to_key(row) if row else None

    async def list_keys_for_principal(self, principal: str) -> list[ApiKey]:
        async with self.db.execute(
            "SELECT * FROM api_keys WHERE owner_principal=? ORDER BY created_at DESC", (principal,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_key(r) for r in rows]

    async def delete_key(self, key_id: str) -> None:
        async with self._wlock:
            await self.db.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
            await self.db.commit()

    async def upsert_key(self, key: ApiKey, raw_key: str | None = None) -> None:
        kh = _hash_key(raw_key) if raw_key else key.key_hash
        async with self._wlock:
            await self.db.execute(
                "INSERT OR REPLACE INTO api_keys(id,label,key_hash,max_projects,max_total_mb,"
                "expires_at,disabled,last_used_at,owner_principal,created_at,preview) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (key.id, key.label, kh, key.max_projects, key.max_total_mb,
                 _iso(key.expires_at), int(key.disabled), _iso(key.last_used_at),
                 key.owner_principal, _iso(key.created_at), key.preview),
            )
            await self.db.commit()

    async def touch_key(self, key_id: str) -> None:
        async with self._wlock:
            await self.db.execute(
                "UPDATE api_keys SET last_used_at=? WHERE id=?", (utcnow().isoformat(), key_id)
            )
            await self.db.commit()

    # -- build job --
    async def put_job(self, job: BuildJob) -> None:
        async with self._wlock:
            await self.db.execute(
                "INSERT INTO jobs(id,project_id,owner_key_id,status,package_id,error,"
                "created_at,finished_at) VALUES(?,?,?,?,?,?,?,?)",
                (job.id, job.project_id, job.owner_key_id, job.status, job.package_id,
                 job.error, job.created_at.isoformat(), _iso(job.finished_at)),
            )
            await self.db.commit()

    async def get_job(self, job_id: str) -> BuildJob | None:
        async with self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cur:
            row = await cur.fetchone()
        return _row_to_job(row) if row else None

    async def update_job(self, job: BuildJob) -> None:
        async with self._wlock:
            await self.db.execute(
                "UPDATE jobs SET status=?,package_id=?,error=?,finished_at=? WHERE id=?",
                (job.status, job.package_id, job.error, _iso(job.finished_at), job.id),
            )
            await self.db.commit()

    async def active_job_for_project(self, project_id: str) -> BuildJob | None:
        async with self.db.execute(
            "SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ) as cur:
            row = await cur.fetchone()
        return _row_to_job(row) if row else None


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _project_bytes(p: Project) -> int:
    return sum(a.size_bytes for a in p.assets)


def _row_to_key(row) -> ApiKey:
    keys = row.keys() if hasattr(row, "keys") else []
    return ApiKey(
        id=row["id"], label=row["label"], key_hash=row["key_hash"],
        max_projects=row["max_projects"], max_total_mb=row["max_total_mb"],
        expires_at=_dt(row["expires_at"]), disabled=bool(row["disabled"]),
        last_used_at=_dt(row["last_used_at"]),
        owner_principal=row["owner_principal"] if "owner_principal" in keys else None,
        created_at=_dt(row["created_at"]) if "created_at" in keys else None,
        preview=row["preview"] if "preview" in keys else None,
    )


def _row_to_pkg(row) -> PackageMeta:
    return PackageMeta(
        id=row["id"], project_id=row["project_id"], owner_key_id=row["owner_key_id"],
        token=row["token"], rel_path=row["rel_path"], size_bytes=row["size_bytes"],
        scorm_version=row["scorm_version"], created_at=_dt(row["created_at"]),
        expires_at=_dt(row["expires_at"]),
    )


def _row_to_job(row) -> BuildJob:
    return BuildJob(
        id=row["id"], project_id=row["project_id"], owner_key_id=row["owner_key_id"],
        status=row["status"], package_id=row["package_id"], error=row["error"],
        created_at=_dt(row["created_at"]), finished_at=_dt(row["finished_at"]),
    )


# --------------------------------------------------------------------------- #
# Fabrika (CONTRACTS.md §12.2)
# --------------------------------------------------------------------------- #
def create_store(db_path: str, data_dir: str) -> Store:
    return SqliteStore(db_path=db_path, data_dir=data_dir)
