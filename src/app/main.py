"""FastAPI entrypoint: wires settings and services, registers the webhook routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI

from app.config import get_settings
from app.routes.webhook import router as webhook_router
from app.services.conversation import ConversationStore
from app.services.llm import LLMClient
from app.services.whatsapp import WhatsAppClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http = httpx.AsyncClient(timeout=30.0)

    app.state.settings = settings
    app.state.conversations = ConversationStore(max_turns=settings.max_history_turns)
    app.state.llm = LLMClient(settings)
    app.state.whatsapp = WhatsAppClient(settings, http)

    try:
        yield
    finally:
        await http.aclose()


app = FastAPI(title="Sunrise Dental WhatsApp Front Desk", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
