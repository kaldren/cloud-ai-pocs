#!/usr/bin/env bash
# PreToolUse guard for Bash: keeps Claude from skipping the secret-scanning git hooks.
# Exit 2 blocks the tool call and shows stderr to Claude.
set -euo pipefail

cmd=$(jq -r '.tool_input.command // ""')

# Only care about commands that commit or push.
grep -qE '\bgit\b.*\b(commit|push)\b' <<<"$cmd" || exit 0

block() {
  echo "Blocked by .claude/hooks/guard-git.sh: $1" >&2
  exit 2
}

if grep -qE -- '--no-verify\b' <<<"$cmd"; then
  block "--no-verify skips the secret scan. Remove the secret instead of bypassing the hook."
fi

if grep -qE '\bcommit\b.*[[:space:]]-[a-zA-Z]*n[a-zA-Z]*\b' <<<"$cmd"; then
  block "'git commit -n' skips the secret scan. Remove the secret instead of bypassing the hook."
fi

if grep -qE 'core\.hooksPath' <<<"$cmd" && ! grep -qE 'core\.hooksPath[= ]+\.githooks\b' <<<"$cmd"; then
  block "Overriding core.hooksPath disables the secret-scanning hooks."
fi

repo=${CLAUDE_PROJECT_DIR:-.}
if [[ "$(git -C "$repo" config --get core.hooksPath || true)" != ".githooks" ]]; then
  block "Secret-scanning hooks are not enabled. Ask the user to run: brew install betterleaks && git config core.hooksPath .githooks"
fi

exit 0
