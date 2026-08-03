#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_ROOT="${1:-${COMFYUI_ROOT:-/workspace/ComfyUI}}"

if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI was not found at ${COMFY_ROOT}. Pass its root as the first argument." >&2
  exit 1
fi

PYTHON_BIN=""
for candidate in \
  "${COMFY_ROOT}/.venv/bin/python" \
  "${COMFY_ROOT}/venv/bin/python" \
  "${COMFY_ROOT}/python_embeded/python" \
  /workspace/venv/bin/python \
  /workspace/.venv/bin/python \
  /opt/pyvenv/bin/python; do
  if [[ -x "${candidate}" ]]; then
    PYTHON_BIN="${candidate}"
    break
  fi
done
if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/build_workflows.py"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/validate_workflows.py"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/install_workflows.py" --comfyui-root "${COMFY_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/download_models.py" --comfyui-root "${COMFY_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/download_models.py" --comfyui-root "${COMFY_ROOT}" --verify-only

echo
echo "Installed three FLUX.2 Klein 9B workflows, all six pinned model files, and no custom nodes."
echo "Models are under ${COMFY_ROOT}/models/{diffusion_models,text_encoders,vae,loras,upscale_models,background_removal}."
echo "Open Workflows > hoi4_portraits after restarting ComfyUI."
