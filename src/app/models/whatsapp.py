"""Pydantic schemas for the WhatsApp Cloud API inbound webhook payload.

Only the fields we use are modeled; unknown fields are ignored so Meta can add
to the payload without breaking parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TextBody(_Lenient):
    body: str


class Message(_Lenient):
    from_: str
    id: str
    type: str
    text: TextBody | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    def __init__(self, **data: object) -> None:
        # Meta sends the sender under the reserved key "from".
        if "from" in data and "from_" not in data:
            data["from_"] = data.pop("from")
        super().__init__(**data)


class Metadata(_Lenient):
    """The business phone number the message was sent to."""

    display_phone_number: str | None = None
    phone_number_id: str | None = None


class Value(_Lenient):
    messaging_product: str | None = None
    metadata: Metadata | None = None
    messages: list[Message] = []


class Change(_Lenient):
    value: Value
    field: str | None = None


class Entry(_Lenient):
    id: str | None = None
    changes: list[Change] = []


class WebhookPayload(_Lenient):
    object: str | None = None
    entry: list[Entry] = []

    def first_text_message(self) -> IncomingMessage | None:
        """Return the first inbound text message, normalized, if present."""
        for entry in self.entry:
            for change in entry.changes:
                metadata = change.value.metadata
                phone_number_id = metadata.phone_number_id if metadata else None
                for message in change.value.messages:
                    if message.type == "text" and message.text is not None:
                        return IncomingMessage(
                            from_number=message.from_,
                            message_id=message.id,
                            text=message.text.body,
                            phone_number_id=phone_number_id,
                        )
        return None


class IncomingMessage(BaseModel):
    """Normalized inbound text message."""

    from_number: str
    message_id: str
    text: str
    phone_number_id: str | None = None
