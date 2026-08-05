#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${1:-${COMFYUI_ROOT:-}}"
PYTHON_BIN="${2:-}"
RES4LYF_URL="https://github.com/ClownsharkBatwing/RES4LYF.git"
RES4LYF_REV="e716cd1cb2c5cff90131bf4914b75b75a0489d48"

if [[ -z "${COMFY_ROOT}" || ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "Pass the ComfyUI root containing main.py as the first argument." >&2
  exit 1
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

RES4LYF_DIR="${COMFY_ROOT}/custom_nodes/RES4LYF"
mkdir -p "${COMFY_ROOT}/custom_nodes"
if [[ -d "${RES4LYF_DIR}/.git" ]]; then
  git -C "${RES4LYF_DIR}" fetch --depth 1 origin "${RES4LYF_REV}"
elif [[ -e "${RES4LYF_DIR}" ]]; then
  echo "${RES4LYF_DIR} exists but is not a Git checkout. Move it aside, then rerun this installer." >&2
  exit 1
else
  git clone --filter=blob:none --no-checkout "${RES4LYF_URL}" "${RES4LYF_DIR}"
  git -C "${RES4LYF_DIR}" fetch --depth 1 origin "${RES4LYF_REV}"
fi
git -C "${RES4LYF_DIR}" checkout --detach "${RES4LYF_REV}"

# RES samplers use float64 for scalar math, but Apple MPS cannot allocate a
# float64 tensor. Keep upstream precision on CUDA/CPU and select float32 only
# when the active sampling device is MPS.
"${PYTHON_BIN}" - "${RES4LYF_DIR}/beta/rk_sampler_beta.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
needle = "    work_device    = 'cpu' if EO(\"work_device_cpu\") else model_device\n"
guard = (
    needle
    + "    if getattr(work_device, \"type\", str(work_device)) == \"mps\":\n"
    + "        default_dtype = torch.float32\n"
)
if guard not in source:
    if needle not in source:
        raise SystemExit(f"Cannot apply the RES4LYF MPS compatibility guard to {path}")
    path.write_text(source.replace(needle, guard, 1), encoding="utf-8")
print("Applied the RES4LYF Apple MPS precision guard.")
PY

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "${PYTHON_BIN}" -r "${RES4LYF_DIR}/requirements.txt"
else
  "${PYTHON_BIN}" -m pip install -r "${RES4LYF_DIR}/requirements.txt"
fi

echo "Installed RES4LYF ${RES4LYF_REV}."
