"""The brake is the most security-critical part, so it gets the most tests.

All offline: no browser, no API. We feed synthetic actions + element metadata
to the classifier and gate and assert the decisions.
"""

from handoff.approval import classify, gate
from handoff.config import ApprovalMode, Settings


def S(**kw):
    return Settings(approval=kw.pop("approval", ApprovalMode.GATED), **kw)


# -- classify ----------------------------------------------------------------

def test_reads_and_scrolls_are_safe():
    for name in ("read_page", "scroll", "wait", "go_back", "ask_human", "done"):
        d = classify({"name": name, "input": {}}, current_url="https://x.com", settings=S())
        assert d.sensitive is False, name


def test_click_mutating_label_is_sensitive():
    for label in ["Send message", "Delete account", "Pay now", "Kirim", "Hapus", "Bayar"]:
        a = {"name": "click", "input": {"element": {"text": label}}}
        d = classify(a, current_url="https://x.com", settings=S())
        assert d.sensitive is True, label


def test_click_plain_link_is_safe():
    a = {"name": "click", "input": {"element": {"text": "Documentation", "type": "", "in_form": False}}}
    assert classify(a, current_url="https://x.com", settings=S()).sensitive is False


def test_click_form_submit_button_is_sensitive():
    a = {"name": "click", "input": {"element": {"text": "OK", "type": "submit", "in_form": True}}}
    assert classify(a, current_url="https://x.com", settings=S()).sensitive is True


def test_type_into_secret_field_is_sensitive():
    a = {"name": "type", "input": {"text": "hunter2", "element": {"name": "password"}}}
    assert classify(a, current_url="https://x.com", settings=S()).sensitive is True


def test_type_plain_text_is_safe_but_submit_is_not():
    safe = {"name": "type", "input": {"text": "hello", "element": {"name": "q", "type": "search"}}}
    assert classify(safe, current_url="https://x.com", settings=S()).sensitive is False
    sub = {"name": "type", "input": {"text": "hello", "submit": True, "element": {"name": "q"}}}
    assert classify(sub, current_url="https://x.com", settings=S()).sensitive is True


def test_cross_origin_navigation_is_sensitive_same_origin_is_not():
    cross = {"name": "navigate", "input": {"url": "https://evil.example/"}}
    assert classify(cross, current_url="https://good.example/a", settings=S()).sensitive is True
    same = {"name": "navigate", "input": {"url": "https://good.example/b"}}
    assert classify(same, current_url="https://good.example/a", settings=S()).sensitive is False


def test_allow_listed_origin_navigation_is_safe():
    s = S(allowed_origins=("https://trusted.example",))
    a = {"name": "navigate", "input": {"url": "https://trusted.example/page"}}
    assert classify(a, current_url="https://other.example", settings=s).sensitive is False


def test_unknown_action_fails_safe():
    a = {"name": "mystery", "input": {}}
    assert classify(a, current_url=None, settings=S()).sensitive is True


# -- gate (modes) ------------------------------------------------------------

def test_dry_run_denies_sensitive_allows_safe():
    s = S(approval=ApprovalMode.DRY_RUN)
    sens = {"name": "click", "input": {"element": {"text": "Delete"}}}
    allowed, _ = gate(sens, current_url="https://x.com", settings=s)
    assert allowed is False
    safe = {"name": "read_page", "input": {}}
    allowed, _ = gate(safe, current_url="https://x.com", settings=s)
    assert allowed is True


def test_yolo_allows_everything_without_prompting():
    s = S(approval=ApprovalMode.YOLO)
    sens = {"name": "click", "input": {"element": {"text": "Delete"}}}

    def boom(_):  # prompter must NOT be called in yolo
        raise AssertionError("yolo must not prompt")

    allowed, _ = gate(sens, current_url="https://x.com", settings=s, prompter=boom, out=lambda *a: None)
    assert allowed is True


def test_gated_prompts_only_on_sensitive():
    s = S(approval=ApprovalMode.GATED)
    calls = []

    def prompter(_):
        calls.append(1)
        return "y"

    safe = {"name": "scroll", "input": {"direction": "down"}}
    gate(safe, current_url="https://x.com", settings=s, prompter=prompter, out=lambda *a: None)
    assert calls == []  # not prompted

    sens = {"name": "click", "input": {"element": {"text": "Submit"}}}
    allowed, _ = gate(sens, current_url="https://x.com", settings=s, prompter=prompter, out=lambda *a: None)
    assert calls == [1] and allowed is True


def test_denied_when_human_says_no():
    s = S(approval=ApprovalMode.GATED)
    sens = {"name": "click", "input": {"element": {"text": "Pay now"}}}
    allowed, reason = gate(sens, current_url="https://x.com", settings=s,
                           prompter=lambda _: "n", out=lambda *a: None)
    assert allowed is False and "denied" in reason.lower()
