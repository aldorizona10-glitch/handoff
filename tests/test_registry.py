"""Tests for the browser-use-style action registry, ActionResult, the new
action vocabulary, and how the approval gate classifies the new actions.

All offline: a tiny FakeBrowser stands in for Playwright; no API, no network.
"""


from handoff.actions import attach_element, registry, tool_schemas
from handoff.approval import classify
from handoff.config import ApprovalMode, Settings
from handoff.registry import ActionContext, ActionResult, Registry


def S(**kw):
    return Settings(approval=kw.pop("approval", ApprovalMode.GATED), **kw)


class FakeBrowser:
    """Records calls and returns canned strings, like the real Browser's API."""

    def __init__(self, text="hello world"):
        self.calls = []
        self._text = text

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return f"{name}{args}"
        return method

    def visible_text(self, limit=4000):
        self.calls.append(("visible_text", (), {"limit": limit}))
        return self._text[:limit]


def ctx(browser=None, llm=None):
    return ActionContext(browser=browser or FakeBrowser(), ask=lambda q: "ok", llm=llm)


# -- ActionResult ------------------------------------------------------------

def test_actionresult_to_text_prefers_content_then_error():
    assert ActionResult(extracted_content="got it").to_text() == "got it"
    assert ActionResult(error="boom").to_text() == "error: boom"
    # a DENIED error is shown verbatim (not double-prefixed)
    assert ActionResult(error="DENIED: nope").to_text() == "DENIED: nope"
    # empty but no error -> a neutral ok, never a crash
    assert ActionResult().to_text() == "ok"


# -- Registry mechanics ------------------------------------------------------

def test_registry_decorator_registers_and_builds_schema():
    r = Registry()

    @r.action("ping", "ping the thing", params={"n": {"type": "integer"}},
              required=["n"])
    def _ping(c, a):
        return ActionResult(extracted_content=f"pong {a['n']}")

    assert "ping" in r.names()
    schema = r.tool_schemas()[0]
    assert schema["name"] == "ping"
    assert schema["input_schema"]["properties"] == {"n": {"type": "integer"}}
    assert schema["input_schema"]["required"] == ["n"]
    assert r.execute("ping", {"n": 3}, ctx()).extracted_content == "pong 3"


def test_registry_unknown_action_returns_error_not_raise():
    r = Registry()
    res = r.execute("nope", {}, ctx())
    assert res.error and "unknown action" in res.error


def test_registry_handler_exception_is_captured():
    r = Registry()

    @r.action("boom", "always fails", params={}, required=[])
    def _boom(c, a):
        raise RuntimeError("kaboom")

    res = r.execute("boom", {}, ctx())
    assert res.error and "kaboom" in res.error and res.is_done is False


# -- the shipped vocabulary --------------------------------------------------

def test_tool_schemas_include_browser_use_style_actions():
    names = {t["name"] for t in tool_schemas()}
    expected = {"navigate", "click", "type", "scroll", "done", "ask_human",
                "extract_content", "scroll_to_text", "wait", "select_option",
                "open_tab", "switch_tab", "list_tabs"}
    assert expected <= names
    assert all("input_schema" in t for t in tool_schemas())


def test_done_action_sets_is_done_and_success():
    res = registry.execute("done", {"summary": "all set", "success": True}, ctx())
    assert res.is_done is True and res.success is True
    assert res.extracted_content == "all set"


def test_extract_content_without_llm_falls_back_to_page_text():
    fb = FakeBrowser(text="Invoice total: $42.00")
    res = registry.execute("extract_content", {"goal": "the total"}, ctx(browser=fb))
    assert res.error is None
    assert "42.00" in res.extracted_content


def test_extract_content_uses_llm_when_present():
    class FakeLLM:
        def extract(self, goal, text):
            return f"answer for {goal}"
    res = registry.execute("extract_content", {"goal": "x"},
                           ctx(browser=FakeBrowser(), llm=FakeLLM()))
    assert res.extracted_content == "answer for x"


def test_list_tabs_renders_indexes():
    class TabBrowser(FakeBrowser):
        def list_tabs(self):
            return [{"index": 0, "title": "A", "url": "https://a"},
                    {"index": 1, "title": "B", "url": "https://b"}]
    res = registry.execute("list_tabs", {}, ctx(browser=TabBrowser()))
    assert "[0] A — https://a" in res.extracted_content
    assert "[1] B — https://b" in res.extracted_content


# -- attach_element now covers select_option --------------------------------

def test_attach_element_adds_metadata_for_select_option():
    elements = [{"index": 4, "tag": "select", "type": "", "text": "Country",
                 "in_form": True}]
    a = attach_element({"name": "select_option",
                        "input": {"index": 4, "value": "ID"}, "id": "t"}, elements)
    assert a["input"]["element"]["text"] == "Country"
    assert a["input"]["element"]["in_form"] is True


# -- gate classification of the new actions ---------------------------------

def test_new_read_only_actions_are_safe():
    for name in ("extract_content", "scroll_to_text", "wait", "switch_tab",
                 "list_tabs"):
        d = classify({"name": name, "input": {}}, current_url="https://x.com",
                     settings=S())
        assert d.sensitive is False, name


def test_open_tab_is_classified_like_navigate():
    cross = {"name": "open_tab", "input": {"url": "https://evil.example/"}}
    assert classify(cross, current_url="https://good.example/a",
                    settings=S()).sensitive is True
    same = {"name": "open_tab", "input": {"url": "https://good.example/b"}}
    assert classify(same, current_url="https://good.example/a",
                    settings=S()).sensitive is False
    allow = {"name": "open_tab", "input": {"url": "https://trusted.example/x"}}
    s = S(allowed_origins=("https://trusted.example",))
    assert classify(allow, current_url="https://other.example",
                    settings=s).sensitive is False


def test_select_option_sensitive_only_inside_a_form():
    in_form = {"name": "select_option",
               "input": {"value": "v", "element": {"in_form": True}}}
    assert classify(in_form, current_url="https://x.com", settings=S()).sensitive is True
    loose = {"name": "select_option",
             "input": {"value": "v", "element": {"in_form": False}}}
    assert classify(loose, current_url="https://x.com", settings=S()).sensitive is False
