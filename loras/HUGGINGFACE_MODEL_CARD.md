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

Portrait style adapter for the public
[`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits)
ComfyUI package. Trigger: `hoi4_portrait`.

## Checkpoint

The workflow uses only
`hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors`, the tuned
2500-step checkpoint, at model strength `1`. It targets the **distilled**
`black-forest-labs/FLUX.2-klein-9B` model and works with the package's full,
FP8, and GGUF variants. FLUX.2 Klein Base variants are unsupported.

## Required stack

The compact **HOI4 Distilled Model Stack** card loads:

1. `flux-2-klein-9b.safetensors`, `flux-2-klein-9b-fp8.safetensors`, or one
   `flux-2-klein-9b-*.gguf` diffusion model;
2. `Qwen3-8B-Q8_0.gguf` through `calcuis/gguf` `ClipLoaderGGUF`, type `flux2`;
3. `flux2-vae.safetensors`;
4. the step-2500 style LoRA;
5. optional `adonis_base.safetensors` and `adonis_refine.safetensors` for
   pre-style restoration.

The style sampler defaults are CFG `1`, guidance `1`, Euler, simple, four
steps, and denoise `1`. Prompt, seed, noise behavior, sampler, scheduler, and
partial-step controls are on one advanced node. ComfyUI's native latent
callback supplies live construction previews.

For source portraits, RealESRGAN follows the centered face-aware crop. The
optional restoration card executes the exact upstream Adonis 1.7 MP
Base → Refine topology before style sampling. Final output is a centered
1024×1365 master and a non-stretched 156×210 game crop.

## Source prompt

```text
make this portrait hoi4_portrait style
```

Keep the exact trigger phrase. Append only short identity or clothing facts
when the model needs help.

## Text-to-image example

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```
