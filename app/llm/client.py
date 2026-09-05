"""Pluggable chat-client factory for LLM-backed agents."""
from __future__ import annotations

from functools import lru_cache

from agent_framework import BaseChatClient

from app.llm.mock_client import MockChatClient
from config import get_settings


@lru_cache(maxsize=1)
def get_chat_client() -> BaseChatClient:
    provider = get_settings().llm_provider.lower()

    if provider == "mock":
        return MockChatClient()

    raise NotImplementedError(f"LLM_PROVIDER={provider!r} is not implemented yet.")
