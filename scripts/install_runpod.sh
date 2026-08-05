#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_ROOT="${1:-${COMFYUI_ROOT:-/workspace/runpod-slim/ComfyUI}}"

if [[ ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "ComfyUI was not found at ${COMFY_ROOT}. Pass its root as the first argument." >&2
  exit 1
fi
COMFY_ROOT="$(cd "${COMFY_ROOT}" && pwd)"

PYTHON_BIN=""
if command -v pgrep >/dev/null 2>&1; then
  COMFY_PID="$(pgrep -f '[p]ython.*[m]ain.py' | head -n 1 || true)"
  if [[ -n "${COMFY_PID}" ]]; then
    RUNNING_PYTHON="$(readlink -f "/proc/${COMFY_PID}/exe" 2>/dev/null || true)"
    if [[ -x "${RUNNING_PYTHON}" ]]; then
      PYTHON_BIN="${RUNNING_PYTHON}"
    fi
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
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "No usable Python interpreter was found for ComfyUI." >&2
  exit 1
fi
printf '%s\n' "${PYTHON_BIN}" > "${COMFY_ROOT}/.hoi4_python"

"${PROJECT_ROOT}/scripts/install_res4lyf.sh" "${COMFY_ROOT}" "${PYTHON_BIN}"
RES4LYF_DIR="${COMFY_ROOT}/custom_nodes/RES4LYF"
if ! git -C "${RES4LYF_DIR}" grep -q 'res_2s' -- '*.py' || \
   ! git -C "${RES4LYF_DIR}" grep -q 'res_2m' -- '*.py'; then
  echo "The installed RES4LYF checkout does not contain the required res_2s and res_2m samplers." >&2
  exit 1
fi
echo "Verified the pinned RES4LYF sampler sources. ComfyUI registers them during restart."

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "${PYTHON_BIN}" -r "${PROJECT_ROOT}/custom_nodes/hoi4_portraits/requirements.txt"
else
  "${PYTHON_BIN}" -m pip install -r "${PROJECT_ROOT}/custom_nodes/hoi4_portraits/requirements.txt"
fi

if ! "${PYTHON_BIN}" -c "import huggingface_hub, hf_xet" >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${PYTHON_BIN}" -r "${PROJECT_ROOT}/scripts/requirements-download.txt"
  else
    "${PYTHON_BIN}" -m pip install -r "${PROJECT_ROOT}/scripts/requirements-download.txt"
  fi
fi

"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/install_workflows.py" --comfyui-root "${COMFY_ROOT}"
COMFY_ROOT="${COMFY_ROOT}" "${PYTHON_BIN}" - <<'PY'
import importlib.util
import os
import sys
from pathlib import Path

comfy_root = Path(os.environ["COMFY_ROOT"])
sys.path.insert(0, str(comfy_root))
node_path = comfy_root / "custom_nodes" / "hoi4_portraits" / "__init__.py"
spec = importlib.util.spec_from_file_location("hoi4_portraits", node_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {node_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if "AdaptivePortraitCrop" not in module.NODE_CLASS_MAPPINGS:
    raise RuntimeError("AdaptivePortraitCrop did not register")
if "Flux2PortraitSampler" not in module.NODE_CLASS_MAPPINGS:
    raise RuntimeError("Flux2PortraitSampler did not register")
print(f"Verified the hoi4_portraits node pack with {sys.executable}")
PY
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/download_models.py" --comfyui-root "${COMFY_ROOT}"

echo
echo "Installed three FLUX.2 Klein 9B workflows, the hoi4_portraits node pack, RES4LYF samplers, and all 15 pinned model files, including every LoRA test checkpoint."
echo "Models are under ${COMFY_ROOT}/models/{diffusion_models,text_encoders,vae,loras,upscale_models,background_removal,detection}."
echo "Open Workflows > hoi4_portraits after restarting ComfyUI."
