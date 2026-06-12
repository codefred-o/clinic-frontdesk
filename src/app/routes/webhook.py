"""WhatsApp webhook: GET verify handshake + POST inbound message handling."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.models.whatsapp import WebhookPayload

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

    Always returns 200 so Meta does not retry; non-text events are ignored.
    """
    payload = WebhookPayload.model_validate(await request.json())
    message = payload.first_text_message()
    if message is None:
        return Response(status_code=200)

    state = request.app.state
    phone = message.from_number

    state.conversations.add_user(phone, message.text)
    reply = await state.llm.reply(state.conversations.get(phone))
    state.conversations.add_assistant(phone, reply)
    await state.whatsapp.send_text(phone, reply)

    return Response(status_code=200)
