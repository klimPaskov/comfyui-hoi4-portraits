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

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "${PYTHON_BIN}" -r "${RES4LYF_DIR}/requirements.txt"
else
  "${PYTHON_BIN}" -m pip install -r "${RES4LYF_DIR}/requirements.txt"
fi

echo "Installed RES4LYF ${RES4LYF_REV}."
