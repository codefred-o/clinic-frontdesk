"""In-memory per-user conversation history.

Keyed by WhatsApp phone number. History is trimmed to the most recent
`max_turns` messages (a turn = one user or one assistant message). This is
intentionally non-persistent — it resets on restart, which is fine for a demo.
"""

from __future__ import annotations

from collections import defaultdict


class ConversationStore:
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        self._history: dict[str, list[dict[str, str]]] = defaultdict(list)

    def get(self, phone: str) -> list[dict[str, str]]:
        return list(self._history[phone])

    def add_user(self, phone: str, text: str) -> None:
        self._append(phone, "user", text)

    def add_assistant(self, phone: str, text: str) -> None:
        self._append(phone, "assistant", text)

    def _append(self, phone: str, role: str, content: str) -> None:
        history = self._history[phone]
        history.append({"role": role, "content": content})
        if len(history) > self._max_turns:
            del history[: len(history) - self._max_turns]
