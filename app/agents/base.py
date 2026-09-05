"""Shared helpers for building and running LLM-backed agents."""
from __future__ import annotations

import json

from agent_framework import Agent

from app.llm.client import get_chat_client
from config import get_settings


class AgentOutputError(RuntimeError):
    pass


def build_agent(instructions: str) -> Agent:
    return Agent(get_chat_client(), instructions=instructions)


def model_identity() -> tuple[str, str]:
    return f"legalguard-{get_settings().llm_provider}", "1.0"


async def run_contract_agent(instructions: str, contract_text: str) -> dict:
    agent = build_agent(instructions)
    prompt = f"Contract text:\n{contract_text}"
    return await run_agent_json(agent, prompt)


async def run_agent_json(agent: Agent, prompt: str) -> dict:
    response = await agent.run(prompt)
    text = response.text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"Agent response was not valid JSON: {text[:200]!r}") from exc

    if not isinstance(parsed, dict):
        raise AgentOutputError(f"Agent response JSON was not an object: {type(parsed).__name__}")

    return parsed
