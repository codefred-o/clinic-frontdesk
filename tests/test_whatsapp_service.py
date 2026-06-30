"""Tests for outbound WhatsApp message delivery."""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.services.whatsapp import WhatsAppClient


class FakeResponse:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True
        if self._exc is not None:
            raise self._exc


class FakeAsyncClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, *, json: dict[str, object], headers: dict[str, str]) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.response


def _settings() -> Settings:
    return Settings(
        whatsapp_token="token-123",
        whatsapp_phone_number_id="phone-id",
        whatsapp_api_version="v20.0",
        whatsapp_verify_token="verify-token",
        llm_api_key="test-key",
    )


@pytest.mark.asyncio
async def test_send_text_posts_expected_graph_api_payload() -> None:
    response = FakeResponse()
    http = FakeAsyncClient(response)
    client = WhatsAppClient(_settings(), http)  # type: ignore[arg-type]

    await client.send_text("2348012345678", "Hello")

    assert http.calls == [
        {
            "url": "https://graph.facebook.com/v20.0/phone-id/messages",
            "json": {
                "messaging_product": "whatsapp",
                "to": "2348012345678",
                "type": "text",
                "text": {"body": "Hello"},
            },
            "headers": {"Authorization": "Bearer token-123"},
        }
    ]
    assert response.raise_for_status_called is True


@pytest.mark.asyncio
async def test_send_text_surfaces_graph_api_failure() -> None:
    request = httpx.Request("POST", "https://graph.facebook.com/v20.0/phone-id/messages")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)
    http = FakeAsyncClient(FakeResponse(error))
    client = WhatsAppClient(_settings(), http)  # type: ignore[arg-type]

    with pytest.raises(httpx.HTTPStatusError):
        await client.send_text("2348012345678", "Hello")
