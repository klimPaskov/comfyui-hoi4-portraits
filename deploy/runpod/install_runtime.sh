#!/usr/bin/env bash
set -Eeuo pipefail

: "${PORTRAIT_PROJECT_ROOT:?PORTRAIT_PROJECT_ROOT is required}"

lock_path="$PORTRAIT_PROJECT_ROOT/dependencies/runtime_requirements_lock.json"
profile_lock="$PORTRAIT_PROJECT_ROOT/dependencies/runtime_profiles/linux_amd64_cuda128.lock.txt"
project_lock="$PORTRAIT_PROJECT_ROOT/dependencies/project_requirements.lock.txt"
if [ ! -f "$lock_path" ] || [ ! -f "$profile_lock" ] || [ ! -f "$project_lock" ]; then
  echo "runtime dependency lock or selected profile/project lock is missing" >&2
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

python3 - "$lock_path" "$profile_lock" "$project_lock" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

lock_path, profile_path, project_path = map(Path, sys.argv[1:])
lock = json.loads(lock_path.read_text(encoding="utf-8"))
profile = lock.get("profile_locks", {}).get("linux_amd64_cuda128", {})
project = lock.get("project_lock", {})
checks = ((profile_path, profile), (project_path, project))
for path, entry in checks:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if entry.get("status") != "RESOLVED" or actual != entry.get("sha256"):
        raise SystemExit(f"checksum-locked requirements mismatch: {path}")
PY

python3 -m venv /opt/portrait-venv
# The profile lock is generated with hashes and an explicit PyTorch/cu128
# index. No unpinned fallback or mirror is allowed here.
/opt/portrait-venv/bin/python -m pip install --require-hashes --no-deps -r "$profile_lock"
/opt/portrait-venv/bin/python -m pip install --require-hashes --no-deps -r "$project_lock"
/opt/portrait-venv/bin/python -m pip install --no-deps --no-build-isolation -e "$PORTRAIT_PROJECT_ROOT"
