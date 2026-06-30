"""Tests for inbound WhatsApp webhook payload parsing."""

from __future__ import annotations

from app.models.whatsapp import WebhookPayload


def test_first_text_message_normalizes_sender_and_text() -> None:
    payload = WebhookPayload.model_validate(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [
                                    {
                                        "from": "2348012345678",
                                        "id": "wamid.123",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }
    )

    message = payload.first_text_message()

    assert message is not None
    assert message.from_number == "2348012345678"
    assert message.message_id == "wamid.123"
    assert message.text == "Hello"


def test_first_text_message_skips_non_text_before_text() -> None:
    payload = WebhookPayload.model_validate(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"from": "2348000000000", "id": "wamid.image", "type": "image"},
                                    {
                                        "from": "2348012345678",
                                        "id": "wamid.text",
                                        "type": "text",
                                        "text": {"body": "Book cleaning"},
                                    },
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    )

    message = payload.first_text_message()

    assert message is not None
    assert message.from_number == "2348012345678"
    assert message.text == "Book cleaning"


def test_first_text_message_returns_none_for_non_text_payload() -> None:
    payload = WebhookPayload.model_validate(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"from": "2348012345678", "id": "wamid.9", "type": "image"}
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    )

    assert payload.first_text_message() is None


def test_first_text_message_returns_none_when_messages_missing() -> None:
    payload = WebhookPayload.model_validate({"entry": [{"changes": [{"value": {}}]}]})

    assert payload.first_text_message() is None
