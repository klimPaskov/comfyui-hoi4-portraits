# Getting started

## Choose a workflow

- Use **source** for an identity-preserving portrait from a reference image.
  It keeps the crop and source composition anchored while preparing and styling
  the final portrait; FLUX.2 restoration is enabled by default.
- Use **processing** when you need a crop, upscale, and optional restoration
  result without LoRA styling.
- The separate **text to image** workflow is for fictional portraits without a
  reference image.
- Use the [identity comparison pack](identity-comparison.md) to test alternate
  preservation methods against the same source and generation settings.

## Prepare a source image

In either source workflow, confirm that the automatic crop contains one
person's complete head and shoulders. **Face zoom** defaults to `0.90`; lower
it to retain more body. **Preserve hat/headwear** defaults to `true`; disable it
when the hat may be cropped and a closer face-led composition is preferred.
Turn off **Toggle face processing** when a multi-person image should retain the
whole composition. Face detection and the head-and-shoulders crop are then
skipped, while centered resizing and RealESRGAN still run. Use **Manual crop**
only when selecting one particular person.

Good input:

- one clearly visible person;
- top of the head and shoulders inside the frame;
- face at least roughly 200 pixels tall before upscaling;
- limited motion blur and obstruction;
- historically accurate visible clothing if preservation matters.

For a group photograph, use the manual bounding box only when the automatic
detector selects the wrong person.

## Required model files

| Folder under `ComfyUI/models/` | File |
| --- | --- |
| `diffusion_models/` | `flux-2-klein-base-9b-fp8.safetensors` |
| `text_encoders/` | `qwen_3_8b_fp8mixed.safetensors` |
| `vae/` | `flux2-vae.safetensors` |
| `loras/` | Portrait checkpoints from steps 2000, 2250, and 2500, plus `adonis_base.safetensors` for optional restoration |
| `upscale_models/` | `RealESRGAN_x2plus.pth` |
| `background_removal/` | `birefnet.safetensors` |
| `detection/` | `mediapipe_face_fp32.safetensors` |
| `detection/` | `face_detection_yunet_2023mar.onnx` |
| `loras/` | Identity comparison LoRAs listed in `models.json` |
| `pulid/` | `pulid_flux2_klein_v2.safetensors` |
| `insightface/models/antelopev2/` | Five AntelopeV2 face-analysis models |

Find the filenames, pinned sources, and sizes in
[`models.json`](../models.json).

Before downloading, follow the [Hugging Face access guide](hugging-face.md) to
accept the FLUX.2 model agreement and create a read-only token.

## First run

1. Open the workflow JSON, not the `.api.json` file, in the ComfyUI editor.
   Every stage and control is visible on the main canvas.
2. Check every model loader. A red loader means the named file has not been installed or imported.
   The retrained 2250-step LoRA is selected initially; choose another installed
   checkpoint in `LoraLoaderModelOnly` when comparing training steps.
3. Select the source image and confirm the automatic crop preview. Adjust
   **Face zoom** if needed. If it chose the wrong person, turn on the
   manual-crop toggle and adjust its box. Turn off **Preserve hat/headwear**
   when the crop should ignore an oversized hat. Turn off **Toggle face
   processing** when the full composition should be retained.
4. Keep each candidate's identity sentence intact. Append deliberate requested
   changes, such as adding a military hat, only to the candidate that should
   test that change.
5. Leave background replacement off for the first run.
6. Queue once. The source workflow creates three final candidates from the
   same input. Its restoration switch is enabled by default; turn it off when
   comparing against the direct ESRGAN result. Use the processing workflow when you
   need the processed image without LoRA styling.
7. Inspect the three 1024 × 1365 masters before choosing a centered 156 × 210 game-size
   file.

Outputs are saved under `ComfyUI/output/hoi4_portraits/`.

## Prompt rules

Each source candidate uses its reference image and its own editable identity
prompt. Keep the default identity sentence, then append only deliberate
changes. Editing one prompt affects only that candidate.

For text-to-image, begin with `hoi4_portrait,` and use a short, general person
description: supported ethnicity or nationality, broad hair or facial-hair
cues, and civilian, military, or clerical clothing. Do not describe the game,
visual style, background, lighting, framing, or rendering.

## Common problems

| Symptom | Likely fix |
| --- | --- |
| Loader is red | Install/import the exact filename from `models.json`, then refresh ComfyUI. |
| Out of memory | Disable FLUX restoration, close other GPU work, use offloading, or move to Comfy Cloud/a 24 GB GPU. |
| Wrong person | Use the manual crop to select that person, or turn face processing off to retain everyone. |
| Too much body | Increase **Face zoom**; `0.90` is the default and `1.00` is the closest safe framing. |
| Background appears too early | Background replacement runs after portrait generation; reopen the published workflow if the graph has been edited. |
| Style is weak | Keep `hoi4_portrait` in the prompt, confirm **LoRA strength** is `1.00`, and keep the crop clean. |
| Monochrome result | Enable **FLUX restoration** so natural color is restored before LoRA styling. |
| Identity or position changes | Confirm the crop, restore the fixed identity instruction, and compare the three seeds before changing LoRA strength. |
| Final looks too smooth | Use a sharper source crop, keep the 1024 × 1365 workflow canvas, and avoid speculative prompt details. Compare the three candidate branches; optional FLUX restoration can soften identity, so disable it first. |
