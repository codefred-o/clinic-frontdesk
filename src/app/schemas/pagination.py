"""Opaque cursor-based pagination helpers.

Cursors are base64-encoded JSON objects so the client never inspects the
internals.  The payload currently encodes ``created_at`` (ISO-8601) and ``id``
(UUID string) of the last item in a page, matching the deterministic ordering
used by inventory queries.

Security note: cursors are not signed.  A tampered cursor produces a decode
error (400) or returns an unexpected page — neither outcome is dangerous for a
read-only public endpoint.
"""

from __future__ import annotations

import base64
import json
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.schemas.errors import CursorDecodeError

T = TypeVar("T")

# Maximum items a caller may request per page.
MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20


class PageMeta(BaseModel):
    """Pagination metadata included in every collection response."""

    limit: int = Field(..., description="Items per page (≤100).")
    next_cursor: str | None = Field(
        None,
        description="Opaque cursor for the next page.  Absent when this is the last page.",
    )


class Page(BaseModel, Generic[T]):
    """Generic page wrapper for collection responses."""

    items: list[T]
    pagination: PageMeta


# ---------------------------------------------------------------------------
# Cursor codec
# ---------------------------------------------------------------------------


def encode_cursor(created_at_iso: str, id_str: str) -> str:
    """Return a URL-safe base64 string encoding the page-position marker."""
    payload = json.dumps({"created_at": created_at_iso, "id": id_str}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Decode a cursor and return ``(created_at_iso, id_str)``.

    Raises :class:`CursorDecodeError` on any decode failure so callers receive
    a stable 400 response rather than an unhandled exception.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode() + b"==")
        data = json.loads(raw)
        return str(data["created_at"]), str(data["id"])
    except Exception as exc:
        raise CursorDecodeError() from exc
