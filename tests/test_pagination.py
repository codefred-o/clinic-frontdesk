"""Unit tests for the opaque cursor codec."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.errors import CursorDecodeError
from app.schemas.pagination import decode_cursor, encode_cursor


def test_encode_then_decode_round_trips() -> None:
    created_at = "2026-10-01T12:00:00+00:00"
    id_str = str(uuid.uuid4())
    cursor = encode_cursor(created_at, id_str)
    decoded_at, decoded_id = decode_cursor(cursor)
    assert decoded_at == created_at
    assert decoded_id == id_str


def test_encode_produces_url_safe_string() -> None:
    cursor = encode_cursor("2026-10-01T12:00:00+00:00", str(uuid.uuid4()))
    assert "/" not in cursor
    assert "+" not in cursor


def test_decode_rejects_arbitrary_string() -> None:
    with pytest.raises(CursorDecodeError):
        decode_cursor("not-a-cursor")


def test_decode_rejects_empty_string() -> None:
    with pytest.raises(CursorDecodeError):
        decode_cursor("")


def test_decode_rejects_missing_fields() -> None:
    """A base64 JSON without the required keys must raise CursorDecodeError."""
    import base64
    import json

    payload = base64.urlsafe_b64encode(json.dumps({"foo": "bar"}).encode()).decode()
    with pytest.raises(CursorDecodeError):
        decode_cursor(payload)


def test_different_timestamps_produce_different_cursors() -> None:
    id_str = str(uuid.uuid4())
    c1 = encode_cursor("2026-10-01T12:00:00+00:00", id_str)
    c2 = encode_cursor("2026-10-02T12:00:00+00:00", id_str)
    assert c1 != c2
