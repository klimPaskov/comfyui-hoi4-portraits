# Local and RunPod installation

## Requirements

- ComfyUI with FLUX.2 Klein support.
- Python 3.10 or newer for the helper scripts.
- The 21 pinned model files occupy 24.06 GB decimal (22.40 GiB). PuLID also
  prepares an 0.86 GB EVA-CLIP weight in the Hugging Face cache. A 30 GB
  RunPod volume is sufficient for the comparison package; keep generated
  outputs tidy while testing. The downloader writes directly to the ComfyUI
  model folders and does not create a second model copy.
- A 24 GB GPU is a sufficient practical target for the FP8 workflows with
  normal offloading. An 18 GB GPU may work with more aggressive offloading and
  a reduced test canvas; 16 GB can work similarly but is slow.
  The upstream model card's roughly 29 GB figure is a conservative
  full-resolution/no-offload guideline, not a hard minimum for this FP8 graph.
- A Hugging Face account that has accepted the gated FLUX.2 Klein agreement.

## Install into an existing ComfyUI

```bash
python scripts/build_workflows.py
python scripts/validate_workflows.py
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
scripts/install_res4lyf.sh /path/to/ComfyUI
scripts/install_flux2_klein_enhancer.sh /path/to/ComfyUI
scripts/install_pulid_flux2.sh /path/to/ComfyUI /path/to/ComfyUI/python
scripts/install_klein_edit_composite.sh /path/to/ComfyUI
python scripts/download_models.py --comfyui-root /path/to/ComfyUI
```

The installer copies the three primary workflows and nine identity comparison
workflows, installs their pinned extensions, and adds the bundled backgrounds
and one sample source image. It does not replace the existing ComfyUI
installation.

The [latest release](https://github.com/klimPaskov/comfyui-hoi4-portraits/releases/latest)
also includes a model-free ZIP, a Windows x64 self-extractor, and the RunPod
runtime archive. The executable only unpacks the project; ComfyUI and model
weights remain separate.

The downloader transfers independent model files in parallel, uses Hugging
Face's accelerated resumable transport, and validates every downloaded model
against the locked project metadata.

## Hugging Face authentication

Before downloading the gated base model:

1. Open the [FLUX.2 Klein base 9B FP8 page](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B-fp8).
2. Accept the model agreement.
3. Create a [read-only Hugging Face token](https://huggingface.co/settings/tokens/new?tokenType=read).
4. Run `hf auth login`, or set `HF_TOKEN` in the shell that runs the downloader.

See the [Hugging Face guide](hugging-face.md) for local and RunPod setup. No
token is written into this repository or a workflow.

## RunPod

On a RunPod image that already contains ComfyUI, the installer places the
workflows in `user/default/workflows/hoi4_portraits`, installs the project nodes
in `custom_nodes/hoi4_portraits`, installs the pinned RES4LYF
samplers in `custom_nodes/RES4LYF`, installs identity preservation in
`custom_nodes/ComfyUI-Flux2Klein-Enhancer`, installs PuLID and Klein edit
compositing, copies the backgrounds and
sample input into `input/`, and downloads every entry in `models.json` to
the exact ComfyUI model folders (`diffusion_models`, `text_encoders`, `vae`,
`loras`, `upscale_models`, and `background_removal`):

```bash
(
set -euo pipefail
export HF_TOKEN="hf_..."
COMFY_ROOT=/workspace/runpod-slim/ComfyUI
RUNTIME_DIR=/workspace/hoi4-portrait-runpod
test -f "$COMFY_ROOT/main.py" || { echo "ComfyUI not found at $COMFY_ROOT; set COMFY_ROOT to the folder containing main.py."; exit 1; }
mkdir -p "$RUNTIME_DIR"
curl -fsSL "https://github.com/klimPaskov/comfyui-hoi4-portraits/releases/latest/download/HOI4-Portrait-RunPod.tar.gz" | tar -xz -C "$RUNTIME_DIR"
"$RUNTIME_DIR/scripts/install_runpod.sh" "$COMFY_ROOT"
)
```

The final verification pass validates all 21 files. If a download is
interrupted or a file was placed in the wrong folder,
the installer stops instead of silently using it. `HF_TOKEN` is read only from
the process environment and is never printed or saved. Confirm that
`COMFY_ROOT` is the folder containing `main.py`; the `runpod-slim` template
uses `/workspace/runpod-slim/ComfyUI`.

Start ComfyUI after installation:

```bash
/workspace/hoi4-portrait-runpod/scripts/start_runpod.sh /workspace/runpod-slim/ComfyUI
```

Startup validates ComfyUI's live node registry before it stays online. It
stops with the exact missing node or sampler name if the installation did not
load correctly.

Supply `HF_TOKEN` to the pod environment before installation. The script does
not print the token.

## Windows

From PowerShell:

```powershell
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI"
```

The release self-extractor accepts an empty destination directory:

```powershell
.\HOI4-Portrait-Workflows-2.6.1-windows-x64.exe -destination "C:\Users\you\Documents\HOI4-Portrait-Workflows-v2.6.1"
```

Use `-SkipModels` if the model files are already installed. Start with:

```powershell
.\scripts\start_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI"
```

## Verify without downloading

```bash
python scripts/download_models.py --comfyui-root /path/to/ComfyUI --verify-only
```

To verify or download only one file, repeat `--only` with its exact filename.

## PNG to DDS

The workflows intentionally save PNG. Convert an approved 156 × 210 PNG to
DDS separately:

```bash
python -m pip install "Pillow>=10"
python scripts/convert/png_to_dds.py input.png output.dds
```

The helper writes an uncompressed 32-bit BGRA DDS with no mipmaps. Keep the
PNG if another modding tool or your game setup expects a different DDS
compression format.
