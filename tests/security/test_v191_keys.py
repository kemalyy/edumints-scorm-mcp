"""API anahtarı geçerliliği iki doğrulayıcıda (MCP/OAuth dual-auth ve özel HTTP) aynı."""
from datetime import datetime, timedelta, timezone

import pytest

from auth.errors import ToolError
from auth.keys import key_rejection, verify_key
from auth.oauth import ApiKeyVerifier
from core.store import ApiKey

NOW = datetime.now(timezone.utc)


def _key(**kw):
    return ApiKey(id="k1", label="t", key_hash="h", owner_principal="logto:u1", **kw)


class _Store:
    def __init__(self, key):
        self.key = key

    async def get_key(self, raw):
        return self.key

    async def touch_key(self, key_id):
        return None


async def _noop():
    return None


@pytest.mark.parametrize("key, reason", [
    (None, "Geçersiz"),
    (_key(disabled=True), "devre dışı"),
    (_key(expires_at=NOW - timedelta(minutes=1)), "süresi dolmuş"),
    (_key(expires_at=(NOW - timedelta(minutes=1)).replace(tzinfo=None)), "süresi dolmuş"),  # naive = UTC
])
def test_key_rejection_reasons(key, reason):
    assert reason in key_rejection(key)


def test_valid_key_has_no_rejection():
    assert key_rejection(_key()) is None
    assert key_rejection(_key(expires_at=NOW + timedelta(days=1))) is None


@pytest.mark.parametrize("key", [_key(disabled=True), _key(expires_at=NOW - timedelta(seconds=5))])
async def test_mcp_and_http_paths_reject_alike(key):
    verifier = ApiKeyVerifier(ensure=_noop, get_key=_Store(key).get_key)
    assert await verifier.verify_token("sk_test") is None
    with pytest.raises(ToolError):
        await verify_key(_Store(key), "sk_test")


async def test_mcp_token_carries_key_expiry():
    exp = NOW + timedelta(hours=2)
    verifier = ApiKeyVerifier(ensure=_noop, get_key=_Store(_key(expires_at=exp)).get_key)
    tok = await verifier.verify_token("sk_test")
    assert tok is not None and tok.expires_at == int(exp.timestamp())
    tok2 = await ApiKeyVerifier(ensure=_noop, get_key=_Store(_key()).get_key).verify_token("sk_test")
    assert tok2 is not None and tok2.expires_at is None
