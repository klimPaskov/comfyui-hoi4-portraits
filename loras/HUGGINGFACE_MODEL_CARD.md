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

FLUX.2 Klein 9B portrait adapter for the public
[`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits)
ComfyUI workflows. Trigger: `hoi4_portrait`.

## Checkpoint

The tuned checkpoint is the 2500-step LoRA
`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors`. It targets the
`black-forest-labs/FLUX.2-klein-9B` model. The FP8 and GGUF variants work with
the same LoRA.

## Workflow settings

1. `UNETLoader`: `flux-2-klein-9b.safetensors` (full / FP8 / GGUF variant)
2. `CLIPLoader`: `qwen_3_8b_fp8mixed.safetensors`, type `flux2`
3. `VAELoader`: `flux2-vae.safetensors`
4. `LoraLoaderModelOnly`: strength `1.00`
5. Advanced sampler card: CFG `1.0`, guidance `1.0`, Euler, simple, 4 steps,
   denoise `1.00`

Every generation branch (including the optional Adonis restoration pass) uses
the same advanced sampler card, so the sampling process is live in the editor
and every control stays on one node.

For source portraits, the graph crops to 1024 × 1365 head-and-shoulders,
applies RealESRGAN, and optionally runs the Adonis Base → Post restoration
pass. It then encodes the processed image as both reference conditioning and
sampler starting latent. The restoration toggle is on by default.

## Source prompt

```text
make this portrait hoi4_portrait style
```

Keep that exact default. Append a short description only when the model needs
help (ethnicity or skin colour, civilian/military clothing, age, hair).

## Text-to-image example

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```
