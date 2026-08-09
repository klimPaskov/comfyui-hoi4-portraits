# Local, RunPod, and Windows installation

## Requirements

- ComfyUI with FLUX.2 Klein support.
- Python 3.10 or newer for the helper scripts.
- A Hugging Face account that has accepted the gated FLUX.2 Klein
  agreement (only needed for the full and FP8 variants; GGUF is not gated).

## Storage and VRAM requirements

The installer downloads only the selected distilled model variant plus the
shared support set. The shared set is **11,966,369,598 bytes (11.97 GB / 11.14
GiB)**: Qwen 3 8B Q8 GGUF, FLUX.2 VAE, the 2500-step style LoRA, Adonis Base
and Refine, RealESRGAN, BiRefNet, and both face detectors.

| Install | Variant file | Exact model payload | Practical free space | VRAM selection |
| --- | --- | --- | --- | --- |
| Full | `flux-2-klein-9b.safetensors` | 30.124 GB / 28.055 GiB | 40 GB | more than 20 GB |
| FP8 | `flux-2-klein-9b-fp8.safetensors` | 21.399 GB / 19.930 GiB | 30 GB | 16–20 GB |
| GGUF Q4_K_M | `flux-2-klein-9b-Q4_K_M.gguf` | 17.876 GB / 16.649 GiB | 25 GB | 8–10 GB |
| GGUF Q5_K_M | `flux-2-klein-9b-Q5_K_M.gguf` | 18.985 GB / 17.681 GiB | 26 GB | 10–14 GB |
| GGUF Q6_K | `flux-2-klein-9b-Q6_K.gguf` | 19.832 GB / 18.470 GiB | 27 GB | 12–16 GB |
| GGUF Q8_0 | `flux-2-klein-9b-Q8_0.gguf` | 21.945 GB / 20.438 GiB | 30 GB | 16+ GB |

The bare minimum for the full workflow's model files is therefore
**30,123,554,766 bytes (30.12 GB / 28.05 GiB)**. Keep about **40 GB free** for
the model payload, ComfyUI package, Hugging Face metadata/cache behavior, and
generated images. For multiple variants, count the shared set once: full +
FP8 + GGUF Q5_K_M is **46.58 GB** of model files.

VRAM guidance used by the installer wizard:

- **8–16 GB** → GGUF (recommended quantization is auto-detected)
- **16–20 GB** → FP8
- **more than 20 GB** → full

The Qwen text encoder is 8.7 GB and is shared by every variant. ComfyUI
offloads it to system RAM when VRAM is tight, so 8 GB GPUs work but are slow.

## Install into an existing ComfyUI

```bash
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
python scripts/install_custom_node_packs.py --comfyui-root /path/to/ComfyUI
python scripts/apply_variant.py --comfyui-root /path/to/ComfyUI --variant fp8
python scripts/download_models.py --comfyui-root /path/to/ComfyUI --variant fp8
```

The setup script changes the `diffusion_model` field on every installed
**HOI4 Distilled Model Stack** card:

- `--variant full` → `flux-2-klein-9b.safetensors`
- `--variant fp8` → `flux-2-klein-9b-fp8.safetensors`
- `--variant gguf --gguf-quants Q5_K_M` → the selected
  `flux-2-klein-9b-*.gguf` quantization

The card uses the native safetensors loader or the pinned
[ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) diffusion loader at
runtime according to the filename.

Pass `--variant` multiple times to prepare several variants; the first is
applied to the four main workflows and the rest are emitted as
ready-made `*_fp8.json` / `*_gguf.json` copies.

## RunPod

On a RunPod image that already contains ComfyUI, the installer places the four
workflows in `user/default/workflows/hoi4_portraits`, installs the project
node pack plus the pinned Adonis/RES4LYF dependencies, copies the bundled
backgrounds and sample source into `input/`, creates the batch/output folders,
and downloads the selected models:

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

The command defaults to the **full** model. On a smaller GPU, pass the variant
and quantization flags:

```bash
"$RUNTIME_DIR/scripts/install_runpod.sh" "$COMFY_ROOT" --variant gguf --gguf-quants Q4_K_M,Q5_K_M
```

The final verification pass checks every downloaded file and the custom
nodes. `HF_TOKEN` is read only from the process environment and is never
printed or saved.

Start ComfyUI after installation:

```bash
/workspace/hoi4-portrait-runpod/scripts/start_runpod.sh /workspace/runpod-slim/ComfyUI
```

Startup checks that every required node loaded and reports anything missing.

## Windows

The release executable is a complete installer wizard, not just an unpacker:

1. Run
   `.\HOI4-Portrait-Workflows-v3.1.0-windows-x64.exe`.
2. It detects your GPU VRAM with `nvidia-smi` and pre-checks the recommended
   variant (GGUF for 8–16 GB, FP8 for 16–20 GB, full above 20 GB).
3. Toggle any combination of variants — including all three, if you want every
   model type available.
4. If GGUF is selected, choose the quantization(s); the recommended one is
   pre-checked (Q4_K_M ≤ 10 GB, Q5_K_M 10–14 GB, Q6_K 12–16 GB, Q8_0 16+ GB).
5. It finds your ComfyUI (or you type its root) and runs the bundled
   PowerShell installer, which installs the node packs, copies the workflows,
   and downloads the selected models.

The wizard works exactly like the RunPod command: after it finishes, restart
ComfyUI and open **Workflows → hoi4_portraits**. Everything is ready out of
the box.

You can also run the installer script directly:

```powershell
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI" -Variant "fp8"
```

Use `-Variant "gguf" -GgufQuants "Q5_K_M"` for GGUF or
`-Variant "full,fp8,gguf"` for several model types. Pass `-SkipModels` if the
model files are already installed. Start ComfyUI with:

```powershell
.\scripts\start_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI"
```

## Hugging Face authentication

Before downloading the gated full or FP8 model:

1. Open the [FLUX.2 Klein 9B page](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B).
2. Accept the model agreement.
3. Create a [read-only Hugging Face token](https://huggingface.co/settings/tokens/new?tokenType=read).
4. Run `hf auth login`, or set `HF_TOKEN` in the shell that runs the installer.

See the [Hugging Face guide](hugging-face.md) for local and RunPod setup. No
token is written into this repository or a workflow.
