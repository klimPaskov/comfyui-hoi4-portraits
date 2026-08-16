# Local, RunPod, and Windows installation

## Requirements

- ComfyUI with FLUX.2 Klein support.
- Python 3.10 or newer for the helper scripts.
- A Hugging Face account that has accepted the gated FLUX.2 Klein agreement (only needed for the full and FP8 variants; GGUF is not gated).

## Storage and VRAM requirements

The installer downloads the selected distilled model plus Qwen, the VAE, the 2500-step HOI4 style LoRA, Adonis Base, Refine, Post, RealESRGAN, BiRefNet, and both face detectors. Each minimum leaves about 2–3 GB of free space for installation and initial outputs.

| Install | Variant file | Minimum storage | VRAM selection |
| --- | --- | --- | --- |
| Full distilled | `flux-2-klein-9b.safetensors` | 34 GB | more than 20 GB |
| FP8 distilled | `flux-2-klein-9b-fp8.safetensors` | 25 GB | 16–20 GB |
| GGUF distilled Q4_K_M | `flux-2-klein-9b-Q4_K_M.gguf` | 21 GB | 8–10 GB |
| GGUF distilled Q5_K_M | `flux-2-klein-9b-Q5_K_M.gguf` | 22 GB | 10–14 GB |
| GGUF distilled Q6_K | `flux-2-klein-9b-Q6_K.gguf` | 23 GB | 12–16 GB |
| GGUF distilled Q8_0 | `flux-2-klein-9b-Q8_0.gguf` | 25.5 GB | 16+ GB |

The Windows installer defaults to **FP8** at every detected VRAM size. The detected VRAM remains visible so you can select GGUF for an 8–16 GB GPU or full BF16 above 20 GB.

- **8–16 GB** → GGUF is available, with an automatically suggested quantization
- **16 GB or more** → the default FP8 selection is appropriate
- **more than 20 GB** → full BF16 is available as an optional selection

The Qwen text encoder is 8.7 GB and is shared by every variant. ComfyUI offloads it to system RAM when VRAM is tight, so 8 GB GPUs work but are slow.

## Install into an existing ComfyUI

```bash
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
python scripts/install_custom_node_packs.py --comfyui-root /path/to/ComfyUI
python scripts/apply_variant.py --comfyui-root /path/to/ComfyUI --variant fp8
python -m pip install -r scripts/requirements-download.txt
python scripts/download_models.py --comfyui-root /path/to/ComfyUI --variant fp8
```

All three choices use the distilled FLUX.2 Klein 9B model; FP8 and GGUF are lower-precision forms of the same distilled weights. The setup script changes the visible diffusion-model loader in every installed workflow:

- `--variant full` → `flux-2-klein-9b.safetensors`
- `--variant fp8` → `flux-2-klein-9b-fp8.safetensors`
- `--variant gguf --gguf-quants Q5_K_M` → the selected `flux-2-klein-9b-*.gguf` quantization

The workflow uses the native safetensors loader or the pinned [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) diffusion loader at runtime according to the filename.

Pass `--variant` multiple times to prepare several variants; the first is applied to the four main workflows and the rest are emitted as ready-made `*_fp8.json` / `*_gguf.json` copies.

## RunPod

On a RunPod image that already contains ComfyUI, the installer places the four workflows in `user/default/workflows/hoi4_portraits`, installs the project node pack plus the pinned Adonis/RES4LYF dependencies, copies the bundled backgrounds and sample source into `input/`, connects the batch and portrait output folders to the runtime workspace, and downloads the selected models:

Open a Jupyter terminal on the pod and run:

```bash
(
set -euo pipefail
export HF_TOKEN="hf_..."
COMFY_ROOT=/workspace/runpod-slim/ComfyUI
RUNTIME_DIR=/workspace/hoi4-portrait-runpod
test -f "$COMFY_ROOT/main.py" || { echo "ComfyUI not found at $COMFY_ROOT; set COMFY_ROOT to the folder containing main.py."; exit 1; }
mkdir -p "$RUNTIME_DIR"
curl -fsSL "https://github.com/klimPaskov/comfyui-hoi4-portraits/releases/latest/download/HOI4-Portrait-RunPod.tar.gz" | tar -xz -C "$RUNTIME_DIR"
"$RUNTIME_DIR/scripts/install_runpod.sh" "$COMFY_ROOT" --variant fp8
)
```

Drop batch sources into `/workspace/hoi4-portrait-runpod/input/`. Each queue creates matching `<batch_name>` folders under `1024x1365` and `156x210`. Full-resolution master, prepared, and restored PNGs use the first folder; game PNGs and DDS files use `156x210/<batch_name>` and `156x210/<batch_name>/dds`. If no batch name is set, the workflow defaults to the next free `batch_1`, `batch_2`, and so on. It also supports direct saves in the standard resolution folders.

The command defaults to **FP8** and requires at least **25 GB** of RunPod storage. Select full BF16 explicitly on a larger GPU or pass a GGUF variant and quantization on a smaller GPU:

```bash
"$RUNTIME_DIR/scripts/install_runpod.sh" "$COMFY_ROOT" --variant gguf --gguf-quants Q4_K_M,Q5_K_M
```

The downloader enables Hugging Face's high-performance Xet mode and keeps up to four independent repositories active in parallel. Files from one repository, such as Adonis Base, Refine, and Post, transfer concurrently inside one Xet group that shares a single read token instead of requesting a token per file. Short adaptive retries absorb temporary rate limits without dropping to a slow connection; resumable HTTPS remains the final fallback, and every completed file is checked against its exact size and SHA-256 hash. Rerunning the command verifies completed files and resumes an interrupted HTTPS fallback. `HF_TOKEN` is read only from the process environment and is never printed or saved.

Start ComfyUI after installation:

```bash
/workspace/hoi4-portrait-runpod/scripts/start_runpod.sh /workspace/runpod-slim/ComfyUI
```

Startup checks that every required node loaded and reports anything missing.

## Windows

The release executable is a complete installer wizard, not just an unpacker:

1. Run `.\HOI4-Portrait-Workflows-1.0.0-windows-x64.exe`.
2. It detects the installed GPU. NVIDIA VRAM is read with `nvidia-smi` for guidance, and FP8 remains pre-checked for every GPU.
3. If ComfyUI is not found, the wizard asks whether to install it automatically. Accepting downloads the official ComfyUI Windows portable package; AMD detection selects the experimental ROCm-enabled package. ComfyUI currently limits that Windows ROCm package to RDNA 3, RDNA 3.5, and RDNA 4 hardware, so the wizard warns when another AMD family is detected. Declining keeps the manual ComfyUI path prompt.
4. Toggle any combination of variants — including all three, if you want every model type available.
5. If GGUF is selected, choose the quantization(s); the recommended one is pre-checked (Q4_K_M ≤ 10 GB, Q5_K_M 10–14 GB, Q6_K 12–16 GB, Q8_0 16+ GB).
6. Choose separate batch input and portrait output locations. Both default to `Documents\hoi4-portraits`, while the ComfyUI folders and custom paths remain selectable.
7. The bundled PowerShell installer installs the node packs, copies the workflows, and downloads the selected models.

The wizard works exactly like the RunPod command: after it finishes, restart ComfyUI and open **Workflows → hoi4_portraits**. Everything is ready out of the box.

You can also run the installer script directly:

```powershell
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Variant "fp8" -BatchInputPath "C:\Users\me\Documents\hoi4-portraits\input" -PortraitOutputPath "C:\Users\me\Documents\hoi4-portraits\output"
```

Use `-Variant "gguf" -GgufQuants "Q5_K_M"` for GGUF or `-Variant "full,fp8,gguf"` for several model types. Pass `-SkipModels` if the model files are already installed. Start ComfyUI with:

```powershell
.\scripts\start_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI"
```

## Hugging Face authentication

Before downloading the gated full or FP8 model:

1. Open the [FLUX.2 Klein 9B page](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B).
2. Accept the model agreement.
3. Create a [read-only Hugging Face token](https://huggingface.co/settings/tokens/new?tokenType=read).
4. Run `hf auth login`, or set `HF_TOKEN` in the shell that runs the installer.

See the [Hugging Face guide](hugging-face.md) for local and RunPod setup. No token is written into this repository or a workflow.
