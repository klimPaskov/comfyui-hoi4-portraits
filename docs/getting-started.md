# Getting started

## Choose a workflow

- Use **full power** when the source is faded, scratched, very small, or needs plausible color recovery. It runs RealESRGAN first and FLUX.2 restoration second.
- Use **ESRGAN only** for a well-preserved source or when you want a faster, less generative preparation stage.
- Use **text to image** when no real person must be preserved.

All three use the same FLUX.2 Klein base 9B model and HOI4 LoRA.

## Prepare a source image

Both source workflows use ComfyUI's built-in `PrimitiveBoundingBox` and
`ImageCropV2` nodes. Set `x`, `y`, `width`, and `height` around one person's
head and shoulders. Confirm the crop preview before running RealESRGAN or
FLUX; no project-specific custom node is required.

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
6. Queue once. If the full workflow is too heavy, turn the restoration switch off or use the ESRGAN-only graph.
7. Inspect the 832 × 1120 master before using the 156 × 210 game-size file.

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
| Wrong person or full-body framing | Adjust the source bounding box until the crop preview is head-and-shoulders. |
| Background appears too early | Only the post-generation background group may replace it; reload the packaged workflow if the graph was rewired. |
| Style is weak | Keep `hoi4_portrait` in the prompt; increase LoRA strength cautiously from the `0.7` default. |
| Identity or position changes | Confirm the crop, keep the encoded-source sampler connection, disable optional restoration if needed, and remove speculative traits. |
| Final looks too smooth | Try 10 or 20 scheduler steps and compare against the six-step default with the same seed. |
