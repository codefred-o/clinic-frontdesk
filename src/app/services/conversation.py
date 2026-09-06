"""In-memory per-conversation history.

Keyed by (clinic_id, patient phone) so the same patient talking to two clinics
gets two independent threads. History is trimmed to the most recent
`max_turns` messages (a turn = one user or one assistant message). This is
intentionally non-persistent — it resets on restart. Single-process only.
"""

from __future__ import annotations

from collections import defaultdict

ConversationKey = tuple[str, str]


class ConversationStore:
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        self._history: dict[ConversationKey, list[dict[str, str]]] = defaultdict(list)

    def get(self, clinic_id: str, phone: str) -> list[dict[str, str]]:
        return list(self._history[(clinic_id, phone)])

    def add_user(self, clinic_id: str, phone: str, text: str) -> None:
        self._append((clinic_id, phone), "user", text)

    def add_assistant(self, clinic_id: str, phone: str, text: str) -> None:
        self._append((clinic_id, phone), "assistant", text)

    def _append(self, key: ConversationKey, role: str, content: str) -> None:
        history = self._history[key]
        history.append({"role": role, "content": content})
        if len(history) > self._max_turns:
            del history[: len(history) - self._max_turns]
