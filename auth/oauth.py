"""auth/oauth.py — IdP-agnostik OAuth resource-server + dual-auth (INTEGRATION.md).

İLKE (re-engineering sigortası): doğrulama YALNIZ standart OIDC alanlarına dayanır —
JWKS + issuer + audience. Logto'ya özgü hiçbir şey gömülü değildir. IdP bir gün değişse
(örn. Keycloak), değişen tek yer env değişkenleridir (LOGTO_ISSUER / LOGTO_JWKS / MCP_AUDIENCE);
bu modülün kodu aynı kalır.

Dual-auth (CONTRACTS.md §2 spec): bir istek YA geçerli OAuth access token (JWT, Logto)
YA DA geçerli API-key (Bearer sk_...) ile geçer. FastMCP MultiAuth ile birleştirilir:
  - server  = RemoteAuthProvider(JWTVerifier)  → OIDC doğrulama + /.well-known/oauth-protected-resource
              + 401 WWW-Authenticate (Claude'un OAuth akışını tetikler)
  - verifiers = [ApiKeyVerifier]                → API-key yolu (terminal/Claude Code) korunur
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timezone

from fastmcp.server.auth import AccessToken, MultiAuth, RemoteAuthProvider, TokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier


class ApiKeyVerifier(TokenVerifier):
    """`sk_` API anahtarlarını store üzerinden doğrular (dual-auth'un API-key bacağı).

    JWT'leri (OAuth) reddeder (None) → onları JWTVerifier ele alır.
    """

    def __init__(
        self,
        ensure: Callable[[], Awaitable[None]],
        get_key: Callable[[str], Awaitable[object]],
        is_revoked: Callable[[str], Awaitable[bool]] | None = None,
    ):
        super().__init__()
        self._ensure = ensure
        self._get_key = get_key
        self._is_revoked = is_revoked

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not token.startswith("sk_"):
            return None  # JWT → JWTVerifier'a bırak
        await self._ensure()
        key = await self._get_key(token)
        from auth.keys import key_rejection  # v1.9.1: verify_key ile aynı kural (süre dahil)
        if key_rejection(key) is not None:
            return None
        owner_principal = getattr(key, "owner_principal", None)
        if owner_principal and self._is_revoked and await self._is_revoked(owner_principal):
            return None  # v1.9.1: iptal edilen principal'ın (yarışla eklenmiş) anahtarı da reddedilir
        exp = getattr(key, "expires_at", None)
        # principal = owner_principal (portaldan üretilmiş, "logto:<sub>") VEYA eski key'lerde key.id.
        principal = getattr(key, "owner_principal", None) or key.id
        return AccessToken(
            token=token,
            client_id=key.id,
            subject=principal,
            scopes=["mcp"],
            expires_at=int(exp.timestamp() if exp.tzinfo else exp.replace(tzinfo=timezone.utc).timestamp())
            if exp else None,
            claims={
                "auth": "apikey",
                "key_id": key.id,
                "owner_principal": getattr(key, "owner_principal", None),
                "max_projects": key.max_projects,
                "max_total_mb": key.max_total_mb,
            },
        )


def make_jwt_verifier(
    *, issuer: str, jwks_uri: str, audience: str, algorithm: str = "ES384"
) -> JWTVerifier:
    """Standalone JWT doğrulayıcı (MCP dışı custom route'larda — örn. /usage — token doğrulamak için)."""
    return JWTVerifier(jwks_uri=jwks_uri, issuer=issuer, audience=audience, algorithm=algorithm)


def build_auth_provider(
    *,
    issuer: str,
    jwks_uri: str,
    audience: str,
    base_url: str,
    api_key_verifier: TokenVerifier,
    algorithm: str = "ES384",
) -> MultiAuth:
    """OAuth (JWT, audience-bound) + API-key dual-auth sağlayıcısı.

    audience:  token'daki `aud` ile BİREBİR eşleşmeli (trailing slash / http(s) / /mcp dahil).
    issuer:    Logto openid-configuration'daki `issuer` ile BİREBİR aynı olmalı.
    algorithm: token imza algoritması — JWTVerifier varsayılanı RS256'dır; uyuşmazsa SESSİZCE
               401 döner. Logto ES384 (EC) imzalar → varsayılan ES384. IdP-agnostik: env'den.
    """
    jwt = JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=audience,
        base_url=base_url,
        algorithm=algorithm,
    )
    remote = RemoteAuthProvider(
        token_verifier=jwt,
        authorization_servers=[issuer],
        base_url=base_url,
        resource_name="scorm-mcp",
        scopes_supported=["mcp"],
    )
    return MultiAuth(server=remote, verifiers=[api_key_verifier])
