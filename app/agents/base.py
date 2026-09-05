"""Shared helpers for building and running LLM-backed agents.

Every agent in this package follows the same shape: wrap the configured
chat client in an `agent_framework.Agent` with fixed instructions, run it
on a prompt built from the contract text (plus whatever upstream stage
output it needs), and parse the JSON text it returns. Putting that shape
here once means each agent module only defines its own instructions,
prompt, and result schema.
"""
from __future__ import annotations

import json

from agent_framework import Agent

from app.llm.client import get_chat_client
from config import get_settings


class AgentOutputError(RuntimeError):
    """Raised when an agent's response can't be parsed as the expected JSON.

    Governance treats this the same as "missing evidence" (plan section
    40) rather than letting a malformed response silently pass through.
    """


def build_agent(instructions: str) -> Agent:
    """Construct an Agent bound to the configured chat client."""
    return Agent(get_chat_client(), instructions=instructions)


def model_identity() -> tuple[str, str]:
    """(model_name, model_version) recorded on every governance event —
    RULE-008: "every model execution must have a version"."""
    return f"legalguard-{get_settings().llm_provider}", "1.0"


async def run_contract_agent(instructions: str, contract_text: str) -> dict:
    """Shared shape for the four agents whose only input is the raw
    contract text (intake, clause, risk, deadline) — compliance_agent
    builds a different prompt (found vs. required clause types), so it
    calls build_agent/run_agent_json directly instead."""
    agent = build_agent(instructions)
    prompt = f"Contract text:\n{contract_text}"
    return await run_agent_json(agent, prompt)


async def run_agent_json(agent: Agent, prompt: str) -> dict:
    """Run `agent` on `prompt` and parse its response as a JSON object."""
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
