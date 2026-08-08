# HOI4 portraits with FLUX.2 Klein 9B

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LoRA](https://img.shields.io/badge/Hugging%20Face-FLUX.2%20Klein%209B%20LoRA-ffd21e)](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora)

Create Hearts of Iron IV-style leader portraits with ComfyUI and the FLUX.2
Klein 9B model plus the project's tuned 2500-step LoRA. The source workflow
keeps the person's crop, pose, framing, and facial identity anchored, restores
old photos, and styles three portrait candidates for comparison. The batch
workflow turns a whole folder of photos into game-ready portraits in one
queue.

The same workflows open locally, on RunPod, and in Comfy Cloud. The installers
detect your GPU VRAM and suggest the right model variant (GGUF / FP8 / full),
and every workflow saves **HOI4-ready 156×210 DDS files** that can be dropped
straight into a mod's `gfx/portraits` folder.

## Four workflows

| Workflow | Best for | What it runs |
| --- | --- | --- |
| [`hoi4_portrait_flux2_klein_9b_source.json`](workflows/hoi4_portrait_flux2_klein_9b_source.json) | Identity-preserving portrait from a photo | RealESRGAN → optional Adonis restoration → **three** HOI4 LoRA candidates |
| [`hoi4_portrait_flux2_klein_9b_text_to_image.json`](workflows/hoi4_portrait_flux2_klein_9b_text_to_image.json) | Fictional portrait without a photo | One HOI4 LoRA generation from a text prompt |
| [`hoi4_portrait_processing_only.json`](workflows/hoi4_portrait_processing_only.json) | Clean a source photo before styling | Crop → RealESRGAN → optional Adonis restoration, no LoRA |
| [`hoi4_portrait_batch.json`](workflows/hoi4_portrait_batch.json) | Many photos at once | One sampler processes every image in `input/hoi4_portraits_batch` |

Every workflow saves:

```text
ComfyUI/output/1024x1365/     full-res master PNG
ComfyUI/output/156x210/       game-size PNG
ComfyUI/output/156x210/dds/   HOI4-ready DDS (DXT5, no mipmaps)
```

## Which model do I need?

The installer downloads only the model variant you choose:

| Variant | File | Download size | VRAM |
| --- | --- | --- | --- |
| Full | `flux-2-klein-9b.safetensors` | 18.2 GB | 24+ GB |
| FP8 | `flux-2-klein-9b-fp8.safetensors` | 9.4 GB | 16–20 GB |
| GGUF | `flux-2-klein-9b-*.gguf` | 5.9–10.0 GB | 8–16 GB |

Shared support files (Qwen text encoder, VAE, LoRA, Adonis LoKrs, RealESRGAN,
BiRefNet, face detectors) add **11.8 GB** on top. Storage and VRAM
requirements for each install are documented in
[`docs/local-install.md`](docs/local-install.md).

The [latest release](https://github.com/klimPaskov/comfyui-hoi4-portraits/releases/latest)
contains:

- a model-free ZIP for manual installs;
- a **Windows x64 installer wizard** that detects VRAM, pre-checks the
  recommended variant, lets you pick any combination (including all three),
  asks for GGUF quantizations when GGUF is selected, finds your ComfyUI, and
  installs workflows, custom nodes, and models;
- a **RunPod runtime archive** whose command defaults to the full model and
  accepts `--variant full|fp8|gguf` plus `--gguf-quants`.

## Fastest start

### Windows

```powershell
.\HOI4-Portrait-Workflows-3.0.0-windows-x64.exe
```

Accept the FLUX.2 Klein 9B agreement first (see below), then let the wizard
detect your VRAM and pre-check the recommended variant. It finds ComfyUI,
installs the node packs, copies the workflows, and downloads the models. After
restarting ComfyUI, open **Workflows → hoi4_portraits** and queue.

### RunPod

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

The RunPod command defaults to the full model. For a GPU with limited VRAM,
add the matching flags, for example:

```bash
"$RUNTIME_DIR/scripts/install_runpod.sh" "$COMFY_ROOT" --variant gguf --gguf-quants Q5_K_M
```

### Manual install

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
python scripts/apply_variant.py --comfyui-root /path/to/ComfyUI --variant fp8
python scripts/download_models.py --comfyui-root /path/to/ComfyUI --variant fp8
```

## Hugging Face access

The full and FP8 FLUX.2 Klein files are gated. Before installing, accept the
agreement on
[`black-forest-labs/FLUX.2-klein-9B`](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B)
(and [`...-9b-fp8`](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8)
for the FP8 variant) and create a
[read-only Hugging Face token](https://huggingface.co/settings/tokens/new?tokenType=read).
The [Hugging Face guide](docs/hugging-face.md) shows the complete setup.
GGUF files are not gated.

## What the source workflow does

These screenshots show the source, ESRGAN, optional restoration, three LoRA
candidates, and the comparison row in the editor. The workflow opens with
FLUX restoration enabled; queueing fills every preview with the completed
image.

![Source workflow overview](docs/assets/workflows/source-workflow-overview.jpg)

### 1. Crop and restore the source

Load the portrait and confirm the source preview. **Face zoom** defaults to
`0.90`; lower values retain more body. **Preserve hat/headwear** defaults to
`true`; disable it for a normal face-led crop. **Toggle face processing**
defaults to on; turn it off to keep a full multi-person composition. Use the
manual crop only when selecting one particular person.

![Source crop and RealESRGAN processing](docs/assets/workflows/step-1-source-processing.jpg)

### 2. Load the model and LoRA

This group loads FLUX.2 Klein 9B (full/FP8/GGUF), the Qwen text encoder, VAE,
the 2500-step HOI4 LoRA, and the Adonis restoration LoKrs.

![FLUX.2 Klein model and LoRA setup](docs/assets/workflows/step-2-model-setup.jpg)

### 3. Optionally restore with FLUX.2

RealESRGAN upscales first, then the optional Adonis Base → Post pass rebuilds
skin, hair, and colour. Its red switch opens enabled; turn it off for the
direct ESRGAN result.

![Optional FLUX.2 restoration stage](docs/assets/workflows/step-3-flux-restoration.jpg)

### 4. Apply the portrait LoRA

The processed portrait becomes the reference and starting image for three
independent LoRA passes, one per seed. Each branch has an editable prompt and
one advanced sampler card (CFG, guidance, seed, steps, sampling algorithm,
scheduler, denoise — the tuned defaults are CFG 1, guidance 1, 4 steps, Euler,
simple). Sampling is live: watch the portrait being constructed.

![Portrait LoRA styling stage](docs/assets/workflows/step-4-lora-styling.jpg)

### 5. Compare, then replace the background (optional)

Below the LoRA cards, a comparison row shows the ESRGAN result, the restoration
pass, and all three game-size finals side by side. Background replacement runs
only after generation and is off by default.

![Portrait comparison and background stage](docs/assets/workflows/step-5-background-replacement.jpg)

### 6. Save PNG and DDS

Every workflow writes a full-res master PNG, a 156×210 game PNG, and a
156×210 **DXT5 DDS with no mipmaps** — the exact format HOI4 reads, so the
file can be dropped into `gfx/portraits` without a crash.

![Preview and output stage](docs/assets/workflows/step-6-preview-and-save.jpg)

## Prompting

Keep the source workflow's default prompt exactly as-is:

```text
make this portrait hoi4_portrait style
```

That phrase already triggers the trained HOI4 look. You can safely append a
short description when the model needs help — ethnicity or skin colour if it
gets the skin wrong, or civilian/military/clerical clothing if it helps the
outfit:

```text
make this portrait hoi4_portrait style, a middle-aged Irish man with dark hair, wearing a military uniform
```

Don't describe the game, background, lighting, or rendering — the LoRA handles
those. The text-to-image workflow uses the exact example prompt:

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```

## Guides

- [Getting started](docs/getting-started.md)
- [Hugging Face model access and read-only token](docs/hugging-face.md)
- [Workflow controls and graph structure](docs/workflows.md)
- [Comfy Cloud](docs/comfy-cloud.md)
- [Local and RunPod installation, storage and VRAM requirements](docs/local-install.md)
- [Contributing](CONTRIBUTING.md)
- [Third-party model terms](THIRD_PARTY_LICENSES.md)

## License and trademark

Project-owned code, workflows, documentation, backgrounds, and the published
LoRA are MIT licensed; third-party models retain their own terms. The FLUX.2
Klein 9B model is gated and non-commercial; using the MIT-licensed workflow or
LoRA does not remove those model restrictions. Hearts of Iron IV is a
trademark of Paradox Interactive. This community project is not affiliated
with or endorsed by Paradox Interactive.
