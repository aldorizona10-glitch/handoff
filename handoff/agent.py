"""The agent loop: observe -> think -> (gate) -> act -> repeat.

This is intentionally a hand-written loop rather than the SDK tool-runner,
because the whole point of handoff is the human brake *between* the model
choosing an action and that action running. That gate lives right here, in the
middle of the loop, where it is easy to read and audit.
"""

from __future__ import annotations

from . import prompts
from .actions import attach_element, execute, tool_schemas
from .approval import gate
from .browser import Browser
from .config import ApprovalMode, Settings
from .llm import LLM


def _user_content(state_text: str, screenshot_b64, settings: Settings,
                  *, prefix: str | None = None, tool_results=None) -> list[dict]:
    content: list[dict] = []
    if tool_results:
        content.extend(tool_results)          # must come first in the turn
    if prefix:
        content.append({"type": "text", "text": prefix})
    content.append({"type": "text", "text": state_text})
    if settings.vision and screenshot_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png",
                       "data": screenshot_b64},
        })
    return content


def _capture(browser: Browser):
    elements = browser.index_elements()
    return browser.url, browser.title(), browser.visible_text(), elements


def run(settings: Settings, *, out=print, ask=input) -> dict:
    settings.validate()
    llm = LLM(settings)
    tools = tool_schemas()

    with Browser(settings) as browser:
        if settings.start_url:
            out(f"→ opening {settings.start_url}")
            browser.navigate(settings.start_url)

        url, title, text, elements = _capture(browser)
        state = prompts.state_block(url, title, text, elements)
        messages = [{
            "role": "user",
            "content": _user_content(
                state, browser.screenshot_b64(), settings,
                prefix=prompts.task_block(settings.task)),
        }]

        summary, success = "(no result)", False

        for step in range(1, settings.max_steps + 1):
            out(f"\n── step {step}/{settings.max_steps} ({browser.url}) ──")
            resp = llm.step(prompts.SYSTEM, messages, tools)
            messages.append({"role": "assistant", "content": resp.content})

            tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            for b in resp.content:
                if getattr(b, "type", "") == "text" and b.text.strip():
                    out(f"  · {b.text.strip()}")

            if not tool_uses:
                summary = "model stopped without requesting an action"
                break

            tool_results = []
            finished = False
            for b in tool_uses:
                action = attach_element(
                    {"name": b.name, "input": b.input, "id": b.id}, elements)

                if action["name"] == "done":
                    summary = (b.input or {}).get("summary", "")
                    success = bool((b.input or {}).get("success"))
                    out(f"  ✔ done: {summary} (success={success})")
                    finished = True
                    break

                allowed, reason = gate(action, current_url=browser.url,
                                       settings=settings, prompter=ask, out=out)
                if allowed:
                    try:
                        result = execute(action, browser, ask=ask)
                    except Exception as exc:  # feed errors back so the model adapts
                        result = f"error while executing: {exc}"
                    out(f"  → {result}")
                else:
                    result = f"DENIED: {reason}"
                    out(f"  ⛔ {result}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": result,
                })

            if finished:
                break

            url, title, text, elements = _capture(browser)
            state = prompts.state_block(url, title, text, elements)
            messages.append({
                "role": "user",
                "content": _user_content(state, browser.screenshot_b64(),
                                         settings, tool_results=tool_results),
            })
        else:
            summary = f"reached step limit ({settings.max_steps}) without finishing"

        return {"summary": summary, "success": success, "final_url": browser.url}


def login(settings: Settings, *, out=print, ask=input) -> None:
    """Open the persistent browser so the human can log into their sites by hand."""
    settings.headless = False
    with Browser(settings) as browser:
        if settings.start_url:
            browser.navigate(settings.start_url)
        out("\nA browser window is open using your local handoff profile:")
        out(f"  {settings.profile_dir}")
        out("Log into the site(s) you want handoff to drive, then come back here.")
        out("Your cookies stay in that local folder — handoff never sees your password.")
        ask("\nPress Enter when you're done logging in… ")
        out("Saved. Future `handoff run` sessions will reuse this login.")
