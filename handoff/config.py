"""Runtime configuration for a handoff session.

Everything here is derived from CLI flags / environment variables. Nothing in
this module reads, stores, or transmits credentials: the human logs in by hand
and the session lives only in the local browser profile on disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Where the logged-in browser profile is persisted between runs. It holds
# cookies/local-storage for the sites *you* logged into by hand. It is listed
# in .gitignore and must never be committed.
DEFAULT_PROFILE_DIR = Path(".handoff-profile")

# The only remote endpoint handoff talks to (besides the sites you drive) is the
# Anthropic API. The key is read from the environment, never written to disk.
API_KEY_ENV = "ANTHROPIC_API_KEY"

DEFAULT_MODEL = "claude-opus-5"


class ApprovalMode:
    """How aggressively the human brake is applied."""

    GATED = "gated"        # prompt before every *sensitive* action (default)
    PARANOID = "paranoid"  # prompt before *every* action
    YOLO = "yolo"          # never prompt (explicitly opt-in; prints a warning)
    DRY_RUN = "dry_run"    # never mutate; sensitive actions are auto-denied

    ALL = (GATED, PARANOID, YOLO, DRY_RUN)


@dataclass
class Settings:
    task: str = ""
    model: str = DEFAULT_MODEL
    approval: str = ApprovalMode.GATED
    max_steps: int = 25
    start_url: str | None = None
    profile_dir: Path = field(default_factory=lambda: DEFAULT_PROFILE_DIR)
    headless: bool = False          # login needs a visible window
    vision: bool = True             # send screenshots to the model
    viewport: tuple[int, int] = (1280, 800)
    # Origins the agent may navigate to without asking. Empty = every
    # cross-origin navigation is treated as sensitive and gated.
    allowed_origins: tuple[str, ...] = ()

    def api_key(self) -> str | None:
        return os.environ.get(API_KEY_ENV)

    def validate(self) -> None:
        if self.approval not in ApprovalMode.ALL:
            raise ValueError(f"unknown approval mode: {self.approval!r}")
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.approval != ApprovalMode.DRY_RUN and not self.api_key():
            raise ValueError(
                f"{API_KEY_ENV} is not set. Export your Anthropic API key "
                f"(see .env.example) or use --dry-run."
            )
