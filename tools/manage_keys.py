"""tools/manage_keys.py — API anahtarı yönetimi (CONTRACTS.md §4).

Auth varsayılan AÇIK olduğundan, kurum/öğretmen anahtarları bu araçla oluşturulur. Ham anahtar
yalnız oluşturma anında bir kez gösterilir; DB'de sha256 hash saklanır.

Kullanım:
  DATA_DIR=/data python tools/manage_keys.py create --label "Okul X" --max-projects 100 --max-mb 500
  DATA_DIR=/data python tools/manage_keys.py list
  DATA_DIR=/data python tools/manage_keys.py disable --id key_...
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.project import new_key_id  # noqa: E402
from core.store import ApiKey, create_store  # noqa: E402


def _store():
    data_dir = os.environ.get("DATA_DIR", "./data")
    db_path = os.environ.get("DB_PATH", os.path.join(data_dir, "scorm.db"))
    return create_store(db_path, data_dir)


async def cmd_create(args):
    store = _store()
    await store.init()
    try:
        await _create(store, args)
    finally:
        await store.close()


async def _create(store, args):
    raw = "sk_" + secrets.token_urlsafe(32)
    key = ApiKey(
        id=new_key_id(),
        label=args.label,
        key_hash="",
        max_projects=args.max_projects,
        max_total_mb=args.max_mb,
    )
    await store.upsert_key(key, raw_key=raw)
    print("API anahtarı oluşturuldu (BU DEĞERİ SAKLAYIN — tekrar gösterilmez):")
    print(f"  id         : {key.id}")
    print(f"  label      : {key.label}")
    print(f"  kota       : {key.max_projects} proje / {key.max_total_mb} MB")
    print(f"  API KEY    : {raw}")


async def cmd_list(args):
    store = _store()
    await store.init()
    try:
        db = store.db  # type: ignore[attr-defined]
        async with db.execute(
            "SELECT id,label,max_projects,max_total_mb,disabled,last_used_at FROM api_keys"
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            print("(anahtar yok)")
            return
        for r in rows:
            flag = " [DEVRE DIŞI]" if r["disabled"] else ""
            print(f"{r['id']}  {r['label']}  {r['max_projects']}proje/{r['max_total_mb']}MB"
                  f"  son:{r['last_used_at'] or '-'}{flag}")
    finally:
        await store.close()


async def cmd_disable(args):
    store = _store()
    await store.init()
    try:
        db = store.db  # type: ignore[attr-defined]
        await db.execute("UPDATE api_keys SET disabled=1 WHERE id=?", (args.id,))
        await db.commit()
        print(f"devre dışı bırakıldı: {args.id}")
    finally:
        await store.close()


def main():
    ap = argparse.ArgumentParser(description="scorm-mcp API anahtar yönetimi")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--label", required=True)
    c.add_argument("--max-projects", type=int, default=100)
    c.add_argument("--max-mb", type=int, default=500)
    c.set_defaults(fn=cmd_create)

    ls = sub.add_parser("list")
    ls.set_defaults(fn=cmd_list)

    d = sub.add_parser("disable")
    d.add_argument("--id", required=True)
    d.set_defaults(fn=cmd_disable)

    args = ap.parse_args()
    asyncio.run(args.fn(args))


if __name__ == "__main__":
    main()
