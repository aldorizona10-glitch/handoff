"""Anthropic API wrapper (official SDK).

Kept deliberately small: ``step`` sends the running message history plus the tool
definitions and returns the assistant's content blocks; ``extract`` is a one-shot
helper the ``extract_content`` action uses to pull structured info out of page
text. The agent loop owns the history and the tool-execution/approval logic.
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

    def extract(self, goal: str, page_text: str) -> str:
        """Pull the information described by `goal` out of `page_text`.

        Used by the read-only ``extract_content`` action — browser-use's
        ``extract_structured_data`` equivalent.
        """
        msg = self.client.messages.create(
            model=self.settings.model,
            max_tokens=1024,
            system=(
                "You extract information from the text of a web page. Return only "
                "what the goal asks for, concisely. If it is not present on the "
                "page, say so plainly — never invent a value."
            ),
            messages=[{
                "role": "user",
                "content": f"Goal: {goal}\n\nPage text:\n{page_text}",
            }],
        )
        return "".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
