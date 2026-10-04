from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..agent import Agent


@runtime_checkable
class VoiceLLM(Protocol):
    def stream(self, text: str, *, turn_id: str) -> AsyncIterator[str]: ...


class AgentVoiceLLM:
    """Voice adapter over the same Agent/session used by text chat.

    This is the key invariant: voice does not get a separate memory or brain.
    """

    def __init__(self, agent: Agent, session_id: str):
        self.agent = agent
        self.session_id = session_id

    async def stream(self, text: str, *, turn_id: str) -> AsyncIterator[str]:
        async for event in self.agent.stream_turn(self.session_id, text):
            event_type = event.get("type")
            if event_type == "delta" and event.get("text"):
                yield str(event["text"])
            elif event_type == "error":
                raise RuntimeError(str(event.get("error") or "voice llm turn failed"))
