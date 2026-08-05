#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${1:-${COMFYUI_ROOT:-}}"
ENHANCER_URL="https://github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer.git"
ENHANCER_REV="6804643bff9a20926106427ff08d5b1bd2e49861"

if [[ -z "${COMFY_ROOT}" || ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "Pass the ComfyUI root containing main.py as the first argument." >&2
  exit 1
fi

ENHANCER_DIR="${COMFY_ROOT}/custom_nodes/ComfyUI-Flux2Klein-Enhancer"
mkdir -p "${COMFY_ROOT}/custom_nodes"
if [[ -d "${ENHANCER_DIR}/.git" ]]; then
  git -C "${ENHANCER_DIR}" fetch --depth 1 origin "${ENHANCER_REV}"
elif [[ -e "${ENHANCER_DIR}" ]]; then
  echo "${ENHANCER_DIR} exists but is not a Git checkout. Move it aside, then rerun this installer." >&2
  exit 1
else
  git clone --filter=blob:none --no-checkout "${ENHANCER_URL}" "${ENHANCER_DIR}"
  git -C "${ENHANCER_DIR}" fetch --depth 1 origin "${ENHANCER_REV}"
fi
git -C "${ENHANCER_DIR}" checkout --detach "${ENHANCER_REV}"

if ! git -C "${ENHANCER_DIR}" grep -q '"IdentityFeatureTransferFinal"' -- '*.py'; then
  echo "The pinned FLUX.2 Klein Enhancer checkout does not contain IdentityFeatureTransferFinal." >&2
  exit 1
fi

echo "Installed ComfyUI-Flux2Klein-Enhancer ${ENHANCER_REV}."
