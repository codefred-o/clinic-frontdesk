"""Tests for in-memory conversation history behavior."""

from __future__ import annotations

from app.services.conversation import ConversationStore


def test_conversation_store_keeps_histories_isolated_per_phone() -> None:
    store = ConversationStore(max_turns=10)

    store.add_user("2348011111111", "Hello")
    store.add_user("2348022222222", "Hi")
    store.add_assistant("2348011111111", "Good morning")

    assert store.get("2348011111111") == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Good morning"},
    ]
    assert store.get("2348022222222") == [{"role": "user", "content": "Hi"}]


def test_conversation_store_returns_copy_of_history() -> None:
    store = ConversationStore(max_turns=10)
    store.add_user("2348012345678", "Hello")

    history = store.get("2348012345678")
    history.append({"role": "assistant", "content": "Mutated outside"})

    assert store.get("2348012345678") == [{"role": "user", "content": "Hello"}]


def test_conversation_store_trims_to_max_turns() -> None:
    store = ConversationStore(max_turns=2)

    store.add_user("2348012345678", "First")
    store.add_assistant("2348012345678", "Reply")
    store.add_user("2348012345678", "Second")

    assert store.get("2348012345678") == [
        {"role": "assistant", "content": "Reply"},
        {"role": "user", "content": "Second"},
    ]
