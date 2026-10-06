"""Thin Playwright wrapper: a *persistent, human-authenticated* browser.

The design choice that defines handoff: we launch a persistent context backed by
a local profile directory. You run ``handoff login`` once, log into your sites by
hand in the window that opens, and close it. The cookies live in that local
folder (git-ignored). On later runs the agent drives an already-logged-in
browser — handoff never sees, stores, or types your password.

The browser also owns multiple tabs (``open_tab`` / ``switch_tab`` /
``list_tabs``): ``self.page`` is always the active tab, and the indexed element
list is built against it.
"""

from __future__ import annotations

import base64
from pathlib import Path

from .config import Settings
from .dom import INDEX_JS

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - import guard for environments w/o playwright
    sync_playwright = None


class Browser:
    def __init__(self, settings: Settings):
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Run:\n"
                "    pip install playwright && playwright install chromium"
            )
        self.settings = settings
        self._pw = None
        self._ctx = None
        self.page = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "Browser":
        self._pw = sync_playwright().start()
        profile = Path(self.settings.profile_dir).resolve()
        profile.mkdir(parents=True, exist_ok=True)
        w, h = self.settings.viewport
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=self.settings.headless,
            viewport={"width": w, "height": h},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    # -- observation -------------------------------------------------------
    @property
    def url(self) -> str:
        return self.page.url if self.page else ""

    def title(self) -> str:
        try:
            return self.page.title()
        except Exception:
            return ""

    def index_elements(self) -> list[dict]:
        """Stamp and return the interactive elements currently in view."""
        try:
            return self.page.evaluate(INDEX_JS) or []
        except Exception:
            return []

    def visible_text(self, limit: int = 4000) -> str:
        try:
            txt = self.page.evaluate("() => document.body ? document.body.innerText : ''")
        except Exception:
            txt = ""
        txt = " ".join((txt or "").split())
        return txt[:limit]

    def screenshot_b64(self) -> str | None:
        try:
            png = self.page.screenshot(type="png", full_page=False)
            return base64.b64encode(png).decode("ascii")
        except Exception:
            return None

    # -- actions (raw; gating happens in the agent before these run) -------
    def navigate(self, url: str) -> str:
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"navigated to {self.page.url}"

    def click_index(self, index: int) -> str:
        sel = f'[data-handoff-index="{int(index)}"]'
        self.page.click(sel, timeout=8000)
        self.page.wait_for_timeout(400)
        return f"clicked element [{index}]"

    def type_index(self, index: int, text: str, submit: bool = False) -> str:
        sel = f'[data-handoff-index="{int(index)}"]'
        self.page.fill(sel, text, timeout=8000)
        if submit:
            self.page.press(sel, "Enter")
            self.page.wait_for_timeout(400)
        return f"typed into [{index}]" + (" and submitted" if submit else "")

    def select_index(self, index: int, value: str) -> str:
        sel = f'[data-handoff-index="{int(index)}"]'
        try:
            self.page.select_option(sel, label=value, timeout=8000)
        except Exception:
            self.page.select_option(sel, value=value, timeout=8000)
        self.page.wait_for_timeout(300)
        return f"selected {value!r} in [{index}]"

    def scroll(self, direction: str = "down", amount: int = 700) -> str:
        dy = amount if direction == "down" else -amount
        self.page.mouse.wheel(0, dy)
        self.page.wait_for_timeout(250)
        return f"scrolled {direction}"

    def scroll_to_text(self, text: str) -> str:
        try:
            loc = self.page.get_by_text(text, exact=False).first
            loc.scroll_into_view_if_needed(timeout=4000)
            self.page.wait_for_timeout(200)
            return f"scrolled to text {text!r}"
        except Exception:
            return f"text {text!r} not found on this page"

    def wait(self, seconds: float) -> str:
        secs = max(0.0, min(float(seconds), 10.0))
        self.page.wait_for_timeout(int(secs * 1000))
        return f"waited {secs:.1f}s"

    def press(self, key: str) -> str:
        self.page.keyboard.press(key)
        self.page.wait_for_timeout(250)
        return f"pressed {key}"

    def go_back(self) -> str:
        self.page.go_back(wait_until="domcontentloaded", timeout=30000)
        return f"went back to {self.page.url}"

    # -- tabs --------------------------------------------------------------
    def list_tabs(self) -> list[dict]:
        tabs = []
        for i, p in enumerate(self._ctx.pages):
            try:
                tabs.append({"index": i, "url": p.url, "title": p.title()})
            except Exception:
                tabs.append({"index": i, "url": getattr(p, "url", ""), "title": ""})
        return tabs

    def open_tab(self, url: str) -> str:
        pg = self._ctx.new_page()
        self.page = pg
        pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"opened new tab -> {pg.url}"

    def switch_tab(self, index: int) -> str:
        pages = self._ctx.pages
        i = int(index)
        if i < 0 or i >= len(pages):
            return f"no tab [{i}] (there are {len(pages)} open)"
        self.page = pages[i]
        try:
            self.page.bring_to_front()
        except Exception:
            pass
        return f"switched to tab [{i}] {self.page.url}"
