#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_ROOT="${1:-${COMFYUI_ROOT:-/workspace/runpod-slim/ComfyUI}}"

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

"${PROJECT_ROOT}/scripts/install_res4lyf.sh" "${COMFY_ROOT}" "${PYTHON_BIN}"

if ! "${PYTHON_BIN}" -c "import cv2, scipy" >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${PYTHON_BIN}" -r "${PROJECT_ROOT}/custom_nodes/adaptive_portrait_crop/requirements.txt"
  else
    "${PYTHON_BIN}" -m pip install -r "${PROJECT_ROOT}/custom_nodes/adaptive_portrait_crop/requirements.txt"
  fi
fi

if ! "${PYTHON_BIN}" -c "import huggingface_hub, hf_xet" >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${PYTHON_BIN}" -r "${PROJECT_ROOT}/scripts/requirements-download.txt"
  else
    "${PYTHON_BIN}" -m pip install -r "${PROJECT_ROOT}/scripts/requirements-download.txt"
  fi
fi

"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/build_workflows.py"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/validate_workflows.py"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/install_workflows.py" --comfyui-root "${COMFY_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/download_models.py" --comfyui-root "${COMFY_ROOT}"

echo
echo "Installed three FLUX.2 Klein 9B workflows, the adaptive crop, RES4LYF samplers, and all 15 pinned model files, including every LoRA test checkpoint."
echo "Models are under ${COMFY_ROOT}/models/{diffusion_models,text_encoders,vae,loras,upscale_models,background_removal,detection}."
echo "Open Workflows > hoi4_portraits after restarting ComfyUI."
