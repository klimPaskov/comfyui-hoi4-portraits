---
license: mit
base_model: black-forest-labs/FLUX.2-klein-9B
library_name: diffusers
pipeline_tag: image-to-image
tags:
  - comfyui
  - flux2
  - flux2-klein
  - lora
  - hearts-of-iron-iv
  - portrait
---

# HOI4 portraits — FLUX.2 Klein 9B LoRA

This is the 2500-step HOI4 portrait style adapter for the [`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits) ComfyUI workflows. Use the trigger `hoi4_portrait`.

## Checkpoint

Use `hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors` at strength `1.0`. It is trained for the **distilled** `black-forest-labs/FLUX.2-klein-9B` model and works with the project's full, FP8, and GGUF distilled variants. FLUX.2 Klein Base variants are not supported.

## Required models

The workflows keep the model loaders visible and use:

1. `flux-2-klein-9b.safetensors`, `flux-2-klein-9b-fp8.safetensors`, or one `flux-2-klein-9b-*.gguf` diffusion model;
2. `Qwen3-8B-Q8_0.gguf` with the `calcuis/gguf` `ClipLoaderGGUF` set to `flux2`;
3. `flux2-vae.safetensors`;
4. `hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors`;
5. `adonis_base.safetensors` and `adonis_post.safetensors` for the default restoration path, with `adonis_refine.safetensors` available as the installed alternative first pass.

The project installers download the style LoRA, all three Adonis LoRAs, RealESRGAN, background removal, and face-detection assets together with the selected distilled FLUX.2 Klein 9B variant.

## Workflow defaults

Style sampling uses LoRA strength `1.0`, CFG `1`, FLUX guidance `1`, Euler, simple scheduling, four steps, and denoise `1.0`. The source workflow starts with fixed style seeds `757254001619850`, `629907966167866`, and `42`; the batch workflow starts with fixed style seed `757254001619850`; text-to-image uses a randomized style seed. Change **Control after generate** to **randomize**, **increment**, or **decrement** when you want different seed behavior. The source workflow creates three candidates, while batch defaults to one candidate per input and can create more.

Adonis Base and Post use the expanded restoration graph with a shared fixed seed of `42` and six steps per model. One red **Use Adonis restoration** switch enables or bypasses the complete Base → Post result. The restoration prompt keeps the original Adonis cleanup and reconstruction guidance for JPEG artifacts, halftone and repeating-pattern noise, deblurring, focus correction, identity preservation, skin and hair detail, and full-scene texture recovery. It removes assumptions about a particular capture device or subject and always colorizes monochrome and sepia sources. The background replacement control is optional and disabled by default.

## Prompts

Source workflow:

```text
make this portrait hoi4_portrait style
```

Append only short identity or clothing details when the source needs extra guidance.

Text-to-image workflow:

```text
hoi4_portrait style, a soviet soldier with the head of a brown bear wearing a soviet hat, ears still visible. No military uniform decorations.
```

## Outputs

Image-based workflows preserve each input image's filename stem. Source candidates use `_1`, `_2`, and `_3`; batch candidates receive non-overwriting numbered suffixes. Every styled or processed portrait has a centered 1024×1365 master PNG, a center-cropped 156×210 game PNG, and a HOI4-ready DDS. Prepared and restored 1024×1365 images are saved in their `processed/` and `restored/` folders. Batch runs use a selected `<batch_name>` folder and default to the next free `batch_1`, `batch_2`, and so on when no name is provided.

See the project's [output layout reference](https://github.com/klimPaskov/comfyui-hoi4-portraits/blob/codex/portrait-pipeline/docs/output-layout.md) for folder names, filename rules, image sizes, and DDS export details. See the [RunPod download guide](https://github.com/klimPaskov/comfyui-hoi4-portraits/blob/codex/portrait-pipeline/docs/download-outputs.md) for SCP, archive, and JupyterLab download options.

## Installation

Place the LoRA in `ComfyUI/models/loras/` and select it in `LoraLoaderModelOnly`, or import it through **Models → Import** in Comfy Cloud. The complete installation and workflow files are in the [comfyui-hoi4-portraits repository](https://github.com/klimPaskov/comfyui-hoi4-portraits).
