"""Async outbound WhatsApp sender using the Meta Graph API.

Every send goes out through the clinic's own phone_number_id, with the clinic's
token if it has one and the shared app token otherwise.
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.models.clinic import ClinicConfig


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def send_text(self, clinic: ClinicConfig, to: str, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        token = clinic.whatsapp_token or self._settings.whatsapp_token
        headers = {"Authorization": f"Bearer {token}"}
        url = self._settings.messages_url_for(clinic.phone_number_id)
        response = await self._http.post(url, json=payload, headers=headers)
        response.raise_for_status()
