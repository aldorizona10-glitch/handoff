"""An extensible action registry — handoff's version of browser-use's `Tools`.

browser-use's defining idea is that the agent's capabilities are not a fixed
`if/elif` ladder but a *registry* of small functions, each self-describing, that
you can extend with a decorator. handoff adopts the same shape:

    from handoff.actions import registry
    from handoff.registry import ActionResult

    @registry.action("star_repo", "Star the current GitHub repo.",
                     params={}, required=[])
    def _star(ctx, args):
        return ActionResult(extracted_content=ctx.browser.click_index(...))

Every registered action becomes an Anthropic tool automatically
(`registry.tool_schemas()`), and the agent dispatches to it by name
(`registry.execute(...)`). The human approval gate sits *between* the model
choosing an action and the registry running it — that is the one thing handoff
keeps that a pure autonomy framework does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ActionResult:
    """The standardised outcome of one action — mirrors browser-use's ActionResult.

    - ``extracted_content``: the useful text to feed back to the model.
    - ``error``: set when the action failed; the loop feeds it back so the model
      can adapt instead of crashing.
    - ``is_done`` / ``success``: set by the terminal ``done`` action.
    - ``include_in_memory``: hint for whether this result is worth keeping in the
      running message history (noise like "page re-read" can be dropped).
    """

    extracted_content: str | None = None
    error: str | None = None
    is_done: bool = False
    success: bool = False
    include_in_memory: bool = True

    def to_text(self) -> str:
        if self.error:
            return f"error: {self.error}" if not self.error.startswith("DENIED") else self.error
        return self.extracted_content if self.extracted_content is not None else "ok"


@dataclass
class ActionContext:
    """Everything an action handler may need, passed to it at execution time."""

    browser: object
    ask: Callable[[str], str] = input
    llm: object | None = None
    settings: object | None = None


@dataclass
class Action:
    name: str
    description: str
    params: dict = field(default_factory=dict)
    required: list = field(default_factory=list)
    handler: Callable[[ActionContext, dict], ActionResult] | None = None
    reads_only: bool = False


class Registry:
    """Holds the available actions and turns them into tools / dispatches them."""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}

    def action(self, name: str, description: str, *, params: dict | None = None,
               required: list | None = None, reads_only: bool = False):
        """Decorator: register ``fn`` as an action named ``name``."""

        def deco(fn: Callable[[ActionContext, dict], ActionResult]):
            self._actions[name] = Action(
                name=name, description=description,
                params=params or {}, required=required or [],
                handler=fn, reads_only=reads_only,
            )
            return fn

        return deco

    # -- introspection -----------------------------------------------------
    def names(self) -> list[str]:
        return list(self._actions)

    def get(self, name: str) -> Action | None:
        return self._actions.get(name)

    def tool_schemas(self) -> list[dict]:
        """Anthropic tool definitions, generated from the registered actions."""
        return [
            {
                "name": a.name,
                "description": a.description,
                "input_schema": {
                    "type": "object",
                    "properties": a.params,
                    "required": a.required,
                },
            }
            for a in self._actions.values()
        ]

    # -- dispatch ----------------------------------------------------------
    def execute(self, name: str, args: dict, ctx: ActionContext) -> ActionResult:
        action = self._actions.get(name)
        if action is None or action.handler is None:
            return ActionResult(error=f"unknown action {name!r}")
        try:
            return action.handler(ctx, args or {})
        except Exception as exc:  # feed errors back so the model adapts
            return ActionResult(error=f"while executing {name}: {exc}")
