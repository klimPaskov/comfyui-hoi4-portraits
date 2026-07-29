#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_ROOT="${1:-${COMFYUI_ROOT:-/workspace/ComfyUI}}"

if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI was not found at ${COMFY_ROOT}." >&2
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

export PYTHONPATH="${PROJECT_ROOT}/src:${PROJECT_ROOT}"
export HOI4_PORTRAIT_PROJECT_ROOT="${PROJECT_ROOT}"
export HOI4_SUBJECT_SERVICE_LOOPBACK="http://127.0.0.1:8790/v1/subject"
export HOI4_MASK_SERVICE_LOOPBACK="http://127.0.0.1:8790/v1/mask"
export HOI4_AUTOPROMPTER_LOOPBACK="http://127.0.0.1:8099/v1/chat/completions"

LOG_ROOT="${PROJECT_ROOT}/.runtime/logs"
mkdir -p "${LOG_ROOT}"

"${PYTHON_BIN}" -m portrait_pipeline.preprocessing_service \
  --root "${PROJECT_ROOT}" --host 127.0.0.1 --port 8790 --device cuda \
  >"${LOG_ROOT}/preprocessing.log" 2>&1 &
PREPROCESSING_PID=$!

"${PYTHON_BIN}" -m portrait_pipeline.autoprompter_service \
  --root "${PROJECT_ROOT}" --profile human_full_power_gpu \
  --host 127.0.0.1 --port 8099 \
  >"${LOG_ROOT}/autoprompter.log" 2>&1 &
AUTOPROMPTER_PID=$!

cleanup() {
  kill "${AUTOPROMPTER_PID}" 2>/dev/null || true
  kill "${PREPROCESSING_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "ComfyUI is starting on loopback at http://127.0.0.1:8188"
echo "Use an authenticated SSH tunnel; do not expose port 8188 publicly."
"${PYTHON_BIN}" "${COMFY_ROOT}/main.py" --listen 127.0.0.1 --port 8188
