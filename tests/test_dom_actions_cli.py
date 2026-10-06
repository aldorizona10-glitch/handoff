"""Offline tests for DOM formatting, action wiring, and CLI flag mapping."""

from handoff.actions import attach_element, tool_schemas
from handoff.cli import build_parser, settings_from_args
from handoff.config import ApprovalMode
from handoff.dom import element_by_index, format_elements

ELEMENTS = [
    {"index": 0, "tag": "a", "type": "", "text": "Home", "href": "/", "in_form": False},
    {"index": 1, "tag": "input", "type": "search", "text": "", "placeholder": "Search", "in_form": False},
    {"index": 2, "tag": "button", "type": "submit", "text": "Send message", "in_form": True},
]


def test_format_elements_is_compact_and_indexed():
    out = format_elements(ELEMENTS)
    assert "[0] a 'Home' (link)" in out
    assert "[2] button:submit 'Send message' (form)" in out


def test_element_by_index_handles_str_and_missing():
    assert element_by_index(ELEMENTS, "1")["tag"] == "input"
    assert element_by_index(ELEMENTS, 99) is None
    assert element_by_index(ELEMENTS, None) is None


def test_attach_element_adds_metadata_for_click():
    a = attach_element({"name": "click", "input": {"index": 2}, "id": "t1"}, ELEMENTS)
    assert a["input"]["element"]["text"] == "Send message"
    assert a["id"] == "t1"


def test_attach_element_noop_for_non_element_actions():
    a = attach_element({"name": "scroll", "input": {"direction": "down"}, "id": "t2"}, ELEMENTS)
    assert "element" not in a["input"]


def test_tool_schemas_expose_the_core_vocabulary():
    names = {t["name"] for t in tool_schemas()}
    assert {"navigate", "click", "type", "scroll", "done", "ask_human"} <= names
    # every tool must carry an input schema
    assert all("input_schema" in t for t in tool_schemas())


# -- CLI flag -> approval mode ----------------------------------------------

def test_cli_defaults_to_gated():
    args = build_parser().parse_args(["run", "do a thing"])
    assert settings_from_args(args).approval == ApprovalMode.GATED


def test_cli_dry_run_and_paranoid_and_yolo():
    p = build_parser()
    assert settings_from_args(p.parse_args(["run", "t", "--dry-run"])).approval == ApprovalMode.DRY_RUN
    assert settings_from_args(p.parse_args(["run", "t", "--paranoid"])).approval == ApprovalMode.PARANOID
    assert settings_from_args(p.parse_args(["run", "t", "--yolo"])).approval == ApprovalMode.YOLO


def test_cli_no_vision_and_url_and_maxsteps():
    args = build_parser().parse_args(
        ["run", "t", "--no-vision", "--url", "https://x.com", "--max-steps", "5"])
    s = settings_from_args(args)
    assert s.vision is False and s.start_url == "https://x.com" and s.max_steps == 5
