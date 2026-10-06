"""Turn a live page into something the model can reason about.

We tag every visible, interactive element with a stable ``data-handoff-index``
attribute and return a compact list. The model then refers to elements by index
("click 12") instead of by fragile CSS selectors, and we click via the tag.

The element labels collected here (text, type, name, whether it sits inside a
<form>) are exactly what `approval.classify` inspects to decide if an action is
sensitive, so this is a security-relevant surface, not just ergonomics.
"""

from __future__ import annotations

# Injected into the page. Returns a JSON-serialisable list of interactive
# elements currently in the viewport, after stamping each with an index.
INDEX_JS = r"""
() => {
  const SELECTOR = [
    'a[href]', 'button', 'input', 'textarea', 'select',
    '[role=button]', '[role=link]', '[role=tab]', '[role=menuitem]',
    '[role=checkbox]', '[role=radio]', '[onclick]', '[contenteditable=""]',
    '[contenteditable="true"]'
  ].join(',');

  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth)
      return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || s.opacity === '0')
      return false;
    if (el.disabled) return false;
    return true;
  };

  const label = (el) => {
    const aria = el.getAttribute('aria-label');
    const txt = (el.innerText || el.value || el.placeholder || aria ||
                 el.getAttribute('title') || el.name || '').trim();
    return txt.replace(/\s+/g, ' ').slice(0, 120);
  };

  const all = [...document.querySelectorAll(SELECTOR)];
  const out = [];
  let i = 0;
  for (const el of all) {
    if (!isVisible(el)) continue;
    el.setAttribute('data-handoff-index', String(i));
    out.push({
      index: i,
      tag: el.tagName.toLowerCase(),
      type: (el.getAttribute('type') || '').toLowerCase(),
      text: label(el),
      aria: el.getAttribute('aria-label') || '',
      name: el.getAttribute('name') || '',
      id: el.id || '',
      placeholder: el.getAttribute('placeholder') || '',
      href: el.tagName === 'A' ? (el.getAttribute('href') || '') : '',
      in_form: !!el.closest('form'),
    });
    i += 1;
  }
  return out;
};
"""


def format_elements(elements: list[dict], limit: int = 120) -> str:
    """Render the indexed element list as a compact, token-cheap text block."""
    lines = []
    for el in elements[:limit]:
        tag = el.get("tag", "?")
        etype = el.get("type") or ""
        tag_disp = f"{tag}:{etype}" if etype else tag
        text = el.get("text") or el.get("placeholder") or el.get("aria") or ""
        flags = []
        if el.get("in_form"):
            flags.append("form")
        if el.get("href"):
            flags.append("link")
        flag_disp = f" ({','.join(flags)})" if flags else ""
        lines.append(f"[{el['index']}] {tag_disp} {text!r}{flag_disp}")
    if len(elements) > limit:
        lines.append(f"... (+{len(elements) - limit} more off-screen; scroll to reveal)")
    return "\n".join(lines) if lines else "(no interactive elements in view)"


def element_by_index(elements: list[dict], index) -> dict | None:
    try:
        index = int(index)
    except (TypeError, ValueError):
        return None
    for el in elements:
        if el.get("index") == index:
            return el
    return None
