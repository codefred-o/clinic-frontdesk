"""Tests for the WhatsApp webhook: verify handshake + inbound message flow."""

from __future__ import annotations

from typing import Any

import pytest

VERIFY_TOKEN = "test-verify-token"


def _inbound_payload(from_number: str, text: str) -> dict:
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
    assert fake_whatsapp.sent == [("2348012345678", fake_llm.reply_text)]


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
    assert fake_whatsapp.sent == [("2348012345678", fake_llm.reply_text)]


def test_downstream_whatsapp_failure_returns_200(
    client,
    fake_llm: Any,
    fake_whatsapp: Any,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fail_send_text(to: str, text: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(fake_whatsapp, "send_text", fail_send_text)

    resp = client.post("/webhook", json=_inbound_payload("2348012345678", "Hello"))

    assert resp.status_code == 200
    assert fake_llm.calls[0][-1] == {"role": "user", "content": "Hello"}
    assert fake_whatsapp.sent == []
