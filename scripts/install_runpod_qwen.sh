#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_ROOT="${1:-${COMFYUI_ROOT:-}}"

if [[ -z "${COMFY_ROOT}" ]]; then
  for candidate in /workspace/ComfyUI /workspace/ComfyUI/comfyui /comfyui /opt/ComfyUI; do
    if [[ -f "${candidate}/main.py" ]]; then
      COMFY_ROOT="${candidate}"
      break
    fi
  done
fi

if [[ -z "${COMFY_ROOT}" || ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI was not found. Pass its directory as the first argument." >&2
  exit 23
fi

PYTHON_BIN=""
for candidate in \
  "${COMFY_ROOT}/.venv/bin/python" \
  "${COMFY_ROOT}/venv/bin/python" \
  /workspace/venv/bin/python; do
  if [[ -x "${candidate}" ]]; then
    PYTHON_BIN="${candidate}"
    break
  fi
done
if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python 3 was not found in the ComfyUI environment." >&2
  exit 20
fi

"${PYTHON_BIN}" -m pip install --require-hashes \
  -r "${PROJECT_ROOT}/dependencies/runpod_sidecar_requirements.lock.txt"

PYTHONPATH="${PROJECT_ROOT}/src:${PROJECT_ROOT}" \
  "${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/install_into_existing_comfyui.py" \
  --comfyui-root "${COMFY_ROOT}" \
  --profile hoi4_portraits_full_power_gpu \
  --workflow hoi4_portraits_prepare_portrait_qwen

echo
echo "Optional Qwen portrait preparation is installed."
