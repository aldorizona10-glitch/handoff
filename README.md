# handoff

**Log in yourself. Hand the browser to an AI. Approve before it acts.**

`handoff` is a small, local-first framework for AI-driven browser automation
with a human brake. You authenticate by hand; a Claude agent then drives your
already–logged-in browser to do a task — and it **stops for your approval before
anything irreversible** (submitting a form, sending a message, buying, deleting,
leaving the site).

It is built on [Playwright](https://playwright.dev) and the
[Anthropic API](https://docs.anthropic.com). MIT-licensed.

---

## Why another browser agent?

Most browser agents optimise for *autonomy*. `handoff` optimises for **trust**,
with three deliberate choices:

1. **You log in — handoff never touches your credentials.**
   There is no password field, no cookie string, no "store my login" in this
   project. You log in by hand once; the session lives only in a local browser
   profile folder on your machine (git-ignored). handoff drives an
   already-authenticated browser. It literally cannot leak a password it never
   receives.

2. **A human brake on every irreversible action.**
   The agent proposes an action; a classifier decides whether it is *sensitive*
   (outbound / mutating / cross-site); if it is, handoff shows it to you and
   waits for `y`. Deny it and the agent adapts. This is the same
   "verify-before-send" gate a careful operator uses by instinct — made explicit
   and default-on.

3. **Local-first. No telemetry.**
   The only things handoff talks to are the Anthropic API and the sites you point
   it at. Nothing about your session is uploaded anywhere else.

---

## How it works

```text
  STEP 1 ·  handoff login
            You log into your sites BY HAND, once.
            Cookies are saved to .handoff-profile/ — a local, git-ignored folder.
            handoff never sees, stores, or types your password.

  STEP 2 ·  handoff run "task"
            The agent drives your already-authenticated browser, looping:

               observe  ->  screenshot + an indexed list of interactive elements
               think    ->  Claude picks the next action
               GATE     ->  is it sensitive? (submit / send / pay / delete /
                            cross-site navigation)
                              - no   ->  run it
                              - yes  ->  ask you:   y -> run it
                                                    N -> denied, the agent adapts
               repeat   ->  until the task is done

  STEP 3 ·  An honest summary of what was -- and wasn't -- accomplished.
```

Each step the agent sees the current URL, the visible text, a screenshot, and an
**indexed list of the interactive elements** on screen. It refers to elements by
index (`click 12`), so there are no brittle hand-written selectors.

---

## Install

```bash
git clone https://github.com/aldorizona10-glitch/handoff
cd handoff
pip install -e .
playwright install chromium
cp .env.example .env     # then put your ANTHROPIC_API_KEY in .env
```

Requires Python 3.10+.

## Quickstart

```bash
# 1) Open a browser and log into the site(s) you want to automate — by hand.
handoff login --url https://example.com

# 2) Give the agent a task. Sensitive actions pause for your approval.
handoff run "find the most recent invoice and tell me the total" --url https://example.com

# Preview the plan without changing anything (sensitive actions auto-denied):
handoff run "draft a reply to the latest message" --dry-run

# Confirm EVERY action, not just sensitive ones:
handoff run "update my profile headline" --paranoid
```

Or use it programmatically — see [`examples/01_read_only_demo.py`](examples/01_read_only_demo.py),
which runs against a bundled local page so you can try it without any real site.

---

## Use from Claude Code

handoff ships a [Claude Code](https://docs.claude.com/claude-code) skill in
[`skills/handoff/`](skills/handoff/SKILL.md). Install it and Claude Code learns
when and how to drive handoff for you:

```bash
cp -r skills/handoff ~/.claude/skills/handoff      # user-level, or
cp -r skills/handoff .claude/skills/handoff        # project-level
```

Then just ask Claude Code to automate a task on a site you're logged into. It
runs `--dry-run` to preview the plan, keeps the human brake intact, and hands you
the exact command to run yourself when an action needs your approval — it will
never answer an approval prompt or use `--yolo` on your behalf.

---

## Approval modes

| Mode | Flag | Behaviour |
|------|------|-----------|
| **Gated** (default) | — | Prompt before every *sensitive* action; run safe ones automatically. |
| **Paranoid** | `--paranoid` | Prompt before *every* action. |
| **Dry run** | `--dry-run` | Never mutate; sensitive actions are auto-denied and reported. No API key needed to preview. |
| **Yolo** | `--yolo` | Never prompt. Opt-in only; prints a warning. |

What counts as **sensitive** (gated by default): navigating to a new site,
clicking a form submit / mutating control (`send`, `delete`, `pay`, `kirim`,
`hapus`, …), typing into a credential field, pressing Enter to submit, or
uploading a file. The classifier judges the *real element on the page*, not the
model's description of it. See [`handoff/approval.py`](handoff/approval.py).

---

## Security model

- **No credentials in the project.** You log in by hand; cookies live in a local
  profile dir (`.handoff-profile/`, git-ignored).
- **`.gitignore` hard-excludes** `.env`, the browser profile, `*.cookies`,
  `auth*.json`, `storage_state*.json`, screenshots, traces, and logs.
- **`.env.example` only** — never a real `.env`.
- **A secret-scanning preflight** refuses to commit API keys or session dumps:
  ```bash
  bash scripts/preflight.sh
  # or install as a hook:
  ln -s ../../scripts/preflight.sh .git/hooks/pre-commit
  ```
- **The agent is told never to type passwords/OTPs/card numbers**; if it hits a
  login wall it stops and asks you.

---

## Honest limitations

- It drives a real browser with vision + DOM — capable, but not magic. Complex,
  multi-page flows can still get stuck; that's what `ask_human` and the step
  limit are for.
- Sending a screenshot each step costs tokens. Use `--no-vision` for cheaper,
  DOM-only runs.
- The sensitivity classifier is deliberately conservative (it fails *safe* — an
  unknown action is treated as sensitive). It can over-ask; tune the word list in
  `approval.py` for your workflow.
- This is a focused framework, not a hosted product. There is no cloud, no
  proxy pool, no CAPTCHA solving — by design.

## Ethics & terms of use

handoff is for automating **your own authenticated sessions** on sites where you
are permitted to do so. Automating a site may violate its Terms of Service — that
is on you to check. Don't use it to mass-create accounts, scrape where it's
disallowed, evade access controls, or spam. The human-in-the-loop gate is there
to keep a person accountable for every outbound action; please keep it that way.

## License

MIT © 2026 Aldo Rizona. See [LICENSE](LICENSE).
