"""WhatsApp webhook: GET verify handshake + POST inbound message handling."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from app.models.whatsapp import WebhookPayload

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    """Meta verification handshake: echo the challenge if the token matches."""
    settings = request.app.state.settings
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge or "")
    return Response(status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request) -> Response:
    """Handle an inbound message: store it, ask the LLM, send the reply.

    Always returns 200 so Meta does not retry; non-text events and unknown numbers are ignored.
    """
    try:
        payload = WebhookPayload.model_validate(await request.json())
    except ValidationError:
        logger.info("Ignoring malformed WhatsApp webhook payload", exc_info=True)
        return Response(status_code=200)

    message = payload.first_text_message()
    if message is None:
        return Response(status_code=200)

    state = request.app.state
    clinic = state.clinics.by_phone_number_id(message.phone_number_id)
    if clinic is None:
        logger.warning(
            "No clinic registered for phone_number_id=%r; ignoring message",
            message.phone_number_id,
        )
        return Response(status_code=200)

    phone = message.from_number

    try:
        state.conversations.add_user(phone, message.text)
        reply = await state.llm.reply(state.conversations.get(phone))
        state.conversations.add_assistant(phone, reply)
        await state.whatsapp.send_text(phone, reply)
    except Exception:
        logger.exception("Failed to process WhatsApp webhook message for clinic %s", clinic.id)

    return Response(status_code=200)
