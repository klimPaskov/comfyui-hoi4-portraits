# Getting started

## Choose a workflow

- Use **full power** when the source is faded, scratched, very small, or needs plausible color recovery. It runs RealESRGAN first and FLUX.2 restoration second.
- Use **ESRGAN only** for a clean source or when you want a faster, less generative preparation stage.
- Use **text to image** when no real person must be preserved.

All three use the same FLUX.2 Klein base 9B model and HOI4 LoRA.

## Prepare a source image

The previous automatic selection/cropping nodes were project-specific and
have been removed for Comfy Cloud compatibility. Give the source workflows a
single-person, head-and-shoulders image whenever possible.

Good input:

- one clearly visible person;
- top of the head and shoulders inside the frame;
- face at least roughly 200 pixels tall before upscaling;
- limited motion blur and obstruction;
- historically accurate visible clothing if preservation matters.

If the source is a group photograph, crop the person first with ComfyUI's
built-in **Crop Image** node or any image editor. The workflow's 832 × 1120
resize uses a center crop; it cannot decide which person is important.

## Required model files

| Folder under `ComfyUI/models/` | File |
| --- | --- |
| `diffusion_models/` | `flux-2-klein-base-9b-fp8.safetensors` |
| `text_encoders/` | `qwen_3_8b_fp8mixed.safetensors` |
| `vae/` | `flux2-vae.safetensors` |
| `loras/` | `hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors` |
| `upscale_models/` | `RealESRGAN_x2plus.pth` |
| `background_removal/` | `birefnet.safetensors` |

The filenames, pinned sources, sizes, and SHA-256 hashes are recorded in
[`models.json`](../models.json).

## First run

1. Open the workflow JSON, not the `.api.json` file, in the ComfyUI editor.
2. Check every model loader. A red loader means the named file has not been installed or imported.
3. Select the source image and edit the positive prompt. Keep the
   `hoi4_portrait,` trigger and describe only the visible person.
4. Leave background replacement off for the first run.
5. Queue once. If the full workflow is too heavy, turn the restoration switch off or use the ESRGAN-only graph.
6. Inspect the 832 × 1120 master before using the 156 × 210 game-size file.

Outputs are saved under `ComfyUI/output/hoi4_portraits/`.

## Person-only prompt rules

For a real person, describe the visible face, hair, expression, clothing, pose,
gaze, and crop accurately. Do not put style, game, background, lighting,
rendering, transformation, restoration, or preservation instructions in the
positive prompt. Do not ask the model to invent medals or insignia. If
identity drifts, try LoRA strength `0.7`, use a cleaner crop, or disable the
optional FLUX restoration pass.

## Common problems

| Symptom | Likely fix |
| --- | --- |
| Loader is red | Install/import the exact filename from `models.json`, then refresh ComfyUI. |
| Out of memory | Disable FLUX restoration, close other GPU work, use offloading, or move to Comfy Cloud/a 32 GB+ GPU. |
| Wrong person in a group photo | Crop to one person before loading the workflow. |
| Background appears too early | Use the current workflow; only the post-generation background group may replace it. |
| Style is weak | Keep `hoi4_portrait` in the prompt and use the default LoRA strength `0.8`. |
| Identity changes | Use the source workflow, try strength `0.7`, disable optional FLUX restoration, and remove speculative traits. |
| Final looks too smooth | Use the public 20-step preset; six-step local previews are for reduced-resource validation. |
