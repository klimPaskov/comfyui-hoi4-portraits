# Getting started

## Choose a workflow

- Use **full power** when the source is faded, scratched, very small, or needs plausible color recovery. It runs RealESRGAN first and FLUX.2 restoration second.
- Use **ESRGAN only** for a well-preserved source or when you want a faster, less generative preparation stage.
- Use **text to image** when no real person must be preserved.

All three use the same FLUX.2 Klein base 9B model and HOI4 LoRA.

## Prepare a source image

In either source workflow, set the crop box around one person's head and
shoulders. Confirm the crop preview before running RealESRGAN or FLUX.

Good input:

- one clearly visible person;
- top of the head and shoulders inside the frame;
- face at least roughly 200 pixels tall before upscaling;
- limited motion blur and obstruction;
- historically accurate visible clothing if preservation matters.

For a group photograph, use the same bounding box to select one person. The
later 832 × 1120 scale is not a subject detector, so the crop box is the step
that determines the portrait framing.

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
3. Select the source image, set the crop box around the head and shoulders,
   and confirm the crop preview.
4. Edit the positive prompt. Keep the `hoi4_portrait,` trigger and describe
   only the visible person.
5. Leave background replacement off for the first run.
6. Queue once. The full workflow's restoration switch is off by default; turn it on only when the source needs the additional pass. Use the ESRGAN-only graph when you never need that branch.
7. Inspect the 832 × 1120 master before using the 156 × 210 game-size file.

Outputs are saved under `ComfyUI/output/hoi4_portraits/`.

## Person-only prompt rules

For a real person, describe only supported ethnicity, approximate age, broad
hair or facial-hair cues, and general clothing classification. Let the source reference carry expression, pose, gaze, and facing
direction. Do not put style, game, background, lighting,
rendering, transformation, restoration, or preservation instructions in the
positive prompt. Do not ask the model to invent medals or insignia. If
identity drifts, try LoRA strength `0.75`, use a cleaner crop, or disable the
optional FLUX restoration pass.

## Common problems

| Symptom | Likely fix |
| --- | --- |
| Loader is red | Install/import the exact filename from `models.json`, then refresh ComfyUI. |
| Out of memory | Disable FLUX restoration, close other GPU work, use offloading, or move to Comfy Cloud/a 24 GB GPU. |
| Wrong person or full-body framing | Adjust the source bounding box until the crop preview is head-and-shoulders. |
| Background appears too early | Only the post-generation background group may replace it; reload the packaged workflow if the graph was rewired. |
| Style is weak | Keep `hoi4_portrait` in the prompt; use the `0.75` default and keep the crop clean. |
| Identity or position changes | Confirm the crop, keep the encoded-source sampler connection, disable optional restoration if needed, and remove speculative traits. |
| Final looks too smooth | Use a sharper source crop, keep the 832 × 1120 workflow canvas, and avoid speculative prompt details. Eight Euler steps is the documented default; the optional FLUX restoration branch can soften identity, so disable it first. |
