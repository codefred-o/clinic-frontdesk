"""Async outbound WhatsApp sender using the Meta Graph API."""

from __future__ import annotations

import httpx

from app.config import Settings


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._url = settings.whatsapp_messages_url
        self._token = settings.whatsapp_token
        self._http = http

    async def send_text(self, to: str, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        headers = {"Authorization": f"Bearer {self._token}"}
        response = await self._http.post(self._url, json=payload, headers=headers)
        response.raise_for_status()
