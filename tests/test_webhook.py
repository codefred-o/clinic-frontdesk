"""Tests for the WhatsApp webhook: verify handshake + inbound message flow."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import GREENFIELD_PHONE_NUMBER_ID, SUNRISE_PHONE_NUMBER_ID

VERIFY_TOKEN = "test-verify-token"


def _inbound_payload(
    from_number: str,
    text: str,
    phone_number_id: str = SUNRISE_PHONE_NUMBER_ID,
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "2349000000000",
                                "phone_number_id": phone_number_id,
                            },
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": "wamid.123",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_verify_handshake_success(client):
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "challenge-42",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge-42"


def test_verify_handshake_wrong_token(client):
    resp = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "challenge-42",
        },
    )
    assert resp.status_code == 403


def test_inbound_text_triggers_reply(client, fake_llm: Any, fake_whatsapp: Any):
    resp = client.post("/webhook", json=_inbound_payload("2348012345678", "Hello"))
    assert resp.status_code == 200

    # LLM was asked once, with the user's message in history.
    assert len(fake_llm.calls) == 1
    history = fake_llm.calls[0]
    assert history[-1] == {"role": "user", "content": "Hello"}

    # The reply was sent back to the same number.
    assert fake_whatsapp.sent == [("sunrise-dental", "2348012345678", fake_llm.reply_text)]


def test_non_text_event_is_ignored(client, fake_llm: Any, fake_whatsapp: Any):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {"from": "2348012345678", "id": "wamid.9", "type": "image"}
                            ],
                        }
                    }
                ]
            }
        ],
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    assert fake_llm.calls == []
    assert fake_whatsapp.sent == []


def test_conversation_history_persists_across_messages(client, fake_llm: Any):
    client.post("/webhook", json=_inbound_payload("2348000000000", "First"))
    client.post("/webhook", json=_inbound_payload("2348000000000", "Second"))

    # On the second call the stored history includes the prior user+assistant turns.
    second_history = fake_llm.calls[1]
    roles = [m["role"] for m in second_history]
    assert roles == ["user", "assistant", "user"]
    assert second_history[-1]["content"] == "Second"


def test_malformed_payload_is_ignored(client, fake_llm: Any, fake_whatsapp: Any):
    resp = client.post("/webhook", json={"entry": [{"changes": [{}]}]})

    assert resp.status_code == 200
    assert fake_llm.calls == []
    assert fake_whatsapp.sent == []


def test_webhook_processes_first_text_across_entries(
    client,
    fake_llm: Any,
    fake_whatsapp: Any,
):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "2348000000000", "id": "wamid.image", "type": "image"}
                            ]
                        }
                    }
                ]
            },
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": SUNRISE_PHONE_NUMBER_ID},
                            "messages": [
                                {
                                    "from": "2348012345678",
                                    "id": "wamid.text",
                                    "type": "text",
                                    "text": {"body": "Book cleaning"},
                                }
                            ]
                        }
                    }
                ]
            },
        ],
    }

    resp = client.post("/webhook", json=payload)

    assert resp.status_code == 200
    assert fake_llm.calls[0][-1] == {"role": "user", "content": "Book cleaning"}
    assert fake_whatsapp.sent == [("sunrise-dental", "2348012345678", fake_llm.reply_text)]


def test_downstream_whatsapp_failure_returns_200(
    client,
    fake_llm: Any,
    fake_whatsapp: Any,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fail_send_text(clinic: Any, to: str, text: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(fake_whatsapp, "send_text", fail_send_text)

    resp = client.post("/webhook", json=_inbound_payload("2348012345678", "Hello"))

    assert resp.status_code == 200
    assert fake_llm.calls[0][-1] == {"role": "user", "content": "Hello"}
    assert fake_whatsapp.sent == []


def test_lifespan_loads_clinics_from_clinics_dir():
    with TestClient(app):
        registry = app.state.clinics

    assert registry.by_id("sunrise-dental") is not None
    assert registry.by_phone_number_id(SUNRISE_PHONE_NUMBER_ID) is not None


def test_unknown_phone_number_id_is_logged_and_ignored(
    client, fake_llm: Any, fake_whatsapp: Any, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level("WARNING", logger="app.routes.webhook"):
        resp = client.post(
            "/webhook",
            json=_inbound_payload("2348012345678", "Hello", phone_number_id="999"),
        )

    assert resp.status_code == 200
    assert fake_llm.calls == []
    assert fake_whatsapp.sent == []
    assert "No clinic registered for phone_number_id='999'" in caplog.text


def test_text_without_metadata_is_ignored(client, fake_llm: Any, fake_whatsapp: Any):
    payload = _inbound_payload("2348012345678", "Hello")
    del payload["entry"][0]["changes"][0]["value"]["metadata"]

    resp = client.post("/webhook", json=payload)

    assert resp.status_code == 200
    assert fake_llm.calls == []
    assert fake_whatsapp.sent == []


def test_message_to_second_clinic_number_is_processed(client, fake_llm: Any, fake_whatsapp: Any):
    resp = client.post(
        "/webhook",
        json=_inbound_payload("2348012345678", "Hello", phone_number_id=GREENFIELD_PHONE_NUMBER_ID),
    )

    assert resp.status_code == 200
    assert len(fake_llm.calls) == 1
    assert fake_whatsapp.sent == [("greenfield-medical", "2348012345678", fake_llm.reply_text)]


def test_conversations_are_isolated_per_clinic(client, fake_llm: Any):
    client.post("/webhook", json=_inbound_payload("2348000000000", "Hello Sunrise"))
    client.post(
        "/webhook",
        json=_inbound_payload(
            "2348000000000", "Hello Greenfield", phone_number_id=GREENFIELD_PHONE_NUMBER_ID
        ),
    )

    # Same patient phone, different clinic: the second history starts fresh.
    assert [m["content"] for m in fake_llm.calls[1]] == ["Hello Greenfield"]


def test_reply_uses_the_receiving_clinics_prompt(client, fake_llm: Any):
    client.post("/webhook", json=_inbound_payload("2348012345678", "How much is a root canal?"))
    client.post(
        "/webhook",
        json=_inbound_payload(
            "2348012345678", "Do you do malaria tests?", phone_number_id=GREENFIELD_PHONE_NUMBER_ID
        ),
    )

    sunrise_prompt, greenfield_prompt = fake_llm.system_prompts
    assert "Root Canal Treatment — 90,000–120,000" in sunrise_prompt
    assert "Malaria Test" not in sunrise_prompt
    assert "Malaria Test — 5,000" in greenfield_prompt
    assert "Root Canal" not in greenfield_prompt
