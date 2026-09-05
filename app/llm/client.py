"""Pluggable chat-client factory for LLM-backed agents.

Every agent talks to the model only through `agent_framework.BaseChatClient`
obtained here. This module is the single seam for swapping providers: set
LLM_PROVIDER in the environment (see config.py / .env.example) and add a
branch below. Only "mock" is implemented today — see mock_client.py.
"""
from __future__ import annotations

from functools import lru_cache

from agent_framework import BaseChatClient

from app.llm.mock_client import MockChatClient
from config import get_settings


@lru_cache(maxsize=1)
def get_chat_client() -> BaseChatClient:
    """Return the configured chat client, cached for the process lifetime."""
    provider = get_settings().llm_provider.lower()

    if provider == "mock":
        return MockChatClient()

    raise NotImplementedError(
        f"LLM_PROVIDER={provider!r} is not implemented yet. Only 'mock' "
        "ships today. To add a real provider: install its agent-framework "
        "extra (e.g. agent-framework-azure-ai or agent-framework-openai) "
        "and return its chat client instance from a new branch here."
    )
