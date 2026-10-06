"""Anthropic API wrapper (official SDK).

Kept deliberately small: one call that sends the running message history plus the
tool definitions and returns the assistant's content blocks. The agent loop owns
the history and the tool-execution/approval logic.
"""

from __future__ import annotations

from .config import Settings

try:
    import anthropic
except Exception:  # pragma: no cover - import guard
    anthropic = None


class LLM:
    def __init__(self, settings: Settings):
        if anthropic is None:
            raise RuntimeError(
                "The anthropic SDK is not installed. Run: pip install anthropic"
            )
        self.settings = settings
        self.client = anthropic.Anthropic(api_key=settings.api_key())

    def step(self, system: str, messages: list[dict], tools: list[dict]):
        """One turn. Returns the SDK Message (with .content, .stop_reason)."""
        return self.client.messages.create(
            model=self.settings.model,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=tools,
            thinking={"type": "adaptive"},
        )
