# Local and RunPod installation

## Requirements

- ComfyUI with FLUX.2 Klein support.
- Python 3.10 or newer for the helper scripts.
- About 20 GB free for the pinned model files, plus output/cache space.
- A practical 32 GB+ GPU target for FLUX.2 Klein 9B image editing; the upstream
  model card reports roughly 29 GB VRAM for the base model.
- A Hugging Face account that has accepted the gated FLUX.2 Klein agreement.

## Install into an existing ComfyUI

```bash
python scripts/build_workflows.py
python scripts/validate_workflows.py
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
python scripts/download_models.py --comfyui-root /path/to/ComfyUI
```

The installer copies three editor workflows, the bundled backgrounds, and one
sample source image. It does not replace the existing ComfyUI installation.

The downloader checks every existing file against its locked byte size and
SHA-256. It refuses to overwrite a mismatching file.

## Hugging Face authentication

Before downloading the gated base model:

1. Open the [FLUX.2 Klein base 9B FP8 page](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B-fp8).
2. Accept the model agreement.
3. Run `hf auth login`, or set `HF_TOKEN` in the shell that runs the downloader.

No token is written into this repository or a workflow.

## RunPod

On a RunPod image that already contains ComfyUI:

```bash
bash -lc 'P=/workspace/comfyui-hoi4-portraits; test -d "$P/.git" || git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git "$P"; "$P/scripts/install_runpod.sh" /workspace/ComfyUI'
```

Start ComfyUI:

```bash
/workspace/comfyui-hoi4-portraits/scripts/start_runpod.sh /workspace/ComfyUI
```

Supply `HF_TOKEN` to the pod environment before installation. The script does
not print the token.

## Windows

From PowerShell:

```powershell
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI"
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
