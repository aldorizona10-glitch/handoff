"""Programmatic example: ask the agent to read a page and report back.

This is a read-only task, so the approval gate never fires — a gentle first run.
Requires ANTHROPIC_API_KEY in your environment (see .env.example) and a browser:
    pip install -e . && playwright install chromium

Run it against the bundled local demo page:
    python examples/01_read_only_demo.py
"""

from pathlib import Path

from handoff.agent import run
from handoff.config import ApprovalMode, Settings

demo = Path(__file__).parent / "demo_page.html"

settings = Settings(
    task="Read this page and tell me the main heading and every button label you see.",
    start_url=demo.resolve().as_uri(),      # file:// — no real site involved
    approval=ApprovalMode.GATED,            # sensitive actions would be gated (none here)
    max_steps=8,
)

if __name__ == "__main__":
    result = run(settings)
    print("\nRESULT:", result)
