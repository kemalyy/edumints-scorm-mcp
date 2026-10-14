"""auth/errors.py — Tool hata kodları (CONTRACTS.md §7)."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "not_found",
    "unauthorized",
    "quota_exceeded",
    "validation_error",
    "asset_error",
    "build_error",
    "rate_limited",
    "unknown_topic",
    "unknown_screen_type",
]


class ToolError(Exception):
    """Kod taşıyan tool hatası. Server katmanı FastMCP ToolError'a sarar."""

    def __init__(self, code: ErrorCode, message: str, extra: dict | None = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.extra = extra or {}
