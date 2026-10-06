"""Command-line interface for handoff.

    handoff login  --url https://example.com
    handoff run    "find the latest invoice and tell me its total" --url ...
    handoff run    "…" --dry-run          # never mutates, previews the plan
    handoff run    "…" --paranoid         # confirm every single action
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import ApprovalMode, DEFAULT_MODEL, DEFAULT_PROFILE_DIR, Settings


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--url", dest="start_url", default=None,
                   help="URL to open before starting")
    p.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR),
                   help="local browser profile directory (holds your logins)")
    p.add_argument("--model", default=DEFAULT_MODEL)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="handoff",
        description="Log in yourself. Hand the browser to an AI. "
                    "Approve before it acts.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("login", help="open the browser to log into your sites")
    _add_common(pl)

    pr = sub.add_parser("run", help="give the agent a task")
    pr.add_argument("task", help="what you want done, in plain language")
    _add_common(pr)
    pr.add_argument("--max-steps", type=int, default=25)
    pr.add_argument("--no-vision", action="store_true",
                    help="don't send screenshots (cheaper, DOM-only)")
    pr.add_argument("--headless", action="store_true",
                    help="run without a visible window (not for first login)")
    mode = pr.add_mutually_exclusive_group()
    mode.add_argument("--paranoid", action="store_true",
                      help="confirm EVERY action, not just sensitive ones")
    mode.add_argument("--yolo", action="store_true",
                      help="never confirm (dangerous; opt-in only)")
    mode.add_argument("--dry-run", action="store_true",
                      help="never mutate; auto-deny sensitive actions")
    return p


def settings_from_args(args: argparse.Namespace) -> Settings:
    approval = ApprovalMode.GATED
    if getattr(args, "paranoid", False):
        approval = ApprovalMode.PARANOID
    elif getattr(args, "yolo", False):
        approval = ApprovalMode.YOLO
    elif getattr(args, "dry_run", False):
        approval = ApprovalMode.DRY_RUN

    return Settings(
        task=getattr(args, "task", ""),
        model=args.model,
        approval=approval,
        max_steps=getattr(args, "max_steps", 25),
        start_url=args.start_url,
        profile_dir=Path(args.profile_dir),
        headless=getattr(args, "headless", False),
        vision=not getattr(args, "no_vision", False),
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # import here so `handoff --help` works without playwright/anthropic installed
    from . import agent

    settings = settings_from_args(args)

    if args.command == "login":
        agent.login(settings)
        return 0

    if args.command == "run":
        if settings.approval == ApprovalMode.YOLO:
            print("⚠  YOLO mode: handoff will NOT ask before sensitive actions.")
        try:
            settings.validate()
        except ValueError as exc:
            print(f"error: {exc}")
            return 2
        result = agent.run(settings)
        print("\n" + "=" * 60)
        print(f"summary : {result['summary']}")
        print(f"success : {result['success']}")
        print(f"url     : {result['final_url']}")
        return 0 if result["success"] else 1

    return 2
