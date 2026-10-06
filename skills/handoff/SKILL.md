---
name: handoff
description: >-
  Drive a browser the user is ALREADY logged into, with a human approval gate on
  every irreversible action. Use when the user asks to automate a task on a
  website where they have an account — fill a form, pull data from behind a
  login, repeat a web workflow, check a dashboard — and wants to stay in control
  (approve submits/sends/payments/deletes). Do NOT use it to scrape public pages
  (use a fetch tool), to log in on the user's behalf, or for anything the user is
  not authorised to do on that site.
---

# handoff — human-in-the-loop browser automation

`handoff` runs a Claude agent that drives a browser the **user logged into by
hand**. A default-on gate stops every sensitive action (submit, send, pay,
delete, cross-site navigation) and asks the human to approve it. Your job from
Claude Code is to set it up and run it correctly — never to bypass the gate.

## Before anything: check prerequisites

```bash
handoff --help            # installed?
echo "$ANTHROPIC_API_KEY" # key present? (needed for run, not for --dry-run)
```

If not installed:

```bash
pip install -e .          # from the repo root
playwright install chromium
```

## Step 1 — the user logs in (never you)

handoff never handles passwords. The human authenticates by hand, once. Ask the
user to run this in THEIR terminal (in Claude Code they can prefix with `! `):

```bash
handoff login --url https://the-site.example
```

They log in, press Enter, and the session is saved to a local, git-ignored
`.handoff-profile/`. Do not attempt to type their credentials yourself.

## Step 2 — run the task

**You (Claude Code) may run `--dry-run` directly** to preview the plan and do
read-only exploration — it never mutates and auto-denies sensitive actions, so it
needs no human at the keyboard:

```bash
handoff run "find the latest invoice and report its total" \
    --url https://the-site.example --dry-run
```

**For real execution, the USER runs it in their own terminal**, because the
approval prompts (`y/N`) need a human to answer. Hand them the exact command:

```bash
handoff run "update my availability to 'open to work'" --url https://the-site.example
# add --paranoid to confirm EVERY action; add --no-vision to run cheaper (DOM-only)
```

Never run with `--yolo` on the user's behalf, and never answer an approval prompt
for them.

## Reading the result

The run ends with `summary`, `success` (true/false), and the final URL. Report
these honestly — if `success` is false or the summary says a step was skipped or
denied, say so; do not claim a task completed that handoff did not verify.

## Safety

- Only automate sites the user is authorised to use; automating a site may
  violate its Terms of Service — flag that, don't decide it for them.
- Keep the gate on. It exists so a person stays accountable for every outbound
  action. Suggesting `--yolo` defeats the point of the tool.
