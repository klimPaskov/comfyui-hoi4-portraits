# HOI4 portraits with FLUX.2 Klein 9B

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![LoRA](https://img.shields.io/badge/Hugging%20Face-FLUX.2%20Klein%209B%20LoRA-ffd21e)](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora) [![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289da?logo=discord&logoColor=white)](https://discord.gg/rAXesGcT2t) [![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20the%20project-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/klimpaskov)

Create Hearts of Iron IV-style leader portraits with ComfyUI, FLUX.2 Klein 9B, and the project's 2500-step HOI4 style LoRA.

The same workflows open locally, on RunPod, and in Comfy Cloud. RunPod defaults to FP8, while the Windows installer uses GPU detection to recommend a suitable model; GGUF and full BF16 remain available as manual selections. Every workflow saves **HOI4-ready 156×210 DDS files** for a mod's `gfx/leaders/TAG/` folder.

## Portrait results

Each comparison shows the original portrait, the restored portrait, and the final HOI4-style result.

![Source portrait before restoration and after HOI4 styling](docs/assets/showcase/source-before-after.png)

![W. T. Cosgrave source, restored, and HOI4 portrait](docs/assets/showcase/wt-cosgrave-before-after.png)

![Douglas Hyde source, restored, and HOI4 portrait](docs/assets/showcase/douglas-hyde-before-after.png)

![Éamon de Valera source, restored, and HOI4 portrait](docs/assets/showcase/eamon-de-valera-before-after.png)

![Seán Lemass source, restored, and HOI4 portrait](docs/assets/showcase/sean-lemass-before-after.png)

See the [complete before-and-after gallery](docs/drive-gallery.md) for all of the image examples.

## Four workflows

| Workflow | Best for | What it runs |
| --- | --- | --- |
| [`hoi4_portrait_source.json`](workflows/hoi4_portrait_source.json) | Identity-preserving portrait from a photo | RealESRGAN → Adonis Base + Post restoration → **three** HOI4 LoRA candidates |
| [`hoi4_portrait_text_to_image.json`](workflows/hoi4_portrait_text_to_image.json) | Fictional portrait without a photo | One HOI4 LoRA generation from a text prompt |
| [`hoi4_portrait_batch.json`](workflows/hoi4_portrait_batch.json) | Many photos at once | Processes every input one by one, with configurable candidates and optional background replacement |
| [`hoi4_portrait_processing_only.json`](workflows/hoi4_portrait_processing_only.json) | Clean a source photo before styling | Crop → RealESRGAN → Adonis Base + Post restoration, no style LoRA |

See the [output layout reference](docs/output-layout.md) for folders, filenames, image sizes, and HOI4 DDS details.

## Which model do I need?

The installer downloads only the model variant you choose. Minimum storage includes the shared support models and about 2–3 GB of free space.

| Variant | Minimum storage | VRAM |
| --- | --- | --- |
| Full distilled | 34 GB | above 20 GB |
| FP8 distilled | 25 GB | 16–20 GB |
| GGUF Q4_K_M | 21 GB | 8–10 GB |
| GGUF Q5_K_M | 22 GB | 10–14 GB |
| GGUF Q6_K | 23 GB | 12–16 GB |
| GGUF Q8_0 | 25.5 GB | 16+ GB |

Every variant includes Qwen, the VAE, the 2500-step HOI4 style LoRA, all three Adonis models, RealESRGAN, BiRefNet, and the face detectors. Refine stays installed as the official alternative first pass; the default graph uses Base → Post. Storage and VRAM requirements are documented in [`docs/local-install.md`](docs/local-install.md).

The [latest release](https://github.com/klimPaskov/comfyui-hoi4-portraits/releases/latest) contains:

- a model-free ZIP for manual installs;
- a **Windows x64 installer wizard** that detects the GPU, recommends a suitable model, offers to install the official ComfyUI portable package when ComfyUI is missing, uses the ROCm package for AMD GPUs, lets you pick any model combination, and installs the workflows, custom nodes, and models;
- a **RunPod runtime archive** whose command defaults to FP8 and accepts `--variant full|fp8|gguf` plus `--gguf-quants`.

## Fastest start

### Windows

```powershell
.\HOI4-Portrait-Workflows-1.0.2-windows-x64.exe
```

Accept the FLUX.2 Klein 9B agreement first (see below), then let the wizard detect your GPU, ComfyUI installation, and recommended model. If ComfyUI is missing, it offers to install the official Windows portable package automatically; AMD detection selects the ROCm-enabled package. For manual selection, paste either the ComfyUI folder (`C:\ComfyUI`) or its full `main.py` path (`C:\ComfyUI\main.py`); quoted and dragged paths work too. The wizard also lets you choose the batch input and portrait output folders, which default to the local `Documents\hoi4-portraits` workspace. It installs the node packs, copies the workflows and example inputs, and downloads the models. After restarting ComfyUI, open **Workflows → hoi4_portraits** and queue.

### RunPod

> **Starting on RunPod? [Use my referral link](https://runpod.io/?ref=9t44ghaf) when creating a new account. You get $5 free once you add $10.**

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

The RunPod command uses FP8 by default and requires at least 25 GB of storage. Batch sources go in `/workspace/hoi4-portrait-runpod/input/`, and every PNG and DDS is written below `/workspace/hoi4-portrait-runpod/output/`. You can explicitly select full BF16 on a larger GPU or use GGUF on a smaller GPU, for example:

```bash
"$RUNTIME_DIR/scripts/install_runpod.sh" "$COMFY_ROOT" --variant gguf --gguf-quants Q5_K_M
```

## Download RunPod outputs

Generated files are in `/workspace/hoi4-portrait-runpod/output`. For direct SCP downloads, a `.tar.gz` archive, or manual JupyterLab downloads, see the full [RunPod output download instructions](docs/download-outputs.md).

### Manual install

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
python scripts/install_custom_node_packs.py --comfyui-root /path/to/ComfyUI
python scripts/apply_variant.py --comfyui-root /path/to/ComfyUI --variant fp8
python -m pip install -r scripts/requirements-download.txt
python scripts/download_models.py --comfyui-root /path/to/ComfyUI --variant fp8
```

## Hugging Face access

The full and FP8 FLUX.2 Klein files are gated. Before installing, accept the agreement on [`black-forest-labs/FLUX.2-klein-9B`](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B) (and [`...-9b-fp8`](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8) for the FP8 variant) and create a [read-only Hugging Face token](https://huggingface.co/settings/tokens/new?tokenType=read). The [Hugging Face guide](docs/hugging-face.md) shows the complete setup. GGUF files are not gated.

## Workflows

### Source portrait

The workflow is arranged from left to right in clear, colour-coded stages.

![Source workflow overview](docs/assets/workflows/current/source-overview.png)

1. **Source and ESRGAN:** load a portrait, adjust **Face zoom** (`1.00`) and **Preserve hat/headwear**, and review the prepared image.
2. **Restoration:** [`Adonis Base + Post`](https://huggingface.co/n8te0/adonis_flux2klein/blob/main/adonis_post_workflows/Adonis_Base_Post_gguf.json) restores detail and colorizes monochrome or sepia photos. Turn off **Use Adonis restoration** to skip it.
3. **Style:** generate three candidates with the 2500-step HOI4 style LoRA and the defaults in [Seed selection](#seed-selection).
4. **Compare and export:** compare the prepared, restored, and styled portraits, optionally replace their background, and export full-size PNGs plus HOI4-ready PNG and DDS files.

### Text to image

![Text-to-image workflow overview](docs/assets/workflows/current/text-to-image-overview.png)

Create a fictional portrait without a source image. Describe the subject in the purple prompt node, then use the same background, sizing, PNG, and DDS controls as the other workflows. The default prompt is:

```text
hoi4_portrait style, a soviet soldier with the head of a brown bear wearing a soviet hat, ears still visible. No military uniform decorations.
```

### Batch

![Batch workflow overview](docs/assets/workflows/current/batch-overview.png)

Process every supported image in the batch input folder one by one. Choose the number of candidates, optionally replace the background, and save each queue in its own matching full-resolution and game-resolution folders.

### Processing only

![Processing-only workflow overview](docs/assets/workflows/current/processing-overview.png)

Crop, upscale, and optionally restore a portrait without applying the HOI4 style LoRA. Prepared and restored portraits are saved separately at 1024×1365.

## Prompting

Keep the source workflow's default prompt exactly as-is:

```text
make this portrait hoi4_portrait style
```

That phrase already triggers the trained HOI4 look. You can append a short subject description when the model needs help with a specific physical feature or clothing choice.

Don't describe the game, background, lighting, or rendering — the LoRA handles those. For a fictional portrait, edit the subject description in the default text-to-image prompt.

## Seed selection

Seeds can change the look of a candidate even when the prompt and settings stay the same. These examples were compared with the FP8 FLUX.2 Klein 9B model and the 2500-step HOI4 style LoRA; the following seeds have worked well: `433682774328322`, `101825966811438`, `757254001619850`, `629907966167866`, `514819207028619`, and `42`.

The source workflow starts with fixed seeds `757254001619850`, `629907966167866`, and `42` for its three candidates. The batch workflow starts with fixed seed `757254001619850`. To vary results, change **Control after generate** from **fixed** to **randomize**, **increment**, or **decrement**. Text-to-image remains randomized by default.

![Seed comparison across repeated portrait examples](docs/assets/showcase/seed-comparison.png)

## Guides

- [Getting started](docs/getting-started.md)
- [Hugging Face model access and read-only token](docs/hugging-face.md)
- [Workflow controls and graph structure](docs/workflows.md)
- [Output folders, filenames, and export format](docs/output-layout.md)
- [Comfy Cloud](docs/comfy-cloud.md)
- [Local and RunPod installation, storage and VRAM requirements](docs/local-install.md)
- [Contributing](CONTRIBUTING.md)
- [Third-party model terms](THIRD_PARTY_LICENSES.md)

## License and trademark

Project-owned code, workflows, documentation, backgrounds, and the published LoRA are MIT licensed; third-party models retain their own terms. The FLUX.2 Klein 9B model is gated and non-commercial; using the MIT-licensed workflow or LoRA does not remove those model restrictions. Hearts of Iron IV is a trademark of Paradox Interactive. This community project is not affiliated with or endorsed by Paradox Interactive.
