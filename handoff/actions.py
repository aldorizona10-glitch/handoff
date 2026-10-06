"""The action vocabulary, defined as a registry (browser-use style).

Each action is a small decorated function registered on the module-level
``registry``. The decorator records its name, human description and JSON-schema
params, so ``registry.tool_schemas()`` can hand Anthropic the exact tool list and
``registry.execute()`` can dispatch a chosen action by name. Adding a capability
is now one decorated function, not an edit in three places.

Handlers run *after* the agent has passed the action through the approval gate.
``attach_element`` enriches element-referencing actions with the real element's
metadata first, so the gate classifies sensitivity from the page, not the model's
guess.
"""

from __future__ import annotations

from .dom import element_by_index
from .registry import ActionContext, ActionResult, Registry

# The single registry every action registers onto; the agent imports this.
registry = Registry()

# Terminal actions end the loop.
TERMINAL = ("done",)

# Actions that reference an indexed element get that element's metadata attached
# before gating, so sensitivity is judged from the real control.
_INDEXED = ("click", "type", "select_option")


# -- navigation --------------------------------------------------------------
@registry.action("navigate", "Load a URL in the current tab.",
                 params={"url": {"type": "string"}}, required=["url"])
def _navigate(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.navigate(args["url"]))


@registry.action("go_back", "Navigate back to the previous page.",
                 params={}, required=[], reads_only=True)
def _go_back(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.go_back())


# -- interaction -------------------------------------------------------------
@registry.action("click",
                 "Click the interactive element with the given index from the "
                 "current element list.",
                 params={"index": {"type": "integer"}}, required=["index"])
def _click(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.click_index(args["index"]))


@registry.action("type",
                 "Type text into the input/textarea with the given index. Set "
                 "submit=true to press Enter afterwards.",
                 params={"index": {"type": "integer"},
                         "text": {"type": "string"},
                         "submit": {"type": "boolean"}},
                 required=["index", "text"])
def _type(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.type_index(
        args["index"], args.get("text", ""), submit=bool(args.get("submit"))))


@registry.action("select_option",
                 "Choose an option in the <select> dropdown with the given index, "
                 "by its visible label (falls back to its value).",
                 params={"index": {"type": "integer"}, "value": {"type": "string"}},
                 required=["index", "value"])
def _select_option(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.select_index(
        args["index"], args["value"]))


@registry.action("press", "Press a single keyboard key (e.g. Enter, Escape, Tab).",
                 params={"key": {"type": "string"}}, required=["key"])
def _press(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.press(args["key"]))


# -- scrolling / waiting -----------------------------------------------------
@registry.action("scroll", "Scroll the page up or down to reveal more elements.",
                 params={"direction": {"type": "string", "enum": ["up", "down"]}},
                 required=["direction"], reads_only=True)
def _scroll(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.scroll(
        args.get("direction", "down")))


@registry.action("scroll_to_text",
                 "Scroll until the given text is in view. Use to reach an element "
                 "that is currently off-screen.",
                 params={"text": {"type": "string"}}, required=["text"],
                 reads_only=True)
def _scroll_to_text(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.scroll_to_text(args["text"]))


@registry.action("wait",
                 "Wait a few seconds for the page to settle (e.g. after a slow "
                 "load). Capped at 10s.",
                 params={"seconds": {"type": "number"}}, required=[],
                 reads_only=True)
def _wait(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.wait(
        float(args.get("seconds", 1))))


# -- reading / extraction ----------------------------------------------------
@registry.action("read_page",
                 "Re-read the current page's visible text and element list.",
                 params={}, required=[], reads_only=True)
def _read_page(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content="page re-read", include_in_memory=False)


@registry.action("extract_content",
                 "Read the current page and extract the information described by "
                 "`goal`. Read-only; does not change the page.",
                 params={"goal": {"type": "string"}}, required=["goal"],
                 reads_only=True)
def _extract_content(ctx: ActionContext, args: dict) -> ActionResult:
    goal = args.get("goal", "")
    text = ctx.browser.visible_text(limit=8000)
    if ctx.llm is not None:
        try:
            content = ctx.llm.extract(goal, text)
        except Exception as exc:
            return ActionResult(error=f"extraction failed: {exc}")
    else:
        # No model available (e.g. dry-run without a key): hand back raw text.
        content = text
    return ActionResult(extracted_content=content)


# -- tabs --------------------------------------------------------------------
@registry.action("list_tabs",
                 "List the currently open browser tabs with their indexes, URLs "
                 "and titles.",
                 params={}, required=[], reads_only=True)
def _list_tabs(ctx: ActionContext, args: dict) -> ActionResult:
    tabs = ctx.browser.list_tabs()
    body = "\n".join(f"[{t['index']}] {t['title']} — {t['url']}" for t in tabs)
    return ActionResult(extracted_content=body or "(no tabs)")


@registry.action("switch_tab",
                 "Switch to the open browser tab with the given index (see "
                 "list_tabs).",
                 params={"index": {"type": "integer"}}, required=["index"],
                 reads_only=True)
def _switch_tab(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.switch_tab(args["index"]))


@registry.action("open_tab", "Open a URL in a new browser tab and switch to it.",
                 params={"url": {"type": "string"}}, required=["url"])
def _open_tab(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=ctx.browser.open_tab(args["url"]))


# -- human-in-the-loop / terminal -------------------------------------------
@registry.action("ask_human",
                 "Ask the human operator a question and wait for their answer. "
                 "Use when the task is ambiguous or you need a decision only they "
                 "can make.",
                 params={"question": {"type": "string"}}, required=["question"],
                 reads_only=True)
def _ask_human(ctx: ActionContext, args: dict) -> ActionResult:
    answer = ctx.ask(f"\n  ❔ {args.get('question', '(no question)')}"
                     f"\n     your answer: ")
    return ActionResult(extracted_content=f"human answered: {answer}")


@registry.action("done",
                 "Finish the task. Provide a summary of what was done and whether "
                 "it succeeded.",
                 params={"summary": {"type": "string"},
                         "success": {"type": "boolean"}},
                 required=["summary", "success"], reads_only=True)
def _done(ctx: ActionContext, args: dict) -> ActionResult:
    return ActionResult(extracted_content=args.get("summary", ""),
                        is_done=True, success=bool(args.get("success")))


# -- helpers the agent / gate rely on ----------------------------------------
def tool_schemas() -> list[dict]:
    """Anthropic tool definitions for the agent loop (from the registry)."""
    return registry.tool_schemas()


def attach_element(action: dict, elements: list[dict]) -> dict:
    """Return a copy of `action` with the referenced element's metadata attached.

    This is what makes the approval gate trustworthy: it classifies against the
    element actually present in the page, not the label the model imagined.
    """
    name = action.get("name")
    args = dict(action.get("input") or {})
    if name in _INDEXED and "index" in args:
        el = element_by_index(elements, args.get("index"))
        if el is not None:
            args["element"] = el
    return {"name": name, "input": args, "id": action.get("id")}
