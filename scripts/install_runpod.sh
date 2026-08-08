#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GGUF_REVISION="6ea2651e7df66d7585f6ffee804b20e92fb38b8a"

VARIANTS=()
GGUF_QUANTS="Q5_K_M"
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANTS+=("$2")
      shift 2
      ;;
    --gguf-quants)
      GGUF_QUANTS="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: install_runpod.sh [COMFYUI_ROOT] [--variant full|fp8|gguf]... [--gguf-quants Q5_K_M,Q4_K_M,...]"
      echo "Defaults to the full FLUX.2 Klein 9B model."
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

COMFY_ROOT="${POSITIONAL[0]:-${COMFYUI_ROOT:-/workspace/runpod-slim/ComfyUI}}"
if [[ ${#VARIANTS[@]} -eq 0 ]]; then
  VARIANTS=(full)
fi
for variant in "${VARIANTS[@]}"; do
  case "$variant" in
    full|fp8|gguf) ;;
    *)
      echo "Unknown variant '$variant'. Use full, fp8, or gguf." >&2
      exit 1
      ;;
  esac
done

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

echo "Installing the hoi4_portraits node pack dependencies..."
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

if [[ " ${VARIANTS[*]} " == *" gguf "* ]]; then
  echo "Installing the ComfyUI-GGUF node pack for the GGUF variant..."
  GGUF_DIR="${COMFY_ROOT}/custom_nodes/ComfyUI-GGUF"
  if [[ -d "${GGUF_DIR}/.git" ]]; then
    git -C "${GGUF_DIR}" fetch --depth 1 origin "${GGUF_REVISION}"
  elif [[ -d "${GGUF_DIR}" ]]; then
    echo "${GGUF_DIR} exists but is not a Git checkout. Move it aside, then rerun this installer." >&2
    exit 1
  else
    git clone --filter=blob:none --no-checkout https://github.com/city96/ComfyUI-GGUF.git "${GGUF_DIR}"
    git -C "${GGUF_DIR}" fetch --depth 1 origin "${GGUF_REVISION}"
  fi
  git -C "${GGUF_DIR}" checkout --detach "${GGUF_REVISION}"
  "${PYTHON_BIN}" -m pip install -r "${GGUF_DIR}/requirements.txt"
fi

"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/install_workflows.py" --comfyui-root "${COMFY_ROOT}"

VARIANT_ARGS=()
for variant in "${VARIANTS[@]}"; do
  VARIANT_ARGS+=(--variant "${variant}")
done
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/apply_variant.py" \
  --comfyui-root "${COMFY_ROOT}" \
  "${VARIANT_ARGS[@]}" \
  --gguf-quants "${GGUF_QUANTS}"

DOWNLOAD_ARGS=()
for variant in "${VARIANTS[@]}"; do
  DOWNLOAD_ARGS+=(--variant "${variant}")
done
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/download_models.py" \
  --comfyui-root "${COMFY_ROOT}" \
  "${DOWNLOAD_ARGS[@]}" \
  --gguf-quants "${GGUF_QUANTS}"

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
for required in ("AdaptivePortraitCrop", "PortraitIdentityMask", "Hoi4PortraitSampler", "Hoi4BatchInput", "Hoi4SaveDDS"):
    if required not in module.NODE_CLASS_MAPPINGS:
        raise RuntimeError(f"{required} did not register")
print(f"Verified the hoi4_portraits node pack with {sys.executable}")
PY

echo
echo "Installed ${#VARIANTS[@]} model variant(s): ${VARIANTS[*]} (GGUF quants: ${GGUF_QUANTS})."
echo "Four workflows are under user/default/workflows/hoi4_portraits."
echo "Restart ComfyUI, then open Workflows > hoi4_portraits."
if [[ " ${VARIANTS[*]} " == *" full "* ]]; then
  echo "Note: the full model needs 24+ GB VRAM and a gated HF token (HF_TOKEN)."
fi
