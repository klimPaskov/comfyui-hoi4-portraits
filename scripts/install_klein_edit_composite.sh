#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${1:-${COMFYUI_ROOT:-}}"
COMPOSITE_URL="https://github.com/supermansundies/comfyui-klein-edit-composite.git"
COMPOSITE_REV="1505bc58d38abf5411457804ed4923e83f986eee"

if [[ -z "${COMFY_ROOT}" || ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "Pass the ComfyUI root containing main.py as the first argument." >&2
  exit 1
fi

COMPOSITE_DIR="${COMFY_ROOT}/custom_nodes/comfyui-klein-edit-composite"
mkdir -p "${COMFY_ROOT}/custom_nodes"
if [[ -d "${COMPOSITE_DIR}/.git" ]]; then
  git -C "${COMPOSITE_DIR}" fetch --depth 1 origin "${COMPOSITE_REV}"
elif [[ -e "${COMPOSITE_DIR}" ]]; then
  echo "${COMPOSITE_DIR} exists but is not a Git checkout. Move it aside, then rerun this installer." >&2
  exit 1
else
  git clone --filter=blob:none --no-checkout "${COMPOSITE_URL}" "${COMPOSITE_DIR}"
  git -C "${COMPOSITE_DIR}" fetch --depth 1 origin "${COMPOSITE_REV}"
fi
git -C "${COMPOSITE_DIR}" checkout --detach "${COMPOSITE_REV}"

if ! git -C "${COMPOSITE_DIR}" grep -q '"KleinEditComposite"' -- '*.py'; then
  echo "The pinned composite checkout does not register KleinEditComposite." >&2
  exit 1
fi
echo "Installed comfyui-klein-edit-composite ${COMPOSITE_REV}."
