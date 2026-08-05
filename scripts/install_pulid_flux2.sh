#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${1:-${COMFYUI_ROOT:-}}"
PYTHON_BIN="${2:-}"
PULID_URL="https://github.com/iFayens/ComfyUI-PuLID-Flux2.git"
PULID_REV="3a0a3f5f18260fc914f96a8c7f0f23c835e881cd"
EVA_REPO="timm/eva02_large_patch14_clip_336.merged2b_s6b_b61k"
EVA_REV="4f62907359c8506be7021582f360564693b22c15"
EVA_FILE="open_clip_pytorch_model.bin"
EVA_SHA256="5f9d2086d150e0748d970ffd33c785bc7e480a5770098b599ea8cfa864b4f315"

if [[ -z "${COMFY_ROOT}" || ! -f "${COMFY_ROOT}/main.py" ]]; then
  echo "Pass the ComfyUI root containing main.py as the first argument." >&2
  exit 1
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

PULID_DIR="${COMFY_ROOT}/custom_nodes/ComfyUI-PuLID-Flux2"
mkdir -p "${COMFY_ROOT}/custom_nodes"
if [[ -d "${PULID_DIR}/.git" ]]; then
  git -C "${PULID_DIR}" fetch --depth 1 origin "${PULID_REV}"
elif [[ -e "${PULID_DIR}" ]]; then
  echo "${PULID_DIR} exists but is not a Git checkout. Move it aside, then rerun this installer." >&2
  exit 1
else
  git clone --filter=blob:none --no-checkout "${PULID_URL}" "${PULID_DIR}"
  git -C "${PULID_DIR}" fetch --depth 1 origin "${PULID_REV}"
fi
git -C "${PULID_DIR}" checkout --detach "${PULID_REV}"

PACKAGES=(
  "insightface==1.0.1"
  "onnxruntime-gpu>=1.16.0"
  "open-clip-torch==3.2.0"
  "safetensors>=0.4.0"
  "huggingface_hub>=0.34.0"
  "hf_xet>=1.1.0"
  "numpy<2.0.0"
  "ml_dtypes==0.3.2"
)
if command -v uv >/dev/null 2>&1; then
  uv pip install --python "${PYTHON_BIN}" "${PACKAGES[@]}"
else
  "${PYTHON_BIN}" -m pip install "${PACKAGES[@]}"
fi

if ! "${PYTHON_BIN}" - <<'PY'
import onnxruntime
raise SystemExit(0 if "CUDAExecutionProvider" in onnxruntime.get_available_providers() else 1)
PY
then
  "${PYTHON_BIN}" -m pip uninstall -y onnxruntime onnxruntime-gpu || true
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${PYTHON_BIN}" "onnxruntime-gpu>=1.16.0"
  else
    "${PYTHON_BIN}" -m pip install "onnxruntime-gpu>=1.16.0"
  fi
fi
"${PYTHON_BIN}" - <<'PY'
import onnxruntime
providers = onnxruntime.get_available_providers()
if "CUDAExecutionProvider" not in providers:
    raise SystemExit(f"PuLID requires ONNX Runtime CUDA on this RunPod: {providers}")
print("Verified ONNX Runtime CUDA for PuLID.")
PY

EVA_REPO="${EVA_REPO}" EVA_REV="${EVA_REV}" EVA_FILE="${EVA_FILE}" EVA_SHA256="${EVA_SHA256}" \
  "${PYTHON_BIN}" - <<'PY'
import hashlib
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

repo = os.environ["EVA_REPO"]
revision = os.environ["EVA_REV"]
filename = os.environ["EVA_FILE"]
expected = os.environ["EVA_SHA256"]
path = Path(hf_hub_download(repo_id=repo, filename=filename, revision=revision))
hasher = hashlib.sha256()
with path.open("rb") as handle:
    while chunk := handle.read(8 * 1024 * 1024):
        hasher.update(chunk)
digest = hasher.hexdigest()
if digest != expected:
    raise SystemExit(f"EVA-CLIP integrity check failed: {digest}")
# Populate the repository's normal cache reference as well. open_clip requests
# the repository without a revision when its loader starts.
hf_hub_download(repo_id=repo, filename=filename)
print(f"Prepared EVA-CLIP at {path}")
PY

if ! git -C "${PULID_DIR}" grep -q '"ApplyPuLIDFlux2"' -- '*.py'; then
  echo "The pinned PuLID checkout does not register ApplyPuLIDFlux2." >&2
  exit 1
fi
"${PYTHON_BIN}" -c "import insightface, onnxruntime, open_clip, safetensors"
echo "Installed ComfyUI-PuLID-Flux2 ${PULID_REV}."
