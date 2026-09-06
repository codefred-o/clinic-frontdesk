"""Tests for LLM service request wiring."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.services import llm as llm_module
from app.services.llm import LLMClient


class FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = FakeMessage(content)


class FakeCompletionResponse:
    def __init__(self, content: str | None) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, parent: FakeAsyncOpenAI) -> None:
        self._parent = parent

    async def create(self, **kwargs: Any) -> FakeCompletionResponse:
        self._parent.calls.append(kwargs)
        return FakeCompletionResponse(self._parent.reply_content)


class FakeChat:
    def __init__(self, parent: FakeAsyncOpenAI) -> None:
        self.completions = FakeCompletions(parent)


class FakeAsyncOpenAI:
    instances: list[FakeAsyncOpenAI] = []
    reply_content: str | None = "  Reply text  "

    def __init__(self, *, api_key: str, base_url: str | None) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.calls: list[dict[str, Any]] = []
        self.chat = FakeChat(self)
        self.instances.append(self)


def _settings() -> Settings:
    return Settings(llm_api_key="test-key", llm_model="demo-model", llm_base_url=None)


@pytest.fixture(autouse=True)
def _reset_fake_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncOpenAI.instances = []
    FakeAsyncOpenAI.reply_content = "  Reply text  "
    monkeypatch.setattr(llm_module, "AsyncOpenAI", FakeAsyncOpenAI)


@pytest.mark.asyncio
async def test_reply_sends_given_system_prompt_plus_conversation_history() -> None:
    client = LLMClient(_settings())
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Good morning"},
    ]

    await client.reply(history, "You are the front desk for Clinic X.")

    fake_openai = FakeAsyncOpenAI.instances[0]
    assert fake_openai.api_key == "test-key"
    assert fake_openai.base_url is None
    assert fake_openai.calls == [
        {
            "model": "demo-model",
            "messages": [
                {"role": "system", "content": "You are the front desk for Clinic X."},
                *history,
            ],
            "temperature": 0.4,
        }
    ]


@pytest.mark.asyncio
async def test_reply_strips_provider_content() -> None:
    client = LLMClient(_settings())

    reply = await client.reply([{"role": "user", "content": "Hello"}], "system")

    assert reply == "Reply text"


@pytest.mark.asyncio
async def test_reply_returns_empty_string_when_provider_content_is_none() -> None:
    FakeAsyncOpenAI.reply_content = None
    client = LLMClient(_settings())

    reply = await client.reply([{"role": "user", "content": "Hello"}], "system")

    assert reply == ""
