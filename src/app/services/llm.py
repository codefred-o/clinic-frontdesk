"""Async LLM client: turns a system prompt plus conversation history into a reply."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
        )

    async def reply(self, history: list[dict[str, str]], system_prompt: str) -> str:
        """Generate the assistant reply for the given clinic prompt and history."""
        messages = [{"role": "system", "content": system_prompt}, *history]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.4,
        )
        content = response.choices[0].message.content
        return (content or "").strip()
