"""The action vocabulary the model is given, and how each one is executed.

Tool schemas here are sent to Claude as `tools`. `execute` maps a chosen action
onto the Browser, *after* the agent has passed it through the approval gate. The
`element` metadata is attached to actions that reference an indexed element so
the gate can judge sensitivity from the real element, not the model's guess.
"""

from __future__ import annotations

from .browser import Browser
from .dom import element_by_index

# Terminal actions end the loop.
TERMINAL = ("done",)


def tool_schemas() -> list[dict]:
    """Anthropic tool definitions for the agent loop."""
    return [
        {
            "name": "navigate",
            "description": "Load a URL in the current tab.",
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
        {
            "name": "click",
            "description": "Click the interactive element with the given index "
                           "from the current element list.",
            "input_schema": {
                "type": "object",
                "properties": {"index": {"type": "integer"}},
                "required": ["index"],
            },
        },
        {
            "name": "type",
            "description": "Type text into the input/textarea with the given index. "
                           "Set submit=true to press Enter afterwards.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "text": {"type": "string"},
                    "submit": {"type": "boolean"},
                },
                "required": ["index", "text"],
            },
        },
        {
            "name": "scroll",
            "description": "Scroll the page up or down to reveal more elements.",
            "input_schema": {
                "type": "object",
                "properties": {"direction": {"type": "string", "enum": ["up", "down"]}},
                "required": ["direction"],
            },
        },
        {
            "name": "press",
            "description": "Press a single keyboard key (e.g. Enter, Escape, Tab).",
            "input_schema": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
        {
            "name": "go_back",
            "description": "Navigate back to the previous page.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "read_page",
            "description": "Re-read the current page's visible text and element list.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "ask_human",
            "description": "Ask the human operator a question and wait for their "
                           "answer. Use when the task is ambiguous or you need a "
                           "decision only they can make.",
            "input_schema": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
        {
            "name": "done",
            "description": "Finish the task. Provide a summary of what was done and "
                           "whether it succeeded.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "success": {"type": "boolean"},
                },
                "required": ["summary", "success"],
            },
        },
    ]


def attach_element(action: dict, elements: list[dict]) -> dict:
    """Return a copy of `action` with the referenced element's metadata attached.

    This is what makes the approval gate trustworthy: it classifies against the
    element actually present in the page, not the label the model imagined.
    """
    name = action.get("name")
    args = dict(action.get("input") or {})
    if name in ("click", "type") and "index" in args:
        el = element_by_index(elements, args.get("index"))
        if el is not None:
            args["element"] = el
    return {"name": name, "input": args, "id": action.get("id")}


def execute(action: dict, browser: Browser, *, ask=input) -> str:
    """Run an approved action against the browser; return a result string."""
    name = action.get("name")
    args = action.get("input") or {}

    if name == "navigate":
        return browser.navigate(args["url"])
    if name == "click":
        return browser.click_index(args["index"])
    if name == "type":
        return browser.type_index(args["index"], args.get("text", ""),
                                  submit=bool(args.get("submit")))
    if name == "scroll":
        return browser.scroll(args.get("direction", "down"))
    if name == "press":
        return browser.press(args["key"])
    if name == "go_back":
        return browser.go_back()
    if name == "read_page":
        return "page re-read"
    if name == "ask_human":
        answer = ask(f"\n  ❔ {args.get('question','(no question)')}\n     your answer: ")
        return f"human answered: {answer}"
    if name == "done":
        return args.get("summary", "done")
    return f"error: unknown action {name!r}"
