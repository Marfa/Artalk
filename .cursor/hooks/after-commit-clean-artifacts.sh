#!/usr/bin/env bash
# Cursor afterShellExecution: clean stale artifacts after a successful git commit.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
input=$(cat || true)

cmd=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print((d.get("command") or d.get("shell_command") or "").replace("\n", " "))
')
status=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(d.get("exit_code", d.get("exitCode", d.get("status", 0))))
')

if [ "$status" != "0" ]; then
  echo '{}'
  exit 0
fi

case "$cmd" in
  *git\ commit*|*"git commit"*) ;;
  *)
    echo '{}'
    exit 0
    ;;
esac

python3 "$ROOT/scripts/clean_old_artifacts.py" --root "$ROOT" >&2 || true
echo '{}'
