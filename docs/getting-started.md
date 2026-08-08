# Getting started

## Choose a workflow

- Use **source** for an identity-preserving portrait from a reference photo.
  It crops, upscales with RealESRGAN, optionally runs the Adonis restoration
  pass, and produces **three** HOI4-style candidates for comparison.
- Use **processing** when you need the crop/upscale/restoration result without
  LoRA styling.
- Use **text to image** for a fictional portrait without a reference photo.
- Use **batch** to drop a whole folder of photos into
  `ComfyUI/input/hoi4_portraits_batch/` and process them one by one with one
  sampler, saving PNGs and HOI4-ready DDS files.

## Prepare a source image

In the source, processing, and batch workflows, confirm that the automatic
crop contains one person's complete head and shoulders. **Face zoom** defaults
to `0.90`; lower it to retain more body. **Preserve hat/headwear** defaults to
`true`; disable it when the hat may be cropped and a closer face-led
composition is preferred. Turn off **Toggle face processing** when a
multi-person image should retain the whole composition (centered resizing and
RealESRGAN still run). Use **Manual crop** only when selecting one particular
person.

Good input:

- one clearly visible person;
- top of the head and shoulders inside the frame;
- face at least roughly 200 pixels tall before upscaling;
- limited motion blur and obstruction;
- historically accurate visible clothing if preservation matters.

For a group photograph, use the manual bounding box only when the automatic
detector selects the wrong person.

## Required model files

The installers place everything for you. For manual installs, use the folders
under `ComfyUI/models/`:

| Folder | File |
| --- | --- |
| `diffusion_models/` | `flux-2-klein-9b.safetensors` (full), `flux-2-klein-9b-fp8.safetensors` (FP8), or `flux-2-klein-9b-Q5_K_M.gguf` (GGUF) |
| `text_encoders/` | `qwen_3_8b_fp8mixed.safetensors` |
| `vae/` | `flux2-vae.safetensors` |
| `loras/` | `hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors` (tuned 2500-step LoRA) |
| `loras/` | `adonis_base.safetensors` and `adonis_post.safetensors` (optional restoration) |
| `upscale_models/` | `RealESRGAN_x2plus.pth` |
| `background_removal/` | `birefnet.safetensors` |
| `detection/` | `mediapipe_face_fp32.safetensors` and `face_detection_yunet_2023mar.onnx` |

Find filenames, pinned sources, and sizes in
[`models.json`](../models.json).

Before downloading the gated full/FP8 distilled model, follow the
[Hugging Face access guide](hugging-face.md) to accept the agreement and
create a read-only token. GGUF files are not gated.

## First run

1. Open the workflow JSON, not the `.api.json` file, in the ComfyUI editor.
   The **Setup guide** note on the left shows the exact model folders.
2. Check the model loaders. A red loader means the named file has not been
   installed.
3. Select the source image and confirm the source / crop + ESRGAN previews.
   Adjust **Face zoom** if needed, or use the manual crop for a specific
   person.
4. Keep the default prompt `make this portrait hoi4_portrait style`. Append a
   short description only when the model needs help (see the Prompting guide).
5. Leave background replacement off for the first run.
6. Queue once. The source workflow creates three candidates from the same
   input and shows them side by side in the comparison row.
7. Pick a final from the comparison row; the game-ready file is the
   `156x210/dds/` output.

Outputs are saved under `ComfyUI/output/1024x1365/`, `ComfyUI/output/156x210/`,
and `ComfyUI/output/156x210/dds/`.

## Prompt rules

Keep the source default prompt `make this portrait hoi4_portrait style`.
Append only deliberate changes to one candidate to test them:

```text
make this portrait hoi4_portrait style, a middle-aged Irish man with dark hair, wearing a military uniform
```

For text-to-image, begin with `hoi4_portrait,` and add a short person
description. Do not describe the game, visual style, background, lighting,
framing, or rendering.

## Common problems

| Symptom | Likely fix |
| --- | --- |
| Loader is red | Install/import the exact filename from `models.json`, then restart ComfyUI. |
| Out of memory | Install the GGUF or FP8 variant, disable FLUX restoration, or use a larger GPU. |
| Wrong person | Use the manual crop to select that person, or turn face processing off. |
| Too much body | Increase **Face zoom**; `0.90` is the default and `1.00` is the closest safe framing. |
| Style is weak | Keep `hoi4_portrait` in the prompt, confirm LoRA strength is `1.00`, and keep the crop clean. |
| Monochrome result | Enable **FLUX restoration** so natural colour is restored before LoRA styling. |
| Game crashes on the DDS | Confirm the file is 156×210 DXT5 with no mipmaps (the workflow's default output). |
