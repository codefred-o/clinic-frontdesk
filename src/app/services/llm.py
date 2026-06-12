"""Async LLM client: turns conversation history into an assistant reply."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config import Settings
from app.prompts import SYSTEM_PROMPT


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
        )

    async def reply(self, history: list[dict[str, str]]) -> str:
        """Generate the assistant reply for the given conversation history."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.4,
        )
        content = response.choices[0].message.content
        return (content or "").strip()
