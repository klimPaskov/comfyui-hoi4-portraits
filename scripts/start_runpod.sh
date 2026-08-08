#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMFY_ROOT="${1:-${COMFYUI_ROOT:-/workspace/runpod-slim/ComfyUI}}"
if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI was not found at ${COMFY_ROOT}." >&2
  exit 1
fi
COMFY_ROOT="$(cd "${COMFY_ROOT}" && pwd)"

PYTHON_BIN=""
if [[ -f "${COMFY_ROOT}/.hoi4_python" ]]; then
  SAVED_PYTHON="$(head -n 1 "${COMFY_ROOT}/.hoi4_python")"
  if [[ -x "${SAVED_PYTHON}" ]]; then
    PYTHON_BIN="${SAVED_PYTHON}"
  fi
fi
for candidate in \
  "${COMFY_ROOT}/.venv/bin/python" \
  "${COMFY_ROOT}/venv/bin/python" \
  "$(dirname "${COMFY_ROOT}")/.venv/bin/python" \
  "$(dirname "${COMFY_ROOT}")/venv/bin/python" \
  "${COMFY_ROOT}/python_embeded/python" \
  /workspace/runpod-slim/venv/bin/python \
  /workspace/venv/bin/python \
  /workspace/.venv/bin/python \
  /opt/pyvenv/bin/python; do
  if [[ -z "${PYTHON_BIN}" && -x "${candidate}" ]]; then
    PYTHON_BIN="${candidate}"
    break
  fi
done
if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

cd "${COMFY_ROOT}"
COMFY_PORT="${PORT:-8188}"
"${PYTHON_BIN}" main.py --listen 0.0.0.0 --port "${COMFY_PORT}" &
COMFY_PID=$!
trap 'kill "${COMFY_PID}" 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 120); do
  if curl -fsS "http://127.0.0.1:${COMFY_PORT}/object_info" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "${COMFY_PID}" 2>/dev/null; then
    wait "${COMFY_PID}"
  fi
  sleep 1
done

"${PYTHON_BIN}" "${SCRIPT_DIR}/validate_comfyui_registry.py" \
  --url "http://127.0.0.1:${COMFY_PORT}" \
  --comfyui-root "${COMFY_ROOT}"
wait "${COMFY_PID}"
