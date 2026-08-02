# HOI4 portraits with FLUX.2 Klein 9B

[![CI](https://github.com/klimPaskov/comfyui-hoi4-portraits/actions/workflows/ci.yml/badge.svg)](https://github.com/klimPaskov/comfyui-hoi4-portraits/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LoRA](https://img.shields.io/badge/Hugging%20Face-FLUX.2%20Klein%209B%20LoRA-ffd21e)](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora)

Generate Hearts of Iron IV-style leader portraits from photographs or written
character descriptions with ComfyUI. The workflows use **FLUX.2 Klein base
9B** plus the project’s `hoi4_portrait` LoRA.

The same workflows open locally and in Comfy Cloud. Start with a source photo
or a written character description, then choose the restoration path that fits
the image and available hardware.

## Workflows

| Workflow | Best for | Restoration path |
| --- | --- | --- |
| [`hoi4_portrait_flux2_klein_9b_full_power`](workflows/hoi4_portrait_flux2_klein_9b_full_power.json) | Best source-photo quality; 32 GB+ GPU or Comfy Cloud | RealESRGAN first, then switchable FLUX.2 restoration |
| [`hoi4_portrait_flux2_klein_9b_esrgan_only`](workflows/hoi4_portrait_flux2_klein_9b_esrgan_only.json) | Faster source-photo conversion | RealESRGAN only, then FLUX.2 LoRA styling |
| [`hoi4_portrait_flux2_klein_9b_text_to_image`](workflows/hoi4_portrait_flux2_klein_9b_text_to_image.json) | Creating a fictional leader without a source image | No restoration pass |

Matching [API-format graphs](workflows/) are included for Comfy Cloud MCP,
the Comfy Cloud API, and local `/prompt` submission.

Krea 2 and Krea Edit variants are available as optional alternatives in the
[Krea workflow release](https://github.com/klimPaskov/comfyui-hoi4-portraits/releases/tag/v1.0.0).
They are not part of the default workflow table or package.

## What the full workflow does

```mermaid
flowchart LR
    A["Source portrait"] --> CROP["Adjustable head-and-shoulders crop"]
    CROP --> B["RealESRGAN x2"]
    B --> C{"FLUX restoration enabled?"}
    C -->|No| D["HOI4 LoRA styling"]
    C -->|Yes| R["FLUX.2 conservative restoration"] --> D
    D --> E["Final styled portrait"]
    E --> F{"Replace background?"}
    F -->|No| G["Save master + 156×210 PNG"]
    F -->|Yes| H["BiRefNet mask + composite"] --> G
```

![Full-power workflow overview](docs/assets/workflows/full-power-overview.png)

### 1. Crop and restore the source

Load the portrait, set the crop box around the head and shoulders, and confirm
the preview. The cropped image goes through RealESRGAN before it is fitted to
the 832 × 1120 working canvas.

![Source crop and RealESRGAN processing](docs/assets/workflows/step-1-source-processing.png)

### 2. Load FLUX.2 and the portrait LoRA

This group loads the FLUX.2 Klein 9B base model, Qwen text encoder, VAE, and
the portrait LoRA. The documented LoRA strength is `0.70`.

![FLUX.2 Klein model and LoRA setup](docs/assets/workflows/step-2-model-setup.png)

### 3. Optionally restore with FLUX.2

Full power uses the ESRGAN result as the reference and starting image for a
conservative FLUX.2 restoration pass. Turn the restoration switch off to skip
this stage and continue with the ESRGAN image.

![Optional FLUX.2 restoration stage](docs/assets/workflows/step-3-flux-restoration.png)

### 4. Apply the portrait LoRA

The selected processed portrait becomes the reference and starting image for
LoRA styling. Describe only the person in the positive prompt. Euler, six
steps, and CFG 5 are the documented defaults.

![Portrait LoRA styling stage](docs/assets/workflows/step-4-lora-styling.png)

### 5. Optionally replace the background

Background masking and compositing receive the decoded final portrait. This
stage is off by default and cannot affect the earlier crop, restoration, or
LoRA generation stages.

![Final-image background replacement stage](docs/assets/workflows/step-5-background-replacement.png)

### 6. Preview and save

Preview the result, save the 832 × 1120 master PNG, and create the 156 × 210
game-size portrait.

![Preview and output stage](docs/assets/workflows/step-6-preview-and-save.png)

Background removal and compositing consume the **decoded final LoRA-styled
image**. They do not run on the source, the ESRGAN image, or the restoration
pass.

Both image-to-image stages start from the encoded processed portrait, not an
empty latent canvas. The reference conditioning and sampler therefore share
the same source composition, which reduces unwanted pose and framing changes.

## Fastest start: Comfy Cloud

1. On a Comfy Cloud Creator or Pro plan, open **Models → Import** and import the [public LoRA file](https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/blob/main/hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors) as a LoRA.
2. Download and open one of the workflow JSON files from the table.
3. For a source workflow, upload a portrait and select it in **Load source portrait**. Set the built-in crop box around the head and shoulders, then check its preview.
4. Upload one of the [`backgrounds/`](backgrounds/) files only if you want background replacement, then turn on the final background switch.
5. Queue the workflow. In full power, turn **Toggle FLUX restoration** off to run ESRGAN-only without rewiring anything.

See [Comfy Cloud setup](docs/comfy-cloud.md) for the exact model-import and MCP
validation flow.

## Experimental: autonomous Comfy Cloud MCP

The MCP path lets an MCP-capable coding agent operate the Cloud workflow from
the source image through installation in a local HOI4 mod. This integration is
experimental. The setup below assumes that you already have:

- a Comfy Cloud **Builder** subscription with Cloud GPU, API, MCP, and custom
  model-import access;
- access to the Comfy Cloud MCP preview;
- the project LoRA imported with the exact filename
  `hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors`;
- an MCP-capable agent with access to this repository and the target mod;
- the mod root, character identifier, output filename, and portrait sprite name
  supplied to the agent. These values are mod-specific and must not be guessed.

### Connect the MCP server

Comfy Cloud hosts the MCP endpoint at `https://cloud.comfy.org/mcp`. In a client
that supports remote OAuth MCP servers, add that URL and complete the Comfy
authorization flow. For API-key clients, create a key at
[`platform.comfy.org/profile/api-keys`](https://platform.comfy.org/profile/api-keys),
then use the official installer:

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/Comfy-Org/comfy-cloud-mcp/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/Comfy-Org/comfy-cloud-mcp/main/install.ps1 | iex
```

Restart the MCP client after installation. A useful connection check is to ask
the agent to inspect the Comfy Cloud server, find FLUX.2 Klein base 9B and the
imported LoRA, then dry-run the selected `.api.json` graph without submitting a
GPU job.

### What the agent does

After the one-time connection and model import, the agent can perform the
portrait job autonomously:

1. Read the appropriate API-format graph from [`workflows/`](workflows/). Use
   full power for ESRGAN plus optional FLUX restoration, or ESRGAN-only for the
   shorter path.
2. Inspect the source at full resolution and write a `hoi4_portrait,` prompt
   describing only the person: identity, facial proportions and texture,
   expression, gaze, facing direction, clothing, and crop.
3. Upload the local source through the MCP file-upload flow. Use the returned
   Cloud filename in **Load source portrait**; a local filesystem path is not a
   valid `LoadImage.image` value in Cloud.
4. Set the head-and-shoulders bounding box before processing. The agent should
   exclude printed borders, oval frames, captions, and empty margins while
   keeping the full head, neck, and shoulders.
5. Set the project LoRA to `0.7`, choose whether FLUX restoration is enabled,
   and keep background replacement after the decoded LoRA result. If a custom
   background is requested, upload it separately and replace that loader's
   filename too.
6. Dry-run the modified API graph. Resolve missing nodes, model filenames, or
   invalid input values before submitting any generation.
7. Submit the graph, retain its returned `prompt_id`, and wait for that exact
   job to finish. Queue status alone is not proof that the agent's job
   completed.
8. Retrieve and download both the 832 × 1120 master and 156 × 210 game output.
   Visually verify the crop, identity, expression, facial detail, background,
   and absence of frame or vignette artifacts.
9. Copy the approved game portrait into the mod's configured portrait path,
   update the configured `spriteType`/portrait definition and character
   reference when needed, then report the exact files changed. Existing mod
   files should be backed up or edited through version control.

For repeatable autonomous installation, give the agent a small job manifest
instead of relying on prose alone:

```yaml
source_image: /absolute/path/to/source.png
workflow: full_power
flux_restoration: true
replace_background: true
mod_root: /absolute/path/to/hoi4-mod
portrait_output: gfx/leaders/TAG/leader_name.png
sprite_name: GFX_portrait_TAG_leader_name
character_file: common/characters/TAG_characters.txt
character_id: TAG_leader_name
```

An example request is: “Use Comfy Cloud MCP and the full-power API workflow to
turn this source into a portrait. Crop to head and shoulders, use the project
LoRA at 0.7, keep FLUX restoration enabled, replace the background only after
the final LoRA image, verify both outputs, and install the 156 × 210 result
according to this manifest.”

The agent must not claim success until the submitted `prompt_id` is complete,
the output has been retrieved, and the destination mod files have been checked.
Comfy's Cloud API and MCP are experimental and may change.

## Local / RunPod start

FLUX.2 Klein 9B needs an up-to-date ComfyUI and substantial memory. Its
upstream model card says the base fits in roughly 29 GB VRAM, so a 32 GB GPU is
the practical local target. Lower-memory systems may require model offloading
and will be slow. The model files use about 19 GB of disk before ComfyUI caches
or outputs.

```bash
git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git
cd comfyui-hoi4-portraits
python scripts/install_workflows.py --comfyui-root /path/to/ComfyUI
python scripts/download_models.py --comfyui-root /path/to/ComfyUI
```

The FLUX.2 base model is gated. Accept its Hugging Face agreement and run
`hf auth login` (or set `HF_TOKEN`) before the model download command.

For a RunPod ComfyUI template:

```bash
bash -lc 'P=/workspace/comfyui-hoi4-portraits; test -d "$P/.git" || git clone https://github.com/klimPaskov/comfyui-hoi4-portraits.git "$P"; "$P/scripts/install_runpod.sh" /workspace/ComfyUI'
```

Windows users can run:

```powershell
.\scripts\install_windows.ps1 -ComfyUIRoot "C:\path\to\ComfyUI"
```

## Prompting

Keep `hoi4_portrait` at the start of the positive prompt, then describe only
the visible person: face, hair, expression, clothing, pose, gaze, and crop.
Do not describe the game, desired style, background, lighting, rendering,
restoration, or transformation. The LoRA and workflow supply those parts.

```text
hoi4_portrait, a middle-aged man with short dark hair, round wire-frame glasses, a long narrow face, a neat moustache, and a reserved expression, wearing a dark jacket over a light collared shirt and tie, shown from the shoulders up while looking slightly left.
```

The workflows default to the selected `0.7` LoRA strength, Euler sampler, six
steps, and CFG 5. The 8-, 10-, and 20-step control below lets you judge whether
the extra runtime helps your source. See [autoprompter
examples](docs/autoprompter-examples.md) for more person-only prompts.

## Verified examples

These are real local runs with the published LoRA, not mockups. Every source
board is initial source → processed crop → final portrait. Qwen generated the
descriptions; the documented prompt contract was then applied to remove
uncertain or forbidden treatment language before inference.

The evidence boards use 416 × 560 because the test Mac has 16 GB unified
memory. That reduction is the main source of preview softness; the committed
workflows keep an 832 × 1120 canvas. More steps can refine a result but cannot
replace missing spatial resolution, which is why the step control is shown
separately.

### Full restoration

![Full restoration example 1](docs/assets/test-runs/full-restoration-01.jpg)

Autoprompter description:

```text
hoi4_portrait, middle-aged man with short wavy hair, a moustache, wearing a suit and tie with a visible collar and lapels, looking slightly upward with a subtle smile, head tilted slightly to his right, shoulders squared, shown from the chest up.
```

![Full restoration example 2](docs/assets/test-runs/full-restoration-02.jpg)

Autoprompter description:

```text
hoi4_portrait, young woman with short dark hair parted to the side, no glasses, wearing a high-collared garment with a visible round fastening, looking directly at the camera with a neutral expression, head slightly tilted, shown from the chest up in an oval crop.
```

![Full restoration example 3](docs/assets/test-runs/full-restoration-03.jpg)

Autoprompter description:

```text
hoi4_portrait, young man with dark hair parted on the left, clean-shaven, wearing a collared shirt and tie, looking upward and to his right with a slight smile, head tilted, shown from the shoulders up in three-quarter profile with a visible ear, nose, and chin.
```

### ESRGAN only

![ESRGAN-only example 1](docs/assets/test-runs/esrgan-only-01.jpg)

Autoprompter description:

```text
hoi4_portrait, middle-aged man with short dark hair, no facial hair, wearing a high-collared uniform with decorative cords and a visible medal, looking slightly to his right with a neutral expression, head tilted slightly and mouth closed, shown from the chest up.
```

![ESRGAN-only example 2](docs/assets/test-runs/esrgan-only-02.jpg)

Autoprompter description:

```text
hoi4_portrait, a man with short dark hair, round-rimmed glasses, no facial hair, and a long narrow face, dressed in a dark suit with a white collared shirt and dark tie, looking directly at the camera with a neutral expression, his head and shoulders angled slightly to his right, shown from the chest up in three-quarter view.
```

![ESRGAN-only example 3](docs/assets/test-runs/esrgan-only-03.jpg)

Autoprompter description:

```text
hoi4_portrait, middle-aged man with a receding hairline, no facial hair, a prominent nose, defined jaw and chin, wearing a high-collared garment with a decorative corded tie and buttoned front, looking directly at the camera with a neutral expression and a slight head tilt, shown from the chest up.
```

### No-input portraits and step control

![Three no-input portraits generated from person-only prompts](docs/assets/test-runs/random-portraits.jpg)

![Fixed-seed Euler comparison at 6, 8, 10, and 20 steps](docs/assets/test-runs/step-comparison.jpg)

See [the three random prompts, exact test conditions, and findings](docs/test-results.md).

## Validation status

- All three editor graphs and API graphs are generated from one deterministic source.
- Link endpoints, slot types, output nodes, visual groups, and node geometry are tested.
- Node and group overlap checks pass with spacing margins.
- Comfy Cloud MCP no-spend preflight passes for all three API graphs;
  the only advisory is the expected project LoRA import.
- Cloud GPU mechanical tests pass every workflow shape and the final
  background branch using a compatible catalog LoRA at zero strength.
- Actual local inference with the project LoRA passes for three full-restoration
  portraits, three ESRGAN-only portraits, three text-to-image portraits, and
  fixed-seed 6/8/10/20-step controls. Reduced 416 × 560 evidence was used on a
  16 GB Apple-silicon Mac; 832 × 1120 remains the workflow canvas.

Run the same checks locally:

```bash
python scripts/build_workflows.py
python scripts/validate_workflows.py
python -m unittest discover -s tests -v
```

## Guides

- [Getting started](docs/getting-started.md)
- [Workflow controls and graph structure](docs/workflows.md)
- [Comfy Cloud and MCP](docs/comfy-cloud.md)
- [Local and RunPod installation](docs/local-install.md)
- [Autoprompter prompt examples](docs/autoprompter-examples.md)
- [Local test results and before/afters](docs/test-results.md)
- [Testing](docs/testing.md)
- [Contributing](CONTRIBUTING.md)
- [Third-party model terms](THIRD_PARTY_LICENSES.md)

## License and trademark

Project-owned code, workflows, documentation, backgrounds, and the published
LoRA are MIT licensed; third-party models retain their own terms. The FLUX.2
Klein 9B base model is gated and non-commercial; using the MIT-licensed
workflow or LoRA does not remove those model restrictions. Hearts of Iron IV
is a trademark of Paradox Interactive. This community project is not
affiliated with or endorsed by Paradox Interactive.
