#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${1:-${COMFYUI_ROOT:-/workspace/runpod-slim/ComfyUI}}"
if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI was not found at ${COMFY_ROOT}." >&2
  exit 1
fi

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
exec "${PYTHON_BIN}" main.py --listen 0.0.0.0 --port "${PORT:-8188}"
