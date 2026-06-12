"""Shared fixtures: a TestClient with fake LLM and WhatsApp services on app.state."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Deterministic settings before the app/settings cache is built.
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("LLM_API_KEY", "test-key")

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

VERIFY_TOKEN = "test-verify-token"


class FakeLLM:
    """Records the history it was given and returns a canned reply."""

    def __init__(self, reply: str = "Good morning! How can I help? 🙂") -> None:
        self.reply_text = reply
        self.calls: list[list[dict[str, str]]] = []

    async def reply(self, history: list[dict[str, str]]) -> str:
        self.calls.append(history)
        return self.reply_text


class FakeWhatsApp:
    """Records outbound sends instead of hitting the Graph API."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, to: str, text: str) -> None:
        self.sent.append((to, text))


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_whatsapp() -> FakeWhatsApp:
    return FakeWhatsApp()


@pytest.fixture
def client(fake_llm: FakeLLM, fake_whatsapp: FakeWhatsApp):
    with TestClient(app) as test_client:
        # Override the real services wired by the lifespan with fakes.
        app.state.llm = fake_llm
        app.state.whatsapp = fake_whatsapp
        yield test_client