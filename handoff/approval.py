"""The brake.

An AI driving an authenticated browser is powerful and therefore dangerous: one
wrong click can send a message, place an order, or delete something. handoff's
answer is a *default-deny gate on anything irreversible or outbound*. A human
confirms every sensitive action before it runs.

This module decides what counts as "sensitive" and asks the human. It is pure
and side-effect-free except for `prompt_human`, so the classifier is unit-tested
offline without a browser or the API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .config import ApprovalMode, Settings

# Words that signal a mutating / outbound / irreversible control, in English and
# Indonesian. Matched case-insensitively against an element's visible label.
_MUTATING_WORDS = [
    # English
    "submit", "send", "post", "publish", "delete", "remove", "buy", "pay",
    "checkout", "place order", "order now", "confirm", "save", "apply",
    "transfer", "withdraw", "deposit", "book", "subscribe", "unsubscribe",
    "accept", "agree", "sign", "sign up", "register", "upload", "share",
    "invite", "approve", "cancel", "delete account", "deactivate",
    # Indonesian
    "kirim", "hapus", "bayar", "simpan", "pesan", "beli", "daftar",
    "berlangganan", "setuju", "unggah", "bagikan", "konfirmasi", "lanjutkan",
    "selesaikan", "ajukan", "lamar",
]
_MUTATING_RE = re.compile("|".join(re.escape(w) for w in _MUTATING_WORDS), re.I)

# Field names/types that must never be auto-filled. The human logs in by hand,
# so these should rarely appear; if they do, we always stop.
_SECRET_FIELD_RE = re.compile(
    r"pass(word|wd|phrase)|secret|otp|2fa|mfa|cvv|cvc|card.?number|iban|"
    r"account.?number|pin|ssn|social.?security|seed.?phrase|private.?key",
    re.I,
)


@dataclass
class Decision:
    sensitive: bool
    reason: str


def _origin(url: str | None) -> str | None:
    if not url:
        return None
    p = urlparse(url)
    if not p.scheme or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}"


def classify(action: dict, *, current_url: str | None, settings: Settings) -> Decision:
    """Return whether `action` is sensitive and why.

    `action` is a dict: {"name": <str>, "input": <dict>}. `element` (when the
    action references one) carries the label/type/field metadata the browser
    layer attached to the indexed element.
    """
    name = action.get("name", "")
    args = action.get("input", {}) or {}
    element = args.get("element") or {}

    # Reads and waits are always safe.
    if name in ("read_page", "scroll", "wait", "go_back", "done", "ask_human"):
        return Decision(False, "read-only/navigational")

    if name == "navigate":
        target = _origin(args.get("url"))
        here = _origin(current_url)
        if target and target in settings.allowed_origins:
            return Decision(False, f"navigation within allow-listed origin {target}")
        if here and target and target == here:
            return Decision(False, "same-origin navigation")
        return Decision(True, f"navigates to a new site: {target or args.get('url')!r}")

    if name == "type":
        label = " ".join(
            str(element.get(k, "")) for k in ("name", "id", "placeholder", "label", "type")
        )
        if _SECRET_FIELD_RE.search(label):
            return Decision(True, "types into a credential/secret field")
        if args.get("submit"):
            return Decision(True, "submits a form (Enter) after typing")
        return Decision(False, "types into a normal text field")

    if name == "press":
        if str(args.get("key", "")).lower() in ("enter", "return"):
            return Decision(True, "presses Enter (may submit a form)")
        return Decision(False, f"presses {args.get('key')!r}")

    if name == "upload":
        return Decision(True, "uploads a file")

    if name == "click":
        label = str(element.get("text", "")) or str(element.get("aria", ""))
        etype = str(element.get("type", "")).lower()
        if etype in ("submit", "button") and element.get("in_form"):
            return Decision(True, f"clicks a form control: {label!r}")
        if _MUTATING_RE.search(label):
            return Decision(True, f"clicks a mutating control: {label!r}")
        return Decision(False, f"clicks a non-mutating element: {label!r}")

    # Unknown action: fail safe -> treat as sensitive.
    return Decision(True, f"unrecognised action {name!r} (gated by default)")


def prompt_human(action: dict, decision: Decision, *, prompter=input, out=print) -> bool:
    """Ask the human to approve a sensitive action. Returns True to proceed.

    `prompter`/`out` are injectable so tests don't touch real stdin/stdout.
    """
    name = action.get("name", "?")
    args = {k: v for k, v in (action.get("input") or {}).items() if k != "element"}
    out("\n  ⚠  handoff wants to run a SENSITIVE action")
    out(f"     action : {name}  {args}")
    out(f"     why    : {decision.reason}")
    try:
        answer = prompter("     proceed? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        out("     -> no input, denied.")
        return False
    ok = answer in ("y", "yes")
    out("     -> approved." if ok else "     -> denied.")
    return ok


def gate(action: dict, *, current_url: str | None, settings: Settings,
         prompter=input, out=print) -> tuple[bool, str]:
    """Apply the configured approval mode to an action.

    Returns (allowed, reason). Never raises for ordinary flow.
    """
    decision = classify(action, current_url=current_url, settings=settings)
    mode = settings.approval

    if mode == ApprovalMode.YOLO:
        return True, "yolo mode (no gate)"

    if mode == ApprovalMode.DRY_RUN:
        if decision.sensitive:
            return False, f"dry-run: sensitive action auto-denied ({decision.reason})"
        return True, "dry-run: read-only action allowed"

    if mode == ApprovalMode.PARANOID:
        if prompt_human(action, decision, prompter=prompter, out=out):
            return True, "approved by human (paranoid)"
        return False, "denied by human (paranoid)"

    # GATED (default): only sensitive actions are prompted.
    if not decision.sensitive:
        return True, decision.reason
    if prompt_human(action, decision, prompter=prompter, out=out):
        return True, "approved by human"
    return False, "denied by human"
