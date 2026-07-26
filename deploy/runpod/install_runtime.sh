#!/usr/bin/env bash
set -Eeuo pipefail

: "${PORTRAIT_PROJECT_ROOT:?PORTRAIT_PROJECT_ROOT is required}"

lock_path="$PORTRAIT_PROJECT_ROOT/dependencies/runtime_requirements_lock.json"
profile_lock="$PORTRAIT_PROJECT_ROOT/dependencies/runtime_profiles/linux_amd64_cuda128.lock.txt"
if [ ! -f "$lock_path" ] || [ ! -f "$profile_lock" ]; then
  echo "runtime dependency lock or profile lock is missing" >&2
  exit 20
fi

lock_status="$(python3 - "$lock_path" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data.get("status", ""))
PY
)"
case "$lock_status" in
  RESOLVED|RESOLVED_*) ;;
  *)
  echo "runtime dependency lock is not RESOLVED; installation refused" >&2
  exit 20
  ;;
esac

python3 -m venv /opt/portrait-venv
# The profile lock is generated with hashes and an explicit PyTorch/cu128
# index. No unpinned fallback or mirror is allowed here.
/opt/portrait-venv/bin/python -m pip install --require-hashes --no-deps -r "$profile_lock"
/opt/portrait-venv/bin/python -m pip install --require-hashes -e "$PORTRAIT_PROJECT_ROOT"
