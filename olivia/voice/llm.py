from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..agent import Agent


@runtime_checkable
class VoiceLLM(Protocol):
    def stream(
        self,
        text: str,
        *,
        turn_id: str,
        locale: str,
    ) -> AsyncIterator[str]: ...


class AgentVoiceLLM:
    """Use the normal Agent/session so voice shares identity, memory and router."""

    def __init__(self, agent: Agent, session_id: str):
        self.agent = agent
        self.session_id = session_id

    async def stream(
        self,
        text: str,
        *,
        turn_id: str,
        locale: str,
    ) -> AsyncIterator[str]:
        async for event in self.agent.stream_turn(self.session_id, text):
            if event.get("type") == "delta" and event.get("text"):
                yield str(event["text"])
            elif event.get("type") == "error":
                raise RuntimeError(str(event.get("error") or "voice llm turn failed"))
