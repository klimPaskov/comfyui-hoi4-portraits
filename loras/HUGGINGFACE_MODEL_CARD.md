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

Portrait style adapter for the public [`comfyui-hoi4-portraits`](https://github.com/klimPaskov/comfyui-hoi4-portraits) ComfyUI package. Trigger: `hoi4_portrait`.

## Checkpoint

The installers include checkpoints from steps 1750, 2000, 2250, 2500, 2750, and 3000 for controlled comparisons. The workflow currently selects `hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors` at model strength `1`. It targets the **distilled** `black-forest-labs/FLUX.2-klein-9B` model and works with the package's full, FP8, and GGUF variants. FLUX.2 Klein Base variants are unsupported.

## Required stack

The workflow's separate model-loader nodes load:

1. `flux-2-klein-9b.safetensors`, `flux-2-klein-9b-fp8.safetensors`, or one `flux-2-klein-9b-*.gguf` diffusion model;
2. `Qwen3-8B-Q8_0.gguf` through `calcuis/gguf` `ClipLoaderGGUF`, type `flux2`;
3. `flux2-vae.safetensors`;
4. the HOI4 style LoRA;
5. `adonis_base.safetensors` and `adonis_post.safetensors` for the default pre-style restoration path; `adonis_refine.safetensors` remains installed as the official alternative first pass.

The installers download all six HOI4 style LoRAs plus Adonis Base, Refine, and Post for every full, FP8, or GGUF installation.

The style sampler defaults are CFG `1`, guidance `1`, Euler, simple, four steps, and denoise `1`. Prompt encoding, FLUX guidance, reference latent, standard ComfyUI `KSampler`, and VAE decode remain separate visible nodes. ComfyUI's native sampler preview shows construction progress.

For source portraits, RealESRGAN follows the centered face-aware crop. The restoration group executes the complete current upstream Adonis 1.7 MP Base → Post topology before style sampling. The detailed source-neutral prompt retains JPEG and compression cleanup, descreening, repeating-noise removal, deblurring, and natural skin, hair, material, object, and background detail recovery without assuming a capture device, ISO, gender, or colour treatment. The Base latent becomes Post reference conditioning and both generations share the seed, nine-step control, empty latent, and Shark options. One red switch enables or bypasses the whole restoration result and defaults to enabled. Final output is a centered 1024×1365 master and a non-stretched 156×210 game crop. Terminal output nodes automatically save both PNG sizes and the HOI4-ready DDS; the batch input rescans its folder on every queue. Source, processing-only, and batch saves preserve each input image stem; source candidates add `_1`, `_2`, and `_3`.

## Source prompt

```text
make this portrait hoi4_portrait style
```

Keep the exact trigger phrase. Append only short identity or clothing facts when the model needs help.

## Text-to-image example

```text
hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.
```
