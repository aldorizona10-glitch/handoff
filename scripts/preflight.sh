#!/usr/bin/env bash
# preflight.sh — refuse to commit secrets or authenticated sessions.
#
# Scans the files git is about to track for things that must never be pushed:
# API keys, .env files, browser-profile cookies, auth/storage-state dumps, and
# obvious private tokens. Exit non-zero if anything is found.
#
# Use as a pre-commit hook:  ln -s ../../scripts/preflight.sh .git/hooks/pre-commit
# or run manually:           bash scripts/preflight.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Files staged for commit (fall back to all tracked files when run manually).
mapfile -t FILES < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
if [ "${#FILES[@]}" -eq 0 ]; then
  mapfile -t FILES < <(git ls-files)
fi

fail=0
note() { echo "  ✗ $1"; fail=1; }

for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  case "$f" in
    .env|.env.*|*.env)
      [ "$f" = ".env.example" ] || note "env file staged: $f (should be git-ignored)";;
    *handoff-profile/*|*cookies.json|auth*.json|storage_state*.json)
      note "authenticated session artifact staged: $f";;
  esac

  # Content scan (skip the example + this scanner itself).
  case "$f" in
    .env.example|scripts/preflight.sh) continue;;
  esac
  if grep -Eq 'sk-ant-[A-Za-z0-9_-]{8,}' "$f"; then
    note "Anthropic API key literal in $f"
  fi
  if grep -Eq '(secret|api[_-]?key|token|password)[\"'"'"' ]*[:=][\"'"'"' ]*[A-Za-z0-9/_+-]{16,}' "$f"; then
    note "possible hard-coded credential in $f"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "preflight FAILED — fix the above before committing."
  exit 1
fi
echo "preflight OK — no secrets or sessions staged."
