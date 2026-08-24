# Getting started

## Choose a workflow

- Use **source** for an identity-preserving portrait from a reference photo. It crops, upscales with RealESRGAN, runs the Adonis Base + Post restoration pass, and produces **three** HOI4-style candidates for comparison.
- Use **processing** when you need the crop/upscale/restoration result without LoRA styling.
- Use **text to image** for a fictional portrait without a reference photo.
- Use **batch** to drop photos into `/workspace/hoi4-portrait-runpod/input/` on RunPod, the selected input folder on Windows, or `ComfyUI/input/hoi4_portraits_batch/` for a manual installation. Supported extensions are matched case-insensitively, and each queue run rescans the folder and automatically saves master PNGs, prepared and restored PNGs, game PNGs, and HOI4-ready DDS files. The candidate control defaults to one portrait per source.

## Prepare a source image

In the source, processing, and batch workflows, confirm that the automatic crop contains one person's complete head and shoulders. **Face zoom** defaults to `1.00`; lower it to retain more body. **Preserve hat/headwear** defaults to `true`; disable it when the hat may be cropped and a closer face-led composition is preferred. If both face detectors miss, the crop automatically uses the foreground mask and continues instead of stopping the queue. Turn off **Toggle face processing** when a multi-person image should retain the whole composition (centered resizing and RealESRGAN still run). Use **Manual crop** only when selecting one particular person.

Good input:

- one clearly visible person;
- top of the head and shoulders inside the frame;
- face at least roughly 200 pixels tall before upscaling;
- limited motion blur and obstruction;
- historically accurate visible clothing if preservation matters.

For a group photograph, use the manual bounding box only when the automatic detector selects the wrong person.

## Required model files

The installers place everything for you. For manual installs, use the folders under `ComfyUI/models/`:

| Folder | File |
| --- | --- |
| `diffusion_models/` | Distilled `flux-2-klein-9b.safetensors` (full), `flux-2-klein-9b-fp8.safetensors` (FP8), or `flux-2-klein-9b-Q5_K_M.gguf` (GGUF) |
| `text_encoders/` | `Qwen3-8B-Q8_0.gguf` |
| `vae/` | `flux2-vae.safetensors` |
| `loras/` | 2500-step HOI4 style LoRA plus Adonis restoration models |
| `loras/` | `adonis_base.safetensors`, `adonis_refine.safetensors`, and `adonis_post.safetensors` |
| `upscale_models/` | `RealESRGAN_x2plus.pth` |
| `background_removal/` | `birefnet.safetensors` |
| `detection/` | `mediapipe_face_fp32.safetensors` and `face_detection_yunet_2023mar.onnx` |

Find filenames and sizes in [`models.json`](../models.json).

Before downloading the gated full/FP8 model, follow the [Hugging Face access guide](hugging-face.md) to accept the agreement and create a read-only token. GGUF files are not gated.

## First run

1. Open the workflow JSON file in the ComfyUI editor. The narrow dark-brown **Setup and downloads** card on the left shows the exact folder tree and gives you clickable links for every required model.
2. Check the diffusion-model loader below the green preparation stage. The installer sets it to the selected full, FP8, or GGUF variant. Qwen Q8, VAE, and every LoRA have their own loaders beside it.
3. Select the source image; the upload card already shows it. Check the prepared portrait in the comparison row, then adjust **Face zoom** if needed or use the manual crop for a specific person.
4. Leave the red **Use Adonis restoration** switch on for the full Base → Post cleanup, or turn it off to use the prepared RealESRGAN portrait directly.
5. Keep the default prompt `make this portrait hoi4_portrait style`. Append a short description only when the model needs help (see the Prompting guide).
6. Leave background replacement off for the first run.
7. Queue once. The source workflow starts with three fixed HOI4 style seeds and shows the full-resolution candidates side by side in the comparison row; see [Seed selection](workflows.md#seed-selection) to change the control to randomize, increment, or decrement.
8. Pick a final from the comparison row; the game-ready file is the `156x210/dds/` output.

![Four game-ready 156×210 portrait examples](assets/examples/game-ready-portraits.png)

RunPod outputs are saved under `/workspace/hoi4-portrait-runpod/output/1024x1365/`, `/workspace/hoi4-portrait-runpod/output/156x210/`, and `/workspace/hoi4-portrait-runpod/output/156x210/dds/`. The Windows installer defaults to `Documents\hoi4-portraits\output` and lets you choose the ComfyUI folder or a custom path. Manual installations use the same subfolders under `ComfyUI/output/hoi4_portraits/`.

Saved PNG and DDS files keep the uploaded image's stem. A source named `general_macarthur.jpg` yields three candidates beginning with `general_macarthur_1`, `general_macarthur_2`, and `general_macarthur_3`. Batch and processing-only outputs keep the stem; multiple batch candidates receive non-overwriting numbered suffixes.

Prepared and restored 1024×1365 portraits use `processed/` and `restored/`. A batch queue creates the same `<batch_name>/` inside both `1024x1365/` and `156x210/`; the full-resolution folder contains `processed/` and `restored/`, while game DDS files use `156x210/<batch_name>/dds/`. Enter a name in **Batch folders and filenames** to use matching named folders. If no name is set, it defaults to the next free `batch_1`, `batch_2`, and so on. Enable **save without batch folder** only when outputs should remain directly in their standard resolution folders; that option is off by default.

## Seed selection

The source workflow starts with fixed seeds `757254001619850`, `629907966167866`, and `42`. The batch workflow starts with fixed seed `757254001619850`. Change **Control after generate** from **fixed** to **randomize**, **increment**, or **decrement** when you want different seed behavior. The text-to-image workflow remains randomized by default. See the comparison sheet and the broader seed list in the [workflow guide](workflows.md#seed-selection).

## Prompt rules

Keep the source default prompt `make this portrait hoi4_portrait style`. Append only deliberate changes to physical features or clothing when the model needs extra guidance.

For text-to-image, start from the example prompt `hoi4_portrait style, a soviet soldier with the head of a brown bear wearing a soviet hat, ears still visible. No military uniform decorations.` and edit the subject description as needed. Do not describe the game, visual style, background, lighting, framing, or rendering.

## Common problems

| Symptom | Likely fix |
| --- | --- |
| Loader is red | Install/import the exact filename from `models.json`, then restart ComfyUI. |
| Out of memory | Install the GGUF or FP8 variant, reduce batch work, or use a larger GPU. |
| Wrong person | Use the manual crop to select that person, or turn face processing off. |
| Too much body | Keep **Face zoom** at its `1.00` default; lower values retain more body. |
| Style is weak | Keep `hoi4_portrait` in the prompt, confirm LoRA strength is `1.00`, and keep the crop clean. |
| Unexpected colour change | Adonis always colorizes monochrome and sepia sources with restrained, period-appropriate colours and corrects unwanted casts in existing colour images. Turn off **Use Adonis restoration** only when the source treatment must remain untouched. |
| Game crashes on the DDS | Confirm the workflow saved it as a 156×210, 32-bit BGRA DDS (A8R8G8B8/B8G8R8A8-style). |
