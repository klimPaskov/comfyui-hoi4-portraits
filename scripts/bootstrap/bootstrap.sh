#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$project_root/scripts/bootstrap/bootstrap.py" "$@"

